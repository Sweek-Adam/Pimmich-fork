"""Messages texte affichés comme des photos dans le diaporama."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from flask_babel import format_datetime
import io
from flask import send_file
from utils import messages_manager


def _screen_size():
    config = load_config()
    return int(config.get("display_width", 1920)), int(config.get("display_height", 1080))


def _refresh_slideshow():
    if is_slideshow_running():
        restart_slideshow_for_update()


@app.route('/api/messages', methods=['GET'])
@login_required
def list_messages_api():
    messages = [dict(m, on_air=messages_manager.on_air(m)) for m in messages_manager.list_messages()]
    translate = _  # libellés marqués N_() dans message_renderer (alias : pybabel ne doit pas extraire « label »)
    return jsonify({"success": True, "messages": messages,
                    "styles": {k: translate(v["label"]) for k, v in messages_manager.STYLES.items()}})


@app.route('/api/messages/preview', methods=['POST'])
@login_required
def preview_message_api():
    data = request.get_json(silent=True) or {}
    try:
        image = messages_manager.preview(data.get("title"), data.get("body"), data.get("signature"), data.get("style"), *_screen_size())
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=80)
    buffer.seek(0)
    return send_file(buffer, mimetype="image/jpeg")


@app.route('/api/messages', methods=['POST'])
@login_required
def create_message_api():
    data = request.get_json(silent=True) or {}
    try:
        schedule = messages_manager.validate_schedule(data.get("starts"), data.get("repeat"), data.get("duration_hours"))
        message = messages_manager.create_message(data.get("title"), data.get("body"), data.get("signature"), data.get("style"),
                                                  data.get("expires"), session.get("username"), *_screen_size(), schedule=schedule)
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400

    # Afficher la source « messages » dans le diaporama dès le premier message
    config = load_config()
    if messages_manager.SOURCE_NAME not in config.get("display_sources", []):
        config["display_sources"] = config.get("display_sources", []) + [messages_manager.SOURCE_NAME]
        save_config(config)
    logger.info(f"[Messages] Message {message['id']} publié par {message['author'] or '?'}")
    from web.routes_history import log
    log("message", _("Message « %(text)s »", text=(message.get("title") or message.get("body") or "")[:60]), {"type": "delete_message", "data": message["id"]})
    _refresh_slideshow()
    if message.get("schedule") and not messages_manager.on_air(message):
        return jsonify({"success": True, "message": _("Message programmé : il apparaîtra à l'heure prévue."), "item": message})
    return jsonify({"success": True, "message": _("Message publié : il apparaîtra dans le diaporama."), "item": message})


def deleted_label(message):
    """Texte de l'historique pour un message supprimé : sa nature (dessin, message vocal, message), son auteur et sa date."""
    message = message or {}
    kind = message.get("kind")
    who = (message.get("signature") or "").strip()
    if kind == "drawing":
        what = _("Dessin de %(who)s", who=who) if who else _("Dessin")
    elif kind == "voice":
        what = _("Message vocal de %(who)s", who=who) if who else _("Message vocal")
    else:
        text = (message.get("title") or message.get("body") or "").strip()
        what = _("Message « %(text)s »", text=text[:60]) if text else _("Message")
    created = str(message.get("created") or "")
    try:
        when = format_datetime(datetime.strptime(created, "%Y-%m-%d %H:%M"), "short")
    except ValueError:
        when = ""
    return _("%(what)s du %(date)s supprimé", what=what, date=when) if when else _("%(what)s supprimé", what=what)


@app.route('/api/messages/<message_id>', methods=['DELETE'])
@login_required
def delete_message_api(message_id):
    removed = next((m for m in messages_manager.list_messages() if m["id"] == message_id), None)
    if not re.fullmatch(r"[0-9a-f]{12}", message_id) or not messages_manager.delete_message(message_id):
        return jsonify({"success": False, "message": _("Message introuvable.")}), 404
    from web.routes_history import log
    log("message", deleted_label(removed), {"type": "restore_message", "data": removed} if removed and removed.get("kind") not in ("drawing", "voice") else None)
    _refresh_slideshow()
    return jsonify({"success": True, "message": _("Message supprimé.")})


@app.route('/api/messages/<message_id>/expires', methods=['POST'])
@login_required
def set_message_expires_api(message_id):
    data = request.get_json(silent=True) or {}
    try:
        message = messages_manager.set_expires(message_id, data.get("expires"))
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    return jsonify({"success": True, "message": _("Date de fin enregistrée."), "item": message})


@app.route('/api/messages/<message_id>/visibility', methods=['POST'])
@login_required
def set_message_visibility_api(message_id):
    data = request.get_json(silent=True) or {}
    try:
        message = messages_manager.set_hidden(message_id, data.get("hidden", True))
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 404
    _refresh_slideshow()
    text = _("Message masqué : il n'est plus affiché.") if message["hidden"] else _("Message de nouveau affiché.")
    return jsonify({"success": True, "message": text, "item": message})
