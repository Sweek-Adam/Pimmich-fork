"""
Réseaux Wi-Fi mémorisés par le cadre (profils NetworkManager) : liste, ajout (même hors de portée ou masqué),
suppression, ordre de préférence et connexion. NetworkManager se connecte tout seul au meilleur réseau connu à
portée ; les mots de passe restent dans NetworkManager et ne sont jamais renvoyés au navigateur.
"""
import re
import subprocess

HOTSPOT_NAME = "pimmich-hotspot"  # point d'accès de secours (utils/hotspot.py), jamais listé comme réseau connu
WIFI_TYPES = ("802-11-wireless", "wifi")


def nmcli(*args, timeout=30, runner=subprocess.run):
    """Commande nmcli (avec sudo -n : droits accordés par setup.sh) ; retourne (succès, sortie)."""
    try:
        result = runner(["sudo", "-n", "/usr/bin/nmcli", *args], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)
    return result.returncode == 0, (result.stdout if result.returncode == 0 else (result.stderr or result.stdout)).strip()


def _fields(line):
    """Champs d'une ligne `nmcli -t` (séparés par « : », les « \\: » font partie du texte)."""
    return [part.replace("\\:", ":").replace("\\\\", "\\") for part in re.split(r"(?<!\\):", line)]


def saved(runner=subprocess.run):
    """Réseaux connus, du préféré au moins préféré : [{name, uuid, priority, active, autoconnect}]."""
    ok, out = nmcli("-t", "-f", "NAME,UUID,TYPE,AUTOCONNECT,AUTOCONNECT-PRIORITY,ACTIVE", "connection", "show", runner=runner)
    if not ok:
        return []
    networks = []
    for line in out.splitlines():
        fields = _fields(line)
        if len(fields) < 6 or fields[2] not in WIFI_TYPES or fields[0] == HOTSPOT_NAME:
            continue
        try:
            priority = int(fields[4])
        except ValueError:
            priority = 0
        networks.append({"name": fields[0], "uuid": fields[1], "autoconnect": fields[3] == "yes", "priority": priority,
                         "active": fields[5] == "yes"})
    return sorted(networks, key=lambda n: (-n["priority"], n["name"].lower()))


def join_payload(runner=subprocess.run):
    """Texte du QR code « rejoindre le Wi-Fi actuel » (mode fête). Le mot de passe est lu dans NetworkManager au moment
    voulu et n'est jamais enregistré ni écrit dans les journaux. (nom du réseau, texte du QR), ou None."""
    active = next((n for n in saved(runner) if n["active"]), None)
    if not active:
        return None
    ok, out = nmcli("-s", "-g", "802-11-wireless.ssid,802-11-wireless-security.psk", "connection", "show", "uuid", active["uuid"], runner=runner)
    lines = out.splitlines() if ok else []
    if not lines or not lines[0]:
        return None
    ssid = lines[0].replace("\\:", ":")
    key = lines[1] if len(lines) > 1 else ""
    from utils import hotspot
    payload = hotspot.qr_payload(ssid, key) if key else f"WIFI:T:nopass;S:{ssid};;"
    return ssid, payload


def check(ssid, password):
    """Message d'erreur (str) si le nom ou le mot de passe ne conviennent pas, sinon None."""
    if not ssid or len(ssid.encode()) > 32 or any(c in ssid for c in "\r\n\x00"):
        return "ssid"
    if password and not 8 <= len(password) <= 63:
        return "password"
    return None


def add(ssid, password="", hidden=False, priority=None, runner=subprocess.run):
    """Ajoute (ou met à jour) un réseau connu, sans exiger qu'il soit à portée. Retourne (succès, message)."""
    known = saved(runner)
    existing = next((n for n in known if n["name"] == ssid), None)
    if priority is None:
        priority = (max((n["priority"] for n in known), default=0) + 10) if not existing else existing["priority"]
    settings = ["802-11-wireless.ssid", ssid, "802-11-wireless.hidden", "yes" if hidden else "no",
                "connection.autoconnect", "yes", "connection.autoconnect-priority", str(int(priority))]
    if password:
        settings += ["wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk", password]
    if existing:  # sans nouveau mot de passe, celui déjà enregistré est gardé
        return nmcli("connection", "modify", "uuid", existing["uuid"], *settings, runner=runner)
    return nmcli("connection", "add", "type", "wifi", "con-name", ssid, "ifname", "wlan0", *settings, runner=runner)


def remove(uuid, runner=subprocess.run):
    return nmcli("connection", "delete", "uuid", uuid, runner=runner)


def connect(uuid, runner=subprocess.run):
    return nmcli("connection", "up", "uuid", uuid, timeout=60, runner=runner)


def reorder(uuids, runner=subprocess.run):
    """Ordre de préférence : le premier réseau de la liste est essayé en premier."""
    total = len(uuids)
    for rank, uuid in enumerate(uuids):
        ok, message = nmcli("connection", "modify", "uuid", uuid, "connection.autoconnect-priority", str((total - rank) * 10), runner=runner)
        if not ok:
            return False, message
    return True, ""


def online(runner=subprocess.run):
    """Le cadre a-t-il un réseau (Wi-Fi connu ou câble) ? Le point d'accès de secours ne compte pas."""
    ok, out = nmcli("-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", runner=runner, timeout=10)
    if not ok:
        return True  # NetworkManager indisponible : on ne fait rien d'automatique
    for line in out.splitlines():
        fields = _fields(line)
        if len(fields) >= 4 and fields[1] in ("wifi", "ethernet") and fields[2] == "connected" and fields[3] != HOTSPOT_NAME:
            return True
    return False
