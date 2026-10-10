import os
import json
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path

TARGET_DIR = Path("static/photos/gdrive")
PREPARED_DIR = Path("static/prepared/gdrive")
# Fichier de suivi : id Drive -> nom local et date de modification (pour la synchro incrémentale)
MANIFEST_FILE = TARGET_DIR / ".gdrive_manifest.json"
KEY_FILE = Path(os.path.dirname(__file__)).parent / "config" / "gdrive_service_account.json"

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.heic', '.heif', '.mp4', '.mov', '.avi', '.mkv'}
FOLDER_MIME = "application/vnd.google-apps.folder"
DRIVE_API = "https://www.googleapis.com/drive/v3"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
# Profondeur maximale de l'arborescence proposée dans le choix des dossiers (rclone)
RCLONE_FOLDER_DEPTH = 4
# Empêche deux synchronisations simultanées (worker automatique + bouton d'import)
_sync_lock = threading.Lock()


def _is_media(name):
    return Path(name).suffix.lower() in ALLOWED_EXTENSIONS


# --- Méthode 1 : rclone (utilise un remote Google Drive déjà configuré avec `rclone config`) ---

_remotes_cache = {"time": 0.0, "value": None}
REMOTES_CACHE_SECONDS = 600  # rclone met plusieurs secondes à démarrer sur un Raspberry Pi 3


def list_rclone_remotes(refresh=False):
    """Retourne les noms des remotes rclone de type Google Drive (sans le ':' final), avec un cache de 10 minutes."""
    import time
    if not refresh and _remotes_cache["value"] is not None and time.time() - _remotes_cache["time"] < REMOTES_CACHE_SECONDS:
        return list(_remotes_cache["value"])
    remotes = _list_rclone_remotes()
    _remotes_cache.update(time=time.time(), value=remotes)
    return list(remotes)


def trash_denied_files():
    """Photos importées que Google refuse de mettre à la corbeille (déposées par un autre compte)."""
    manifest = _load_manifest()
    files = []
    for fid, entry in manifest.items():
        if not entry.get("trash_denied"):
            continue
        real_id = "/" not in fid  # identifiant Google Drive (et non chemin de secours)
        files.append({"id": fid, "name": entry.get("name", ""), "remote_path": entry.get("remote_path") or entry.get("name", ""),
                      "denied_at": entry.get("denied_at", ""), "drive_url": f"https://drive.google.com/file/d/{fid}/view" if real_id else None,
                      "local": (TARGET_DIR / entry.get("name", "")).is_file()})
    return sorted(files, key=lambda f: f["remote_path"].lower())


def retry_trash_denied():
    """Réessayer à la prochaine synchronisation (ex. le propriétaire vous a donné les droits)."""
    manifest = _load_manifest()
    count = 0
    for entry in manifest.values():
        if entry.pop("trash_denied", None):
            entry.pop("denied_at", None)
            count += 1
    _save_manifest(manifest)
    return count


def _list_rclone_remotes():
    if not shutil.which("rclone"):
        return []
    try:
        result = subprocess.run(["rclone", "listremotes", "--long"], capture_output=True, text=True, timeout=15)
    except (subprocess.SubprocessError, OSError):
        return []
    remotes = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == "drive":
            remotes.append(parts[0].rstrip(":"))
    return remotes


def _rclone_lsjson(target, *args, timeout=300):
    result = subprocess.run(["rclone", "lsjson", target, *args], capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"rclone : {result.stderr.strip().splitlines()[-1] if result.stderr.strip() else 'erreur inconnue'}")
    return json.loads(result.stdout or "[]")


class RcloneBackend:
    def __init__(self, remote):
        if not remote:
            raise ValueError("Aucun remote rclone Google Drive n'est configuré (lancez `rclone config` sur le Raspberry Pi).")
        self.remote = remote

    def list_folders(self):
        """Les dossiers sont identifiés par leur chemin dans le Drive."""
        entries = _rclone_lsjson(f"{self.remote}:", "--dirs-only", "-R", "--max-depth", str(RCLONE_FOLDER_DEPTH))
        return [{"id": e["Path"], "name": e["Path"].replace("/", " / ")} for e in entries]

    def list_media(self, folder_id, recursive):
        args = ["--files-only"] + (["-R"] if recursive else [])
        files = []
        for e in _rclone_lsjson(f"{self.remote}:{folder_id}", *args):
            if _is_media(e["Name"]):
                files.append({
                    "id": e.get("ID") or f"{folder_id}/{e['Path']}",
                    "name": e["Name"],
                    "modifiedTime": e.get("ModTime"),
                    "remote_path": f"{folder_id}/{e['Path']}",
                })
        return files

    def download(self, f, dest):
        result = subprocess.run(["rclone", "copyto", f"{self.remote}:{f['remote_path']}", str(dest)],
                                capture_output=True, text=True, timeout=1800)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "rclone copyto a échoué")

    def trash(self, f):
        """Met le fichier dans la corbeille Google Drive (récupérable pendant 30 jours)."""
        result = subprocess.run(["rclone", "deletefile", "--drive-use-trash=true", f"{self.remote}:{f['remote_path']}"],
                                capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "rclone deletefile a échoué")


