"""Livre photo de l'année et calendrier photo (PDF prêts à imprimer) : création en arrière-plan, téléchargement."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from flask import send_file
from utils import import_progress, photo_book

OUTPUT_DIR = BASE_DIR / "cache" / "photobook"
KINDS = {"book": "livre_photo", "calendar": "calendrier", "film": "film"}
EXTENSIONS = {"book": "pdf", "calendar": "pdf", "film": "mp4"}
FILM_SOURCE = "films"  # films ajoutés au diaporama
_job = {"running": False, "kind": None, "year": None, "done": 0, "total": 0, "error": None, "pages": 0}
_job_lock = threading.Lock()


def _output(kind, year):
    return OUTPUT_DIR / f"{KINDS[kind]}_{int(year)}.{EXTENSIONS[kind]}"


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


def _build(kind, year, music=None):
    config, index, choices = _choices()
    for old in OUTPUT_DIR.glob(f"{KINDS[kind]}_*.{EXTENSIONS[kind]}") if OUTPUT_DIR.is_dir() else []:
        old.unlink(missing_ok=True)  # un seul de chaque gardé : ils sont lourds
    progress = lambda done, total: _job.update(done=done, total=total)  # noqa: E731
    with app.app_context():
        if kind == "film":
            from utils import busy, year_film
            with busy.working(_("Film de l'année")):
                return year_film.build(index, year, _output(kind, year), BASE_DIR, music=music, progress=progress, translate=_, **choices)
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
            for p in OUTPUT_DIR.glob(f"{prefix}_*.{EXTENSIONS[kind]}") if OUTPUT_DIR.is_dir() else []:
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
    music = None
    if kind == "film" and data.get("music"):
        music = BASE_DIR / "static" / "music" / Path(str(data["music"])).name
        if not music.is_file():
            return jsonify({"success": False, "message": _("Musique introuvable.")}), 400
    with _job_lock:
        if _job["running"]:
            return jsonify({"success": False, "message": _("Un livre photo est déjà en cours de création.")}), 409
        _job.update(running=True, kind=kind, year=year, done=0, total=0, error=None, pages=0)

    def work():
        try:
            pages = _build(kind, year, music)
            _job.update(pages=pages, error=None if pages else "empty")
        except Exception as e:
            logger.error(f"[Livre photo] {e}", exc_info=True)
            _job.update(error=str(e)[:200])
        finally:
            _job["running"] = False

    threading.Thread(target=work, daemon=True, name="photobook").start()
    if kind == "calendar":
        return jsonify({"success": True, "message": _("Création du calendrier %(year)s : quelques minutes.", year=year)})
    if kind == "film":
        return jsonify({"success": True, "message": _("Montage du film %(year)s : une dizaine de minutes sur un Raspberry Pi.", year=year)})
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


@app.route('/api/photobook/film_<year>.mp4')
@login_required
def photobook_film_download(year):
    path = _output("film", year) if year.isdigit() else None
    if not path or not path.is_file():
        abort(404)
    return send_file(path, mimetype="video/mp4", as_attachment=request.args.get("download") == "1",
                     download_name=f"{_('Film')} {year}.mp4", conditional=True)


@app.route('/api/photobook/film_<year>/slideshow', methods=['POST'])
@login_required
def photobook_film_to_slideshow(year):
    """Ajoute le film de l'année au diaporama (source « films »), préparé comme une vidéo."""
    path = _output("film", year) if year.isdigit() else None
    if not path or not path.is_file():
        return jsonify({"success": False, "message": _("Film introuvable.")}), 404
    target = BASE_DIR / "static" / "photos" / FILM_SOURCE
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target / f"film_{int(year)}.mp4")
    config = load_config()
    if FILM_SOURCE not in config.get("display_sources", []):
        save_config(dict(config, display_sources=list(config.get("display_sources", [])) + [FILM_SOURCE]))

    def prepare():
        cfg = load_config()
        for _update in import_progress.tracked(FILM_SOURCE, "prepare", prepare_all_photos_with_progress(
                cfg.get("display_width", 1920), cfg.get("display_height", 1080), source_type=FILM_SOURCE)):
            pass
        if is_slideshow_running():
            restart_slideshow_for_update()
    threading.Thread(target=prepare, daemon=True, name="film-slideshow").start()
    return jsonify({"success": True, "message": _("Le film passera dans le diaporama dès qu'il sera préparé.")})
