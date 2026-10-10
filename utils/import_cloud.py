"""
Autres clouds (Dropbox, OneDrive, pCloud, Box, Mega...) via rclone : même synchronisation que Google Drive
(utils/import_gdrive.py, profil « cloud »), photos rangées dans la source « cloud ».

Ajout d'un compte depuis l'interface : sur un ordinateur, `rclone authorize "dropbox"` (ou onedrive...) donne un
jeton à coller ; Pimmich crée alors le compte rclone sur le cadre.
"""
import json
import re
import subprocess
import threading
from pathlib import Path

from utils import import_gdrive as drive

TARGET_DIR = Path("static/photos/cloud")
PREPARED_DIR = Path("static/prepared/cloud")
MANIFEST_FILE = TARGET_DIR / ".cloud_manifest.json"
PROVIDERS = {"dropbox": "Dropbox", "onedrive": "OneDrive", "pcloud": "pCloud", "box": "Box", "mega": "Mega",
             "yandex": "Yandex Disk", "koofr": "Koofr", "jottacloud": "Jottacloud", "webdav": "WebDAV", "sftp": "SFTP"}
NAME = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
_sync_lock = threading.Lock()


def remotes():
    """Comptes rclone autres que Google Drive : [{name, type, label}]."""
    try:
        out = subprocess.run(["rclone", "listremotes", "--long"], capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    found = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] != "drive":
            found.append({"name": parts[0].rstrip(":"), "type": parts[1], "label": PROVIDERS.get(parts[1], parts[1].capitalize())})
    return found


def add_remote(name, provider, token):
    """Crée le compte rclone à partir du jeton donné par `rclone authorize` (aucun mot de passe stocké en clair)."""
    if not NAME.match(name or "") or provider not in PROVIDERS:
        raise ValueError("Nom ou service invalide.")
    try:
        parsed = json.loads(token)
    except (TypeError, ValueError):
        raise ValueError("Jeton invalide : collez tout le texte affiché par rclone authorize (entre accolades).")
    if not isinstance(parsed, dict) or "access_token" not in parsed:
        raise ValueError("Jeton invalide : collez tout le texte affiché par rclone authorize (entre accolades).")
    result = subprocess.run(["rclone", "config", "create", name, provider, "token", json.dumps(parsed), "--non-interactive"],
                            capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise ValueError(result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "rclone a refusé le compte.")


class CloudBackend(drive.RcloneBackend):
    """Comme Google Drive (rclone), sans les options propres au Drive."""

    def __init__(self, remote):
        if not remote:
            raise ValueError("Aucun compte cloud n'est configuré.")
        self.remote = remote

    def trash(self, f):
        """Supprime le fichier du cloud (Dropbox, OneDrive... le gardent dans leur corbeille pendant 30 jours)."""
        result = subprocess.run(["rclone", "deletefile", f"{self.remote}:{f['remote_path']}"], capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "rclone deletefile a échoué")


def profile(config):
    remote = config.get("cloud_rclone_remote")
    kind = next((r["label"] for r in remotes() if r["name"] == remote), "Cloud") if remote else "Cloud"
    return {"label": kind, "folders": config.get("cloud_folders") or [], "recursive": config.get("cloud_recursive", True),
            "trash": config.get("cloud_trash_after_import", False), "backend": lambda: CloudBackend(remote),
            "target": TARGET_DIR, "prepared": PREPARED_DIR, "manifest": MANIFEST_FILE}


def list_folders(config):
    remote = config.get("cloud_rclone_remote")
    return sorted(CloudBackend(remote).list_folders(), key=lambda f: f["name"].lower())


def import_cloud_photos(config):
    """Synchronise les dossiers choisis du cloud (mêmes étapes et mêmes protections que Google Drive)."""
    if not _sync_lock.acquire(blocking=False):
        yield {"type": "error", "message": "Une synchronisation est déjà en cours, réessayez dans un instant."}
        return
    try:
        yield from drive._import_gdrive_photos(config, profile(config))
    finally:
        _sync_lock.release()
