"""
Médias présents sur le cadre et leur préparation : inventaire par source (préparés ou non, échecs), bouton
« Préparer » pour rattraper un média resté de côté (ancien bug, import interrompu), détails de l'import en cours.
"""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from utils import import_progress
from utils import prepare_all_photos as prep
import glob

_queued = set()  # (source, nom) déjà demandés : un double clic ne prépare pas deux fois
_queued_lock = threading.Lock()


def _sources():
    photos = BASE_DIR / "static" / "photos"
    return sorted(d.name for d in photos.iterdir() if d.is_dir() and not d.name.startswith(".")) if photos.is_dir() else []


def _labels():
    from web.routes_settings import source_choices
    labels = {key: label for key, label in source_choices()}
    labels.update({k: _(v) for k, v in import_progress.SOURCE_LABELS.items() if k not in labels})
    return labels


def _screen():
    config = load_config()
    return int(config.get("display_width", 1920)), int(config.get("display_height", 1080))


@app.route('/api/media/inventory')
@login_required
def media_inventory_api():
    width, height = _screen()
    labels = _labels()
    with _queued_lock:
        queued = set(_queued)
    sources = []
    for source in _sources():
        items = prep.media_inventory(source, width, height)
        for item in items:
            item["queued"] = (source, item["name"]) in queued
        if items:
            sources.append({"source": source, "label": labels.get(source, source), "items": items,
                            "total": len(items), "prepared": sum(1 for i in items if i["state"] == "ok")})
    return jsonify({"success": True, "sources": sources, "screen": [width, height]})


def _prepare_selected(source, names, width, height):
    """Prépare les médias demandés (les plus légers d'abord), avec les mêmes événements qu'un import."""
    folder = BASE_DIR / "static" / "photos" / source
    names = sorted(names, key=lambda n: (folder / n).stat().st_size if (folder / n).exists() else 0)
    total = len(names)
    yield {"type": "stats", "message": f"{total} média(s) à préparer", "total": total, "current": 0}
    for index, name in enumerate(names, start=1):
        try:
            prep.prepare_media(source, name, width, height, index=index, total=total)
            yield {"type": "progress", "message": f"{name} préparé", "current": index, "total": total}
        except Exception as e:
            yield {"type": "warning", "message": f"{name} : {e}", "current": index, "total": total}
        finally:
            with _queued_lock:
                _queued.discard((source, name))
    yield {"type": "done", "message": "Préparation terminée"}


@app.route('/api/media/prepare', methods=['POST'])
@login_required
def media_prepare_api():
    data = request.get_json(silent=True) or {}
    source, names = data.get("source"), data.get("names") or []
    if source not in _sources() or not isinstance(names, list):
        return jsonify({"success": False, "message": _("Source inconnue.")}), 400
    folder = BASE_DIR / "static" / "photos" / source
    wanted = []
    with _queued_lock:
        for name in names:
            if not isinstance(name, str) or Path(name).name != name or not prep.is_media(name) or not (folder / name).is_file():
                continue
            if (source, name) not in _queued:
                _queued.add((source, name))
                wanted.append(name)
    if not wanted:
        return jsonify({"success": False, "message": _("Rien à préparer (déjà en cours ou introuvable).")}), 400
    width, height = _screen()

    def work():
        for _event in import_progress.tracked(source, "prepare", _prepare_selected(source, wanted, width, height)):
            pass
        if is_slideshow_running():
            restart_slideshow_for_update()

    threading.Thread(target=work, daemon=True, name=f"prepare-{source}").start()
    return jsonify({"success": True, "message": _("%(count)s média(s) en préparation : suivez l'avancement ci-dessous.", count=len(wanted))})


