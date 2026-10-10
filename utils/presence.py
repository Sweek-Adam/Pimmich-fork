"""
Présence à la maison : les téléphones de la famille sur le Wi-Fi (adresses MAC choisies dans l'interface).

Quand un téléphone revient après une absence, le cadre se réveille (même en dehors de ses heures, pour un
moment), affiche un mot d'accueil et peut lancer la playlist de la personne. Lecture seule du réseau :
table ARP du système (`ip neigh`), rafraîchie par un ping des dernières adresses connues.
"""
import json
import re
import socket
import subprocess
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = BASE_DIR / "cache" / "presence.json"
MAC = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")
AWAY_AFTER = 20 * 60      # plus vu depuis 20 min : parti
ARRIVAL_AFTER = 30 * 60   # revenu après au moins 30 min d'absence : « arrivée »


def neighbors():
    """Appareils vus récemment sur le réseau local : [{ip, mac}]."""
    try:
        out = subprocess.run(["ip", "neigh", "show"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    found = []
    for line in out.splitlines():
        match = re.match(r"^(\S+) .*lladdr ([0-9a-fA-F:]{17}) (\w+)", line)
        if match and match.group(3) not in ("FAILED", "INCOMPLETE"):
            found.append({"ip": match.group(1), "mac": match.group(2).lower(), "state": match.group(3)})
    return found


def hostname(ip):
    """Nom donné par la box (ex. « iPhone-de-Lea »), sinon ''."""
    try:
        socket.setdefaulttimeout(1)
        return socket.gethostbyaddr(ip)[0].split(".")[0]
    except (OSError, socket.herror):
        return ""
    finally:
        socket.setdefaulttimeout(None)


def _ping(ip):
    try:
        subprocess.run(["ping", "-c", "1", "-W", "1", ip], capture_output=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        pass


def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state))


def tick(devices, now=None, seen=None):
    """
    Un passage de détection. `devices` : [{mac, name, ...}] choisis dans l'interface.
    Retourne la liste des appareils qui viennent d'arriver.
    """
    now = now or time.time()
    state = load_state()
    if seen is None:
        for entry in state.values():  # réveiller les entrées ARP des téléphones (souvent en veille)
            if entry.get("ip"):
                _ping(entry["ip"])
        seen = {n["mac"]: n["ip"] for n in neighbors()}
    arrivals = []
    for device in devices:
        mac = (device.get("mac") or "").lower()
        if not MAC.match(mac):
            continue
        known = mac in state
        entry = state.setdefault(mac, {"last_seen": 0, "present": False})
        if mac in seen:
            absent_for = now - entry.get("last_seen", 0)
            # Premier passage (démarrage du cadre, appareil tout juste ajouté) : pas d'accueil, on note seulement
            if known and not entry.get("present") and absent_for >= ARRIVAL_AFTER:
                arrivals.append(device)
            entry.update(last_seen=now, present=True, ip=seen[mac])
        elif entry.get("present") and now - entry.get("last_seen", 0) > AWAY_AFTER:
            entry["present"] = False
    save_state(state)
    return arrivals


def status(devices):
    """Qui est à la maison : [{mac, name, present, last_seen}]."""
    state = load_state()
    return [dict(d, present=bool(state.get(d.get("mac", "").lower(), {}).get("present")),
                 last_seen=state.get(d.get("mac", "").lower(), {}).get("last_seen")) for d in devices]
