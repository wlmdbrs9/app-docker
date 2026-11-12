Nous avons réaliser ce projet à 4 étudiants: Ilies, William, Malchaz et Cherif.
Pour le fonctionnement interne, nous avons utiliser une VM sous Debian13 sur le poste d'un étudiant afin de travailler sur une machine commune par SSH à l'aide d'une règle NAT sur VMWare.
Chaque étudiant a son propre utilisateur pour la connexion. Nous avons établit le projet sur un dossier commun, le "var/opt/laba4-docker"

Chaque étudiant a sa partie du travail:
- Ilies: Reverse Proxy (Nginx)
- William: Mail Server & Webmail (docker-mailserver & roundcube)
- Malchaz: base de données (MariaDB)
- Cherif: monitoring (Python)

Quant au projet de l'application, nous l'avons fait en commun a l'aide de l'IA en demandant un jeu d'echecs. Ce jeu d'echec nécessite une connexion ou une inscription créant un compte dans la base de données dans la BDD "game" ce qui réplique les informations saisie dans la BDD "webmail" en créant un utilisateur pour le webmail avec les mêmes identifiants.
Lors de l'inscription, les mails sont forcés avec le domaine @site1.local pour rester dans un réseau interne, étant restés sur une base de certificat auto-signé, les organismes officiels tel que Gmail, Outlook, etc n'auraient pas accepter nos mails.
Une fonction sur l'application finale "Mot de passe oubliée" permet de reinitialiser le mot de passe de l'utilisateur uniquemenet sur l'application web. La requete utilisateur demande au serveur de générer un mot de passe sécuriser, l'applique à l'utilisateur dans la BDD "game" et l'envoi par mail à l'utilisateur.

Le reverse proxy permet via l'IP Publique de rediriger les utilisateurs vers l'application tournant sur le port 9000 puis avec l'args "/webmail" de rediriger vers l'interface RoundCube. Le tout en HTTP.
La partie monitoring, via le DNS Interne du Docker compose, d'effectuer des ping tous les 3 secondes sur les différents conteneurs.
Dans le cas où un conteneur est down, nous recevons un mail sur l'adresse mail "supervision@site1.local" avec le nom du conteneur avec le statut DOWN. Le statut est enregistrer dans la base de données dans la BDD "supervision" permettant de sauvegarder l'heure du dernier statut down, le nombre de fois où il a été detecter DOWN permettant de vérifier si c'est récurent et son statut actuel.
Tant qu'il n'est pas redefini UP, nous ne recevons plus de mail à son propos. Lorsqu'il remonte, nous recevons un mail avec ces informations:
- Le temps qu'il a été down, le nombre de fois et l'heure à laquelle il est tombé pour la dernière fois.


Pour les axes d'améliorations:
- Passer la partie WEB en HTTPS (ouvrir le port 443 sur la conf du ReverseProxy)
- Remettre au propre la partie BDD
- Améliorer la partie monitoring: avoir le code erreur du conteneur et un timer
- Stocker les credentials dans des .env: certains secret (mailserver) sont en clair dans la conf
- Passer un coup de Trivie sur l'infrastructure
- Trouver un moyen pour améliorer la partie "Mot de passe oubliée"
