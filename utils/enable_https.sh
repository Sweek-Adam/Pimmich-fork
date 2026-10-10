#!/bin/bash
# Active le HTTPS pour l'interface Pimmich (à lancer une fois : sudo ./utils/enable_https.sh)
#
# - Crée un certificat auto-signé (valable 10 ans) pour le nom et les adresses IP du cadre.
# - Configure nginx : l'interface d'administration passe en HTTPS (redirection automatique depuis HTTP) ;
#   la page d'envoi des invités reste aussi accessible en HTTP, pour ne pas leur afficher d'avertissement.
# - Corrige au passage la transmission des en-têtes Host / X-Real-IP à Pimmich.
# Le navigateur affichera un avertissement à la première visite en HTTPS (certificat non reconnu) :
# il suffit de l'accepter une fois sur chaque appareil.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Ce script doit être lancé avec sudo : sudo $0" >&2
    exit 1
fi

CERT_DIR=/etc/ssl/pimmich
SITE=/etc/nginx/sites-available/pimmich
HOST=$(hostname)

# --- Certificat ---
mkdir -p "$CERT_DIR"
SAN="DNS:${HOST},DNS:${HOST}.local,DNS:localhost,IP:127.0.0.1"
for ip in $(hostname -I); do
    SAN="${SAN},IP:${ip}"
done
if [ ! -f "$CERT_DIR/pimmich.crt" ] || [ "${1:-}" = "--renew" ]; then
    echo "Création du certificat pour : $SAN"
    openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
        -keyout "$CERT_DIR/pimmich.key" -out "$CERT_DIR/pimmich.crt" \
        -subj "/CN=${HOST}/O=Pimmich" -addext "subjectAltName=${SAN}" 2>/dev/null
    chmod 600 "$CERT_DIR/pimmich.key"
else
    echo "Certificat existant conservé ($CERT_DIR/pimmich.crt). Pour le recréer (nouvelle adresse IP) : sudo $0 --renew"
fi

# --- Configuration nginx ---
[ -f "$SITE" ] && cp "$SITE" "$SITE.bak"
cat > "$SITE" <<'EOL'
# Configuration générée par utils/enable_https.sh
upstream pimmich_app { server 127.0.0.1:5000; }

server {
    listen 80;
    listen [::]:80;
    server_name _;
    client_max_body_size 200M;

    # Page d'envoi des invités (et ses ressources) : accessible aussi en HTTP
    location ~ ^/(upload|handle_upload|static/)  {
        proxy_pass http://pimmich_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }
    # Tout le reste (connexion, administration) : HTTPS obligatoire
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name _;
    client_max_body_size 200M;

    ssl_certificate     /etc/ssl/pimmich/pimmich.crt;
    ssl_certificate_key /etc/ssl/pimmich/pimmich.key;
    ssl_protocols TLSv1.2 TLSv1.3;

    location / {
        proxy_pass http://pimmich_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_buffering off;                 # flux de progression (imports, mises à jour)
        proxy_connect_timeout 600s;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }
}
EOL
ln -sf "$SITE" /etc/nginx/sites-enabled/pimmich

if nginx -t 2>/dev/null; then
    systemctl reload nginx
    echo "✅ HTTPS activé : https://$(hostname -I | awk '{print $1}')  (ou https://${HOST}.local)"
else
    echo "❌ Configuration nginx invalide, retour à la configuration précédente." >&2
    nginx -t || true
    [ -f "$SITE.bak" ] && cp "$SITE.bak" "$SITE" && systemctl reload nginx
    exit 1
fi
