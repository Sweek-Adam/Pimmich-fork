"""
Stockage sur plusieurs supports : les photos d'une source (Google Drive, iCloud, clé USB...) peuvent vivre sur la
carte SD, sur un disque USB ou sur un partage réseau (NAS). Pimmich garde ses dossiers habituels
(static/photos/<source> et static/prepared/<source>) : sur un autre support, ce sont des liens vers
<support>/pimmich/photos/<source> et <support>/pimmich/prepared/<source>. Rien d'autre dans le code n'a à le savoir.

Les disques sont reconnus par leur identifiant (UUID) et remontés automatiquement au démarrage, au même endroit.
"""
import json
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path

import psutil

BASE_DIR = Path(__file__).resolve().parent.parent
PHOTOS_DIR = BASE_DIR / "static" / "photos"
PREPARED_DIR = BASE_DIR / "static" / "prepared"
MOUNT_ROOT = Path("/mnt/pimmich")
CREDENTIALS_DIR = BASE_DIR / "config" / "storage"
SD = "sd"
FILESYSTEMS = {"ext4", "ext3", "exfat", "vfat", "ntfs", "ntfs3", "btrfs", "xfs", "f2fs"}
SOURCE_NAME = re.compile(r"^[^/\\.][^/\\]{0,60}$")
_move_lock = threading.Lock()


def _run(command, timeout=30, **kwargs):
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, **kwargs)


def empty_dir(path):
    """Vide un dossier sans le supprimer (il peut être un lien vers un autre support)."""
    path = Path(path)
    if not path.is_dir():
        path.mkdir(parents=True, exist_ok=True)
        return
    for child in path.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


# --- Supports ---

