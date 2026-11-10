-- =====================================================================
--  Bases de données du projet labA4
--    game        : comptes du jeu (WICM Game)
--    webmail     : Roundcube + comptes de messagerie
--    supervision : supervision (déjà en place, non modifiée ici)
--
--  Exécuté automatiquement au PREMIER démarrage de MariaDB (volume vide).
--  Sur une base existante :
--    docker exec -i laba4-db mariadb -uroot -pprivate < db/init/01-init.sql
-- =====================================================================

CREATE DATABASE IF NOT EXISTS game        CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS webmail     CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS supervision CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

GRANT ALL PRIVILEGES ON game.*        TO 'user'@'%';
GRANT ALL PRIVILEGES ON webmail.*     TO 'user'@'%';
GRANT ALL PRIVILEGES ON supervision.* TO 'user'@'%';
FLUSH PRIVILEGES;

-- Comptes du jeu
CREATE TABLE IF NOT EXISTS game.users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_reset_at TIMESTAMP NULL DEFAULT NULL
) ENGINE=InnoDB;

-- Comptes de messagerie (les tables de Roundcube sont créées par Roundcube lui-même
-- dans cette même base ; "mail_accounts" ne rentre pas en conflit avec elles)
CREATE TABLE IF NOT EXISTS webmail.mail_accounts (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,   -- format docker-mailserver : {SHA512-CRYPT}$6$...
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;
