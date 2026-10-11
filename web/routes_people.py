"""Personnes (reconnaissance de visages d'Immich) : liste, photos de chacun, playlist « Photos de … »."""
from flask import send_file

from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from utils import import_progress, people

PLAYLIST_PREFIX = "person-"


def run_people_refresh(config=None):
    """Met à jour les personnes depuis Immich, prépare les photos importées des personnes suivies."""
    config = config or load_config()
    result = people.refresh(config)
    if result.get("downloaded"):
        if people.SOURCE not in config.get("display_sources", []):
            config = dict(config, display_sources=list(config.get("display_sources", [])) + [people.SOURCE])
            save_config(config)
        for _update in import_progress.tracked(people.SOURCE, "prepare", prepare_all_photos_with_progress(
                config.get("display_width", 1920), config.get("display_height", 1080), source_type=people.SOURCE)):
            pass
        people.reindex()
        if is_slideshow_running():
            restart_slideshow_for_update()
    _sync_playlists()
    return result


def _sync_playlists():
    """Met à jour les playlists « Photos de … » déjà créées (nouvelles photos, photos disparues)."""
    index = people.load()
    playlists = load_playlists()
    changed = False
    for playlist in playlists:
        person_id = str(playlist.get("id", ""))[len(PLAYLIST_PREFIX):] if str(playlist.get("id", "")).startswith(PLAYLIST_PREFIX) else None
        if person_id and person_id in index and playlist.get("photos") != index[person_id]["files"]:
            playlist["photos"] = index[person_id]["files"]
            changed = True
    if changed:
        save_playlists(playlists)


def person_playlist(person_id):
    """Crée ou met à jour la playlist de la personne ; renvoie son identifiant (None si personne inconnue)."""
    person = people.load().get(person_id)
    if not person:
        return None
    playlist_id = f"{PLAYLIST_PREFIX}{person_id}"
    playlists = load_playlists()
    playlist = next((p for p in playlists if p.get("id") == playlist_id), None)
    if playlist is None:
        playlist = {"id": playlist_id, "name": _("Photos de %(name)s", name=person["name"]), "music_file": None}
        playlists.append(playlist)
    playlist["photos"] = person["files"]
    save_playlists(playlists)
    return playlist_id


@app.route('/api/people', methods=['GET'])
@login_required
def people_api():
    config = load_config()
    followed = set(config.get("people_followed") or [])
    playlists = {p.get("id") for p in load_playlists()}
    items = [{"id": pid, "name": p["name"], "count": p.get("count", 0), "on_frame": len(p.get("files", [])),
              "followed": pid in followed, "playlist": f"{PLAYLIST_PREFIX}{pid}" in playlists,
              "thumb": url_for("people_thumbnail_api", person_id=pid)}
             for pid, p in people.load().items()]
    items.sort(key=lambda p: (-p["on_frame"], p["name"].lower()))
    return jsonify({"success": True, "configured": bool(config.get("immich_url") and config.get("immich_token")), "people": items})


@app.route('/api/people/<person_id>/thumbnail', methods=['GET'])
@login_required
def people_thumbnail_api(person_id):
    path = people.THUMBS_DIR / f"{re.sub(r'[^A-Za-z0-9-]', '', person_id)}.jpg"
    if not path.is_file():
        abort(404)
    return send_file(path, mimetype="image/jpeg", max_age=86400)


@app.route('/api/people/refresh', methods=['POST'])
@login_required
def people_refresh_api():
    config = load_config()
    if not (config.get("immich_url") and config.get("immich_token")):
        return jsonify({"success": False, "message": _("Configurez d'abord Immich (adresse et clé API).")}), 400
    try:
        result = run_people_refresh(config)
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": _("Immich ne répond pas : %(error)s", error=str(e)[:200])}), 502
    return jsonify({"success": True, "message": _("%(count)s personne(s) trouvée(s) dans Immich.", count=result["people"])})


@app.route('/api/people/<person_id>/follow', methods=['POST'])
@login_required
def people_follow_api(person_id):
    if person_id not in people.load():
        return jsonify({"success": False, "message": _("Personne inconnue.")}), 404
    follow = bool((request.get_json(silent=True) or {}).get("follow"))
    config = dict(load_config())
    followed = [p for p in config.get("people_followed") or [] if p != person_id] + ([person_id] if follow else [])
    config["people_followed"] = followed
    save_config(config)
    threading.Thread(target=run_people_refresh, args=(config,), daemon=True).start()
    return jsonify({"success": True, "message": _("Import de toutes ses photos depuis Immich lancé.") if follow
                    else _("Ses photos importées seront retirées du cadre.")})


@app.route('/api/people/<person_id>/play', methods=['POST'])
@login_required
def people_play_api(person_id):
    """« Montre-moi les photos de Léo » : crée sa playlist et la lance sur le cadre."""
    from web.routes_slideshow import start_photo_playlist
    playlist_id = person_playlist(person_id)
    if playlist_id is None:
        return jsonify({"success": False, "message": _("Personne inconnue.")}), 404
    if (request.get_json(silent=True) or {}).get("create_only"):
        return jsonify({"success": True, "playlist": playlist_id, "message": _("Playlist créée : elle se met à jour toute seule.")})
    ok, message, status = start_photo_playlist(playlist_id)
    if not ok and status == 400:
        message = _("Aucune photo de cette personne sur le cadre pour l'instant : suivez-la pour importer ses photos.")
    return jsonify({"success": ok, "message": message, "playlist": playlist_id}), status


import_progress.ON_FINISHED.append(people.reindex)  # photos fraîchement préparées : rattachées aux personnes
