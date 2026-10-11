"""
Fiabilité : surveillance du diaporama (relancé s'il se fige) et rotation des journaux (ils ne grossissent plus sans fin).

Le diaporama signale qu'il est vivant (« battement ») en mémoire vive, plusieurs fois par minute, depuis toutes ses
boucles ; avant une vidéo, il annonce un délai de grâce (la lecture bloque le diaporama le temps du film).
"""
import gzip
import json
import shutil
import time
from pathlib import Path

HEARTBEAT = Path("/tmp/pimmich_heartbeat.json")
_last_beat = [0.0]


def beat(grace=0, force=False):
    """Battement du diaporama (au plus toutes les 10 s, sauf si un délai de grâce est annoncé)."""
    now = time.time()
    if not force and not grace and now - _last_beat[0] < 10:
        return
    _last_beat[0] = now
    try:
        HEARTBEAT.write_text(json.dumps({"at": now, "grace": int(grace)}))
    except OSError:
        pass


def frozen(display_duration=10, now=None, heartbeat=None, started=None):
    """Le diaporama semble figé : aucun battement depuis bien plus longtemps que prévu
    (`started` : heure de démarrage du processus ; un diaporama qui démarre a le temps de s'installer)."""
    if heartbeat is None:
        try:
            heartbeat = json.loads(HEARTBEAT.read_text())
        except (OSError, ValueError):
            return False  # pas encore de battement : le diaporama démarre
    now = now or time.time()
    allowed = max(180, 4 * float(display_duration or 10)) + int(heartbeat.get("grace") or 0)
    if started and now - started < allowed:
        return False
    return now - max(float(heartbeat.get("at", now)), float(started or 0)) > allowed


def slideshow_started():
    """Heure de démarrage du processus du diaporama (None s'il ne tourne pas)."""
    import psutil
    for proc in psutil.process_iter(attrs=["cmdline", "create_time"]):
        if any("local_slideshow.py" in part for part in proc.info.get("cmdline") or []):
            return proc.info["create_time"]
    return None


def rotate_logs(folder, max_bytes=5 * 1024 * 1024, keep=3):
    """Journaux trop gros : copie compressée (.1.gz, .2.gz…) puis remise à zéro sur place
    (le fichier reste ouvert par Pimmich en ajout : on le vide sans le remplacer). Renvoie les journaux tournés."""
    rotated = []
    for log in sorted(Path(folder).glob("*.log")):
        try:
            if log.stat().st_size <= max_bytes:
                continue
        except OSError:
            continue
        for n in range(keep, 1, -1):
            older = log.with_name(f"{log.name}.{n - 1}.gz")
            if older.exists():
                older.replace(log.with_name(f"{log.name}.{n}.gz"))
        with open(log, "rb") as source, gzip.open(log.with_name(f"{log.name}.1.gz"), "wb") as target:
            shutil.copyfileobj(source, target)
        with open(log, "r+b") as handle:
            handle.truncate(0)
        rotated.append(log.name)
    return rotated
