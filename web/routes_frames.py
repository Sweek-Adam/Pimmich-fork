"""
Plusieurs cadres depuis une seule interface (ex. chez Mamie et chez soi). Chaque cadre peut :
- générer un code d'association (côté cadre piloté) ;
- enregistrer d'autres cadres avec leur adresse et leur code (côté cadre qui pilote), puis voir leur état et la photo
  affichée, les allumer ou les endormir, passer à la photo suivante, leur envoyer des photos ou un message.
Les échanges entre cadres passent par /api/frame/* avec le code (en-tête X-Pimmich-Frame-Token) : jamais la session.
"""
import hmac
import io
import os
import secrets
import signal
from functools import wraps

import requests
from flask import send_file

from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from utils import members, messages_manager

TOKEN_HEADER = "X-Pimmich-Frame-Token"
SHARED_SOURCE = "cadres"
TIMEOUT = 15


# --- Côté cadre piloté : code d'association et API protégée par ce code ---

def frame_token_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        given = request.headers.get(TOKEN_HEADER, "")
        tokens = [t.get("token", "") for t in load_config().get("frame_link_tokens") or []]
        if not given or not any(hmac.compare_digest(given, t) for t in tokens if t):
            return jsonify({"success": False, "message": "Code d'association invalide."}), 401
        return view(*args, **kwargs)
    return wrapper


@app.route('/api/frame/pairing', methods=['GET', 'POST', 'DELETE'])
@admin_required
def frame_pairing_api():
    """Code d'association de ce cadre (à saisir sur le cadre qui le pilotera)."""
    config = dict(load_config())
    tokens = list(config.get("frame_link_tokens") or [])
    if request.method == 'POST':
        label = str((request.get_json(silent=True) or {}).get("label") or "").strip()[:60] or _("Autre cadre")
        tokens.append({"token": secrets.token_urlsafe(24), "label": label})
        config["frame_link_tokens"] = tokens[-20:]
        save_config(config)
    elif request.method == 'DELETE':
        token = (request.get_json(silent=True) or {}).get("token")
        config["frame_link_tokens"] = [t for t in tokens if t.get("token") != token]
        save_config(config)
    return jsonify({"success": True, "codes": config.get("frame_link_tokens") or []})


@app.route('/api/frame/status', methods=['GET'])
@frame_token_required
def frame_status_api():
    config = load_config()
    try:
        photo = Path(CURRENT_PHOTO_FILE).read_text().strip()
    except OSError:
        photo = ""
    count = sum(1 for _p in PREPARED_DIR.glob("*/*.jpg")) if PREPARED_DIR.is_dir() else 0
    return jsonify({"success": True, "name": config.get("frame_name") or config.get("mqtt_device_name") or "Pimmich",
                    "running": is_slideshow_running(), "has_photo": bool(photo), "photos": count})


@app.route('/api/frame/current.jpg', methods=['GET'])
@frame_token_required
def frame_current_photo_api():
    """Photo affichée en ce moment (réduite)."""
    from PIL import Image
    try:
        path = BASE_DIR / "static" / Path(CURRENT_PHOTO_FILE).read_text().strip()
        with Image.open(path) as image:
            image = image.convert("RGB")
            image.thumbnail((640, 640))
            buffer = io.BytesIO()
            image.save(buffer, "JPEG", quality=80)
    except (OSError, ValueError):
        abort(404)
    buffer.seek(0)
    return send_file(buffer, mimetype="image/jpeg", max_age=0)


@app.route('/api/frame/command', methods=['POST'])
@frame_token_required
def frame_command_api():
    action = (request.get_json(silent=True) or {}).get("action")
    config = dict(load_config())
    if action == "next":
        try:
            os.kill(int(open("/tmp/pimmich_slideshow.pid").read()), signal.SIGUSR1)
        except (OSError, ValueError):
            return jsonify({"success": False, "message": _("Le diaporama n'est pas en cours.")}), 409
    elif action in ("on", "off"):
        config["manual_override"] = "start" if action == "on" else "stop"
        save_config(config)
        if action == "on" and not is_slideshow_running():
            set_display_power(on=True)
            start_slideshow()
        elif action == "off" and is_slideshow_running():
            stop_slideshow()
    else:
        return jsonify({"success": False, "message": _("Action inconnue.")}), 400
    return jsonify({"success": True})


