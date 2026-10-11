"""
Musique selon l'heure : des plages horaires (« 7 h - 10 h : FIP, calme ; 18 h - 21 h : playlist festive »), chacune avec
une radio, une playlist Spotify ou une musique du cadre. Au début d'une plage, le cadre lance sa musique ; il ne
coupe jamais une musique lancée à la main, et n'arrête à la fin de la plage que ce qu'il a lui-même lancé.
"""
import re
from datetime import datetime
from pathlib import Path

KINDS = ("radio", "spotify", "file")
TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
MUSIC_DIR = Path(__file__).resolve().parent.parent / "static" / "music"


def clean_slots(slots):
    clean = []
    for slot in slots if isinstance(slots, list) else []:
        if not isinstance(slot, dict) or slot.get("kind") not in KINDS:
            continue
        start, end, value = str(slot.get("start", "")), str(slot.get("end", "")), str(slot.get("value", "")).strip()
        if not TIME.match(start) or not TIME.match(end) or start == end or not value:
            continue
        if slot["kind"] == "file" and (Path(value).name != value or not (MUSIC_DIR / value).is_file()):
            continue
        clean.append({"start": start, "end": end, "kind": slot["kind"], "value": value[:500], "label": str(slot.get("label", ""))[:80]})
    return clean[:12]


def _inside(slot, now):
    current = now.strftime("%H:%M")
    if slot["start"] < slot["end"]:
        return slot["start"] <= current < slot["end"]
    return current >= slot["start"] or current < slot["end"]  # plage qui passe minuit


def current(config, now=None):
    """Plage en cours (la première qui convient), ou None."""
    now = now or datetime.now()
    return next((s for s in clean_slots((config.get("music_schedule") or {}).get("slots")) if _inside(s, now)), None)


def key(slot, now=None):
    """Identifiant d'une plage pour la journée (une même plage n'est lancée qu'une fois par jour)."""
    now = now or datetime.now()
    return f"{now.date().isoformat()}|{slot['start']}|{slot['kind']}|{slot['value']}"


class Conductor:
    """Décide quoi lancer ou arrêter, minute après minute (l'état « qui a lancé quoi » est gardé ici)."""

    def __init__(self):
        self.started = None  # {"key", "source", "title"} : ce que la programmation a lancé

    def tick(self, config, playing, now=None):
        """`playing` : {"source", "title"} de ce qui joue (ou None). Renvoie ("start", plage) / ("stop", source) / None."""
        if not (config.get("music_schedule") or {}).get("enabled"):
            return None
        slot = current(config, now)
        ours = bool(self.started) and not self.started.get("manual")
        if ours and playing and (playing.get("source") != self.started["source"]
                                 or (self.started.get("title") and playing.get("title") != self.started["title"] and self.started["source"] == "radio")):
            self.started["manual"] = True  # quelqu'un a lancé autre chose : on n'y touche plus
            ours = False
        if slot is None:
            source = self.started["source"] if ours and playing and playing.get("source") == self.started["source"] else None
            self.started = None
            return ("stop", source) if source else None
        if self.started and self.started["key"] == key(slot, now):
            return None  # plage déjà lancée aujourd'hui
        if playing and not (ours and playing.get("source") == self.started["source"]):
            return None  # une musique lancée à la main joue : on la respecte
        return ("start", slot)

    def mark_started(self, slot, source, title, now=None):
        self.started = {"key": key(slot, now), "source": source, "title": title}
