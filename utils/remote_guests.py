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
ALLOWED_ENDPOINTS = {"upload_page", "handle_upload", "guest_message_preview", "guest_message_publish", "guest_drawing_publish", "guest_voice_publish"}
ALLOWED_STATIC = ("vendor/tailwind/", "styles.css", "guest.css", "guestbook/", "pimmich_logo.png", "favicon.ico", "pwa/")


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


def set_funnel(enabled, timeout=40):
    """Publie (ou retire) l'entrée invités sur internet. Retourne (ok, message ou adresse d'activation).

    Si Funnel n'est pas encore autorisé sur le compte Tailscale, la commande affiche une adresse d'activation puis
    attend : on renvoie cette adresse sans attendre. Le retrait ne touche qu'au port 443 (pas à l'administration).
    """
    args = ["tailscale", "funnel", "--bg", str(REMOTE_PORT)] if enabled else ["tailscale", "funnel", "--https=443", "off"]
    return _tailscale(args, timeout)


# --- Administration en HTTPS dans le tailnet (certificat reconnu, fourni et renouvelé par Tailscale) ---

ADMIN_PORT = 8443  # le port 443 de l'adresse *.ts.net est réservé à la page invités (Funnel)


def admin_https_status():
    """L'administration est-elle publiée dans le tailnet (https://machine.tailnet.ts.net:8443) ?"""
    if not shutil.which("tailscale"):
        return False
    result = _run("tailscale", "serve", "status", "--json")
    try:
        data = json.loads(result.stdout) if result and result.returncode == 0 and result.stdout.strip() else {}
    except ValueError:
        return False
    return str(ADMIN_PORT) in (data.get("TCP") or {})


def set_admin_https(enabled, timeout=60):
    """Publie l'administration dans le tailnet seulement (jamais sur internet) : Tailscale termine le HTTPS avec un
    vrai certificat et transmet à nginx (certificat local auto-signé, d'où « https+insecure »)."""
    args = (["tailscale", "serve", "--bg", f"--https={ADMIN_PORT}", "https+insecure://127.0.0.1:443"] if enabled
            else ["tailscale", "serve", f"--https={ADMIN_PORT}", "off"])
    return _tailscale(args, timeout)


def _tailscale(args, timeout):
    """Lance une commande Tailscale ; si elle attend une autorisation dans la console Tailscale, renvoie tout de suite
    (False, sortie contenant l'adresse d'activation)."""
    import os
    import re
    import select
    import time
    if not shutil.which("tailscale"):
        return False, "tailscale introuvable"
    try:
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except OSError as e:
        return False, str(e)
    output, deadline = b"", time.time() + timeout
    while time.time() < deadline:
        ready, _w, _x = select.select([process.stdout], [], [], 0.5)
        if ready:
            chunk = os.read(process.stdout.fileno(), 4096)  # lecture directe : pas de tampon caché
            if not chunk:
                break
            output += chunk
            if re.search(rb"https://login\.tailscale\.com/\S+\s", output):  # activation à faire dans la console Tailscale
                process.kill()
                return False, output.decode(errors="replace").strip()
        elif process.poll() is not None:
            break
    if process.poll() is None:
        try:
            process.wait(timeout=max(0.1, deadline - time.time()))
        except subprocess.TimeoutExpired:
            process.kill()
            return False, output.decode(errors="replace").strip() or "Tailscale ne répond pas."
    return process.returncode == 0, output.decode(errors="replace").strip()
