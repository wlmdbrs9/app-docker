## L'équipe

Nous avons réalisé ce projet à 4 étudiants : **Ilies**, **William**, **Malchaz** et **Cherif**.

## Fonctionnement interne

Pour le fonctionnement interne, nous avons utilisé une VM sous **Debian 13** sur le poste d'un étudiant afin de travailler sur une machine commune par **SSH**, à l'aide d'une règle NAT sur **VMware**.

Chaque étudiant a son propre utilisateur pour la connexion. Nous avons établi le projet sur un dossier commun : `/var/opt/laba4-docker`.

## Répartition du travail

Chaque étudiant a sa partie du travail :

| Étudiant | Partie |
|----------|--------|
| Ilies    | Reverse Proxy (Nginx) |
| William  | Mail Server & Webmail (docker-mailserver & Roundcube) |
| Malchaz  | Base de données (MariaDB) |
| Cherif   | Monitoring (Python) |

## L'application

Quant au projet de l'application, nous l'avons fait en commun à l'aide de l'IA en demandant un **jeu d'échecs**.

Ce jeu d'échecs nécessite une connexion ou une inscription créant un compte dans la base de données `game`, ce qui réplique les informations saisies dans la base `webmail` en créant un utilisateur pour le webmail avec les mêmes identifiants.

Lors de l'inscription, les mails sont forcés avec le domaine `@site1.local` pour rester dans un réseau interne. Étant restés sur une base de certificat auto-signé, les organismes officiels tels que Gmail, Outlook, etc. n'auraient pas accepté nos mails.

Une fonction **« Mot de passe oublié »** sur l'application finale permet de réinitialiser le mot de passe de l'utilisateur, uniquement sur l'application web. La requête utilisateur demande au serveur de générer un mot de passe sécurisé, l'applique à l'utilisateur dans la base `game` et l'envoie par mail à l'utilisateur.

## Reverse Proxy

Le reverse proxy permet, via l'IP publique, de rediriger les utilisateurs vers l'application tournant sur le port `9000`, puis avec l'argument `/webmail` de rediriger vers l'interface Roundcube. Le tout en **HTTP**.

## Monitoring

La partie monitoring permet, via le DNS interne du Docker Compose, d'effectuer des pings toutes les **3 secondes** sur les différents conteneurs.

Dans le cas où un conteneur est down, nous recevons un mail sur l'adresse `supervision@site1.local` avec le nom du conteneur et le statut **DOWN**.

Le statut est enregistré dans la base `supervision`, ce qui permet de sauvegarder :
- l'heure du dernier statut DOWN ;
- le nombre de fois où il a été détecté DOWN (pour vérifier si c'est récurrent) ;
- son statut actuel.

Tant qu'il n'est pas redéfini **UP**, nous ne recevons plus de mail à son propos. Lorsqu'il remonte, nous recevons un mail avec ces informations :
- le temps pendant lequel il a été down ;
- le nombre de fois ;
- l'heure à laquelle il est tombé pour la dernière fois.

## Axes d'amélioration

- Passer la partie web en **HTTPS** (ouvrir le port `443` dans la conf du reverse proxy)
- Remettre au propre la partie BDD
- Améliorer la partie monitoring : avoir le code erreur du conteneur et un timer
- Stocker les credentials dans des `.env` : certains secrets (mailserver) sont en clair dans la conf
- Passer un coup de **Trivy** sur l'infrastructure
- Trouver un moyen d'améliorer la partie « Mot de passe oublié »
