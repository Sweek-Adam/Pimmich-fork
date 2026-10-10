"""
Surveillance de l'espace disque et nettoyage automatique optionnel.

Le nettoyage ne supprime que des photos/vidéos Google Drive déjà retirées du Drive (mode « corbeille après import »),
les plus anciennes d'abord, et jamais les favoris.
"""
import json
import shutil
import logging
from pathlib import Path

from utils import import_gdrive

logger = logging.getLogger("pimmich.disk")

PROJECT_DIR = Path(__file__).resolve().parent.parent
PREPARED_GDRIVE = PROJECT_DIR / "static" / "prepared" / "gdrive"
BACKUPS_GDRIVE = PROJECT_DIR / "static" / ".backups" / "gdrive"
FAVORITES_FILE = PROJECT_DIR / "config" / "favorites.json"
GB = 1024 ** 3
CLEANUP_MARGIN = 1 * GB  # espace libéré au-delà du seuil, pour ne pas nettoyer à chaque vérification


def disk_status(config):
    usage = shutil.disk_usage(PROJECT_DIR)
    threshold = float(config.get("disk_alert_free_gb", 2)) * GB
    return {
        "total_gb": round(usage.total / GB, 1),
        "free_gb": round(usage.free / GB, 1),
        "used_percent": round(100 * usage.used / usage.total, 1),
        "threshold_gb": round(threshold / GB, 1),
        "low": usage.free < threshold,
    }


def _favorites():
    try:
        return set(json.loads(FAVORITES_FILE.read_text()))
    except (OSError, json.JSONDecodeError):
        return set()


def cleanup_candidates():
    """Photos/vidéos Drive supprimables (retirées du Drive, hors favoris), les plus anciennes d'abord."""
    manifest = import_gdrive._load_manifest()
    favorites = _favorites()
    candidates = []
    for entry in manifest.values():
        if not entry.get("trashed"):
            continue  # encore sur le Drive : il serait simplement retéléchargé
        stem = Path(entry["name"]).stem
        if any(f.startswith(f"gdrive/{stem}.") for f in favorites):
            continue
        source = import_gdrive.TARGET_DIR / entry["name"]
        files = [source] + list(PREPARED_GDRIVE.glob(f"{stem}*")) + list(BACKUPS_GDRIVE.glob(f"{stem}*"))
        files = [f for f in files if f.is_file()]
        if files:
            candidates.append((min(f.stat().st_mtime for f in files), stem, sum(f.stat().st_size for f in files), files))
    return sorted(candidates)


def free_space(config):
    """Supprime les médias les plus anciens jusqu'à repasser au-dessus du seuil ; retourne la liste des noms supprimés."""
    threshold = float(config.get("disk_alert_free_gb", 2)) * GB
    free = shutil.disk_usage(PROJECT_DIR).free
    removed = []
    for _, stem, size, files in cleanup_candidates():
        if free >= threshold + CLEANUP_MARGIN:
            break
        for f in files:
            f.unlink(missing_ok=True)
        import_gdrive.remove_local_media(stem)
        free += size
        removed.append(stem)
    if removed:
        logger.warning(f"[Disque] Espace insuffisant : {len(removed)} média(s) Google Drive les plus anciens supprimés : {removed}")
    return removed
