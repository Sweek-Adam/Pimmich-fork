"""
« Votre semaine sur le cadre » : le dimanche soir, une diapositive résume les sept derniers jours (photos reçues et
leurs expéditeurs, messages, cœurs envoyés depuis les téléphones), avec quelques-unes des nouvelles photos.
"""
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

WEEK = 7 * 24 * 3600
START_HOUR = 17          # le dimanche, à partir de 17 h
MIN_PHOTOS = 3           # en dessous, pas de résumé (semaine calme)
NOT_COUNTED = {"messages"}


def showing(now=None):
    """Vrai pendant la plage du résumé (dimanche soir)."""
    now = now or datetime.now()
    return now.weekday() == 6 and now.hour >= START_HOUR


def collect(photos_dir, prepared_dir, messages, reactions_recent, prepared_name, is_media, now=None, since=None):
    """Chiffres de la semaine (ou de `since` à `now`) : {photos, by_source (Counter), messages, hearts, new_prepared, loved}."""
    now = now or time.time()
    since = now - WEEK if since is None else since
    by_source, new_prepared = Counter(), []
    for folder in Path(photos_dir).iterdir() if Path(photos_dir).is_dir() else []:
        if not folder.is_dir() or folder.name in NOT_COUNTED or folder.name.startswith("."):
            continue
        for path in folder.iterdir():
            try:
                if not path.is_file() or not is_media(path.name) or not since <= path.stat().st_mtime < now:
                    continue
            except OSError:
                continue
            by_source[folder.name] += 1
            prepared = Path(prepared_dir) / folder.name / prepared_name(path.name)
            if prepared.suffix.lower() in (".jpg", ".jpeg", ".png") and prepared.exists():
                new_prepared.append(str(prepared))
    week_messages = 0
    for message in messages:
        try:
            if since <= time.mktime(time.strptime(message.get("created", ""), "%Y-%m-%d %H:%M")) < now:
                week_messages += 1
        except ValueError:
            pass
    hearts = [r for r in reactions_recent if since <= float(r.get("at") or 0) < now]
    loved = Counter(r.get("photo") for r in hearts).most_common()
    return {"photos": sum(by_source.values()), "by_source": by_source, "messages": week_messages, "hearts": len(hearts),
            "new_prepared": new_prepared, "loved": [p for p, _n in loved if p]}


def pick_photos(stats, static_dir, count=5, rng=None):
    """Photos de la diapositive : les plus aimées de la semaine d'abord, puis des nouvelles photos au hasard."""
    import random
    rng = rng or random.Random()
    new = list(stats["new_prepared"])
    chosen = [str(Path(static_dir) / p) for p in stats["loved"] if str(Path(static_dir) / p) in new][:count]
    rest = [p for p in new if p not in chosen]
    rng.shuffle(rest)
    return (chosen + rest)[:count]
