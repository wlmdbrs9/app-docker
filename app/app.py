"""
WICM Game - backend

  POST /api/register : crée le compte dans la base "game" ET dans la base "webmail"
                       (même mot de passe), active la boîte mail, envoie un mail de bienvenue
  POST /api/login    : connexion au jeu
  POST /api/logout   : déconnexion
  GET  /api/me       : utilisateur connecté
  POST /api/forgot   : génère un nouveau mot de passe DU JEU (base "game") et l'envoie par mail
                       (le mot de passe webmail ne change pas)
  POST /internal/mail-password : changement du mot de passe webmail, appelé par Roundcube
                       (plugin "password"), bloqué par le proxy depuis l'extérieur

Le webmail (Roundcube) vérifie les mots de passe auprès du serveur mail (Dovecot),
qui lit mailserver/config/postfix-accounts.cf : ce fichier est donc tenu synchronisé
avec la table webmail.mail_accounts.
"""
import fcntl
import hmac
import imaplib
import os
import re
import secrets
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage

import pymysql
from flask import Flask, jsonify, request, send_from_directory, session
from passlib.hash import sha512_crypt
from werkzeug.security import check_password_hash, generate_password_hash

# --- Configuration (docker-compose.yml) -------------------------------------
DB_CONN = dict(
    host=os.getenv("DB_HOST", "db"),
    port=int(os.getenv("DB_PORT", "3306")),
    user=os.getenv("DB_USER", "user"),
    password=os.getenv("DB_PASSWORD", "private"),
)
GAME_DB = os.getenv("GAME_DB", "game")
WEBMAIL_DB = os.getenv("WEBMAIL_DB", "webmail")
T_GAME = f"`{GAME_DB}`.users"
T_MAIL = f"`{WEBMAIL_DB}`.mail_accounts"

MAIL_DOMAIN = os.getenv("MAIL_DOMAIN", "site1.local")
SMTP_HOST = os.getenv("SMTP_HOST", "mail")
SMTP_PORT = int(os.getenv("SMTP_PORT", "25"))
MAIL_FROM = os.getenv("MAIL_FROM", f"noreply@{MAIL_DOMAIN}")
ACCOUNTS_FILE = os.getenv("ACCOUNTS_FILE", "/mailconfig/postfix-accounts.cf")
IMAP_HOST = os.getenv("IMAP_HOST", "mail")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
# Secret partagé avec Roundcube pour l'API interne de changement de mot de passe
MAIL_API_TOKEN = os.getenv("MAIL_API_TOKEN", "IliesWilliamMalchazCherif0351")

MIN_PASSWORD = 8
RESET_COOLDOWN = 60  # secondes entre deux "mot de passe oublié" pour un même compte
LOCAL_PART_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,31}$")
RESERVED = {"noreply", "postmaster", "admin", "root", "abuse", "webmaster", "supervision"}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-me")


# --- Base de données ---------------------------------------------------------
def db():
    """Connexion MariaDB sans autocommit : les écritures dans "game" et "webmail"
    se font dans une même transaction (tout ou rien)."""
    return pymysql.connect(**DB_CONN, charset="utf8mb4", autocommit=False,
                           cursorclass=pymysql.cursors.DictCursor)


def find_user(email):
    conn = db()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {T_GAME} WHERE email = %s", (email,))
            return cur.fetchone()
    finally:
        conn.close()


def normalize(email):
    email = (email or "").strip().lower()
    return email if "@" in email else f"{email}@{MAIL_DOMAIN}"


# --- Hachages ----------------------------------------------------------------
def game_hash(password):
    return generate_password_hash(password)


def mail_hash(password):
    # Format attendu par docker-mailserver / Dovecot
    return "{SHA512-CRYPT}" + sha512_crypt.using(rounds=5000).hash(password)


# --- Fichier des comptes du serveur mail --------------------------------------
def mailbox_exists(email):
    # Pas de try/except : si le fichier est introuvable ou illisible, il faut le savoir
    # (sinon on croirait l'adresse libre et on créerait un doublon).
    with open(ACCOUNTS_FILE, encoding="utf-8") as f:
        return any(l.split("|", 1)[0].strip().lower() == email for l in f)