# --- Méthode 2 : compte de service Google (API Drive) ---

def parse_service_account_key(raw_json):
    """Valide le contenu JSON d'une clé de compte de service et le retourne sous forme de dict."""
    try:
        info = json.loads(raw_json)
    except json.JSONDecodeError:
        raise ValueError("La clé n'est pas un JSON valide.")
    if info.get("type") != "service_account" or not info.get("client_email") or not info.get("private_key"):
        raise ValueError("Ce fichier n'est pas une clé de compte de service Google (type 'service_account').")
    return info


def save_service_account_key(info):
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(KEY_FILE, 'w') as f:
        json.dump(info, f)
    os.chmod(KEY_FILE, 0o600)


def load_service_account_key():
    if not KEY_FILE.exists():
        return None
    try:
        with open(KEY_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def get_service_account_email():
    info = load_service_account_key()
    return info.get("client_email") if info else None


class ServiceAccountBackend:
    def __init__(self, key_info=None):
        info = key_info or load_service_account_key()
        if not info:
            raise ValueError("Aucune clé de compte de service Google Drive n'est configurée.")
        # Import tardif : google-auth n'est nécessaire que pour cette méthode
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        self.session = AuthorizedSession(creds)

    def _list_files(self, query, fields="id, name, mimeType, modifiedTime, parents"):
        """Liste tous les fichiers correspondant à la requête, en gérant la pagination."""
        params = {
            "q": query,
            "fields": f"nextPageToken, files({fields})",
            "pageSize": 1000,
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        while True:
            resp = self.session.get(f"{DRIVE_API}/files", params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            yield from data.get("files", [])
            token = data.get("nextPageToken")
            if not token:
                break
            params["pageToken"] = token

    def list_folders(self):
        folders = {f["id"]: f for f in self._list_files(f"mimeType='{FOLDER_MIME}' and trashed=false", "id, name, parents")}

        def path_of(folder_id, seen=()):
            folder = folders.get(folder_id)
            if not folder or folder_id in seen:
                return []
            parent = (folder.get("parents") or [None])[0]
            return path_of(parent, seen + (folder_id,)) + [folder["name"]]

        return [{"id": fid, "name": " / ".join(path_of(fid))} for fid in folders]

    def list_media(self, folder_id, recursive, seen=None):
        seen = set() if seen is None else seen
        if folder_id in seen:
            return []
        seen.add(folder_id)
        media = []
        for f in self._list_files(f"'{folder_id}' in parents and trashed=false"):
            if f["mimeType"] == FOLDER_MIME:
                if recursive:
                    media.extend(self.list_media(f["id"], recursive, seen))
            elif _is_media(f["name"]):
                media.append(f)
        return media

    def download(self, f, dest):
        with self.session.get(f"{DRIVE_API}/files/{f['id']}", params={"alt": "media", "supportsAllDrives": "true"},
                              stream=True, timeout=120) as resp:
            resp.raise_for_status()
            with open(dest, 'wb') as out:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    out.write(chunk)

    def trash(self, f):
        # Un compte de service n'est pas propriétaire des fichiers partagés avec lui : Google refuse la mise à la corbeille
        raise NotImplementedError("La mise à la corbeille après import n'est possible qu'avec la connexion rclone.")


# --- Point d'entrée commun ---

def resolve_backend_name(config):
    """'rclone' ou 'service_account'. En mode 'auto', rclone est préféré s'il a un remote Google Drive."""
    backend = config.get("gdrive_backend", "auto")
    if backend == "auto":
        return "rclone" if list_rclone_remotes() else "service_account"
    return backend


def get_backend(config, key_info=None):
    if resolve_backend_name(config) == "rclone":
        remote = config.get("gdrive_rclone_remote") or next(iter(list_rclone_remotes()), None)
        return RcloneBackend(remote)
    return ServiceAccountBackend(key_info)


def list_folders(config, key_info=None):
    """Retourne les dossiers Google Drive accessibles, avec leur chemin complet, triés par chemin."""
    return sorted(get_backend(config, key_info).list_folders(), key=lambda f: f["name"].lower())


def _local_name(drive_file, used_names):
    """Nom local unique : le nom d'origine, suffixé par l'id Drive en cas de doublon."""
    name = drive_file["name"].replace("/", "_")
    if name in used_names:
        stem, ext = os.path.splitext(name)
        name = f"{stem}_{drive_file['id'][:8]}{ext}"
    used_names.add(name)
    return name


def _load_manifest(path=None):
    path = path or MANIFEST_FILE
    if path.exists():
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _save_manifest(manifest, path=None):
    path = path or MANIFEST_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as mf:
        json.dump(manifest, mf)


def remove_local_media(stem=None):
    """
    Retire du cadre les fichiers Google Drive téléchargés (tous, ou ceux portant ce nom sans extension),
    pour qu'ils ne soient pas préparés à nouveau. Appelé lors d'une suppression depuis l'Aperçu.
    """
    manifest = _load_manifest()
    for fid, entry in list(manifest.items()):
        if stem is None or Path(entry["name"]).stem == stem:
            (TARGET_DIR / entry["name"]).unlink(missing_ok=True)
            del manifest[fid]
    if TARGET_DIR.exists():
        for f in TARGET_DIR.iterdir():
            if f.is_file() and f != MANIFEST_FILE and (stem is None or f.stem == stem):
                f.unlink(missing_ok=True)
    _save_manifest(manifest)


def import_gdrive_photos(config):
    """
    Synchronise les photos des dossiers Google Drive sélectionnés et retourne des objets structurés pour le suivi.
    Télécharge uniquement les fichiers nouveaux ou modifiés et supprime les fichiers locaux obsolètes.
    """
    if not _sync_lock.acquire(blocking=False):
        yield {"type": "error", "message": "Une synchronisation Google Drive est déjà en cours, réessayez dans un instant."}
        return
    try:
        yield from _import_gdrive_photos(config)
    finally:
        _sync_lock.release()


def drive_profile(config):
    """Ce que l'import synchronise pour Google Drive : dossiers, méthode, emplacements sur le cadre."""
    backend_name = resolve_backend_name(config)
    # Les dossiers choisis avec une autre méthode de connexion n'ont pas le même identifiant
    folders = [f for f in config.get("gdrive_folders", []) if f.get("backend", backend_name) == backend_name]
    return {"label": "Google Drive", "folders": folders, "recursive": config.get("gdrive_recursive", True),
            "trash": config.get("gdrive_trash_after_import", False), "backend": lambda: get_backend(config),
            "target": TARGET_DIR, "prepared": PREPARED_DIR, "manifest": MANIFEST_FILE}


def _import_gdrive_photos(config, profile=None):
    P = profile or drive_profile(config)  # Google Drive par défaut ; autres clouds : utils/import_cloud.py
    folders, recursive, trash_after_import, label = P["folders"], P["recursive"], P["trash"], P["label"]

    if not folders:
        yield {"type": "error", "message": f"Aucun dossier {label} sélectionné."}
        return

    yield {"type": "progress", "stage": "CONNECTING", "percent": 5, "message": f"Connexion à {label}..."}

    try:
        backend = P["backend"]()

        # --- Phase 1: Lister les fichiers distants ---
        yield {"type": "progress", "stage": "SCANNING", "percent": 10, "message": f"Analyse de {len(folders)} dossier(s) {label}..."}
        remote_files = {}
        for folder in folders:
            try:
                for f in backend.list_media(folder["id"], recursive):
                    remote_files[f["id"]] = f
            except Exception as e:
                # Ne rien supprimer localement si un dossier n'a pas pu être lu
                yield {"type": "error", "message": f"Impossible de lire le dossier '{folder['name']}' : {e}"}
                return

        P["target"].mkdir(parents=True, exist_ok=True)
        P["prepared"].mkdir(parents=True, exist_ok=True)
        manifest = _load_manifest(P["manifest"])

        # --- Phase 2: Supprimer les fichiers locaux obsolètes (retirés du Drive ou dossier désélectionné) ---
        # En mode corbeille, le Drive n'est qu'une boîte d'envoi : un fichier qui en disparaît reste sur le cadre.
        # Les fichiers déjà mis à la corbeille appartiennent au cadre dans tous les cas.
        if trash_after_import:
            obsolete_ids = []
        else:
            obsolete_ids = [fid for fid in manifest if fid not in remote_files and not manifest[fid].get("trashed")]
        if obsolete_ids:
            yield {"type": "progress", "stage": "CLEANING", "percent": 15, "message": f"Suppression de {len(obsolete_ids)} photos obsolètes..."}
            for fid in obsolete_ids:
                try:
                    (P["target"] / manifest[fid]["name"]).unlink(missing_ok=True)
                except OSError as e:
                    yield {"type": "warning", "message": f"Impossible de supprimer {manifest[fid]['name']}: {e}"}
                del manifest[fid]

        # --- Phase 3: Déterminer les fichiers à télécharger ---
        used_names = {entry["name"] for entry in manifest.values()}
        to_download = []
        to_trash = []  # Fichiers déjà présents sur le cadre, à mettre à la corbeille sur le Drive
        for fid, f in remote_files.items():
            entry = manifest.get(fid)
            if entry is not None:
                entry["remote_path"] = f.get("remote_path") or f["name"]  # chemin dans le Drive (liste des photos non supprimables)
            if entry and entry.get("modifiedTime") == f.get("modifiedTime") and (P["target"] / entry["name"]).exists():
                # Ne pas réessayer indéfiniment un fichier que Google refuse de mettre à la corbeille
                if trash_after_import and not entry.get("trash_denied"):
                    to_trash.append(f)
                continue
            name = entry["name"] if entry else _local_name(f, used_names)
            to_download.append((f, name))

        def trash_on_drive(files):
            trashed = 0
            for f in files:
                # Marquer le fichier comme « à garder » AVANT de le retirer du Drive : si l'opération est
                # interrompue (redémarrage, coupure), il ne sera jamais pris pour un fichier supprimé.
                manifest[f["id"]]["trashed"] = True
                _save_manifest(manifest, P["manifest"])
                try:
                    backend.trash(f)
                    trashed += 1
                except NotImplementedError as e:
                    manifest[f["id"]].pop("trashed", None)
                    _save_manifest(manifest, P["manifest"])
                    yield {"type": "warning", "message": str(e)}
                    break
                except Exception as e:
                    if "insufficientFilePermissions" in str(e) or "403" in str(e):
                        # Seul le propriétaire d'un fichier peut le mettre à la corbeille (ex : photo déposée par un
                        # autre compte dans un dossier partagé). Le fichier reste sur le cadre, on ne réessaie plus.
                        manifest[f["id"]]["trash_denied"] = True
                        manifest[f["id"]]["denied_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                        _save_manifest(manifest, P["manifest"])
                        yield {"type": "warning", "message": f"{f['name']} gardé sur le cadre mais laissé sur {label} : seul son propriétaire peut le mettre à la corbeille."}
                    else:
                        yield {"type": "warning", "message": f"Impossible de mettre {f['name']} à la corbeille {label} : {e}"}
            if trashed:
                yield {"type": "info", "message": f"{trashed} fichier(s) importé(s) mis à la corbeille {label}."}

        if to_trash:
            yield from trash_on_drive(to_trash)

        total = len(to_download)
        if total == 0:
            _save_manifest(manifest, P["manifest"])
            yield {"type": "info", "message": "Aucune nouvelle photo à importer. Les dossiers sont à jour."}
            yield {"type": "done", "stage": "IMPORT_COMPLETE", "percent": 100, "message": "Synchronisation terminée. Aucune nouvelle photo.", "changes": len(obsolete_ids)}
            return

        yield {"type": "stats", "stage": "COPYING", "percent": 20, "message": f"Début du téléchargement de {total} fichiers...", "total": total}

        # --- Phase 4: Télécharger ---
        cancel_flag = Path('/tmp/pimmich_cancel_import.flag')
        downloaded = 0
        downloaded_files = []
        for i, (f, name) in enumerate(to_download, 1):
            if cancel_flag.exists():
                yield {"type": "warning", "message": "Import annulé par l'utilisateur."}
                break
            dest = P["target"] / name
            tmp = dest.with_name(dest.name + ".part")
            try:
                backend.download(f, tmp)
                tmp.replace(dest)
                manifest[f["id"]] = {"name": name, "modifiedTime": f.get("modifiedTime"), "remote_path": f.get("remote_path") or f["name"]}
                downloaded_files.append(f)
                downloaded += 1
            except Exception as e:
                tmp.unlink(missing_ok=True)
                yield {"type": "warning", "message": f"Impossible de télécharger {f['name']}: {e}"}

            percent = 20 + int((i / total) * 60)  # Le téléchargement représente 60% de la barre (de 20% à 80%)
            yield {
                "type": "progress", "stage": "COPYING", "percent": percent,
                "message": f"Téléchargement en cours... ({i}/{total})",
                "current": i, "total": total
            }

        # Mise à la corbeille seulement une fois le fichier bien enregistré sur le cadre
        _save_manifest(manifest, P["manifest"])
        if trash_after_import and downloaded_files:
            yield from trash_on_drive(downloaded_files)
        _save_manifest(manifest, P["manifest"])

        yield {"type": "done", "stage": "IMPORT_COMPLETE", "percent": 80, "message": f"{downloaded} photos synchronisées depuis {label}.", "total_imported": downloaded, "changes": downloaded + len(obsolete_ids)}

    except ValueError as e:
        yield {"type": "error", "message": str(e)}
    except Exception as e:
        yield {"type": "error", "message": f"Erreur {label} : {str(e)}"}
