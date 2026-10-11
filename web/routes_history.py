"""Historique des actions (qui a fait quoi, ce qui a été affiché) et annulation de la dernière action."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from utils import history, messages_manager


def log(kind, text, undo=None, merge=False, who=None):
    """Note une action de la personne connectée (ou `who`)."""
    try:
        return history.record(kind, text, who if who is not None else (session.get("username") or ""), undo, merge)
    except Exception as e:
        logger.debug(f"[Historique] {e}")


# --- Annulations ---

def _restore_config(data):
    if isinstance(data, dict) and data:
        save_config(data)
        restart_slideshow_process()


def _delete_playlist(data):
    save_playlists([p for p in load_playlists() if p.get("id") != data])


def _restore_playlist(data):
    playlists = load_playlists()
    if isinstance(data, dict) and data.get("id") and not any(p.get("id") == data["id"] for p in playlists):
        playlists.append(data)
        save_playlists(playlists)


def _delete_message(data):
    messages_manager.delete_message(str(data))
    if is_slideshow_running():
        restart_slideshow_for_update()


def _restore_message(data):
    if not isinstance(data, dict) or not data.get("id") or data.get("kind") in ("drawing", "voice"):
        raise ValueError("Ce message ne peut pas être restauré.")
    with messages_manager._lock:
        messages = messages_manager._load()
        if not any(m["id"] == data["id"] for m in messages):
            messages.append(data)
            messages_manager._save(messages)
    config = load_config()
    messages_manager.ensure_images(int(config.get("display_width", 1920)), int(config.get("display_height", 1080)))
    if is_slideshow_running():
        restart_slideshow_for_update()


history.UNDO_HANDLERS.update(restore_config=_restore_config, delete_playlist=_delete_playlist, restore_playlist=_restore_playlist,
                             delete_message=_delete_message, restore_message=_restore_message)


@app.route('/api/history', methods=['GET'])
@login_required
def history_api():
    items = []
    for entry in history.recently_displayed(30):
        rel = str(entry["path"])
        if rel.startswith(("prepared/", "compositions/")):
            items.append({"thumb": url_for("static", filename=rel), "at": entry["at"]})
    last = history.last_undoable()
    return jsonify({"success": True, "events": history.events(60), "displayed": items, "undo": last["text"] if last else None})


@app.route('/api/history/undo', methods=['POST'])
@login_required
def history_undo_api():
    try:
        event = history.undo_last(session.get("username"))
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    if event is None:
        return jsonify({"success": False, "message": _("Rien à annuler.")}), 404
    return jsonify({"success": True, "message": _("Annulé : %(action)s", action=event["text"])})


@app.route('/api/tour/done', methods=['POST'])
@login_required
def tour_done_api():
    """La visite guidée ne se relance plus d'elle-même pour ce compte (elle reste dans le menu du compte)."""
    config = dict(load_config())
    seen = list(config.get("tour_seen_users") or [])
    if (session.get("username") or "") not in seen:
        config["tour_seen_users"] = (seen + [session.get("username") or ""])[-50:]
        save_config(config)
    return jsonify({"success": True})