def set_mailbox_password(email, hashed):
    """Ajoute ou met à jour la ligne `email|hash` dans postfix-accounts.cf.
    Le fichier est réécrit sur place (même inode) ; docker-mailserver détecte
    la modification et recharge les comptes en quelques secondes."""
    fd = os.open(ACCOUNTS_FILE, os.O_RDWR | os.O_CREAT, 0o640)
    with os.fdopen(fd, "r+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        lines = [l.rstrip("\n") for l in f if l.strip()]
        new_line = f"{email}|{hashed}"
        for i, l in enumerate(lines):
            if l.split("|", 1)[0].strip().lower() == email:
                lines[i] = new_line
                break
        else:
            lines.append(new_line)
        f.seek(0)
        f.write("\n".join(lines) + "\n")
        f.truncate()
        fcntl.flock(f, fcntl.LOCK_UN)


# --- Envoi de mails ----------------------------------------------------------
def send_mail(to, subject, body):
    msg = EmailMessage()
    msg["From"] = f"WICM Game <{MAIL_FROM}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
        smtp.send_message(msg)


def send_mail_async(to, subject, body, attempts=20, delay=3):
    """Envoi en arrière-plan avec réessais : une boîte toute neuve est refusée
    par le serveur mail tant qu'il n'a pas rechargé ses comptes."""
    def worker():
        err = None
        for _ in range(attempts):
            try:
                send_mail(to, subject, body)
                app.logger.info("Mail '%s' envoyé à %s", subject, to)
                return
            except (smtplib.SMTPException, OSError) as e:
                err = e
                time.sleep(delay)
        app.logger.error("Échec d'envoi du mail à %s : %s", to, err)
    threading.Thread(target=worker, daemon=True).start()


def generate_password(length=12):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def error(msg, code=400):
    return jsonify(ok=False, error=msg), code


# --- Routes ------------------------------------------------------------------
@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.post("/api/register")
def register():
    data = request.get_json(silent=True) or {}
    local = (data.get("identifiant") or "").strip().lower()
    password = data.get("password") or ""
    email = f"{local}@{MAIL_DOMAIN}"

    if not LOCAL_PART_RE.match(local):
        return error("Identifiant invalide : 2 à 32 caractères (minuscules, chiffres, . _ -).")
    if local in RESERVED:
        return error("Cet identifiant est réservé.")
    if len(password) < MIN_PASSWORD:
        return error(f"Le mot de passe doit faire au moins {MIN_PASSWORD} caractères.")
    try:
        if find_user(email) or mailbox_exists(email):
            return error("Cette adresse existe déjà.", 409)
    except Exception as e:
        app.logger.exception("Vérification de %s impossible : %s", email, e)
        return error("Service indisponible (base de données ou serveur mail). Réessaie plus tard.", 500)

    m_hash = mail_hash(password)
    conn = db()
    try:
        with conn.cursor() as cur:
            cur.execute(f"INSERT INTO {T_GAME} (email, password_hash) VALUES (%s, %s)",
                        (email, game_hash(password)))
            cur.execute(f"INSERT INTO {T_MAIL} (email, password_hash) VALUES (%s, %s)",
                        (email, m_hash))
        set_mailbox_password(email, m_hash)   # si ça échoue -> rollback des 2 bases
        conn.commit()
    except pymysql.err.IntegrityError:
        conn.rollback()
        return error("Cette adresse existe déjà.", 409)
    except Exception as e:
        conn.rollback()
        app.logger.exception("Inscription de %s impossible : %s", email, e)
        return error("Impossible de créer le compte. Réessaie plus tard.", 500)
    finally:
        conn.close()

    send_mail_async(
        email,
        "Bienvenue sur WICM Game !",
        f"Salut {local} !\n\n"
        f"Ton compte est prêt.\n\n"
        f"  Adresse e-mail : {email}\n"
        f"  Mot de passe   : celui que tu as choisi à l'inscription\n"
        f"                   (le même pour WICM Game et pour le webmail)\n\n"
        f"Bonne partie !\n"
        f"William, Ilyes, Chérif et Malchaz\n",
    )
    session["email"] = email
    return jsonify(ok=True, email=email)


@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    email = normalize(data.get("email"))
    user = find_user(email)
    if not user or not check_password_hash(user["password_hash"], data.get("password") or ""):
        return error("E-mail ou mot de passe incorrect.", 401)
    session["email"] = email
    return jsonify(ok=True, email=email)


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/me")
def me():
    return jsonify(ok=True, email=session.get("email"))


@app.post("/api/forgot")
def forgot():
    data = request.get_json(silent=True) or {}
    email = normalize(data.get("email"))

    conn = db()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT TIMESTAMPDIFF(SECOND, last_reset_at, NOW()) AS age "
                        f"FROM {T_GAME} WHERE email = %s FOR UPDATE", (email,))
            row = cur.fetchone()
            if row is None:
                conn.rollback()
                # Même réponse que le compte existe ou non (on ne révèle pas les adresses)
                return jsonify(ok=True)
            if row["age"] is not None and row["age"] < RESET_COOLDOWN:
                conn.rollback()
                return error("Attends une minute avant de redemander un mot de passe.", 429)

            # Seul le mot de passe du JEU change : le webmail n'est pas touché,
            # la session Roundcube reste ouverte et permet de lire ce mail.
            new_pwd = generate_password()
            cur.execute(f"UPDATE {T_GAME} SET password_hash = %s, last_reset_at = NOW() "
                        f"WHERE email = %s", (game_hash(new_pwd), email))
        conn.commit()
    except Exception as e:
        conn.rollback()
        app.logger.exception("Réinitialisation de %s impossible : %s", email, e)
        return error("Impossible de réinitialiser le mot de passe. Réessaie plus tard.", 500)
    finally:
        conn.close()

    send_mail_async(
        email,
        "Ton nouveau mot de passe WICM Game",
        f"Salut,\n\n"
        f"Tu as demandé un nouveau mot de passe pour WICM Game.\n\n"
        f"  Nouveau mot de passe du jeu : {new_pwd}\n\n"
        f"Il remplace l'ancien dès maintenant.\n"
        f"Le mot de passe de ton webmail ne change pas.\n",
    )
    return jsonify(ok=True)


