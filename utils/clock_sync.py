"""
L'heure du cadre est-elle fiable ? Le Raspberry Pi 3 n'a pas d'horloge sur pile : sans Internet au démarrage, il
repart de l'heure de son dernier arrêt (parfois des jours plus tôt). Tant qu'elle n'est pas synchronisée, les heures
d'affichage sont ignorées : le cadre montre les photos plutôt que de rester éteint par erreur.
"""
import subprocess
import time
from pathlib import Path

_cache = {"at": 0.0, "value": True}


def trusted(runner=subprocess.run, rtc=Path("/sys/class/rtc/rtc0"), ttl=60):
    """Vrai si l'heure est synchronisée (NTP) ou donnée par une horloge sur pile ; vrai aussi hors Raspberry Pi."""
    now = time.monotonic()
    if now - _cache["at"] < ttl:
        return _cache["value"]
    value = True
    try:
        out = runner(["timedatectl", "show", "-p", "NTPSynchronized", "--value"], capture_output=True, text=True, timeout=5).stdout.strip()
        if out == "no" and not rtc.exists():
            value = False
    except (OSError, subprocess.SubprocessError):
        value = True  # pas de timedatectl : on fait confiance à l'horloge
    _cache.update(at=now, value=value)
    return value
