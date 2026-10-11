"""
Personnes : « montre-moi les photos de Léo », grâce à la reconnaissance de visages d'Immich.

Le cadre lit les personnes nommées dans Immich et la liste de leurs photos, puis retrouve ces photos parmi celles
qu'il affiche déjà (source « immich », par le nom de fichier d'origine). Pour une personne suivie, il peut aussi
importer toutes ses photos (source « personnes »). Chaque personne a sa playlist « Photos de … », que la
détection de présence peut lancer à son arrivée.
"""
import json
import re
import threading
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_FILE = BASE_DIR / "cache" / "people.json"
THUMBS_DIR = BASE_DIR / "cache" / "people"
PREPARED_DIR = BASE_DIR / "static" / "prepared"
PEOPLE_DIR = BASE_DIR / "static" / "photos" / "personnes"
SOURCE = "personnes"
MAX_IMPORT = 300  # photos importées au plus par personne suivie
TIMEOUT = 30
_lock = threading.Lock()


def _api(config):
    url = str(config.get("immich_url") or "").rstrip("/")
    token = config.get("immich_token")
    if not url or not token:
        raise ValueError("Immich n'est pas configuré (adresse et clé API).")
    return url, {"x-api-key": token, "Accept": "application/json"}


def people(config, session=None):
    """Personnes nommées dans Immich : [{id, name}] (les visages sans nom et masqués sont ignorés)."""
    session = session or requests
    url, headers = _api(config)
    response = session.get(f"{url}/api/people", params={"withHidden": "false", "size": 500}, headers=headers, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()
    found = data.get("people", data) if isinstance(data, dict) else data
    return [{"id": str(p["id"]), "name": str(p["name"]).strip()} for p in found or []
            if p.get("id") and str(p.get("name") or "").strip() and not p.get("isHidden")]


def person_assets(config, person_id, session=None, limit=5000):
    """Photos et vidéos d'une personne : [{id, name, video}]."""
    session = session or requests
    url, headers = _api(config)
    assets, page = [], 1
    while page and len(assets) < limit:
        response = session.post(f"{url}/api/search/metadata", json={"personIds": [person_id], "page": page, "size": 250},
                                headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        block = (response.json() or {}).get("assets") or {}
        for item in block.get("items") or []:
            if item.get("id") and item.get("originalFileName"):
                assets.append({"id": str(item["id"]), "name": str(item["originalFileName"]), "video": item.get("type") == "VIDEO"})
        page = int(block["nextPage"]) if str(block.get("nextPage") or "").isdigit() else None
    return assets


def _local_name(asset):
    """Nom des photos importées pour une personne : identifiant Immich + nom d'origine (pas de collision)."""
    stem = re.sub(r"[^A-Za-z0-9_-]", "_", Path(asset["name"]).stem)[:60]
    return f"{asset['id'][:8]}_{stem}{Path(asset['name']).suffix.lower()}"


def _prepared_stems():
    """{source: {nom sans extension: chemin relatif}} des photos et vidéos préparées des sources Immich."""
    found = {}
    for source in ("immich", SOURCE):
        folder = PREPARED_DIR / source
        stems = {}
        for f in folder.iterdir() if folder.is_dir() else []:
            if f.suffix.lower() in (".jpg", ".mp4") and not f.stem.endswith(("_polaroid", "_postcard", "_thumbnail")):
                stems[f.stem] = f"{source}/{f.name}"
        found[source] = stems
    return found


def load():
    try:
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(index):
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = INDEX_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(INDEX_FILE)


def by_photo(index=None):
    """{chemin relatif: [prénoms]} : qui apparaît sur chaque photo du cadre."""
    found = {}
    for person in (index if index is not None else load()).values():
        for path in person.get("files", []):
            found.setdefault(path, []).append(person["name"])
    return found


def _thumbnail(config, person_id, session):
    url, headers = _api(config)
    try:
        response = session.get(f"{url}/api/people/{person_id}/thumbnail", headers=dict(headers, Accept="image/*"), timeout=TIMEOUT)
        if response.status_code == 200 and response.content:
            THUMBS_DIR.mkdir(parents=True, exist_ok=True)
            (THUMBS_DIR / f"{re.sub(r'[^A-Za-z0-9-]', '', person_id)}.jpg").write_bytes(response.content)
    except requests.RequestException:
        pass


def _download(config, asset, session):
    """Télécharge l'original d'une photo d'une personne suivie (sans rien écraser)."""
    url, headers = _api(config)
    target = PEOPLE_DIR / _local_name(asset)
    if target.is_file():
        return False
    PEOPLE_DIR.mkdir(parents=True, exist_ok=True)
    part = target.with_name(f".{target.name}.part")
    with session.get(f"{url}/api/assets/{asset['id']}/original", headers=dict(headers, Accept="*/*"), stream=True, timeout=TIMEOUT) as r:
        r.raise_for_status()
        with open(part, "wb") as out:
            for chunk in r.iter_content(1 << 16):
                out.write(chunk)
    part.replace(target)
    return True


def refresh(config, session=None):
    """Met à jour les personnes et leurs photos ; renvoie {"people": n, "downloaded": n}."""
    if not _lock.acquire(blocking=False):
        return {"people": len(load()), "downloaded": 0, "busy": True}
    try:
        return _refresh(config, session or requests.Session())
    finally:
        _lock.release()


def _refresh(config, session):
    followed = set(config.get("people_followed") or [])
    old = load()
    index, downloaded, keep = {}, 0, set()
    for person in people(config, session):
        assets = person_assets(config, person["id"], session)
        if person["id"] in followed:
            for asset in assets[:MAX_IMPORT]:
                keep.add(_local_name(asset))
                try:
                    downloaded += _download(config, asset, session)
                except (OSError, requests.RequestException):
                    continue
        index[person["id"]] = {"name": person["name"], "count": len(assets), "assets": [[a["id"], a["name"]] for a in assets]}
        if person["id"] not in old or not (THUMBS_DIR / f"{person['id']}.jpg").is_file():
            _thumbnail(config, person["id"], session)
    # Personnes plus suivies : leurs photos importées disparaissent
    for f in PEOPLE_DIR.iterdir() if PEOPLE_DIR.is_dir() else []:
        if f.is_file() and not f.name.startswith(".") and f.name not in keep:
            f.unlink()
    _match(index)
    _save(index)
    return {"people": len(index), "downloaded": downloaded}


def _match(index):
    """Retrouve sur le cadre les photos de chaque personne (par le nom de fichier d'origine)."""
    stems = _prepared_stems()
    for person in index.values():
        files = set()
        for asset_id, name in person.get("assets", []):
            path = stems["immich"].get(Path(name).stem) or stems[SOURCE].get(Path(_local_name({"id": asset_id, "name": name})).stem)
            if path:
                files.add(path)
        person["files"] = sorted(files)
    return index


def reindex():
    """Après une préparation : rattache les photos fraîchement préparées aux personnes (sans appeler Immich)."""
    index = load()
    if index:
        _save(_match(index))
    return index
