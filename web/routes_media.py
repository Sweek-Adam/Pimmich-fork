"""
Médias présents sur le cadre et leur préparation : inventaire par source (préparés ou non, échecs), bouton
« Préparer » pour rattraper un média resté de côté (ancien bug, import interrompu), détails de l'import en cours.
"""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from utils import import_progress
from utils import prepare_all_photos as prep

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
