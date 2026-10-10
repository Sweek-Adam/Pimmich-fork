"""Messages texte affichés comme des photos dans le diaporama."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
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
    return jsonify({"success": True, "messages": messages_manager.list_messages(),
                    "styles": {k: v["label"] for k, v in messages_manager.STYLES.items()}})


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
        message = messages_manager.create_message(data.get("title"), data.get("body"), data.get("signature"), data.get("style"),
                                                  data.get("expires"), session.get("username"), *_screen_size())
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400

    # Afficher la source « messages » dans le diaporama dès le premier message
    config = load_config()
    if messages_manager.SOURCE_NAME not in config.get("display_sources", []):
        config["display_sources"] = config.get("display_sources", []) + [messages_manager.SOURCE_NAME]
        save_config(config)
    logger.info(f"[Messages] Message {message['id']} publié par {message['author'] or '?'}")
    _refresh_slideshow()
    return jsonify({"success": True, "message": _("Message publié : il apparaîtra dans le diaporama."), "item": message})


@app.route('/api/messages/<message_id>', methods=['DELETE'])
@login_required
def delete_message_api(message_id):
    if not re.fullmatch(r"[0-9a-f]{12}", message_id) or not messages_manager.delete_message(message_id):
        return jsonify({"success": False, "message": _("Message introuvable.")}), 404
    _refresh_slideshow()
    return jsonify({"success": True, "message": _("Message supprimé.")})