# --- Changement du mot de passe webmail (appelé par Roundcube) ---------------
def _current_mail_hash(email):
    with open(ACCOUNTS_FILE, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("|")
            if len(parts) >= 2 and parts[0].strip().lower() == email:
                return parts[1]
    return None


def _check_mail_password(email, password):
    stored = _current_mail_hash(email)
    if not stored or not stored.startswith("{SHA512-CRYPT}"):
        return False
    try:
        return sha512_crypt.verify(password, stored[len("{SHA512-CRYPT}"):])
    except ValueError:
        return False


def _wait_until_active(email, password, timeout=20):
    """docker-mailserver recharge ses comptes ~2 s après la modification du fichier.
    On attend que le nouveau mot de passe fonctionne en IMAP avant de répondre à
    Roundcube, sinon sa session (qui utilise déjà le nouveau mot de passe) serait coupée."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE   # certificat auto-signé du labo
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, ssl_context=ctx, timeout=5) as imap:
                imap.login(email, password)
                return True
        except (imaplib.IMAP4.error, OSError):
            time.sleep(1.5)
    return False


@app.post("/internal/mail-password")
def mail_password():
    """Appelé par le plugin « password » de Roundcube (driver httpapi).
    Répond "OK" (HTTP 200) si le mot de passe a été changé."""
    if not MAIL_API_TOKEN or not hmac.compare_digest(request.args.get("token", ""), MAIL_API_TOKEN):
        return "Accès refusé", 403

    email = normalize(request.form.get("username"))
    curpass = request.form.get("curpass") or ""
    newpass = request.form.get("newpass") or ""

    if len(newpass) < MIN_PASSWORD:
        return f"Le mot de passe doit faire au moins {MIN_PASSWORD} caractères.", 200
    try:
        if not _check_mail_password(email, curpass):
            return "Mot de passe actuel incorrect.", 200

        m_hash = mail_hash(newpass)
        conn = db()
        try:
            with conn.cursor() as cur:
                cur.execute(f"INSERT INTO {T_MAIL} (email, password_hash) VALUES (%s, %s) "
                            f"ON DUPLICATE KEY UPDATE password_hash = VALUES(password_hash)",
                            (email, m_hash))
            set_mailbox_password(email, m_hash)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    except Exception as e:
        app.logger.exception("Changement du mot de passe webmail de %s impossible : %s", email, e)
        return "Erreur interne.", 500

    if not _wait_until_active(email, newpass):
        app.logger.warning("Nouveau mot de passe webmail de %s pas encore actif après 20 s", email)
    app.logger.info("Mot de passe webmail de %s changé", email)
    return "OK", 200