def disks():
    """Partitions des disques branchés (hors carte SD) : [{uuid, label, fstype, size, mountpoint, model}]."""
    try:
        data = json.loads(_run(["lsblk", "-J", "-b", "-o", "NAME,UUID,LABEL,FSTYPE,SIZE,MOUNTPOINT,TYPE,TRAN,MODEL,PKNAME"]).stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return []
    found = []

    def walk(devices, parent=None):
        for dev in devices or []:
            name = dev.get("name", "")
            if name.startswith(("mmcblk", "zram", "loop", "ram")):
                continue
            if dev.get("type") == "part" or (dev.get("type") == "disk" and not dev.get("children")):
                if dev.get("uuid") and (dev.get("fstype") or "") in FILESYSTEMS:
                    found.append({"uuid": dev["uuid"], "label": dev.get("label") or (parent or {}).get("model") or name,
                                  "fstype": dev["fstype"], "size": int(dev.get("size") or 0),
                                  "mountpoint": dev.get("mountpoint"), "device": f"/dev/{name}"})
            walk(dev.get("children"), dev if dev.get("type") == "disk" else parent)

    walk(data.get("blockdevices"))
    return found


def mountpoint(storage):
    return MOUNT_ROOT / storage["id"]


def root(storage_id, config):
    """Dossier Pimmich d'un support (None pour la carte SD, ou support inconnu)."""
    storage = next((s for s in config.get("storages") or [] if s.get("id") == storage_id), None)
    return mountpoint(storage) / "pimmich" if storage else None


def is_mounted(storage):
    return os.path.ismount(mountpoint(storage))


def _owner_options():
    return f"uid={os.getuid()},gid={os.getgid()}"


def mount(storage):
    """Monte un support configuré (disque par UUID, ou partage réseau) ; renvoie (succès, message)."""
    target = mountpoint(storage)
    if os.path.ismount(target):
        return True, "déjà monté"
    _run(["sudo", "-n", "mkdir", "-p", str(target)])
    if storage["kind"] == "disk":
        disk = next((d for d in disks() if d["uuid"] == storage["uuid"]), None)
        if disk is None:
            return False, "disque débranché"
        if disk.get("mountpoint"):  # déjà monté ailleurs par le système : on le démonte d'abord
            _run(["sudo", "-n", "umount", disk["mountpoint"]])
        options = ["-o", f"{_owner_options()},umask=022"] if disk["fstype"] in ("vfat", "exfat", "ntfs", "ntfs3") else []
        result = _run(["sudo", "-n", "mount", *options, f"UUID={storage['uuid']}", str(target)])
    else:
        if not (shutil.which("mount.cifs") or Path("/sbin/mount.cifs").exists() or Path("/usr/sbin/mount.cifs").exists()):
            return False, "outil de partage réseau absent : sudo apt install cifs-utils"
        credentials = CREDENTIALS_DIR / f"{storage['id']}.cred"
        options = f"{_owner_options()},file_mode=0644,dir_mode=0755,vers=3.0"
        if credentials.is_file():
            options += f",credentials={credentials}"
        else:
            options += ",guest"
        result = _run(["sudo", "-n", "mount", "-t", "cifs", storage["share"], str(target), "-o", options], timeout=40)
    if result.returncode != 0:
        return False, (result.stderr or result.stdout).strip()[-300:] or "montage impossible"
    if storage["kind"] == "disk":
        _run(["sudo", "-n", "mkdir", "-p", str(target / "pimmich")])
        _run(["sudo", "-n", "chown", f"{os.getuid()}:{os.getgid()}", str(target / "pimmich")])
    (target / "pimmich").mkdir(exist_ok=True)
    return True, "monté"


def unmount(storage):
    target = mountpoint(storage)
    if not os.path.ismount(target):
        return True
    return _run(["sudo", "-n", "umount", str(target)]).returncode == 0


def save_credentials(storage_id, username, password, domain=""):
    """Identifiants d'un partage réseau : fichier lisible par le seul compte du cadre (jamais dans la configuration)."""
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    path = CREDENTIALS_DIR / f"{storage_id}.cred"
    lines = [f"username={username}", f"password={password}"] + ([f"domain={domain}"] if domain else [])
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    return path


def usage(path):
    try:
        u = psutil.disk_usage(str(path))
        return {"total": u.total, "used": u.used, "free": u.free, "percent": u.percent}
    except OSError:
        return None


def mount_all(config):
    """Au démarrage (et régulièrement) : remonte les supports configurés et recrée les liens des sources."""
    states = {}
    for storage in config.get("storages") or []:
        states[storage["id"]] = mount(storage)
    ensure_links(config)
    return states


# --- Emplacement des sources ---

def location(source):
    """Support où vivent les photos d'une source : identifiant du support, ou "sd"."""
    link = PHOTOS_DIR / source
    if link.is_symlink():
        target = Path(os.readlink(link))
        try:
            parts = target.relative_to(MOUNT_ROOT).parts
            return parts[0] if parts else SD
        except ValueError:
            return SD
    return SD


def sources():
    """Sources existantes (dossiers de photos ou de photos préparées)."""
    names = set()
    for folder in (PHOTOS_DIR, PREPARED_DIR):
        for child in folder.iterdir() if folder.is_dir() else []:
            if (child.is_dir() or child.is_symlink()) and not child.name.startswith("."):
                names.add(child.name)
    return sorted(names)


def _size(path):
    total = count = 0
    for dirpath, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(dirpath, name))
                count += 1
            except OSError:
                pass
    return total, count


def source_sizes():
    """{source: {bytes, files, location, online}}."""
    found = {}
    for source in sources():
        total = files = 0
        online = True
        for folder in (PHOTOS_DIR, PREPARED_DIR):
            path = folder / source
            if path.is_symlink() and not path.exists():
                online = False
                continue
            if path.is_dir():
                size, count = _size(path)
                total, files = total + size, files + count
        found[source] = {"bytes": total, "files": files, "location": location(source), "online": online}
    return found


