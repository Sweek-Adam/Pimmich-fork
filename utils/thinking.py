"""
« Je pense à toi » entre cadres jumelés : un appui (page Partage, mode grands-parents, touche bleue de la
télécommande) fait s'envoler des cœurs sur les autres cadres de la famille, avec « Mamie pense à vous ».
L'événement reçu est gardé en mémoire vive ; s'il arrive pendant la veille du cadre, il est montré au réveil (le jour même).
"""
import json
import time
from pathlib import Path

from utils.platform_info import tmp_path

EVENT_FILE = tmp_path("pimmich_thinking.json")
KEEP_SECONDS = 12 * 3600


def receive(name):
    Path(str(EVENT_FILE)).write_text(json.dumps({"name": str(name or "")[:40], "at": time.time()}, ensure_ascii=False))


def pending(since):
    """Événement arrivé après `since` (et pas trop vieux), sinon None."""
    try:
        event = json.loads(Path(str(EVENT_FILE)).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if event.get("at", 0) <= since or time.time() - event.get("at", 0) > KEEP_SECONDS:
        return None
    return event
