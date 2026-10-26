"""
Statistiques des photos : les plus vues, les plus aimées, la répartition par source, les affichages par jour.
Les affichages notés en mémoire vive par le diaporama sont additionnés ici toutes les 30 minutes
(une écriture sur la carte SD par demi-heure, au lieu d'une par photo).
"""
import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from utils import history

BASE_DIR = Path(__file__).resolve().parent.parent
STORE = BASE_DIR / "cache" / "view_counts.json"
PREPARED_DIR = BASE_DIR / "static" / "prepared"
SKIP = {"messages", "compositions", "citation", "voyages", "voyages_recits"}


def _load():
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"photos": {}, "days": {}, "until": 0}


def collect():
    """Ajoute aux compteurs les affichages notés depuis la dernière fois ; renvoie le nombre ajouté."""
    data = _load()
    since = data.get("until", 0)
    fresh = [e for e in reversed(history.recently_displayed(history.MAX_DISPLAYED)) if e.get("at", 0) > since]
    if not fresh:
        return 0
    for entry in fresh:
        path = str(entry["path"])
        if not path.startswith("prepared/") or "/messages/" in path:
            continue
        rel = path[len("prepared/"):]
        data["photos"][rel] = data["photos"].get(rel, 0) + 1
        day = datetime.fromtimestamp(entry["at"]).date().isoformat()
        data["days"][day] = data["days"].get(day, 0) + 1
    data["until"] = max(e["at"] for e in fresh)
    cutoff = (date.today() - timedelta(days=400)).isoformat()
    data["days"] = {d: n for d, n in data["days"].items() if d >= cutoff}
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(STORE)
    return len(fresh)


def sources():
    """Répartition par source : {source: {"photos", "videos", "bytes"}}."""
    found = {}
    for folder in sorted(PREPARED_DIR.iterdir()) if PREPARED_DIR.is_dir() else []:
        if not folder.is_dir() or folder.name in SKIP or folder.name.startswith("."):
            continue
        photos = videos = size = 0
        for f in folder.iterdir():
            if f.stem.endswith(("_polaroid", "_postcard", "_thumbnail")):
                continue
            if f.suffix.lower() == ".jpg":
                photos += 1
            elif f.suffix.lower() == ".mp4":
                videos += 1
            else:
                continue
            try:
                size += f.stat().st_size
            except OSError:
                pass
        if photos or videos:
            found[folder.name] = {"photos": photos, "videos": videos, "bytes": size}
    return found


def summary(days=14):
    data = _load()
    existing = lambda rel: (PREPARED_DIR / rel).exists()
    top = sorted(((p, n) for p, n in data["photos"].items() if existing(p)), key=lambda x: -x[1])[:20]
    today = date.today()
    per_day = [{"day": (today - timedelta(days=k)).isoformat(), "views": data["days"].get((today - timedelta(days=k)).isoformat(), 0)}
               for k in range(days - 1, -1, -1)]
    by_source = sources()
    return {"top": top, "per_day": per_day, "sources": by_source, "total_views": sum(data["photos"].values()),
            "viewed": len([p for p in data["photos"] if existing(p)]), "updated": data.get("until") or None}


def forgotten_extra(relative_paths, boost=2, counts=None):
    """Photos oubliées : passages en plus dans la liste du diaporama ({chemin relatif: n}). Une photo jamais montrée
    reçoit `boost` passages de plus, une photo parmi le quart le moins vu en reçoit un ; les autres rien."""
    if boost <= 0:
        return {}
    counts = counts if counts is not None else _load().get("photos", {})
    views = {rel: counts.get(rel, 0) for rel in relative_paths}
    if not views:
        return {}
    ordered = sorted(views.values())
    quarter = ordered[len(ordered) // 4]
    extra = {}
    for rel, seen in views.items():
        if seen == 0:
            extra[rel] = boost
        elif seen <= quarter and quarter < ordered[-1]:
            extra[rel] = max(1, boost // 2)
    return extra
