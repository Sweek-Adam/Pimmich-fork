"""Diffusion sur une télé Chromecast (voir utils/chromecast.py) : télés du réseau, lancer et arrêter."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from utils import chromecast

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png")


def _base_url():
    from web.routes_home import _local_ip
    return f"http://{_local_ip()}"  # adresse IP : le Chromecast ne connaît pas toujours les noms en .local


def _slideshow_keys(config):
    keys = []
    for source in config.get("display_sources") or []:
        folder = PREPARED_DIR / source
        if source == "messages" or not folder.is_dir():
            continue
        keys += [f"{source}/{p.name}" for p in folder.iterdir()
                 if p.suffix.lower() in IMAGE_SUFFIXES and not p.stem.endswith(("_polaroid", "_postcard", "_thumbnail"))]
    return keys


@app.route('/api/chromecast', methods=['GET'])
@login_required
def chromecast_state_api():
    films = sorted(p.name for p in (PREPARED_DIR / "films").glob("film_*.mp4")) if (PREPARED_DIR / "films").is_dir() else []
    return jsonify({"success": True, "available": chromecast.available(), "running": chromecast.running(), "state": dict(chromecast.STATE),
                    "films": films})


@app.route('/api/chromecast/devices', methods=['GET'])
@login_required
def chromecast_devices_api():
    if not chromecast.available():
        return jsonify({"success": False, "message": _("Diffusion indisponible : lancez une fois ~/pimmich/venv/bin/pip install pychromecast")}), 409
    try:
        return jsonify({"success": True, "devices": chromecast.discover()})
    except Exception as e:
        return jsonify({"success": False, "message": _("Recherche impossible : %(error)s", error=str(e)[:200])}), 502


@app.route('/api/chromecast/start', methods=['POST'])
@login_required
def chromecast_start_api():
    data = request.get_json(silent=True) or {}
    device, mode = str(data.get("uuid") or ""), data.get("mode") or "photos"
    if not re.fullmatch(r"[0-9a-fA-F-]{32,36}", device) or not chromecast.available():
        return jsonify({"success": False, "message": _("Choisissez une télé.")}), 400
    config = load_config()
    if mode == "film":
        name = Path(str(data.get("film") or "")).name
        if not (PREPARED_DIR / "films" / name).is_file():
            return jsonify({"success": False, "message": _("Film introuvable.")}), 404
        from urllib.parse import quote
        items = [(f"{_base_url()}/static/prepared/films/{quote(name)}", "video/mp4", _("Film de l'année"))]
    else:
        items = chromecast.photo_items(_base_url(), _slideshow_keys(config))
        if not items:
            return jsonify({"success": False, "message": _("Aucune photo à diffuser.")}), 400
    chromecast.start(device, items, seconds=max(5, int(config.get("display_duration", 10) or 10)), mode=mode)
    return jsonify({"success": True, "message": _("Diffusion lancée sur la télé.")})


@app.route('/api/chromecast/stop', methods=['POST'])
@login_required
def chromecast_stop_api():
    chromecast.stop()
    return jsonify({"success": True, "message": _("Diffusion arrêtée.")})
