"""Accueil : santé du cadre, assistant de démarrage, ambiances, disposition immédiate, QR code des invités."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _, _send_slideshow_signal
import io
import qrcode
from flask import send_file
from utils import ambiances, health, layout_engine, now_playing, spotify
from utils.message_renderer import N_

FORCE_LAYOUT_FILE = Path("/tmp/pimmich_force_layout.json")


def _tr(text, **params):
    """Traduit un texte marqué N_ ailleurs (appel indirect : l'extracteur ne doit pas prendre la clé du dict pour un texte)."""
    return _(text, **params) if params else _(text)


def _translated(items):
    """Traduit les textes (marqués N_) et insère leurs paramètres."""
    out = []
    for item in items:
        item = dict(item)
        params = {k: _tr(v) if isinstance(v, str) else v for k, v in (item.pop("params", {}) or {}).items()}
        item["title"] = _tr(item["title"])
        item["detail"] = _tr(item["detail"], **params)
        out.append(item)
    return out


@app.route('/api/health', methods=['GET'])
@login_required
def health_api():
    config = dict(load_config())
    config["_active_hours"] = is_active_hours(config)
    workers = {"Immich": immich_status_manager.get_status().get("status_message"),
               "Samba": samba_status_manager.get_status().get("status_message"),
               "Google Drive": gdrive_status_manager.get_status().get("status_message")}
    items = health.checks(config, is_slideshow_running(), is_admin(), proxy_host_ok=bool(request.host), worker_messages=workers)
    return jsonify({"success": True, "items": _translated(items)})


@app.route('/api/hardware', methods=['GET'])
@login_required
def hardware_api():
    from utils import hardware
    return jsonify({"success": True, **hardware.status()})


@app.route('/api/memories/today', methods=['GET'])
@login_required
def memories_today_api():
    """« Ce jour-là » : photos prises un jour comme aujourd'hui, les années précédentes."""
    from utils import photo_index
    today = datetime.now().date()
    items = [{"thumb": url_for("static", filename=f"prepared/{key}"), "year": taken.year, "years_ago": today.year - taken.year}
             for key, taken in photo_index.on_this_day(today)
             if (photo_index.PREPARED_DIR / key).is_file()]
    return jsonify({"success": True, "items": items[-24:]})


@app.route('/api/setup', methods=['GET'])
@login_required
def setup_api():
    config = load_config()
    steps = [dict(s, title=_tr(s["title"])) for s in health.setup_steps(config, is_admin())]
    return jsonify({"success": True, "steps": steps, "dismissed": bool(config.get("setup_dismissed")),
                    "done": sum(1 for s in steps if s["done"]), "total": len(steps)})


@app.route('/api/setup/dismiss', methods=['POST'])
@login_required
def setup_dismiss_api():
    config = dict(load_config())
    config["setup_dismissed"] = bool((request.get_json(silent=True) or {}).get("dismissed", True))
    save_config(config)
    return jsonify({"success": True})


SETUP_MARKS = {"guests"}  # étapes validées par une action de l'utilisateur (ex. lien des invités partagé)


@app.route('/api/setup/mark', methods=['POST'])
@login_required
def setup_mark_api():
    step = (request.get_json(silent=True) or {}).get("step")
    if step not in SETUP_MARKS:
        return jsonify({"success": False, "message": _("Étape inconnue.")}), 400
    config = dict(load_config())
    marks = set(config.get("setup_marks") or [])
    if step not in marks:
        config["setup_marks"] = sorted(marks | {step})
        save_config(config)
    return jsonify({"success": True})


@app.route('/api/ambiances', methods=['GET'])
@login_required
def ambiances_api():
    current = load_config().get("ambiance")
    items = [dict(a, label=_tr(a["label"]), description=_tr(a["description"])) for a in ambiances.listing(current)]
    return jsonify({"success": True, "ambiances": items, "current": current, "can_restore": bool(load_config().get("ambiance_backup"))})


@app.route('/api/ambiance', methods=['POST'])
@login_required
def apply_ambiance_api():
    key = (request.get_json(silent=True) or {}).get("ambiance")
    try:
        config = ambiances.apply(load_config(), key)
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    save_config(config)
    restart_slideshow_process()
    spotify.play_linked_in_background((config.get("spotify_links") or {}).get(f"ambiance:{key}"), logger)  # musique associée
    label = _("Mes réglages") if key == ambiances.MINE else _tr(ambiances.AMBIANCES[key]["label"])
    return jsonify({"success": True, "message": _("Ambiance « %(name)s » appliquée.", name=label)})


@app.route('/api/slideshow/layout/now', methods=['POST'])
@login_or_internal_required
def force_layout_now_api():
    """Affiche tout de suite une diapositive avec cette disposition (une seule fois), puis le diaporama reprend."""
    layout = (request.get_json(silent=True) or {}).get("layout")
    if not layout_engine.is_valid_choice(layout) or layout == layout_engine.AUTO:
        return jsonify({"success": False, "message": _("Disposition inconnue.")}), 400
    if not is_slideshow_running():
        return jsonify({"success": False, "message": _("Le diaporama n'est pas en cours.")}), 409
    FORCE_LAYOUT_FILE.write_text(json.dumps({"layout": layout, "requested": time.time()}))
    _send_slideshow_signal(signal.SIGUSR1)  # passer tout de suite à la diapositive suivante
    return jsonify({"success": True, "message": _("Préparation de la disposition... elle s'affiche dans quelques secondes.")})


def _local_ip():
    """Adresse IP du cadre sur le réseau local."""
    try:
        return subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=3).stdout.split()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        return request.host.split(":")[0] or "127.0.0.1"


