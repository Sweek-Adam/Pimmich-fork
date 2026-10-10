#!/bin/bash
# Prépare la publication de la page invités sur internet (Tailscale Funnel). À lancer une fois :
#   ~/pimmich/utils/enable_remote_guests.sh        (demande le mot de passe sudo)
# Ensuite, l'activation se fait depuis l'interface : Partage > Invités > « Hors de la maison ».
#
# Ce script :
# - crée une entrée nginx locale (127.0.0.1:8088) qui ne laisse passer QUE la page invités et ses fichiers,
#   et marque chaque requête (X-Pimmich-Remote: 1) : Pimmich exige alors le lien secret ;
# - autorise le compte de Pimmich à piloter Tailscale (publication on/off depuis l'interface).
set -euo pipefail
SITE=/etc/nginx/sites-available/pimmich-guests
PIMMICH_USER="${SUDO_USER:-$USER}"

if ! command -v tailscale >/dev/null; then
    echo "Tailscale n'est pas installé : https://tailscale.com/download/linux" >&2
    exit 1
fi

sudo tee "$SITE" >/dev/null <<'EOL'
# Configuration générée par utils/enable_remote_guests.sh : page invités publiée par Tailscale Funnel.
# Seules les adresses ci-dessous sont transmises ; tout le reste répond 404.
server {
    listen 127.0.0.1:8088;
    server_name _;
    client_max_body_size 200M;

    location ~ ^/(upload|upload/message|upload/message/preview|handle_upload)$ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Pimmich-Remote 1;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }
    location ~ ^/static/(vendor/tailwind/[\w.-]+|styles\.css|pimmich_logo\.png|favicon\.ico|pwa/[\w.-]+)$ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Pimmich-Remote 1;
    }
    location / {
        return 404;
    }
}
EOL
sudo ln -sf "$SITE" /etc/nginx/sites-enabled/pimmich-guests
if sudo nginx -t 2>/dev/null; then
    sudo systemctl reload nginx
else
    echo "❌ Configuration nginx invalide : entrée invités retirée." >&2
    sudo rm -f /etc/nginx/sites-enabled/pimmich-guests
    sudo nginx -t || true
    exit 1
fi

sudo tailscale set --operator="$PIMMICH_USER"
echo "✅ Prêt. Activez « Hors de la maison » dans Partage > Invités."
echo "   (La première fois, Tailscale peut demander d'autoriser Funnel dans sa console : l'adresse s'affichera dans l'interface.)"
