"""
Notifications sur le téléphone, via ntfy (application libre pour iPhone et Android, https://ntfy.sh) :
le cadre publie sur un canal secret auquel le téléphone est abonné. Aucun compte nécessaire.

Événements : photo d'invité à valider, message d'invité, erreur de synchronisation, problème du cadre
(alimentation, chaleur, disque), import terminé. Une même alerte n'est pas répétée plus d'une fois
toutes les 10 minutes.
"""
import secrets
import threading
import time

import requests

from utils.message_renderer import N_

DEFAULT_SERVER = "https://ntfy.sh"
EVENTS = {
    "guest": {"label": N_("Photos et messages des invités"), "default": True, "tags": "camera", "priority": 3},
    "sync": {"label": N_("Erreurs de synchronisation"), "default": True, "tags": "warning", "priority": 4},
    "health": {"label": N_("Problèmes du cadre (alimentation, chaleur, disque)"), "default": True, "tags": "rotating_light", "priority": 4},
    "imports": {"label": N_("Imports terminés"), "default": False, "tags": "white_check_mark", "priority": 2},
}
REPEAT_AFTER = 10 * 60
_last_sent = {}
_lock = threading.Lock()


def base_url(config):
    """Adresse de l'interface pour les liens des notifications (sur le Wi-Fi de la maison)."""
    if config.get("public_url"):
        return config["public_url"].rstrip("/")
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("192.0.2.1", 80))  # aucune donnée envoyée : sert seulement à connaître l'adresse locale
            return f"http://{sock.getsockname()[0]}"
    except OSError:
        return None


def new_topic():
    return "pimmich-" + secrets.token_urlsafe(16).replace("_", "").replace("-", "")[:20].lower()


def topic_url(config):
    server = (config.get("notify_server") or DEFAULT_SERVER).rstrip("/")
    return f"{server}/{config.get('notify_topic')}" if config.get("notify_topic") else None


def wants(config, event):
    if not (config.get("notify_enabled") and config.get("notify_topic")):
        return False
    events = config.get("notify_events") or {}
    return bool(events.get(event, EVENTS.get(event, {}).get("default", False)))


def send(config, event, title, message, key=None, click=None, force=False, repeat_after=REPEAT_AFTER):
    """Envoie une notification (en arrière-plan). Retourne True si elle part."""
    if not force and not wants(config, event):
        return False
    key = key or f"{event}:{title}"
    with _lock:
        if not force and time.time() - _last_sent.get(key, 0) < repeat_after:
            return False
        _last_sent[key] = time.time()
    if not config.get("notify_topic"):
        return False
    info = EVENTS.get(event, {})
    # Publication JSON (accents et emojis sans souci, contrairement aux en-têtes HTTP)
    payload = {"topic": config["notify_topic"], "title": title, "message": message,
               "tags": [info.get("tags", "frame_with_picture")], "priority": info.get("priority", 3)}
    if click:
        payload["click"] = click
    server = (config.get("notify_server") or DEFAULT_SERVER).rstrip("/")

    def post():
        try:
            requests.post(server, json=payload, timeout=10)
        except requests.RequestException:
            pass
    threading.Thread(target=post, daemon=True).start()
    return True