@app.route('/api/guest_qr.png', methods=['GET'])
@login_required
def guest_qr_png():
    """QR code de la page invités (sur le Wi-Fi ; ?remote=1 : lien secret utilisable de partout), à afficher ou imprimer."""
    url = f"http://{_local_ip()}/upload"
    if request.args.get("remote") and is_admin():
        from utils import remote_guests
        config, status = load_config(), remote_guests.tailscale_status()
        if not (config.get("remote_guests_enabled") and config.get("guest_link_token") and status["dns_name"]):
            return "", 404
        url = f"https://{status['dns_name']}/upload?k={config['guest_link_token']}"
    qr = qrcode.QRCode(border=2, box_size=12)
    qr.add_data(url)
    qr.make(fit=True)
    buffer = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buffer, "PNG")
    buffer.seek(0)
    response = send_file(buffer, mimetype="image/png")
    response.headers["X-Guest-Url"] = url
    return response


# --- Son : musique de fond du diaporama, enceinte Spotify Connect / récepteur AirPlay ---

MUSIC_DIR = BASE_DIR / "static" / "music"


def _service_active(name):
    """Vrai si le service (utilisateur ou système) est actif."""
    for command in (["systemctl", "--user", "is-active", name], ["systemctl", "is-active", name]):
        try:
            if subprocess.run(command, capture_output=True, text=True, timeout=5).stdout.strip() == "active":
                return True
        except (OSError, subprocess.SubprocessError):
            pass
    return False


@app.route('/api/sound', methods=['GET'])
@login_required
def sound_settings_api():
    config = load_config()
    files = sorted(f.name for f in MUSIC_DIR.iterdir() if f.suffix.lower() in (".mp3", ".wav")) if MUSIC_DIR.exists() else []
    return jsonify({"success": True, "background_music": config.get("background_music", ""), "music_volume": config.get("music_volume", 80),
                    "now_playing_display": config.get("now_playing_display", "change"),
                    "now_playing_position": config.get("now_playing_position", "bottom_left"),
                    "files": files, "receivers": {"spotify": _service_active("pimmich-spotify"), "airplay": _service_active("pimmich-airplay"),
                                  "bluetooth": _service_active("pimmich-bluetooth")}})


@app.route('/api/sound', methods=['POST'])
@login_required
def save_sound_settings_api():
    data = request.get_json(silent=True) or {}
    config = dict(load_config())
    music = data.get("background_music", config.get("background_music", "")) or ""
    if music and not (MUSIC_DIR / Path(music).name).is_file():
        return jsonify({"success": False, "message": _("Musique introuvable.")}), 400
    try:
        volume = max(0, min(100, int(data.get("music_volume", config.get("music_volume", 80)))))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": _("Volume invalide.")}), 400
    display = data.get("now_playing_display", config.get("now_playing_display", "change"))
    position = data.get("now_playing_position", config.get("now_playing_position", "bottom_left"))
    if display not in NOW_PLAYING_MODES or position not in CORNERS:
        return jsonify({"success": False, "message": _("Réglage invalide.")}), 400
    music_changed = (Path(music).name if music else "", volume) != (config.get("background_music", ""), config.get("music_volume", 80))
    config["background_music"], config["music_volume"] = Path(music).name if music else "", volume
    config["now_playing_display"], config["now_playing_position"] = display, position
    save_config(config)
    if music_changed:  # l'affichage du lecteur est relu en direct par le diaporama
        restart_slideshow_process()
    return jsonify({"success": True, "message": _("Réglages du son enregistrés.")})


NOW_PLAYING_MODES = ("off", "change", "always")
CORNERS = ("bottom_left", "bottom_right", "top_left", "top_right")
SOURCE_LABELS = {"spotify": "Spotify", "airplay": "AirPlay", "bluetooth": "Bluetooth", "pimmich": N_("Musique du diaporama")}


@app.route('/api/now_playing', methods=['GET'])
@login_required
def now_playing_api():
    """Morceau en cours (Spotify, AirPlay ou musique du diaporama), pour l'accueil et l'onglet Son."""
    info = now_playing.current(exclude=() if is_slideshow_running() else ("pimmich",))
    if not info:
        return jsonify({"success": True, "playing": None})
    cover = info.get("cover")
    has_cover = bool(cover) and Path(cover).parent == now_playing.COVER_DIR and Path(cover).is_file()
    return jsonify({"success": True, "playing": {
        "title": info.get("title", ""), "artist": info.get("artist", ""), "album": info.get("album", ""),
        "source": info["source"], "source_label": _tr(SOURCE_LABELS.get(info["source"], info["source"])),
        "cover": url_for("now_playing_cover", v=Path(cover).name) if has_cover else None}})


@app.route('/api/now_playing/cover', methods=['GET'])
@login_required
def now_playing_cover():
    info = now_playing.latest(exclude=() if is_slideshow_running() else ("pimmich",))  # aussi en pause (télécommande)
    cover = Path(info["cover"]) if info and info.get("cover") else None
    if not cover or cover.parent != now_playing.COVER_DIR or not cover.is_file():  # uniquement le dossier des pochettes
        return "", 404
    return send_file(cover, mimetype="image/jpeg", max_age=3600)
