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


def _spotify_call(function, *args):
    """Appel à l'API Spotify avec les messages d'erreur de l'interface."""
    try:
        return function(*args), None
    except spotify.SpotifyError as e:
        return None, _spotify_error(e)
    except (requests.RequestException, ValueError, TypeError):
        return None, (jsonify({"success": False, "message": _("Spotify ne répond pas : vérifiez la connexion internet du cadre.")}), 502)


@app.route('/api/spotify/player', methods=['GET'])
@login_required
def spotify_player_api():
    """Lecture en cours sur le compte : titre, avancement, appareil, file d'attente."""
    state, error = _spotify_call(spotify.player_state)
    return error or jsonify({"success": True, **state})


@app.route('/api/spotify/player', methods=['POST'])
@login_required
def spotify_player_action_api():
    data = request.get_json(silent=True) or {}
    _result, error = _spotify_call(spotify.player_action, data.get("action", ""), data.get("value"))
    return error or jsonify({"success": True})


@app.route('/api/spotify/search', methods=['GET'])
@login_required
def spotify_search_api():
    results, error = _spotify_call(spotify.search, request.args.get("q", ""))
    return error or jsonify({"success": True, **results})


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


# --- Radios et podcasts ---

def _radio_favorites(config):
    return [f for f in config.get("radio_favorites") or [] if isinstance(f, dict) and f.get("url")]


@app.route('/api/radio', methods=['GET'])
@login_required
def radio_status_api():
    from utils import radio
    config = load_config()
    return jsonify({"success": True, "stations": radio.STATIONS, "favorites": _radio_favorites(config),
                    "podcasts": config.get("podcasts") or [], "playing": radio.playing()})


@app.route('/api/radio/search', methods=['GET'])
@login_required
def radio_search_api():
    from utils import radio
    try:
        return jsonify({"success": True, "stations": radio.search(request.args.get("q", ""))})
    except requests.RequestException:
        return jsonify({"success": False, "message": _("L'annuaire des radios ne répond pas.")}), 502


@app.route('/api/radio/play', methods=['POST'])
@login_required
def radio_play_api():
    from utils import radio
    data = request.get_json(silent=True) or {}
    try:
        radio.play(data.get("url", ""), (data.get("name") or "Radio").strip(), volume=load_config().get("music_volume", 80))
    except ValueError:
        return jsonify({"success": False, "message": _("Adresse de radio invalide.")}), 400
    except OSError:
        return jsonify({"success": False, "message": _("Lecteur audio (mpv) introuvable sur le cadre.")}), 500
    return jsonify({"success": True, "message": _("Radio lancée sur le cadre.")})


@app.route('/api/radio/stop', methods=['POST'])
@login_required
def radio_stop_api():
    from utils import radio
    radio.stop()
    return jsonify({"success": True, "message": _("Radio arrêtée.")})


@app.route('/api/radio/favorites', methods=['POST'])
@login_required
def radio_favorites_api():
    """Ajoute (ou retire, « remove ») une radio favorite."""
    from utils import radio
    data = request.get_json(silent=True) or {}
    url, name = data.get("url", ""), (data.get("name") or "").strip()[:80]
    if not radio._valid_url(url):
        return jsonify({"success": False, "message": _("Adresse de radio invalide.")}), 400
    config = dict(load_config())
    favorites = [f for f in _radio_favorites(config) if f["url"] != url]
    if not data.get("remove"):
        favorites.append({"name": name or url, "url": url})
    config["radio_favorites"] = favorites[:50]
    save_config(config)
    return jsonify({"success": True, "favorites": favorites})


@app.route('/api/podcasts', methods=['POST'])
@login_required
def podcasts_api():
    """Ajoute un podcast (flux RSS vérifié) ou en retire un (« remove »)."""
    from utils import radio
    data = request.get_json(silent=True) or {}
    feed = (data.get("feed") or "").strip()
    config = dict(load_config())
    podcasts = [p for p in config.get("podcasts") or [] if p.get("feed") != feed]
    if not data.get("remove"):
        try:
            episode = radio.latest_episode(feed)
        except Exception:  # flux introuvable, invalide ou XML illisible
            return jsonify({"success": False, "message": _("Flux de podcast introuvable ou invalide.")}), 400
        podcasts.append({"name": episode["show"] or feed, "feed": feed})
    config["podcasts"] = podcasts[:30]
    save_config(config)
    return jsonify({"success": True, "podcasts": podcasts})


@app.route('/api/podcast/play', methods=['POST'])
@login_required
def podcast_play_api():
    """Lit le dernier épisode d'un podcast enregistré."""
    from utils import radio
    feed = (request.get_json(silent=True) or {}).get("feed", "")
    if feed not in [p.get("feed") for p in load_config().get("podcasts") or []]:
        return jsonify({"success": False, "message": _("Podcast inconnu.")}), 404
    try:
        episode = radio.latest_episode(feed)
        radio.play(episode["url"], f"{episode['show']} — {episode['title']}", kind="podcast", volume=load_config().get("music_volume", 80))
    except Exception:  # flux introuvable, invalide ou épisode absent
        return jsonify({"success": False, "message": _("Épisode introuvable.")}), 502
    return jsonify({"success": True, "message": _("Dernier épisode lancé : %(title)s", title=episode["title"])})
