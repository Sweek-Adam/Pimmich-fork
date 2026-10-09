import os
import json
from pathlib import Path

from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

TARGET_DIR = Path("static/photos/gdrive")
PREPARED_DIR = Path("static/prepared/gdrive")
# Fichier de suivi : id Drive -> nom local et date de modification (pour la synchro incrémentale)
MANIFEST_FILE = TARGET_DIR / ".gdrive_manifest.json"
KEY_FILE = Path(os.path.dirname(__file__)).parent / "config" / "gdrive_service_account.json"

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.heic', '.heif', '.mp4', '.mov', '.avi', '.mkv'}
FOLDER_MIME = "application/vnd.google-apps.folder"
DRIVE_API = "https://www.googleapis.com/drive/v3"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


# --- Gestion de la clé du compte de service ---

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


def _session(key_info=None):
    info = key_info or load_service_account_key()
    if not info:
        raise ValueError("Aucune clé de compte de service Google Drive n'est configurée.")
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return AuthorizedSession(creds)


# --- Appels à l'API Drive ---

def _list_files(session, query, fields="id, name, mimeType, modifiedTime, parents"):
    """Liste tous les fichiers correspondant à la requête, en gérant la pagination."""
    params = {
        "q": query,
        "fields": f"nextPageToken, files({fields})",
        "pageSize": 1000,
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
    }
    while True:
        resp = session.get(f"{DRIVE_API}/files", params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        yield from data.get("files", [])
        token = data.get("nextPageToken")
        if not token:
            break
        params["pageToken"] = token


def list_folders(key_info=None):
    """
    Retourne tous les dossiers accessibles au compte de service, avec leur chemin complet
    (ex: 'Photos / Vacances 2024'), triés par chemin.
    """
    session = _session(key_info)
    folders = {f["id"]: f for f in _list_files(session, f"mimeType='{FOLDER_MIME}' and trashed=false", "id, name, parents")}

    def path_of(folder_id, seen=()):
        folder = folders.get(folder_id)
        if not folder or folder_id in seen:
            return []
        parent = (folder.get("parents") or [None])[0]
        return path_of(parent, seen + (folder_id,)) + [folder["name"]]

    result = [{"id": fid, "name": " / ".join(path_of(fid))} for fid in folders]
    return sorted(result, key=lambda f: f["name"].lower())


def _collect_media(session, folder_id, recursive, seen):
    """Retourne les fichiers image/vidéo d'un dossier (et de ses sous-dossiers si recursive)."""
    if folder_id in seen:
        return []
    seen.add(folder_id)
    media = []
    for f in _list_files(session, f"'{folder_id}' in parents and trashed=false"):
        if f["mimeType"] == FOLDER_MIME:
            if recursive:
                media.extend(_collect_media(session, f["id"], recursive, seen))
        elif Path(f["name"]).suffix.lower() in ALLOWED_EXTENSIONS:
            media.append(f)
    return media


def _local_name(drive_file, used_names):
    """Nom local unique : le nom d'origine, suffixé par l'id Drive en cas de doublon."""
    name = drive_file["name"].replace("/", "_")
    if name in used_names:
        stem, ext = os.path.splitext(name)
        name = f"{stem}_{drive_file['id'][:8]}{ext}"
    used_names.add(name)
    return name


def _load_manifest():
    if MANIFEST_FILE.exists():
        try:
            with open(MANIFEST_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def import_gdrive_photos(config):
    """
    Synchronise les photos des dossiers Google Drive sélectionnés et retourne des objets structurés pour le suivi.
    Télécharge uniquement les fichiers nouveaux ou modifiés et supprime les fichiers locaux obsolètes.
    """
    folders = config.get("gdrive_folders", [])
    recursive = config.get("gdrive_recursive", True)

    if not folders:
        yield {"type": "error", "message": "Aucun dossier Google Drive sélectionné."}
        return

    yield {"type": "progress", "stage": "CONNECTING", "percent": 5, "message": "Connexion à Google Drive..."}

    try:
        session = _session()

        # --- Phase 1: Lister les fichiers distants ---
        yield {"type": "progress", "stage": "SCANNING", "percent": 10, "message": f"Analyse de {len(folders)} dossier(s) Google Drive..."}
        remote_files = {}
        seen = set()
        for folder in folders:
            for f in _collect_media(session, folder["id"], recursive, seen):
                remote_files[f["id"]] = f

        TARGET_DIR.mkdir(parents=True, exist_ok=True)
        PREPARED_DIR.mkdir(parents=True, exist_ok=True)
        manifest = _load_manifest()

        # --- Phase 2: Supprimer les fichiers locaux obsolètes (retirés du Drive ou dossier désélectionné) ---
        obsolete_ids = [fid for fid in manifest if fid not in remote_files]
        if obsolete_ids:
            yield {"type": "progress", "stage": "CLEANING", "percent": 15, "message": f"Suppression de {len(obsolete_ids)} photos obsolètes..."}
            for fid in obsolete_ids:
                try:
                    (TARGET_DIR / manifest[fid]["name"]).unlink(missing_ok=True)
                except OSError as e:
                    yield {"type": "warning", "message": f"Impossible de supprimer {manifest[fid]['name']}: {e}"}
                del manifest[fid]

        # --- Phase 3: Déterminer les fichiers à télécharger ---
        used_names = {entry["name"] for entry in manifest.values()}
        to_download = []
        for fid, f in remote_files.items():
            entry = manifest.get(fid)
            if entry and entry.get("modifiedTime") == f.get("modifiedTime") and (TARGET_DIR / entry["name"]).exists():
                continue
            name = entry["name"] if entry else _local_name(f, used_names)
            to_download.append((f, name))

        total = len(to_download)
        if total == 0:
            with open(MANIFEST_FILE, 'w') as mf:
                json.dump(manifest, mf)
            yield {"type": "info", "message": "Aucune nouvelle photo à importer. Les dossiers sont à jour."}
            yield {"type": "done", "stage": "IMPORT_COMPLETE", "percent": 100, "message": "Synchronisation terminée. Aucune nouvelle photo."}
            return

        yield {"type": "stats", "stage": "COPYING", "percent": 20, "message": f"Début du téléchargement de {total} fichiers...", "total": total}

        # --- Phase 4: Télécharger ---
        cancel_flag = Path('/tmp/pimmich_cancel_import.flag')
        downloaded = 0
        for i, (f, name) in enumerate(to_download, 1):
            if cancel_flag.exists():
                yield {"type": "warning", "message": "Import annulé par l'utilisateur."}
                break
            dest = TARGET_DIR / name
            try:
                with session.get(f"{DRIVE_API}/files/{f['id']}", params={"alt": "media", "supportsAllDrives": "true"}, stream=True, timeout=120) as resp:
                    resp.raise_for_status()
                    tmp = dest.with_name(dest.name + ".part")
                    with open(tmp, 'wb') as out:
                        for chunk in resp.iter_content(chunk_size=1024 * 1024):
                            out.write(chunk)
                    tmp.replace(dest)
                manifest[f["id"]] = {"name": name, "modifiedTime": f.get("modifiedTime")}
                downloaded += 1
            except Exception as e:
                yield {"type": "warning", "message": f"Impossible de télécharger {f['name']}: {e}"}

            percent = 20 + int((i / total) * 60)  # Le téléchargement représente 60% de la barre (de 20% à 80%)
            yield {
                "type": "progress", "stage": "COPYING", "percent": percent,
                "message": f"Téléchargement en cours... ({i}/{total})",
                "current": i, "total": total
            }

        with open(MANIFEST_FILE, 'w') as mf:
            json.dump(manifest, mf)

        yield {"type": "done", "stage": "IMPORT_COMPLETE", "percent": 80, "message": f"{downloaded} photos synchronisées depuis Google Drive.", "total_imported": downloaded}

    except ValueError as e:
        yield {"type": "error", "message": str(e)}
    except Exception as e:
        yield {"type": "error", "message": f"Erreur Google Drive : {str(e)}"}
