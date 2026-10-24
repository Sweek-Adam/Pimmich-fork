"""
Albums partagés iCloud : le cadre suit un ou plusieurs albums partagés publics (lien « Site web public » de l'app
Photos), sans identifiant Apple. Photos et vidéos sont rangées dans la source « icloud », les légendes de l'album
deviennent les légendes des photos, et une photo retirée de l'album disparaît du cadre.
"""
import json
import re
import threading
from pathlib import Path

import requests

TARGET_DIR = Path("static/photos/icloud")
PREPARED_DIR = Path("static/prepared/icloud")
MANIFEST_FILE = TARGET_DIR / ".icloud_manifest.json"
CAPTIONS_FILE = Path("cache") / "icloud_captions.json"
CANCEL_FLAG = Path("/tmp/pimmich_cancel_import.flag")
TOKEN = re.compile(r"^[A-Za-z0-9]{10,40}$")
BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
HEADERS = {"Content-Type": "text/plain", "Origin": "https://www.icloud.com", "User-Agent": "Mozilla/5.0 Pimmich"}
TIMEOUT = 30
_sync_lock = threading.Lock()


def album_token(link):
    """Jeton d'un album partagé à partir de son lien (https://www.icloud.com/sharedalbum/#B0xxxx) ou du jeton seul."""
    link = str(link or "").strip()
    token = link.rsplit("#", 1)[-1].strip("/ ") if "#" in link else link.rstrip("/").rsplit("/", 1)[-1]
    if not TOKEN.match(token):
        raise ValueError("Lien d'album iCloud invalide : copiez le lien « Site web public » de l'album partagé.")
    return token


def _host(token):
    """Serveur iCloud de l'album (déduit du jeton ; iCloud redirige au besoin)."""
    digits = token[1] if token[0] == "A" else token[1:3]
    partition = 0
    for char in digits:
        partition = partition * 62 + BASE62.index(char)
    return f"p{partition:02d}-sharedstreams.icloud.com"


def _post(session, host, token, endpoint, payload):
    """Appel à l'API publique des albums partagés, en suivant la redirection vers le bon serveur (code 330)."""
    for _attempt in range(3):
        response = session.post(f"https://{host}/{token}/sharedstreams/{endpoint}", data=json.dumps(payload),
                                headers=HEADERS, timeout=TIMEOUT)
        if response.status_code == 330:
            host = (response.json() or {}).get("X-Apple-MMe-Host") or response.headers.get("X-Apple-MMe-Host") or host
            continue
        if response.status_code in (401, 403, 404):
            raise ValueError("Album introuvable : le lien public a peut-être été désactivé dans l'app Photos.")
        response.raise_for_status()
        return host, response.json()
    raise ValueError("iCloud ne répond pas comme prévu, réessayez plus tard.")


def _best(photo):
    """Meilleure version d'un élément : la plus grande image, ou la vidéo en meilleure qualité (pas l'affiche)."""
    video = str(photo.get("mediaAssetType", "")).lower() == "video"
    best = None
    for name, derivative in (photo.get("derivatives") or {}).items():
        if not isinstance(derivative, dict) or not derivative.get("checksum"):
            continue
        if video and name == "PosterFrame":
            continue
        size = int(derivative.get("fileSize") or 0) or int(derivative.get("width") or 0) * int(derivative.get("height") or 0)
        if best is None or size > best[0]:
            best = (size, derivative["checksum"])
    return (best[1], video) if best else (None, video)


def album(link, session=None):
    """Contenu d'un album partagé : {name, items: [{guid, checksum, video, caption, date, url}]}."""
    token = album_token(link)
    session = session or requests.Session()
    host, stream = _post(session, _host(token), token, "webstream", {"streamCtag": None})
    items = []
    for photo in stream.get("photos") or []:
        checksum, video = _best(photo)
        if photo.get("photoGuid") and checksum:
            items.append({"guid": str(photo["photoGuid"]), "checksum": checksum, "video": video,
                          "caption": str(photo.get("caption") or "").strip(), "date": photo.get("dateCreated", "")})
    urls = {}
    for start in range(0, len(items), 25):
        _ignored, data = _post(session, host, token, "webasseturls", {"photoGuids": [i["guid"] for i in items[start:start + 25]]})
        for checksum, where in (data.get("items") or {}).items():
            if where.get("url_location") and where.get("url_path"):
                urls[checksum] = f"https://{where['url_location']}{where['url_path']}"
    for item in items:
        item["url"] = urls.get(item["checksum"])
    return {"name": stream.get("streamName") or "iCloud", "token": token, "items": [i for i in items if i["url"]]}