def ensure_links(config):
    """Recrée les liens des sources placées sur un autre support (ex. après une mise à jour qui les aurait effacés)."""
    for source, storage_id in (config.get("storage_placement") or {}).items():
        base = root(storage_id, config)
        if base is None or not SOURCE_NAME.match(source):
            continue
        for kind, folder in (("photos", PHOTOS_DIR), ("prepared", PREPARED_DIR)):
            link, target = folder / source, base / kind / source
            if link.is_symlink() or link.exists():
                continue
            if target.parent.parent.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            folder.mkdir(parents=True, exist_ok=True)
            link.symlink_to(target, target_is_directory=True)


def _copy(src, dst, progress, state):
    for dirpath, _dirs, files in os.walk(src):
        rel = Path(dirpath).relative_to(src)
        (dst / rel).mkdir(parents=True, exist_ok=True)
        for name in files:
            shutil.copy2(os.path.join(dirpath, name), dst / rel / name)
            state["done"] += 1
            if state["done"] % 25 == 0 or state["done"] == state["total"]:
                progress(state["done"], state["total"])


def _verify(copy, expected):
    if _size(copy)[1] < expected:
        raise RuntimeError("Copie incomplète : les photos restent à leur place d'origine.")


def move(source, storage_id, config, progress=lambda done, total: None):
    """Déplace les photos d'une source vers un support ("sd" : la carte SD). Copie vérifiée, puis bascule du lien."""
    if not SOURCE_NAME.match(source or ""):
        raise ValueError("Source invalide.")
    if storage_id != SD and root(storage_id, config) is None:
        raise ValueError("Support inconnu.")
    if not _move_lock.acquire(blocking=False):
        raise RuntimeError("Un déplacement est déjà en cours.")
    try:
        current = location(source)
        if current == storage_id:
            return 0
        if storage_id != SD:
            storage = next(s for s in config["storages"] if s["id"] == storage_id)
            ok, message = mount(storage)
            if not ok:
                raise RuntimeError(f"Support indisponible : {message}")
            needed = sum(_size(folder / source)[0] for folder in (PHOTOS_DIR, PREPARED_DIR) if (folder / source).is_dir())
            free = (usage(mountpoint(storage)) or {}).get("free", 0)
            if needed > free * 0.95:
                raise RuntimeError("Pas assez de place sur ce support.")
        state = {"done": 0, "total": sum(_size(folder / source)[1] for folder in (PHOTOS_DIR, PREPARED_DIR) if (folder / source).is_dir())}
        moved = []
        for kind, folder in (("photos", PHOTOS_DIR), ("prepared", PREPARED_DIR)):
            link = folder / source
            if not link.exists() and not link.is_symlink():
                continue
            if link.is_symlink() and not link.exists():
                raise RuntimeError("Le support actuel de cette source est débranché.")
            old_real = link.resolve()
            expected = _size(old_real)[1]
            if storage_id == SD:
                staging = folder / f".{source}.moving"
                if staging.exists():
                    shutil.rmtree(staging)
                _copy(old_real, staging, progress, state)
                _verify(staging, expected)
                link.unlink()
                staging.rename(link)
            else:
                target = root(storage_id, config) / kind / source
                target.mkdir(parents=True, exist_ok=True)
                _copy(old_real, target, progress, state)
                _verify(target, expected)
                if link.is_symlink():
                    link.unlink()
                else:
                    link.rename(folder / f".{source}.old")
                link.symlink_to(target, target_is_directory=True)
            moved.append(old_real)
        # Copie vérifiée et lien basculé : l'ancienne copie peut partir
        for kind, folder in (("photos", PHOTOS_DIR), ("prepared", PREPARED_DIR)):
            leftover = folder / f".{source}.old"
            if leftover.exists():
                shutil.rmtree(leftover)
        for old in moved:
            if old.exists() and MOUNT_ROOT in old.parents:
                shutil.rmtree(old, ignore_errors=True)
        return state["done"]
    finally:
        _move_lock.release()
