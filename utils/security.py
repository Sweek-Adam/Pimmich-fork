"""
Sécurité de l'application web : clé de session, jeton des appels internes et protection CSRF.
"""
import os
import json
import hmac
import socket
import secrets
import logging
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger("pimmich.security")

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
SECRET_KEY_FILE = CONFIG_DIR / ".flask_secret_key"
INTERNAL_TOKEN_FILE = CONFIG_DIR / ".internal_api_token"
INTERNAL_TOKEN_HEADER = "X-Pimmich-Internal-Token"


def _write_private(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w") as f:
        f.write(content)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _read_or_create_secret(path):
    try:
        value = path.read_text().strip()
        if value:
            return value
    except OSError:
        pass
    value = secrets.token_hex(32)
    _write_private(path, value)
    return value


def load_secret_key(credentials_path):
    """
    Clé de signature des sessions : celle de credentials.json (créée par setup.sh), sinon une clé
    aléatoire propre à ce cadre, générée une fois et conservée. Jamais de valeur par défaut connue.
    """
    try:
        with open(credentials_path, "r") as f:
            key = json.load(f).get("flask_secret_key")
        if key:
            return key
    except (OSError, json.JSONDecodeError):
        pass
    logger.warning("Aucune clé de session dans %s : utilisation de la clé locale %s.", credentials_path, SECRET_KEY_FILE)
    return _read_or_create_secret(SECRET_KEY_FILE)


# --- Jeton des appels internes (commande vocale, bouton physique) ---

def ensure_internal_token():
    """Crée le jeton partagé avec les processus locaux s'il n'existe pas (fichier lisible par l'utilisateur seul)."""
    return _read_or_create_secret(INTERNAL_TOKEN_FILE)


def internal_headers():
    """En-têtes à ajouter aux appels HTTP internes vers l'API Pimmich."""
    try:
        return {INTERNAL_TOKEN_HEADER: INTERNAL_TOKEN_FILE.read_text().strip()}
    except OSError:
        return {}


def is_internal_request(request):
    token = request.headers.get(INTERNAL_TOKEN_HEADER)
    if not token:
        return False
    try:
        expected = INTERNAL_TOKEN_FILE.read_text().strip()
    except OSError:
        return False
    return bool(expected) and hmac.compare_digest(token, expected)


# --- Protection CSRF ---

# Requêtes GET qui déclenchent une action (flux SSE d'import / de mise à jour)
STATE_CHANGING_GET_PREFIXES = ("/api/update_app", "/import-", "/prepare-photos")


@lru_cache(maxsize=1)
def _local_host_names():
    """Noms et adresses IP sous lesquels le cadre est joignable (pour valider l'en-tête Origin)."""
    names = {"localhost", "127.0.0.1", "::1"}
    hostname = socket.gethostname().lower()
    names.update({hostname, f"{hostname}.local"})
    try:
        import psutil
        for addrs in psutil.net_if_addrs().values():
            for addr in addrs:
                if addr.family in (socket.AF_INET, socket.AF_INET6):
                    names.add(addr.address.split("%")[0].lower())
    except Exception:
        pass
    return frozenset(names)


def is_cross_site_request(request):
    """
    Vrai si la requête provient d'un autre site que l'interface Pimmich.
    S'appuie sur l'en-tête Sec-Fetch-Site envoyé par les navigateurs modernes,
    et à défaut sur l'en-tête Origin.
    """
    site = request.headers.get("Sec-Fetch-Site")
    if site is not None:
        # 'same-origin' : l'interface elle-même ; 'none' : URL tapée ou favori
        return site not in ("same-origin", "none")
    origin = request.headers.get("Origin")
    if origin is None:
        return False  # Client non navigateur (curl, scripts) : pas de cookie de session tiers à détourner
    if origin == "null":
        return True
    parsed = urlparse(origin)
    hosts = {h for h in (request.host, request.headers.get("X-Forwarded-Host")) if h}
    if parsed.netloc in hosts:
        return False
    # Le Host transmis par le proxy peut être absent ou faux : on accepte aussi les adresses du cadre lui-même
    return (parsed.hostname or "").lower() not in _local_host_names()


def csrf_violation(request):
    """Retourne True si la requête doit être refusée par la protection CSRF."""
    if is_internal_request(request):
        return False
    if request.method in ("GET", "HEAD", "OPTIONS"):
        if not request.path.startswith(STATE_CHANGING_GET_PREFIXES):
            return False
    return is_cross_site_request(request)
