"""Albums intelligents : playlists définies par des règles, recalculées à chaque nouvelle photo."""
import secrets

from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from utils import import_progress, smart_albums


def _name(suggestion):
    translate = _
    event = suggestion["event"]
    if event == "christmas_all":
        return _("Noël en famille")
    if event == "place":
        return suggestion["place"]
    return f"{translate(smart_albums.EVENTS[event]['label'])} {suggestion['year']}"


def refresh_smart_albums():
    try:
        smart_albums.refresh(load_playlists, save_playlists, load_favorites())
    except Exception as e:
        logger.warning(f"[Albums intelligents] Mise à jour : {e}")


@app.route('/api/smart_albums', methods=['GET'])
@login_required
def smart_albums_api():
    items = smart_albums.library(load_favorites())
    playlists = load_playlists()
    names = {p.get("name", "").lower() for p in playlists}
    suggestions = []
    for suggestion in smart_albums.suggestions(items):
        name = _name(suggestion)
        if name.lower() not in names:
            suggestions.append({"name": name, "count": suggestion["count"], "icon": suggestion["icon"], "rules": suggestion["rules"]})
    translate = _
    return jsonify({"success": True, "suggestions": suggestions,
                    "albums": [{"id": p["id"], "name": p["name"], "rules": p["smart"], "count": len(p.get("photos", []))}
                               for p in playlists if isinstance(p.get("smart"), dict)],
                    "events": {k: {"label": translate(v["label"]), "from": v["from"], "to": v["to"]} for k, v in smart_albums.EVENTS.items()},
                    "people": sorted({n for i in items for n in i["people"]}),
                    "sources": sorted({i["source"] for i in items}),
                    "years": sorted({int(i["date"][:4]) for i in items if i["date"]}, reverse=True)})


@app.route('/api/smart_albums/preview', methods=['POST'])
@login_required
def smart_albums_preview_api():
    rules = smart_albums.clean_rules((request.get_json(silent=True) or {}).get("rules"))
    photos = smart_albums.select(smart_albums.library(load_favorites()), rules)
    thumbs = [p.rsplit(".", 1)[0] + "_thumbnail.jpg" if p.lower().endswith(smart_albums.VIDEO_EXT) else p for p in photos[-8:]]
    return jsonify({"success": True, "count": len(photos), "thumbs": [url_for("static", filename=f"prepared/{t}") for t in thumbs]})


@app.route('/api/smart_albums', methods=['POST'])
@login_required
def smart_albums_save_api():
    """Crée (ou modifie, avec un id) un album intelligent."""
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or "").strip()[:80]
    if not name:
        return jsonify({"success": False, "message": _("Donnez un nom à l'album.")}), 400
    rules = smart_albums.clean_rules(data.get("rules"))
    if not rules:
        return jsonify({"success": False, "message": _("Choisissez au moins un critère (période, personnes, lieu...).")}), 400
    playlists = load_playlists()
    album_id = str(data.get("id") or "")
    album = next((p for p in playlists if p.get("id") == album_id and isinstance(p.get("smart"), dict)), None) if album_id else None
    if any(p.get("name", "").lower() == name.lower() and p is not album for p in playlists):
        return jsonify({"success": False, "message": _("Une playlist porte déjà ce nom.")}), 409
    if album is not None and album.get("owner") and not is_admin() and album["owner"] != session.get("username"):
        return jsonify({"success": False, "message": _("Cette playlist appartient à %(owner)s.", owner=album["owner"])}), 403
    if album is None:
        album = {"id": f"{smart_albums.PREFIX}{secrets.token_hex(6)}", "music_file": None, "owner": session.get("username")}
        playlists.append(album)
    album.update(name=name, smart=rules, photos=smart_albums.select(smart_albums.library(load_favorites()), rules))
    save_playlists(playlists)
    return jsonify({"success": True, "id": album["id"], "count": len(album["photos"]),
                    "message": _("Album « %(name)s » : %(count)s photos, mis à jour automatiquement.", name=name, count=len(album["photos"]))})


def refresh_in_background():
    threading.Thread(target=refresh_smart_albums, daemon=True, name="smart-albums").start()


import_progress.ON_FINISHED.append(refresh_smart_albums)  # nouvelles photos préparées : albums à jour
ON_FAVORITES_CHANGED.append(refresh_in_background)  # albums « favoris »
