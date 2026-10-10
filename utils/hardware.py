"""
État matériel du Raspberry Pi : alimentation (sous-tension), température, carte SD.
Lu sans droits particuliers (vcgencmd, /sys) ; chaque information absente vaut None (ex. hors Raspberry Pi).
"""
import re
import subprocess
from pathlib import Path

SYS = Path("/sys")
PROC = Path("/proc")

# Bits de « vcgencmd get_throttled »
UNDERVOLT_NOW, CAPPED_NOW, THROTTLED_NOW, TEMP_LIMIT_NOW = 0x1, 0x2, 0x4, 0x8
UNDERVOLT_SINCE_BOOT, CAPPED_SINCE_BOOT, THROTTLED_SINCE_BOOT, TEMP_LIMIT_SINCE_BOOT = 0x10000, 0x20000, 0x40000, 0x80000

# Alimentation officielle conseillée selon le modèle
POWER_SUPPLY = {"5": "5,1 V / 5 A (USB-C, 27 W)", "4": "5,1 V / 3 A (USB-C, 15 W)", "3": "5,1 V / 2,5 A (micro-USB)"}


def _read(path):
    try:
        return Path(path).read_text().strip().strip("\x00")
    except OSError:
        return None


def model():
    return _read(PROC / "device-tree" / "model")


def recommended_supply(model_name=None):
    match = re.search(r"Raspberry Pi (\d)", model_name or model() or "")
    return POWER_SUPPLY.get(match.group(1)) if match else None


def throttled():
    """Valeur de get_throttled (entier), sinon None."""
    try:
        out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r"throttled=(0x[0-9a-fA-F]+)", out)
    return int(match.group(1), 16) if match else None


def temperature():
    """Température du processeur en °C, sinon None."""
    raw = _read(SYS / "class" / "thermal" / "thermal_zone0" / "temp")
    try:
        return round(int(raw) / 1000, 1) if raw else None
    except ValueError:
        return None


def sd_errors():
    """Nombre d'erreurs signalées par le système de fichiers de la carte SD (ext4), sinon None."""
    base = SYS / "fs" / "ext4"
    if not base.exists():
        return None
    total, found = 0, False
    for device in base.iterdir():
        value = _read(device / "errors_count")
        if value and value.isdigit():
            total, found = total + int(value), True
    return total if found else None


def status():
    flags = throttled()
    return {
        "model": model(),
        "supply": recommended_supply(),
        "temperature": temperature(),
        "throttled": flags,
        "undervoltage_now": bool(flags & UNDERVOLT_NOW) if flags is not None else None,
        "undervoltage_since_boot": bool(flags & UNDERVOLT_SINCE_BOOT) if flags is not None else None,
        "slowed_by_heat": bool(flags & (TEMP_LIMIT_NOW | TEMP_LIMIT_SINCE_BOOT)) if flags is not None else None,
        "sd_errors": sd_errors(),
    }
