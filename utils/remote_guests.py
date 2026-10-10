"""
Invités hors de la maison : la page d'envoi de photos et de messages, publiée sur internet par Tailscale Funnel.

Sécurité, en profondeur :
- nginx (port local 8088, seule entrée publiée) ne laisse passer que la page invités et ses fichiers, et marque
  chaque requête (X-Pimmich-Remote: 1) ; l'administration et les photos ne sont jamais joignables ;
- l'application vérifie le lien secret (jeton) sur toute requête marquée, et refuse tout le reste ;
- désactivé par défaut ; le jeton peut être changé à tout moment (l'ancien lien cesse de fonctionner).
"""
import json
import secrets
import shutil
import subprocess

REMOTE_PORT = 8088
REMOTE_HEADER = "X-Pimmich-Remote"
# Points d'entrée autorisés depuis internet (noms des routes Flask) et fichiers statiques de la page invités
ALLOWED_ENDPOINTS = {"upload_page", "handle_upload", "guest_message_preview", "guest_message_publish"}
ALLOWED_STATIC = ("vendor/tailwind/", "styles.css", "pimmich_logo.png", "favicon.ico", "pwa/")


def new_token():
    return secrets.token_urlsafe(18)


def static_allowed(filename):
    return any(filename == p or (p.endswith("/") and filename.startswith(p)) for p in ALLOWED_STATIC)


def _run(*args, timeout=20):
    try:
        return subprocess.run(list(args), capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None


def tailscale_status():
    """État de Tailscale : installé, connecté, nom public (machine.tailnet.ts.net) et Funnel actif."""
    if not shutil.which("tailscale"):
        return {"installed": False, "connected": False, "dns_name": None, "funnel": False}
    result = _run("tailscale", "status", "--json")
    try:
        data = json.loads(result.stdout) if result and result.returncode == 0 else {}
    except ValueError:
        data = {}
    me = data.get("Self") or {}
    dns = (me.get("DNSName") or "").rstrip(".") or None
    funnel = _run("tailscale", "funnel", "status", "--json")
    try:
        funnel_on = bool(json.loads(funnel.stdout).get("AllowFunnel")) if funnel and funnel.returncode == 0 and funnel.stdout.strip() else False
    except ValueError:
        funnel_on = False
    return {"installed": True, "connected": data.get("BackendState") == "Running", "dns_name": dns, "funnel": funnel_on}


def set_funnel(enabled):
    """Publie (ou retire) l'entrée invités sur internet. Retourne (ok, message ou adresse d'activation)."""
    args = ["tailscale", "funnel", "--bg", str(REMOTE_PORT)] if enabled else ["tailscale", "funnel", "reset"]
    result = _run(*args, timeout=40)
    if result is None:
        return False, "tailscale introuvable"
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        return False, output  # ex. Funnel à autoriser dans la console Tailscale (l'adresse est dans le message)
    return True, output