@app.route('/api/frame/photos', methods=['POST'])
@frame_token_required
def frame_receive_photos_api():
    """Photos envoyées par un autre cadre de la famille : source « cadres », préparées en arrière-plan."""
    files = [f for f in request.files.getlist("photos") if f and f.filename]
    sender = members.slug(request.form.get("from") or "cadre")
    if not files:
        return jsonify({"success": False, "message": _("Aucun fichier sélectionné.")}), 400
    target = BASE_DIR / "static" / "photos" / SHARED_SOURCE
    target.mkdir(parents=True, exist_ok=True)
    for file in files:
        name = secure_filename(file.filename) or "photo.jpg"
        if Path(name).suffix.lower() not in (".jpg", ".jpeg", ".png", ".heic") + VIDEO_EXTENSIONS:
            continue
        file.save(members.unique_name(target, f"{sender}_{name}"))
    config = load_config()
    if SHARED_SOURCE not in config.get("display_sources", []):
        save_config(dict(config, display_sources=list(config.get("display_sources", [])) + [SHARED_SOURCE]))

    def prepare():
        cfg = load_config()
        for _update in prepare_all_photos_with_progress(cfg.get("display_width", 1920), cfg.get("display_height", 1080), source_type=SHARED_SOURCE):
            pass
        if is_slideshow_running():
            restart_slideshow_for_update()
    threading.Thread(target=prepare, daemon=True, name="frame-photos").start()
    return jsonify({"success": True, "message": _("%(count)s photo(s) reçue(s).", count=len(files))})


@app.route('/api/frame/message', methods=['POST'])
@frame_token_required
def frame_receive_message_api():
    data = request.get_json(silent=True) or {}
    config = load_config()
    try:
        messages_manager.create_message(data.get("title"), data.get("body"), data.get("signature"), data.get("style"), None,
                                        str(data.get("from") or "")[:60], int(config.get("display_width", 1920)), int(config.get("display_height", 1080)))
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    if messages_manager.SOURCE_NAME not in config.get("display_sources", []):
        save_config(dict(config, display_sources=list(config.get("display_sources", [])) + [messages_manager.SOURCE_NAME]))
    if is_slideshow_running():
        restart_slideshow_for_update()
    return jsonify({"success": True, "message": _("Message publié : il apparaîtra dans le diaporama.")})


# --- Côté cadre qui pilote : la liste des cadres de la famille ---

def _frames():
    return [f for f in load_config().get("family_frames") or [] if f.get("id") and f.get("url") and f.get("token")]


def _frame(frame_id):
    return next((f for f in _frames() if f["id"] == frame_id), None)


def _call(frame, method, path, **kwargs):
    """Requête vers un autre cadre (adresse Tailscale ou réseau local ; certificat du cadre auto-signé)."""
    url = frame["url"].rstrip("/") + path
    return requests.request(method, url, headers={TOKEN_HEADER: frame["token"]}, timeout=TIMEOUT, verify=False, **kwargs)


def _clean_url(url):
    url = str(url or "").strip().rstrip("/")
    if not re.match(r"^https?://[A-Za-z0-9.\-:\[\]]+(/.*)?$", url):
        return None
    return url