@app.route('/api/media/delete_failed', methods=['POST'])
@login_required
def media_delete_failed_api():
    """Supprime des médias en échec (fichier illisible, vidéo abîmée…) : seulement ceux qui ont échoué et ne sont pas prêts."""
    data = request.get_json(silent=True) or {}
    source, names = data.get("source"), data.get("names") or []
    if source not in _sources() or not isinstance(names, list):
        return jsonify({"success": False, "message": _("Source inconnue.")}), 400
    width, height = _screen()
    failed = {i["name"] for i in prep.media_inventory(source, width, height) if i["state"] != "ok" and i["error"]}
    folder = BASE_DIR / "static" / "photos" / source
    removed = 0
    for name in names:
        if not isinstance(name, str) or name not in failed:
            continue  # jamais un média prêt, ni un nom qui ne vient pas de l'inventaire
        try:
            (folder / name).unlink(missing_ok=True)
            for leftover in (PREPARED_DIR / source).glob(f"{glob.escape(Path(name).stem)}.*") if (PREPARED_DIR / source).is_dir() else []:
                leftover.unlink(missing_ok=True)  # préparation incomplète
            prep.forget_error(source, name)
            removed += 1
        except OSError as e:
            logger.warning(f"Suppression de {source}/{name} impossible : {e}")
    if not removed:
        return jsonify({"success": False, "message": _("Aucun média en échec à supprimer.")}), 400
    return jsonify({"success": True, "message": _("%(count)s média(s) en échec supprimé(s).", count=removed)})


# --- Gagner de la place : originaux énormes remplacés par une version réduite ---

@app.route('/api/media/space')
@login_required
def media_space_api():
    from utils import space_saver
    width, height = _screen()
    labels = _labels()
    items = space_saver.candidates(width, height)
    for item in items:
        item["label"] = labels.get(item["source"], item["source"])
    return jsonify({"success": True, "items": items, "gain": sum(i["gain"] for i in items), **space_saver.summary()})


@app.route('/api/media/reduce', methods=['POST'])
@login_required
def media_reduce_api():
    from utils import night_work, space_saver
    data = request.get_json(silent=True) or {}
    width, height = _screen()
    allowed = {(c["source"], c["name"]) for c in space_saver.candidates(width, height)}
    items = [(i.get("source"), i.get("name")) for i in data.get("items") or [] if isinstance(i, dict)]
    items = [i for i in items if i in allowed]  # seulement des candidats (préparés, assez gros) : rien d'autre n'est touché
    if not items:
        return jsonify({"success": False, "message": _("Aucun média à réduire.")}), 400
    night = not night_work.active_now(load_config())
    result = space_saver.request(items, now_ok_for_videos=night)
    if result["videos_now"]:
        threading.Thread(target=space_saver.run_videos, args=(result["videos_now"],), daemon=True, name="reduce-videos").start()
    parts = []
    if result["photos"]:
        parts.append(_("%(count)s photo(s) réduite(s) : %(size)s Mo gagnés.", count=result["photos"], size=round(result["saved"] / 1048576)))
    if result["videos_now"]:
        parts.append(_("%(count)s vidéo(s) en cours de réduction.", count=len(result["videos_now"])))
    if result["videos_later"]:
        parts.append(_("%(count)s vidéo(s) réduite(s) cette nuit, quand le cadre sera éteint.", count=result["videos_later"]))
    if result["errors"]:
        parts.append(_("Échecs : %(list)s", list="; ".join(result["errors"][:3])))
    return jsonify({"success": not result["errors"] or bool(result["photos"] or result["videos_now"] or result["videos_later"]),
                    "message": " ".join(parts)})


# --- Photos animées des téléphones (Samsung, Google, Live Photos) ---

_motion_running = threading.Event()


@app.route('/api/media/motion', methods=['GET', 'POST'])
@login_required
def media_motion_api():
    from utils import motion_photos
    width, height = _screen()
    config = load_config()
    clips = int(config.get("short_videos_max_seconds", motion_photos.CLIP_MAX_DEFAULT)) if config.get("short_videos_in_layouts", True) else 0
    if request.method == 'GET':
        return jsonify({"success": True, "pending": len(motion_photos.pending(width, height, clip_max_seconds=clips)), "running": _motion_running.is_set(),
                        "enabled": config.get("motion_photos_enabled", True) or bool(clips)})
    if _motion_running.is_set():
        return jsonify({"success": False, "message": _("Les animations sont déjà en cours de création.")}), 409
    todo = motion_photos.pending(width, height, clip_max_seconds=clips)
    if not todo:
        return jsonify({"success": False, "message": _("Aucune photo animée en attente.")}), 400

    def work():
        _motion_running.set()
        try:
            motion_photos.run(todo)
            if is_slideshow_running():
                restart_slideshow_for_update()
        finally:
            _motion_running.clear()

    threading.Thread(target=work, daemon=True, name="motion-photos").start()
    return jsonify({"success": True, "message": _("%(count)s animation(s) en cours de création.", count=len(todo))})
