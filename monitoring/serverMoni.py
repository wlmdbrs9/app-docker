import os
import subprocess
import time
from email.message import EmailMessage


# Conteneurs à surveiller
conteneurs = [
    "laba4-proxy",
    "laba4-webmail",
    "laba4-web",
    "laba4-mail",
    "laba4-db",
]


def est_en_marche(nom):
    commande = ["docker", "inspect", "-f", "{{.State.Running}}", nom]
    resultat = subprocess.run(commande, capture_output=True, text=True)
    return resultat.stdout.strip() == "true"


def envoyer_mail(nom, etat):
    message = EmailMessage()
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = os.environ["SMTP_TO"]
    message["Subject"] = f"{etat} : {nom}"

    if etat == "DOWN":
        message.set_content(f"Le conteneur {nom} ne fonctionne plus.")
    else:
        message.set_content(f"Le conteneur {nom} fonctionne de nouveau.")

    commande = ["docker", "exec", "-i", "laba4-mail", "/usr/sbin/sendmail", "-t"]
    resultat = subprocess.run(
        commande,
        input=message.as_string(),
        capture_output=True,
        text=True,
    )

    if resultat.returncode != 0:
        raise RuntimeError(resultat.stderr.strip())


def enregistrer_panne(nom):
    requete = f"""
        INSERT INTO service_downs (service_name, down_count, last_down_at)
        VALUES ('{nom}', 1, NOW())
        ON DUPLICATE KEY UPDATE
            down_count = down_count + 1,
            last_down_at = NOW()
    """

    commande = [
        "docker",
        "exec",
        "-e",
        f"MYSQL_PWD={os.environ['DB_PASSWORD']}",
        "laba4-db",
        "mariadb",
        f"-u{os.environ['DB_USER']}",
        "-D",
        os.environ["DB_NAME"],
        "-e",
        requete,
    ]

    resultat = subprocess.run(commande, capture_output=True, text=True)

    if resultat.returncode != 0:
        raise RuntimeError(resultat.stderr.strip())


# Mémorise les conteneurs déjà signalés en panne
conteneurs_en_panne = set()

while True:
    for nom in conteneurs:
        actif = est_en_marche(nom)
        print(f"[{'UP' if actif else 'DOWN'}] {nom}", flush=True)

        if not actif and nom not in conteneurs_en_panne:
            try:
                enregistrer_panne(nom)
                print("Panne enregistrée dans MariaDB", flush=True)
            except Exception as erreur:
                print(f"Erreur base de données : {erreur}", flush=True)

            try:
                envoyer_mail(nom, "DOWN")
                print("Mail d'alerte envoyé", flush=True)
            except Exception as erreur:
                print(f"Erreur mail : {erreur}", flush=True)

            conteneurs_en_panne.add(nom)

        elif actif and nom in conteneurs_en_panne:
            try:
                envoyer_mail(nom, "UP")
                print("Mail de rétablissement envoyé", flush=True)
                conteneurs_en_panne.remove(nom)
            except Exception as erreur:
                print(f"Erreur mail : {erreur}", flush=True)

    time.sleep(10)
