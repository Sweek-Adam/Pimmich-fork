"""
Travaux lourds réservés à la nuit (heures où le diaporama est éteint) :
  - grosses vidéos : pendant la journée, les imports ne préparent que les photos et les petites vidéos ; les vidéos
    de plus de `video_night_above_mb` Mo attendent la nuit (réglage `heavy_videos_at_night`) ;
  - médias en échec : une nouvelle tentative chaque nuit, puis une notification s'il en reste.
Le bouton « Préparer » de l'inventaire agit toujours tout de suite (choix explicite).
"""
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

HEAVY_DEFAULT_MB = 50
STATE_FILE = Path("cache") / "night_work.json"


def active_now(config, now=None):
    """Vrai si l'heure actuelle est dans la plage d'affichage du diaporama (semaine / week-end).
    Heure pas encore synchronisée (démarrage sans Internet) : toujours vrai, pour ne pas rester éteint par erreur."""
    if now is None:
        from utils import clock_sync
        if not clock_sync.trusted():
            return True
    now = now or datetime.now()
    if now.weekday() >= 5:
        start_str = config.get("active_start_weekend", config.get("active_start", "07:00"))
        end_str = config.get("active_end_weekend", config.get("active_end", "23:00"))
    else:
        start_str = config.get("active_start_weekday", config.get("active_start", "07:00"))
        end_str = config.get("active_end_weekday", config.get("active_end", "22:00"))
    try:
        start_t = datetime.strptime(start_str, "%H:%M").time()
        end_t = datetime.strptime(end_str, "%H:%M").time()
    except (TypeError, ValueError):
        return True
    now_t = now.time()
    return (start_t <= now_t <= end_t) if start_t <= end_t else (now_t >= start_t or now_t <= end_t)


def heavy_limit(config):
    """Poids (octets) à partir duquel une vidéo attend la nuit ; None si le réglage est désactivé."""
    if not config.get("heavy_videos_at_night", True):
        return None
    try:
        return max(0.0, float(config.get("video_night_above_mb", HEAVY_DEFAULT_MB))) * 1024 * 1024
    except (TypeError, ValueError):
        return HEAVY_DEFAULT_MB * 1024 * 1024


def is_heavy(path, config):
    from utils.prepare_all_photos import is_video
    limit = heavy_limit(config)
    if limit is None or not is_video(str(path)):
        return False
    try:
        return os.path.getsize(path) >= limit
    except OSError:
        return False


def heavy_allowed(config, now=None):
    """Les grosses vidéos peuvent-elles être préparées maintenant ? (la nuit, ou réglage désactivé)"""
    return heavy_limit(config) is None or not active_now(config, now)


def night_key(now=None):
    """La nuit en cours, nommée par sa date de début (après minuit : la veille)."""
    now = now or datetime.now()
    return (now - timedelta(hours=12)).date().isoformat()


def _sources():
    root = Path("static") / "photos"
    return sorted(d.name for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")) if root.is_dir() else []


def pending(config, width, height):
    """Ce qui attend la nuit : (grosses vidéos non préparées, médias en échec), en [(source, nom)] du plus léger au plus lourd."""
    from utils import prepare_all_photos as prep
    heavy, failed = [], []
    errors = prep.preparation_errors()
    for source in _sources():
        for item in prep.media_inventory(source, width, height):
            if item["state"] == "ok":
                continue
            path = Path("static") / "photos" / source / item["name"]
            if f"{source}/{item['name']}" in errors:
                failed.append((item["size"], source, item["name"]))
            elif is_heavy(path, config):
                heavy.append((item["size"], source, item["name"]))
    return [(s, n) for _size, s, n in sorted(heavy)], [(s, n) for _size, s, n in sorted(failed)]


def _state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(state):
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state), encoding="utf-8")
        os.replace(tmp, STATE_FILE)
    except OSError:
        pass


def _prepare_group(items, width, height, prepare, still_night):
    """Prépare des médias, source par source, avec le suivi habituel (bandeau et page Préparation)."""
    from utils import import_progress
    by_source = {}
    for source, name in items:
        by_source.setdefault(source, []).append(name)
    for source, names in by_source.items():
        def events(names=names, source=source):
            yield {"type": "stats", "message": f"{len(names)} média(s) préparé(s) cette nuit", "total": len(names), "current": 0}
            for index, name in enumerate(names, start=1):
                if not still_night():
                    yield {"type": "info", "message": "Le cadre se rallume : la suite attendra la nuit prochaine"}
                    break
                try:
                    prepare(source, name, width, height, index=index, total=len(names))
                    yield {"type": "progress", "message": f"{name} préparé", "current": index, "total": len(names)}
                except Exception as e:
                    yield {"type": "warning", "message": f"{name} : {e}", "current": index, "total": len(names)}
            yield {"type": "done", "message": "Préparation de nuit terminée"}
        for _event in import_progress.tracked(source, "prepare", events()):
            pass


def run_once(config, width, height, now=None, prepare=None, notify=None, still_night=None):
    """
    Un passage du travail de nuit. Retourne ce qui a été fait : {"heavy": n, "retried": n, "notified": [...]}.
    `prepare` / `notify` / `still_night` : remplaçables pour les tests.
    """
    from utils import prepare_all_photos as prep
    prepare = prepare or prep.prepare_media
    still_night = still_night or (lambda: heavy_allowed(config) if heavy_limit(config) is not None else not active_now(config))
    done = {"heavy": 0, "retried": 0, "notified": []}
    night = not active_now(config, now)
    heavy, failed = pending(config, width, height)
    if heavy and heavy_allowed(config, now):
        _prepare_group(heavy, width, height, prepare, still_night)
        done["heavy"] = len(heavy)
    # Photos animées des téléphones : leur animation (courte vidéo extraite de la photo)
    if night and (config.get("motion_photos_enabled", True) or config.get("short_videos_in_layouts", True)):
        from utils import motion_photos
        clips = int(config.get("short_videos_max_seconds", motion_photos.CLIP_MAX_DEFAULT)) if config.get("short_videos_in_layouts", True) else 0
        todo = motion_photos.pending(width, height, clip_max_seconds=clips)
        if todo:
            done["motion"] = motion_photos.run(todo, still_night)
    # Vidéos à réduire (Gagner de la place), demandées pendant la journée
    from utils import space_saver
    waiting = space_saver.queued()
    if night and waiting:
        done["reduced"] = space_saver.run_videos(waiting, still_night)
    state = _state()
    key = night_key(now)
    if night and failed and state.get("retried") != key:
        state["retried"] = key
        _save_state(state)
        _prepare_group(failed, width, height, prepare, still_night)
        done["retried"] = len(failed)
        _heavy, failed = pending(config, width, height)
        if failed and notify and state.get("notified") != key:
            notify(failed)
            state["notified"] = key
            _save_state(state)
            done["notified"] = failed
    return done
