"""Pilotage de l'enceinte Bluetooth depuis l'interface (via bluetoothctl) : état, association, appareils."""
import re
import subprocess

MAC = re.compile(r"^[0-9A-F]{2}(:[0-9A-F]{2}){5}$")
PAIRING_SECONDS = 180


def _ctl(*args, timeout=8):
    try:
        return subprocess.run(["bluetoothctl", *args], capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _flag(text, name):
    match = re.search(rf"^\s*{name}:\s*(yes|no)", text, re.MULTILINE)
    return bool(match) and match.group(1) == "yes"


def parse_devices(text):
    """Lignes « Device AA:BB:CC:DD:EE:FF Nom » -> [(mac, nom)]."""
    devices = []
    for line in text.splitlines():
        match = re.match(r"^Device ([0-9A-F:]{17}) (.+)$", line.strip())
        if match:
            devices.append((match.group(1), match.group(2)))
    return devices


def status():
    """État de l'adaptateur et appareils associés (nom, connecté ou non)."""
    show = _ctl("show")
    if "Controller" not in show:
        return {"available": False, "powered": False, "discoverable": False, "devices": []}
    devices = [{"mac": mac, "name": name, "connected": _flag(_ctl("info", mac), "Connected")}
               for mac, name in parse_devices(_ctl("devices", "Paired"))]
    return {"available": True, "powered": _flag(show, "Powered"), "discoverable": _flag(show, "Discoverable"), "devices": devices}


def open_pairing():
    """Rend le cadre visible quelques minutes : un téléphone peut alors s'y associer."""
    _ctl("discoverable-timeout", str(PAIRING_SECONDS))
    _ctl("pairable", "on")
    return "succeeded" in _ctl("discoverable", "on").lower() or _flag(_ctl("show"), "Discoverable")


def forget(mac):
    """Oublie un appareil associé (il devra être associé à nouveau)."""
    if not MAC.match(mac or ""):
        raise ValueError("Adresse Bluetooth invalide")
    return "removed" in _ctl("remove", mac).lower()