def _filename(token, item):
    """Nom local stable d'un élément (même élément = même nom d'un import à l'autre)."""
    path = item["url"].split("?", 1)[0]
    ext = Path(path).suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".gif", ".heic", ".mp4", ".mov"):
        ext = ".mp4" if item["video"] else ".jpg"
    guid = re.sub(r"[^A-Za-z0-9]", "", item["guid"])[:24]
    return f"{token[:8]}_{guid}{ext}"


def _load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def captions():
    """Légendes des photos iCloud ({nom de fichier: légende}), utilisées à la préparation."""
    return _load_json(CAPTIONS_FILE, {})


def import_icloud_photos(config, session=None):
    """Synchronise les albums partagés choisis : nouveaux éléments téléchargés, éléments retirés supprimés."""
    if not _sync_lock.acquire(blocking=False):
        yield {"type": "error", "message": "Une synchronisation est déjà en cours, réessayez dans un instant."}
        return
    try:
        yield from _sync(config, session or requests.Session())
    finally:
        _sync_lock.release()


def _sync(config, session):
    links = [a.get("url") for a in config.get("icloud_albums") or [] if a.get("url")]
    if not links:
        yield {"type": "error", "message": "Aucun album partagé iCloud n'est configuré."}
        return
    yield {"type": "progress", "stage": "CONNECTING", "percent": 5, "message": "Lecture des albums partagés iCloud..."}
    wanted, failed = {}, False
    for link in links:
        try:
            content = album(link, session)
        except (ValueError, requests.RequestException) as e:
            failed = True
            yield {"type": "warning", "message": f"Album iCloud : {e}"}
            continue
        for item in content["items"]:
            wanted[_filename(content["token"], item)] = item
    if failed and not wanted:
        yield {"type": "error", "message": "Impossible de lire les albums partagés iCloud."}
        return

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    manifest = _load_json(MANIFEST_FILE, {})
    removed = 0
    if not failed:  # un album illisible ne doit pas vider le cadre
        for name in list(manifest):
            if name not in wanted:
                (TARGET_DIR / name).unlink(missing_ok=True)
                manifest.pop(name)
                removed += 1
    caption_map = captions()
    for name, item in wanted.items():
        if item["caption"]:
            caption_map[name] = item["caption"]
        else:
            caption_map.pop(name, None)
    caption_map = {k: v for k, v in caption_map.items() if k in wanted or k in manifest}
    _save_json(CAPTIONS_FILE, caption_map)

    missing = [name for name in wanted if not (TARGET_DIR / name).is_file()]
    total = len(missing)
    if total:
        yield {"type": "stats", "stage": "COPYING", "percent": 10, "message": f"Téléchargement de {total} éléments iCloud...", "total": total}
    added = 0
    for index, name in enumerate(missing, 1):
        if CANCEL_FLAG.exists():
            yield {"type": "warning", "message": "Import annulé par l'utilisateur."}
            break
        tmp = TARGET_DIR / f".{name}.part"
        try:
            with session.get(wanted[name]["url"], stream=True, timeout=TIMEOUT) as response:
                response.raise_for_status()
                with open(tmp, "wb") as out:
                    for chunk in response.iter_content(1 << 16):
                        out.write(chunk)
            tmp.replace(TARGET_DIR / name)
            manifest[name] = wanted[name]["guid"]
            added += 1
        except (OSError, requests.RequestException) as e:
            tmp.unlink(missing_ok=True)
            yield {"type": "warning", "message": f"Impossible de télécharger {name} : {e}"}
        yield {"type": "progress", "stage": "COPYING", "percent": 10 + int(index / total * 70),
               "message": f"Téléchargement... ({index}/{total})", "current": index, "total": total}
    for name in wanted:
        if name not in manifest and (TARGET_DIR / name).is_file():
            manifest[name] = wanted[name]["guid"]
    _save_json(MANIFEST_FILE, manifest)
    yield {"type": "done", "stage": "IMPORT_COMPLETE", "percent": 80, "changes": added + removed, "total_imported": added,
           "message": f"Albums iCloud synchronisés : {added} ajouts, {removed} retraits."}
