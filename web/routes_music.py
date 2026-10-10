"""Musique : enceinte Bluetooth, compte Spotify (association du cadre, pilotage et musiques associées)."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
import secrets

import requests

from utils import ambiances, bluetooth_control, music_remote, now_playing, spotify
from utils.message_renderer import N_
from utils.playlist_manager import load_playlists
from web.routes_home import SOURCE_LABELS, _service_active, _tr


# --- Bluetooth ---

@app.route('/api/bluetooth', methods=['GET'])
@login_required
def bluetooth_status_api():
    state = bluetooth_control.status()
    state["service"] = _service_active("pimmich-bluetooth")
    return jsonify({"success": True, **state})


@app.route('/api/bluetooth/pair', methods=['POST'])
@login_required
def bluetooth_pair_api():
    if not _service_active("pimmich-bluetooth"):
        return jsonify({"success": False, "message": _("L'enceinte Bluetooth n'est pas installée.")}), 400
    if not bluetooth_control.open_pairing():
        return jsonify({"success": False, "message": _("Impossible de rendre le cadre visible en Bluetooth.")}), 500
    return jsonify({"success": True, "seconds": bluetooth_control.PAIRING_SECONDS,
                    "message": _("Le cadre est visible pendant 3 minutes : choisissez « Cadre photo » dans les réglages Bluetooth du téléphone.")})


@app.route('/api/bluetooth/forget', methods=['POST'])
@login_required
def bluetooth_forget_api():
    mac = (request.get_json(silent=True) or {}).get("mac", "")
    try:
        removed = bluetooth_control.forget(mac)
    except ValueError:
        return jsonify({"success": False, "message": _("Appareil inconnu.")}), 400
    return jsonify({"success": removed, "message": _("Appareil oublié.") if removed else _("Impossible d'oublier cet appareil.")})


# --- Spotify ---

SPOTIFY_ERRORS = {
    "not_connected": N_("Spotify n'est pas connecté."),
    "expired": N_("La connexion à Spotify a expiré : reconnectez-vous."),
    "no_device": N_("Le cadre n'apparaît pas dans votre compte Spotify : associez-le d'abord (étape 1)."),
    "premium": N_("Spotify refuse la lecture : un compte Premium est nécessaire."),
    "invalid_uri": N_("Playlist Spotify invalide."),
    "invalid_action": N_("Commande inconnue."),
}


def _spotify_error(e, status=400):
    message = SPOTIFY_ERRORS.get(str(e))
    return jsonify({"success": False, "message": _tr(message) if message else str(e)}), status


def _redirect_uri():
    """Adresse de retour à déclarer dans l'application Spotify (HTTPS obligatoire)."""
    return url_for("spotify_callback", _external=True, _scheme="https")


def spotify_links(config=None):
    links = (config or load_config()).get("spotify_links") or {}
    return links if isinstance(links, dict) else {}


@app.route('/api/spotify', methods=['GET'])
@login_required
def spotify_status_api():
    config = load_config()
    return jsonify({"success": True, **spotify.link_status(), "client_id": config.get("spotify_client_id", ""),
                    "connected": spotify.connected(), "redirect_uri": _redirect_uri(), "links": spotify_links(config),
                    "ambiances": [{"key": k, "label": _tr(a["label"])} for k, a in ambiances.AMBIANCES.items()],
                    "photo_playlists": [{"id": p.get("id"), "name": p.get("name", "")} for p in load_playlists() if p.get("id")]})


@app.route('/api/spotify/link', methods=['POST'])
@login_required
def spotify_link_api():
    """Étape 1 : associer le cadre au compte (code à saisir sur spotify.com/pair)."""
    try:
        return jsonify({"success": True, **spotify.start_link()})
    except spotify.SpotifyError as e:
        return _spotify_error(e, 500)


@app.route('/api/spotify/unlink', methods=['POST'])
@login_required
def spotify_unlink_api():
    spotify.unlink()
    return jsonify({"success": True, "message": _("Le cadre n'est plus associé à ce compte Spotify.")})


@app.route('/api/spotify/client_id', methods=['POST'])
@login_required
def spotify_client_id_api():
    client_id = ((request.get_json(silent=True) or {}).get("client_id") or "").strip().lower()
    if not spotify.CLIENT_ID.match(client_id):
        return jsonify({"success": False, "message": _("Identifiant client invalide (32 caractères, chiffres et lettres a à f).")}), 400
    config = dict(load_config())
    config["spotify_client_id"] = client_id
    save_config(config)
    return jsonify({"success": True, "message": _("Identifiant enregistré : vous pouvez vous connecter.")})


@app.route('/spotify/login')
@login_required
def spotify_login():
    """Étape 2 : connexion à l'API Spotify (OAuth avec PKCE)."""
    client_id = load_config().get("spotify_client_id", "")
    if not spotify.CLIENT_ID.match(client_id):
        flash(_("Saisissez d'abord l'identifiant client de votre application Spotify."), "error")
        return redirect(url_for("configure") + "#tab-son")
    verifier, challenge = spotify.pkce_pair()
    state = secrets.token_urlsafe(24)
    session["spotify_oauth"] = {"state": state, "verifier": verifier, "redirect_uri": _redirect_uri()}
    return redirect(spotify.authorize_url(client_id, _redirect_uri(), state, challenge))


