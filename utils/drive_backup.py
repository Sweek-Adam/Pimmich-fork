"""
Sauvegarde automatique des réglages de Pimmich sur Google Drive (via rclone) et restauration.

L'archive contient les fichiers de réglages de config/ : configuration, comptes, playlists, favoris, filtres,
textes, invitations, messages. Les jetons techniques propres à l'installation n'y sont pas inclus.
"""
import io
import json
import zipfile
import logging
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("pimmich.backup")

PROJECT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_DIR / "config"
STATUS_FILE = CONFIG_DIR / "backup_status.json"
BACKUP_PREFIX = "pimmich-sauvegarde-"
# Fichiers sauvegardés (les autres, comme les jetons internes ou l'état d'import, sont propres à l'installation)
BACKED_UP_FILES = ["config.json", "users.json", "playlists.json", "favorites.json", "filter_states.json",
                   "text_states.json", "polaroid_texts.json", "invitations.json", "telegram_guest_users.json",
                   "messages.json", "gdrive_service_account.json"]


def _rclone(*args, timeout=300):
    result = subprocess.run(["rclone", *args], capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        lines = result.stderr.strip().splitlines()
        raise RuntimeError(lines[-1] if lines else "rclone a échoué")
    return result.stdout


def _remote(config):
    from utils.import_gdrive import list_rclone_remotes
    remote = config.get("gdrive_rclone_remote") or next(iter(list_rclone_remotes()), None)
    if not remote:
        raise RuntimeError("Aucun remote rclone Google Drive n'est configuré (lancez « rclone config » sur le Raspberry Pi).")
    return f"{remote}:{config.get('backup_drive_folder') or 'Pimmich-Sauvegardes'}"


def build_archive():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in BACKED_UP_FILES:
            path = CONFIG_DIR / name
            if path.is_file():
                zf.write(path, name)
        zf.writestr("pimmich_backup.json", json.dumps({"created": datetime.now().isoformat(timespec="seconds")}))
    return buffer.getvalue()


def restore_archive(data):
    """Restaure les réglages contenus dans une archive ; retourne la liste des fichiers restaurés."""
    restored = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        if "pimmich_backup.json" not in zf.namelist():
            raise ValueError("Ce fichier n'est pas une sauvegarde Pimmich.")
        for name in zf.namelist():
            if name not in BACKED_UP_FILES:
                continue  # n'écrire que des fichiers attendus, jamais un chemin arbitraire
            content = zf.read(name)
            json.loads(content)  # chaque fichier doit être un JSON valide
            target = CONFIG_DIR / name
            tmp = target.with_suffix(".restore.tmp")
            tmp.write_bytes(content)
            if name in ("users.json", "gdrive_service_account.json"):
                tmp.chmod(0o600)
            tmp.replace(target)
            restored.append(name)
    return restored


def load_status():
    try:
        return json.loads(STATUS_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _save_status(**fields):
    status = {**load_status(), **fields}
    STATUS_FILE.write_text(json.dumps(status, indent=2, ensure_ascii=False))
    return status


def list_backups(config):
    """Sauvegardes présentes sur le Drive, la plus récente en premier."""
    try:
        entries = json.loads(_rclone("lsjson", "--files-only", _remote(config), timeout=120) or "[]")
    except RuntimeError as e:
        if "directory not found" in str(e).lower():
            return []
        raise
    backups = [e["Name"] for e in entries if e["Name"].startswith(BACKUP_PREFIX) and e["Name"].endswith(".zip")]
    return sorted(backups, reverse=True)


def backup_now(config):
    """Envoie une sauvegarde sur le Drive et supprime les plus anciennes au-delà du nombre à conserver."""
    target = _remote(config)
    name = f"{BACKUP_PREFIX}{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.zip"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / name
            local.write_bytes(build_archive())
            _rclone("copyto", str(local), f"{target}/{name}")
        keep = max(1, int(config.get("backup_drive_keep", 10)))
        for old in list_backups(config)[keep:]:
            _rclone("deletefile", f"{target}/{old}", timeout=120)
    except Exception as e:
        _save_status(last_attempt=datetime.now().isoformat(timespec="seconds"), last_error=str(e))
        logger.error(f"[Sauvegarde] Échec de la sauvegarde sur Google Drive : {e}")
        raise
    logger.info(f"[Sauvegarde] {name} envoyée sur Google Drive ({target})")
    return _save_status(last_attempt=datetime.now().isoformat(timespec="seconds"),
                        last_success=datetime.now().isoformat(timespec="seconds"), last_name=name, last_error=None)


def restore_latest(config):
    """Télécharge la sauvegarde la plus récente du Drive et la restaure ; retourne (nom, fichiers restaurés)."""
    backups = list_backups(config)
    if not backups:
        raise RuntimeError("Aucune sauvegarde trouvée sur Google Drive.")
    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp) / backups[0]
        _rclone("copyto", f"{_remote(config)}/{backups[0]}", str(local))
        restored = restore_archive(local.read_bytes())
    logger.info(f"[Sauvegarde] Restauration de {backups[0]} : {restored}")
    return backups[0], restored


def is_due(config, now=None):
    if not config.get("backup_drive_enabled"):
        return False
    last = load_status().get("last_attempt")
    if not last:
        return True
    hours = float(config.get("backup_drive_interval_hours", 24))
    return ((now or datetime.now()) - datetime.fromisoformat(last)).total_seconds() >= hours * 3600
