"""
Pilotage de la télévision par HDMI-CEC (cec-ctl, paquet v4l-utils) : allumer la TV et passer sur l'entrée du
cadre au réveil, la mettre en veille avec le cadre. Sans effet si la TV ou le Pi ne gèrent pas le CEC.
"""
import shutil
import subprocess
from pathlib import Path

DEVICE = "/dev/cec0"


def available():
    return Path(DEVICE).exists() and shutil.which("cec-ctl") is not None


def _ctl(*args, timeout=10):
    try:
        result = subprocess.run(["cec-ctl", "-d", DEVICE, *args], capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def tv_on():
    """Allume la TV et la met sur l'entrée HDMI du cadre."""
    if not available():
        return False
    _ctl("--playback", "--osd-name", "Cadre photo")  # se présenter comme lecteur
    woke = _ctl("--to", "0", "--image-view-on")
    _ctl("--to", "0", "--active-source", "phys-addr=" + physical_address())
    return woke


def tv_standby():
    return available() and _ctl("--to", "0", "--standby")


def physical_address():
    """Adresse HDMI du cadre (ex. 1.0.0.0), lue auprès du pilote CEC."""
    try:
        out = subprocess.run(["cec-ctl", "-d", DEVICE], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return "1.0.0.0"
    for line in out.splitlines():
        if "Physical Address" in line and ":" in line:
            value = line.split(":", 1)[1].strip()
            if value.count(".") == 3:
                return value
    return "1.0.0.0"
