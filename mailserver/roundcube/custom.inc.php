<?php
$ssl = ['ssl' => ['verify_peer' => false, 'verify_peer_name' => false, 'allow_self_signed' => true]];
$config['imap_conn_options'] = $ssl;
$config['smtp_conn_options'] = $ssl;
$config['request_path'] = '/webmail/';

// ---------------------------------------------------------------------
// Plugin "password" : Paramètres > Mot de passe
// Roundcube envoie la demande à l'app web (API interne), qui met à jour
// la base "webmail" et le serveur mail (postfix-accounts.cf).
// Le plugin est activé par ROUNDCUBEMAIL_PLUGINS dans docker-compose.yml.
// ---------------------------------------------------------------------
$config['password_driver']             = 'httpapi';
$config['password_httpapi_url']        = 'http://web:9000/internal/mail-password?token=' . urlencode(getenv('MAIL_API_TOKEN') ?: '');
$config['password_httpapi_method']     = 'POST';
$config['password_httpapi_var_user']   = 'username';
$config['password_httpapi_var_curpass'] = 'curpass';
$config['password_httpapi_var_newpass'] = 'newpass';
$config['password_httpapi_expect']     = '/^OK$/';
$config['password_confirm_current']    = true;
$config['password_minimum_length']     = 8;
