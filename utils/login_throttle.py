"""
Protection contre les essais de mot de passe en série.

Après MAX_FAILURES échecs pour un même compte (et une même adresse quand elle est connue), la connexion
à ce compte est bloquée temporairement ; la durée double à chaque nouveau blocage (jusqu'à MAX_LOCK).
État en mémoire : il est remis à zéro au redémarrage de l'application.
"""
import time
import ipaddress
import threading

MAX_FAILURES = 5          # échecs autorisés par fenêtre
WINDOW = 15 * 60          # fenêtre de comptage des échecs (secondes)
BASE_LOCK = 5 * 60        # premier blocage (secondes)
MAX_LOCK = 60 * 60        # blocage maximal (secondes)
IP_MAX_FAILURES = 20      # échecs tous comptes confondus pour une même adresse

_lock = threading.Lock()
_state = {}  # clé -> {"failures": [horodatages], "locked_until": float, "lockouts": int}


def client_ip(request):
    """Adresse du client : X-Real-IP transmis par nginx s'il est valide, sinon l'adresse de connexion."""
    for candidate in (request.headers.get("X-Real-IP"), request.remote_addr):
        try:
            return str(ipaddress.ip_address((candidate or "").strip()))
        except ValueError:
            continue
    return None


def _keys(username, ip):
    keys = [("user", (username or "").strip().lower(), ip)]
    # Derrière un proxy mal configuré, toutes les requêtes semblent venir de 127.0.0.1 :
    # un blocage par adresse bloquerait alors tout le monde, on ne l'applique qu'aux vraies adresses.
    if ip and not ipaddress.ip_address(ip).is_loopback:
        keys.append(("ip", ip))
    return keys


def _limit(key):
    return IP_MAX_FAILURES if key[0] == "ip" else MAX_FAILURES


def seconds_locked(username, ip, now=None):
    """Secondes restantes de blocage pour cette tentative (0 si autorisée)."""
    now = now or time.time()
    with _lock:
        return max([int(_state.get(k, {}).get("locked_until", 0) - now) for k in _keys(username, ip)] + [0])


def register_failure(username, ip, now=None):
    now = now or time.time()
    with _lock:
        for key in _keys(username, ip):
            entry = _state.setdefault(key, {"failures": [], "locked_until": 0, "lockouts": 0})
            entry["failures"] = [t for t in entry["failures"] if now - t < WINDOW] + [now]
            if len(entry["failures"]) >= _limit(key):
                entry["lockouts"] += 1
                entry["locked_until"] = now + min(BASE_LOCK * 2 ** (entry["lockouts"] - 1), MAX_LOCK)
                entry["failures"] = []


def register_success(username, ip):
    with _lock:
        _state.pop(("user", (username or "").strip().lower(), ip), None)


def reset():
    with _lock:
        _state.clear()
