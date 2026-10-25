"""
Point d'accès de secours : quand le cadre ne trouve aucun réseau connu (ni câble), il crée son propre Wi-Fi
« Cadre-Pimmich ». Le nom, le mot de passe et un QR code s'affichent sur l'écran : on s'y connecte avec un téléphone,
puis on ouvre http://10.42.0.1 pour choisir un réseau dans Système > Réseau.
Régulièrement (si personne n'y est connecté), le point d'accès s'arrête le temps de réessayer les réseaux connus.
Réglage « wifi_hotspot_fallback » (désactivé par défaut : le cadre émet alors son propre Wi-Fi).
"""
import json
import secrets
import time
from pathlib import Path

from utils import wifi_networks
from utils.platform_info import tmp_path

STATE_FILE = tmp_path("pimmich_hotspot.json")  # lu par le diaporama pour afficher les instructions
SSID = "Cadre-Pimmich"
ADDRESS = "10.42.0.1"  # adresse du cadre sur son point d'accès (partage de connexion de NetworkManager)
OFFLINE_DELAY = 120  # secondes sans réseau avant d'ouvrir le point d'accès
RETRY_EVERY = 300  # secondes entre deux essais des réseaux connus (si personne n'est connecté au point d'accès)
RETRY_WAIT = 45  # secondes laissées à NetworkManager pour se connecter à un réseau connu
ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # sans lettres ou chiffres faciles à confondre


def password(config, save):
    """Mot de passe du point d'accès (créé une fois, gardé dans la configuration)."""
    value = config.get("wifi_hotspot_password")
    if not value or len(value) < 8:
        value = "".join(secrets.choice(ALPHABET) for _ in range(10))
        save(dict(config, wifi_hotspot_password=value))
    return value


def qr_payload(ssid, key):
    """Texte du QR code « rejoindre ce Wi-Fi » (format reconnu par les appareils photo des téléphones)."""
    escape = lambda text: "".join("\\" + c if c in '\\;,:"' else c for c in text)
    return f"WIFI:T:WPA;S:{escape(ssid)};P:{escape(key)};;"


def state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return None


def start(key, runner=None):
    kwargs = {"runner": runner} if runner else {}
    ok, message = wifi_networks.nmcli("device", "wifi", "hotspot", "ifname", "wlan0", "con-name", wifi_networks.HOTSPOT_NAME,
                                      "ssid", SSID, "password", key, timeout=40, **kwargs)
    if ok:
        STATE_FILE.write_text(json.dumps({"ssid": SSID, "password": key, "address": ADDRESS, "since": time.time()}))
    return ok, message


def stop(runner=None):
    kwargs = {"runner": runner} if runner else {}
    STATE_FILE.unlink(missing_ok=True)
    return wifi_networks.nmcli("connection", "down", wifi_networks.HOTSPOT_NAME, **kwargs)


def clients(runner=None):
    """Appareils connectés au point d'accès (voisins réseau sur wlan0)."""
    import subprocess
    run = runner or subprocess.run
    try:
        out = run(["ip", "neigh", "show", "dev", "wlan0"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return 0
    return sum(1 for line in out.splitlines() if line.strip() and "FAILED" not in line and "INCOMPLETE" not in line)


class Fallback:
    """Décide d'ouvrir, de garder ou de fermer le point d'accès (appelé toutes les 30 s par le worker)."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.offline_since = None
        self.started_at = None

    def step(self, enabled, is_online, key, actions):
        """`actions` : {start(key), stop(), clients(), wait(seconds), online()} ; retourne ce qui a été fait."""
        now = self.clock()
        if self.started_at is not None:  # point d'accès ouvert
            if not enabled:
                actions["stop"]()
                self.started_at = None
                return "stopped"
            if now - self.started_at >= RETRY_EVERY and actions["clients"]() == 0:
                actions["stop"]()  # personne dessus : on réessaie les réseaux connus
                actions["wait"](RETRY_WAIT)
                if actions["online"]():
                    self.started_at, self.offline_since = None, None
                    return "back_online"
                actions["start"](key)
                self.started_at = self.clock()
                return "restarted"
            return "kept"
        if not enabled or is_online:
            self.offline_since = None
            return "idle"
        if self.offline_since is None:
            self.offline_since = now
        if now - self.offline_since >= OFFLINE_DELAY:
            ok, _message = actions["start"](key)
            if ok:
                self.started_at = now
                return "started"
            return "failed"
        return "waiting"
