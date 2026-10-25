"""Livre photo de l'année (PDF prêt à imprimer) : années disponibles, création en arrière-plan, téléchargement."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from flask import send_file
from utils import photo_book

OUTPUT_DIR = BASE_DIR / "cache" / "photobook"
_job = {"running": False, "year": None, "done": 0, "total": 0, "error": None, "pages": 0}
_job_lock = threading.Lock()


def _output(year):
    return OUTPUT_DIR / f"livre_photo_{int(year)}.pdf"


def _build(year):
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
    favorites = photo_book.favorites_keys(load_favorites())
    for old in OUTPUT_DIR.glob("livre_photo_*.pdf") if OUTPUT_DIR.is_dir() else []:
        old.unlink(missing_ok=True)  # un seul livre gardé : ils sont lourds
    with app.app_context():
        return photo_book.build(index, year, _output(year), BASE_DIR, excluded=excluded, loved=loved, favorites=favorites,
                                progress=lambda done, total: _job.update(done=done, total=total), translate=_)


@app.route('/api/photobook', methods=['GET', 'POST'])
@login_required
def photobook_api():
    from utils import photo_index
    if request.method == 'GET':
        books = [{"year": int(p.stem.rsplit("_", 1)[-1]), "size": p.stat().st_size, "created": int(p.stat().st_mtime)}
                 for p in OUTPUT_DIR.glob("livre_photo_*.pdf")] if OUTPUT_DIR.is_dir() else []
        return jsonify({"success": True, "years": photo_book.years(photo_index.load()), "job": dict(_job), "books": books})
    try:
        year = int((request.get_json(silent=True) or {}).get("year"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": _("Année invalide.")}), 400
    with _job_lock:
        if _job["running"]:
            return jsonify({"success": False, "message": _("Un livre photo est déjà en cours de création.")}), 409
        _job.update(running=True, year=year, done=0, total=0, error=None, pages=0)

    def work():
        try:
            pages = _build(year)
            _job.update(pages=pages, error=None if pages else "empty")
        except Exception as e:
            logger.error(f"[Livre photo] {e}", exc_info=True)
            _job.update(error=str(e)[:200])
        finally:
            _job["running"] = False

    threading.Thread(target=work, daemon=True, name="photobook").start()
    return jsonify({"success": True, "message": _("Création du livre photo %(year)s : quelques minutes.", year=year)})


@app.route('/api/photobook/<year>.pdf')
@login_required
def photobook_download(year):
    if not year.isdigit():
        abort(404)
    path = _output(year)
    if not path.is_file():
        abort(404)
    return send_file(path, mimetype="application/pdf", as_attachment=True, download_name=f"{_('Livre photo')} {year}.pdf")