@app.route('/spotify/callback')
@login_required
def spotify_callback():
    pending = session.pop("spotify_oauth", None) or {}
    if not pending or request.args.get("state") != pending.get("state"):
        flash(_("Connexion Spotify refusée (demande expirée) : recommencez."), "error")
    elif request.args.get("error") or not request.args.get("code"):
        flash(_("Connexion Spotify annulée."), "error")
    else:
        try:
            spotify.exchange_code(load_config().get("spotify_client_id", ""), request.args["code"], pending["redirect_uri"], pending["verifier"])
            flash(_("Spotify est connecté."), "success")
        except (spotify.SpotifyError, requests.RequestException) as e:
            logger.warning(f"[Spotify] Connexion impossible : {e}")
            flash(_("Connexion Spotify impossible : vérifiez l'identifiant client et l'adresse de retour."), "error")
    return redirect(url_for("configure") + "#tab-son")


@app.route('/api/spotify/disconnect', methods=['POST'])
@login_required
def spotify_disconnect_api():
    spotify.disconnect()
    return jsonify({"success": True, "message": _("Spotify est déconnecté de l'interface.")})


@app.route('/api/spotify/playlists', methods=['GET'])
@login_required
def spotify_playlists_api():
    try:
        return jsonify({"success": True, "playlists": spotify.playlists()})
    except spotify.SpotifyError as e:
        return _spotify_error(e)
    except requests.RequestException:
        return jsonify({"success": False, "message": _("Spotify ne répond pas : vérifiez la connexion internet du cadre.")}), 502


@app.route('/api/spotify/play', methods=['POST'])
@login_required
def spotify_play_api():
    data = request.get_json(silent=True) or {}
    try:
        spotify.play_on_frame(data.get("uri", ""), shuffle=bool(data.get("shuffle", True)))
    except spotify.SpotifyError as e:
        return _spotify_error(e)
    except requests.RequestException:
        return jsonify({"success": False, "message": _("Spotify ne répond pas : vérifiez la connexion internet du cadre.")}), 502
    return jsonify({"success": True, "message": _("Lecture lancée sur le cadre.")})


@app.route('/api/spotify/control', methods=['POST'])
@login_required
def spotify_control_api():
    try:
        spotify.control((request.get_json(silent=True) or {}).get("action", ""))
    except spotify.SpotifyError as e:
        return _spotify_error(e)
    except requests.RequestException:
        return jsonify({"success": False, "message": _("Spotify ne répond pas : vérifiez la connexion internet du cadre.")}), 502
    return jsonify({"success": True})


@app.route('/api/spotify/links', methods=['POST'])
@login_required
def spotify_links_api():
    """Associe une playlist Spotify à une ambiance ou à une playlist de photos (vide : aucune)."""
    data = request.get_json(silent=True) or {}
    key, uri = data.get("key", ""), (data.get("uri") or "").strip()
    kind, _sep, ident = key.partition(":")
    valid_target = (kind == "ambiance" and ident in ambiances.AMBIANCES) or \
                   (kind == "playlist" and any(p.get("id") == ident for p in load_playlists()))
    if not valid_target or (uri and not spotify.URI.match(uri)):
        return jsonify({"success": False, "message": _("Association invalide.")}), 400
    config = dict(load_config())
    links = dict(spotify_links(config))
    if uri:
        links[key] = uri
    else:
        links.pop(key, None)
    config["spotify_links"] = links
    save_config(config)
    return jsonify({"success": True, "message": _("Musique associée enregistrée.")})


# --- Télécommande (toutes sources) ---

REMOTE_ERRORS = dict(SPOTIFY_ERRORS, unsupported=N_("Cette source ne peut pas être commandée d'ici."),
                     unreachable=N_("Le lecteur ne répond pas."))


def _remote_track():
    return now_playing.latest(exclude=() if is_slideshow_running() else ("pimmich",))


@app.route('/api/music/remote', methods=['GET'])
@login_required
def music_remote_api():
    """Morceau en cours ou en pause, commandes possibles et volume du cadre."""
    track = _remote_track()
    volume, muted = music_remote.get_volume()
    data = {"success": True, "volume": volume, "muted": muted, "track": None, "actions": []}
    if track:
        cover = track.get("cover")
        has_cover = bool(cover) and Path(cover).parent == now_playing.COVER_DIR and Path(cover).is_file()
        data["track"] = {"title": track.get("title", ""), "artist": track.get("artist", ""), "source": track["source"],
                         "source_label": _tr(SOURCE_LABELS.get(track["source"], track["source"])),
                         "playing": track.get("state") == "playing",
                         "cover": url_for("now_playing_cover", v=Path(cover).name) if has_cover else None}
        data["actions"] = music_remote.actions_for(track["source"])
        if not data["actions"]:
            data["hint"] = _("Pour commander Spotify d'ici, connectez-le (Écran > Son > Spotify, étape 2).") if track["source"] == "spotify" \
                else _("Commandez la lecture depuis le téléphone.")
    return jsonify(data)


@app.route('/api/music/remote', methods=['POST'])
@login_required
def music_remote_control_api():
    action = (request.get_json(silent=True) or {}).get("action", "")
    track = _remote_track()
    if not track:
        return jsonify({"success": False, "message": _("Aucune musique en cours.")}), 409
    error = music_remote.control(track["source"], action)
    if error:
        message = REMOTE_ERRORS.get(error)
        return jsonify({"success": False, "message": _tr(message) if message else error}), 400
    return jsonify({"success": True})


@app.route('/api/music/volume', methods=['POST'])
@login_required
def music_volume_api():
    try:
        volume = int((request.get_json(silent=True) or {}).get("volume"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": _("Volume invalide.")}), 400
    if not music_remote.set_volume(volume):
        return jsonify({"success": False, "message": _("Le son du cadre ne répond pas.")}), 500
    return jsonify({"success": True, "volume": max(0, min(100, volume))})
