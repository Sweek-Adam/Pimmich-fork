"""
Recherche dans la bibliothèque : texte (lieu, légende, nom de fichier), période, source, personne, favoris.
S'appuie sur l'index des photos (dates, lieux), les personnes d'Immich et les légendes saisies.
"""
import json
import unicodedata
from pathlib import Path

from utils import smart_albums

BASE_DIR = Path(__file__).resolve().parent.parent
TEXTS = BASE_DIR / "config" / "text_states.json"


def _fold(text):
    """Texte sans accents ni majuscules (« Été » trouve « ete »)."""
    return unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()


def _captions():
    try:
        return json.loads(TEXTS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def search(favorites=(), text="", start=None, end=None, source="", person="", only_favorites=False, media="", limit=300, smart=None):
    """
    Photos qui correspondent : (résultats, total), les plus récentes d'abord.
    `smart` : noms trouvés par la recherche par contenu d'Immich (utils/immich_search.py) ; les résultats suivent
    alors l'ordre de pertinence d'Immich et le texte n'est plus cherché dans les légendes.
    """
    from utils import immich_search
    captions = _captions()
    words = [w for w in _fold(text).split() if w]
    found = []
    for item in smart_albums.library(favorites):
        if source and item["source"] != source:
            continue
        if person and person not in item["people"]:
            continue
        if only_favorites and not item["favorite"]:
            continue
        if media == "photos" and item["video"] or media == "videos" and not item["video"]:
            continue
        day = (item["date"] or "")[:10]
        if (start or end) and not day:
            continue
        if start and day < start or end and day > end:
            continue
        if smart is not None:
            position = immich_search.rank(item["path"], smart)
            if position is None:
                continue
            found.append(dict(item, caption=captions.get(item["path"], ""), _rank=position))
            continue
        if words:
            haystack = _fold(" ".join([item["path"], item.get("place") or "", captions.get(item["path"], ""), " ".join(item["people"])]))
            if not all(w in haystack for w in words):
                continue
        found.append(dict(item, caption=captions.get(item["path"], "")))
    if smart is not None:
        found.sort(key=lambda i: i["_rank"])
    else:
        found.sort(key=lambda i: i["date"] or "", reverse=True)
    return found[:limit], len(found)
