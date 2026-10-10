"""Limiteur de fréquence simple, en mémoire (remis à zéro au redémarrage de l'application)."""
import time
import threading

_lock = threading.Lock()
_events = {}  # clé -> horodatages récents


def allow(key, limit, window, now=None):
    """Enregistre une action et retourne False si `limit` actions ont déjà eu lieu dans les `window` dernières secondes."""
    now = now or time.time()
    with _lock:
        recent = [t for t in _events.get(key, []) if now - t < window]
        if len(recent) >= limit:
            _events[key] = recent
            return False
        recent.append(now)
        _events[key] = recent
        return True


def reset():
    with _lock:
        _events.clear()