@app.route('/api/frames', methods=['GET'])
@admin_required
def frames_api():
    import urllib3
    urllib3.disable_warnings()
    items = []
    for frame in _frames():
        status = {"online": False}
        try:
            response = _call(frame, "GET", "/api/frame/status")
            if response.status_code == 200:
                status = dict(response.json(), online=True)
            elif response.status_code == 401:
                status = {"online": True, "unauthorized": True}
        except requests.RequestException:
            pass
        items.append({**status, "id": frame["id"], "name": frame.get("name") or status.get("name") or frame["url"], "url": frame["url"]})
    return jsonify({"success": True, "frames": items})


@app.route('/api/frames', methods=['POST'])
@admin_required
def frames_add_api():
    import urllib3
    urllib3.disable_warnings()
    data = request.get_json(silent=True) or {}
    url, token = _clean_url(data.get("url")), str(data.get("token") or "").strip()
    if not url or not token:
        return jsonify({"success": False, "message": _("Adresse ou code invalide.")}), 400
    frame = {"id": secrets.token_hex(4), "url": url, "token": token, "name": str(data.get("name") or "").strip()[:60]}
    try:
        response = _call(frame, "GET", "/api/frame/status")
    except requests.RequestException:
        return jsonify({"success": False, "message": _("Ce cadre ne répond pas : vérifiez son adresse (réseau local ou Tailscale).")}), 502
    if response.status_code != 200:
        return jsonify({"success": False, "message": _("Le code d'association est refusé par ce cadre.")}), 400
    frame["name"] = frame["name"] or response.json().get("name") or url
    config = dict(load_config())
    config["family_frames"] = (config.get("family_frames") or []) + [frame]
    save_config(config)
    return jsonify({"success": True, "message": _("Cadre « %(name)s » ajouté.", name=frame["name"])})


@app.route('/api/frames/<frame_id>', methods=['DELETE'])
@admin_required
def frames_remove_api(frame_id):
    config = dict(load_config())
    config["family_frames"] = [f for f in config.get("family_frames") or [] if f.get("id") != frame_id]
    save_config(config)
    return jsonify({"success": True, "message": _("Cadre retiré.")})


@app.route('/api/frames/<frame_id>/current.jpg', methods=['GET'])
@admin_required
def frames_current_photo_api(frame_id):
    import urllib3
    urllib3.disable_warnings()
    frame = _frame(frame_id)
    if not frame:
        abort(404)
    try:
        response = _call(frame, "GET", "/api/frame/current.jpg")
    except requests.RequestException:
        abort(502)
    if response.status_code != 200:
        abort(404)
    return send_file(io.BytesIO(response.content), mimetype="image/jpeg", max_age=0)


@app.route('/api/frames/<frame_id>/<action>', methods=['POST'])
@admin_required
def frames_action_api(frame_id, action):
    import urllib3
    urllib3.disable_warnings()
    frame = _frame(frame_id)
    if not frame:
        return jsonify({"success": False, "message": _("Cadre inconnu.")}), 404
    sender = load_config().get("frame_name") or session.get("username") or "Pimmich"
    try:
        if action in ("next", "on", "off"):
            response = _call(frame, "POST", "/api/frame/command", json={"action": action})
        elif action == "photos":
            files = [("photos", (f.filename, f.stream, f.mimetype)) for f in request.files.getlist("photos") if f and f.filename]
            if not files:
                return jsonify({"success": False, "message": _("Aucun fichier sélectionné.")}), 400
            response = _call(frame, "POST", "/api/frame/photos", files=files, data={"from": sender})
        elif action == "message":
            response = _call(frame, "POST", "/api/frame/message", json=dict(request.get_json(silent=True) or {}, **{"from": sender}))
        else:
            return jsonify({"success": False, "message": _("Action inconnue.")}), 400
    except requests.RequestException:
        return jsonify({"success": False, "message": _("Ce cadre ne répond pas.")}), 502
    try:
        result = response.json()
    except ValueError:
        result = {"success": response.ok}
    return jsonify({"success": bool(result.get("success")), "message": result.get("message") or (_("C'est fait.") if response.ok else _("Ce cadre a refusé la demande."))}), (200 if response.ok else 502)
