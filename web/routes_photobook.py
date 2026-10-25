"""Livre photo de l'année et calendrier photo (PDF prêts à imprimer) : création en arrière-plan, téléchargement."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from flask import send_file
from utils import photo_book

OUTPUT_DIR = BASE_DIR / "cache" / "photobook"
KINDS = {"book": "livre_photo", "calendar": "calendrier"}
_job = {"running": False, "kind": None, "year": None, "done": 0, "total": 0, "error": None, "pages": 0}
_job_lock = threading.Lock()


def _output(kind, year):
    return OUTPUT_DIR / f"{KINDS[kind]}_{int(year)}.pdf"


def _choices():
    """Ce qui guide le choix des photos : photos écartées par le tri, cœurs reçus, favorites."""
    from utils import photo_index, photo_quality, reactions
    from utils.dedup import hashes_for
    config = load_config()
    index = photo_index.load()
    hashes = None
    if config.get("filter_bursts", True):
        paths = [str(PREPARED_DIR / key) for key in index]
        hashes = {photo_index.key_for(p): h for p, h in hashes_for(paths).items() if h is not None}
    excluded = photo_quality.excluded(index, dict(config, auto_filter_enabled=True), hashes)
    loved = photo_book.loved_by_key(photo_book.load_json(reactions.STORE, {}))
    return config, index, dict(excluded=excluded, loved=loved, favorites=photo_book.favorites_keys(load_favorites()))


def _build(kind, year):
    config, index, choices = _choices()
    for old in OUTPUT_DIR.glob(f"{KINDS[kind]}_*.pdf") if OUTPUT_DIR.is_dir() else []:
        old.unlink(missing_ok=True)  # un seul de chaque gardé : ils sont lourds
    progress = lambda done, total: _job.update(done=done, total=total)  # noqa: E731
    with app.app_context():
        if kind == "calendar":
            from utils import photo_calendar
            return photo_calendar.build(index, config, year, _output(kind, year), BASE_DIR, progress=progress, translate=_, **choices)
        return photo_book.build(index, year, _output(kind, year), BASE_DIR, progress=progress, translate=_, **choices)


@app.route('/api/photobook', methods=['GET', 'POST'])
@login_required
def photobook_api():
    from utils import photo_index
    if request.method == 'GET':
        books = []
        for kind, prefix in KINDS.items():
            for p in OUTPUT_DIR.glob(f"{prefix}_*.pdf") if OUTPUT_DIR.is_dir() else []:
                books.append({"kind": kind, "year": int(p.stem.rsplit("_", 1)[-1]), "size": p.stat().st_size, "created": int(p.stat().st_mtime)})
        return jsonify({"success": True, "years": photo_book.years(photo_index.load()), "job": dict(_job), "books": books,
                        "calendar_year": datetime.now().year + (1 if datetime.now().month >= 9 else 0)})
    data = request.get_json(silent=True) or {}
    kind = data.get("kind") or "book"
    try:
        year = int(data.get("year"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": _("Année invalide.")}), 400
    if kind not in KINDS or not 1900 < year < 2200:
        return jsonify({"success": False, "message": _("Année invalide.")}), 400
    with _job_lock:
        if _job["running"]:
            return jsonify({"success": False, "message": _("Un livre photo est déjà en cours de création.")}), 409
        _job.update(running=True, kind=kind, year=year, done=0, total=0, error=None, pages=0)

    def work():
        try:
            pages = _build(kind, year)
            _job.update(pages=pages, error=None if pages else "empty")
        except Exception as e:
            logger.error(f"[Livre photo] {e}", exc_info=True)
            _job.update(error=str(e)[:200])
        finally:
            _job["running"] = False

    threading.Thread(target=work, daemon=True, name="photobook").start()
    if kind == "calendar":
        return jsonify({"success": True, "message": _("Création du calendrier %(year)s : quelques minutes.", year=year)})
    return jsonify({"success": True, "message": _("Création du livre photo %(year)s : quelques minutes.", year=year)})


@app.route('/api/photobook/<name>.pdf')
@login_required
def photobook_download(name):
    kind, _sep, year = name.rpartition("_")
    kind = kind or "book"
    if kind not in KINDS or not year.isdigit():
        abort(404)
    path = _output(kind, year)
    if not path.is_file():
        abort(404)
    label = _("Calendrier") if kind == "calendar" else _("Livre photo")
    return send_file(path, mimetype="application/pdf", as_attachment=True, download_name=f"{label} {year}.pdf")
