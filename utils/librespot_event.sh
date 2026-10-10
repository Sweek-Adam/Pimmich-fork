#!/bin/sh
# Appelé par librespot (Spotify Connect, option --onevent) à chaque événement de lecture :
# met à jour le morceau affiché par le cadre. Les informations arrivent par variables d'environnement.
cd "$(dirname "$0")/.." || exit 0
exec ./venv/bin/python -m utils.now_playing spotify
