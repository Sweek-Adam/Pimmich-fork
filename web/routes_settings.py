"""
Réglages en JSON pour la nouvelle interface : chaque réglage a un type, des bornes ou des choix, et une valeur par
défaut (la même que dans l'interface classique). Toute valeur est vérifiée avant d'être enregistrée ; le diaporama est
relancé une seule fois après une série de changements, et la modification peut être annulée (historique).
Les secrets (mots de passe, jetons) ne passent jamais par ici.
"""
import copy

from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from web.routes_config import schedule_slideshow_restart

TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
URL = re.compile(r"^https?://[^\s\x00-\x1f]+$")
COLOR = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
TRANSITIONS = ["fade", "fade_black", "zoom", "slide_left", "slide_right", "slide_up", "slide_down", "push_left", "push_up",
               "wipe", "blinds", "iris", "random"]

# clé : (type, options, valeur par défaut) ; options = (min, max) pour les nombres, liste pour les choix
SETTINGS = {
    # Affichage
    "display_duration": ("int", (3, 3600), 10),
    "active_start_weekday": ("time", None, "07:00"),
    "active_end_weekday": ("time", None, "22:00"),
    "active_start_weekend": ("time", None, "07:00"),
    "active_end_weekend": ("time", None, "23:00"),
    # Le soir et la nuit
    "dim_enabled": ("bool", None, False),
    "dim_start": ("time_or_sunset", None, "21:00"),
    "dim_level": ("int", (10, 90), 40),
    "night_mode": ("choice", ["off", "clock"], "off"),
    "night_brightness": ("int", (5, 100), 25),
    "night_color": ("choice", ["amber", "red", "white", "blue"], "amber"),
    "night_show_date": ("bool", None, True),
    # Effets
    "pan_zoom_enabled": ("bool", None, False),
    "pan_zoom_factor": ("float", (1.0, 2.0), 1.15),
    "transition_enabled": ("bool", None, True),
    "transition_duration": ("float", (0.0, 10.0), 1.0),
    "transition_type": ("choice", TRANSITIONS, "fade"),
    "beat_sync": ("bool", None, True),
    "transition_fps": ("choice", ["auto", "30", "60"], "auto"),
    # Fréquence des photos
    "favorite_boost_factor": ("int", (0, 20), 2),
    "anniversary_boost_enabled": ("bool", None, False),
    "anniversary_boost_factor": ("int", (0, 20), 2),
    "memories_banner": ("bool", None, True),
    "memories_composition": ("bool", None, True),
    "memories_every_minutes": ("int", (1, 1440), 30),
    "agenda_slide": ("bool", None, True),
    "agenda_every_minutes": ("int", (1, 1440), 30),
    # Vidéos
    "slideshow_video_enabled": ("bool", None, True),
    "media_mode": ("choice", ["all", "videos"], "all"),
    "video_audio_enabled": ("bool", None, False),
    "video_hwdec_enabled": ("bool", None, False),
    "video_light_above_mb": ("int", (0, 100000), 150),
    "heavy_videos_at_night": ("bool", None, True),
    "motion_photos_enabled": ("bool", None, True),
    "hardware_profile": ("choice", ["auto", "leger", "standard", "complet"], "auto"),
    "family_game_enabled": ("bool", None, True),
    "language": ("choice", ["fr", "en", "es", "de", "ja"], "fr"),
    "game_rounds": ("int", (1, 15), 6),
    "game_question_seconds": ("int", (5, 300), 25),
    "game_reveal_seconds": ("int", (3, 60), 9),
    "game_podium_seconds": ("int", (5, 300), 25),
    "game_memorize_seconds": ("int", (3, 60), 12),
    "game_timeline_seconds": ("int", (10, 300), 40),
    "game_caption_seconds": ("int", (10, 600), 60),
    "game_vote_seconds": ("int", (5, 300), 30),
    "game_challenge_seconds": ("int", (30, 1800), 180),
    "game_lobby_minutes": ("int", (1, 120), 15),
    "game_bingo_minutes": ("int", (5, 600), 45),
    "game_max_players": ("int", (2, 50), 20),
    "game_speed_bonus": ("bool", None, True),
    "game_auto_reveal": ("bool", None, True),
    "game_keep_challenge_photos": ("bool", None, False),
    "short_videos_in_layouts": ("bool", None, True),
    "short_videos_max_seconds": ("int", (2, 120), 15),
    "video_night_above_mb": ("int", (0, 100000), 50),
    "video_audio_output": ("choice", ["auto", "hdmi", "jack"], "auto"),
    "video_audio_volume": ("int", (0, 100), 100),
    "music_duck_videos": ("bool", None, True),
    # Écran : orientation et dimensions (les photos sont repréparées si la taille change)
    "screen_orientation": ("choice", ["landscape", "portrait", "landscape_flipped", "portrait_flipped", "auto"], "landscape"),
    "display_width": ("int", (240, 7680), 1920),
    "display_height": ("int", (240, 7680), 1080),
    "screen_height_percent": ("int", (10, 100), 100),
    "display_backend": ("choice", ["x11", "wayland"], "x11"),
    "wifi_hotspot_fallback": ("bool", None, False),
    # Télévision et prise connectée
    "cec_enabled": ("bool", None, False),
    "smart_plug_enabled": ("bool", None, False),
    "smart_plug_on_url": ("url", 500, ""),
    "smart_plug_off_url": ("url", 500, ""),
    "smart_plug_status_url": ("url", 500, ""),
    "smart_plug_on_delay": ("int", (0, 30), 5),
    # Bouton physique (GPIO, numérotation BCM)
    "button_enabled": ("bool", None, False),
    "button_pin": ("int", (2, 27), 23),
    # Dispositions
    "compositions_every": ("int", (0, 100), 5),
    "compositions_full_photos": ("bool", None, True),
    "smart_crop": ("bool", None, True),
    "compositions_include_messages": ("bool", None, True),
    "compositions_seasonal": ("bool", None, True),
    # Telegram
    "telegram_bot_enabled": ("bool", None, False),
    "telegram_authorized_users": ("text", 200, ""),
    "telegram_boost_enabled": ("bool", None, True),
    "telegram_boost_duration_days": ("int", (1, 365), 7),
    "telegram_boost_factor": ("int", (0, 20), 4),
    # Commande vocale
    "voice_control_enabled": ("bool", None, False),
    "voice_control_engine": ("choice", ["porcupine", "vosk"], "porcupine"),
    "voice_control_language": ("choice", ["fr", "en"], "fr"),
    "voice_control_device_index": ("device", None, ""),
    "notification_sound_volume": ("int", (0, 100), 80),
    # Invités
    "show_guest_qr": ("bool", None, True),
    "guest_qr_position": ("choice", ["bottom_right", "bottom_left", "top_right", "top_left"], "bottom_right"),
    "guest_messages_enabled": ("bool", None, True),
    "voice_messages_enabled": ("bool", None, True),
    "voice_volume": ("int", (10, 100), 100),
    "guest_reactions_enabled": ("bool", None, True),
    # Sources
    "album_name": ("text", 200, ""),
    "immich_url": ("text", 300, ""),
    "immich_max_photos": ("int", (0, 100000), 10),  # rangé dans max_photos_to_download.immich (0 = sans limite)
    "random_content_in_album": ("bool", None, True),
    "immich_auto_update": ("bool", None, False),
    "immich_update_interval_hours": ("int", (1, 720), 24),
    "smb_host": ("text", 200, ""),
    "smb_share": ("text", 200, ""),
    "smb_path": ("text", 300, ""),
    "smb_user": ("text", 100, ""),
    "smb_auto_update": ("bool", None, False),
    "smb_update_interval_hours": ("int", (1, 720), 24),
    "gdrive_backend": ("choice", ["auto", "rclone", "service_account"], "auto"),
    "gdrive_rclone_remote": ("text", 100, ""),
    "gdrive_recursive": ("bool", None, True),
    "gdrive_trash_after_import": ("bool", None, False),
    "gdrive_auto_update": ("bool", None, False),
    "gdrive_update_interval_minutes": ("int", (5, 10080), 60),
    "hide_duplicates": ("bool", None, True),
    "skip_initial_auto_import": ("bool", None, False),
    # Horloge et date
    "show_clock": ("bool", None, False),
    "clock_position": ("choice", ["left", "center", "right"], "center"),
    "clock_font_size": ("int", (12, 400), 48),
    "clock_offset_x": ("int", (-2000, 2000), 30),
    "clock_offset_y": ("int", (-2000, 2000), 30),
    "clock_color": ("color", None, "#FFFFFF"),
    "clock_outline_color": ("color", None, "#000000"),
    "clock_background_enabled": ("bool", None, False),
    "clock_background_color": ("color", None, "#00000080"),
    "clock_background_style": ("choice", ["band", "box"], "band"),
    "clock_layout": ("choice", ["line", "stacked"], "line"),
    "clock_second_line_percent": ("int", (30, 100), 55),
    "clock_font_path": ("font", None, "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    "clock_format": ("choice", ["%H:%M", "%H:%M:%S", "%I:%M %p"], "%H:%M"),
    "show_date": ("bool", None, False),
    "date_format": ("text", 60, "%A %d %B %Y"),
    # Météo
    "show_weather": ("bool", None, False),
    "show_sun_moon": ("bool", None, False),
    "weather_animation": ("choice", ["start", "always", "off"], "start"),
    "weather_city": ("text", 80, ""),
    "weather_units": ("choice", ["metric", "imperial"], "metric"),
    "weather_update_interval_minutes": ("int", (10, 1440), 30),
    # Marées
    "show_tides": ("bool", None, False),
    "tide_latitude": ("coord", (-90, 90), ""),
    "tide_longitude": ("coord", (-180, 180), ""),
    "tide_offset_x": ("int", (-2000, 2000), 0),
    "tide_offset_y": ("int", (-2000, 2000), 0),
    # Infos des photos
    "show_photo_date": ("bool", None, False),
    "photo_date_format": ("text", 60, "%d %B %Y"),
    "show_photo_location": ("bool", None, False),
    "geocode_enabled": ("bool", None, False),
    "photo_location_format": ("choice", ["city_country", "city", "country"], "city_country"),
    "show_country_flag": ("bool", None, False),
    "country_flag_size": ("choice", ["128x96", "192x144", "256x192"], "128x96"),
    "country_flag_opacity": ("float", (0.0, 1.0), 1.0),
    "country_flag_position": ("choice", ["top_right", "top_left", "bottom_right", "bottom_left"], "top_right"),
    "country_flag_offset_x": ("int", (-2000, 2000), 15),
    "country_flag_offset_y": ("int", (-2000, 2000), 15),
}


# Réglages visibles et modifiables seulement par un administrateur (comme dans l'interface classique)
ADMIN_ONLY = {"telegram_authorized_users", "wifi_hotspot_fallback", "hardware_profile"}

# Secrets : jamais renvoyés au navigateur ; on sait seulement s'ils sont définis, et on peut les remplacer
SECRETS = ("immich_token", "smb_password", "weather_api_key", "stormglass_api_key", "telegram_bot_token",
           "porcupine_access_key", "home_assistant_token", "email_password", "mqtt_password")


def clean(key, value):
    """Valeur vérifiée et convertie ; ValueError si elle ne convient pas."""
    kind, options, _default = SETTINGS[key]
    if kind == "bool":
        if not isinstance(value, bool):
            raise ValueError
        return value
    if kind in ("int", "float"):
        if isinstance(value, bool):
            raise ValueError
        number = int(value) if kind == "int" else float(value)
        low, high = options
        if not low <= number <= high:
            raise ValueError
        return number
    if kind == "choice":
        if str(value) not in options:
            raise ValueError
        return str(value)
    if kind == "time":
        if not TIME.match(str(value)):
            raise ValueError
        return str(value)
    if kind == "color":
        if not COLOR.match(str(value)):
            raise ValueError
        return str(value)
    if kind == "text":
        text = str(value)
        if len(text) > options or any(c in text for c in "\r\n\t\x00"):
            raise ValueError
        return text.strip()
    if kind == "url":  # adresse http(s) appelée par le cadre, ou "" (non renseignée)
        text = str(value).strip()
        if text and (len(text) > options or not URL.match(text)):
            raise ValueError
        return text
    if kind == "coord":  # latitude ou longitude en degrés décimaux, ou "" (non renseignée)
        text = str(value).strip().replace(",", ".")
        if not text:
            return ""
        number = float(text)
        low, high = options
        if not low <= number <= high:
            raise ValueError
        return text
    if kind == "font":  # uniquement une police présente sur le cadre
        if str(value) not in {path for path, _label in clock_fonts()}:
            raise ValueError
        return str(value)
    if kind == "device":  # index d'un périphérique audio, ou "" (par défaut)
        text = str(value)
        if text and not text.isdigit():
            raise ValueError
        return text
    if kind == "time_or_sunset":
        if value != "sunset" and not TIME.match(str(value)):
            raise ValueError
        return str(value)
    raise ValueError


FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVu Sans (gras)"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVu Sans"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-ExtraLight.ttf", "DejaVu Sans (fin)"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf", "DejaVu Sans condensé (gras)"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", "DejaVu Serif (gras)"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf", "DejaVu Serif (italique)"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", "DejaVu Mono (gras)"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "Liberation Sans"),
    ("/usr/share/fonts/truetype/freefont/FreeSans.ttf", "FreeSans"),
    ("/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf", "FreeMono (gras)"),
]
PROJECT_FONTS = [("Caveat-Regular.ttf", "Caveat (manuscrit)"), ("PatrickHand-Regular.ttf", "Patrick Hand"),
                 ("PermanentMarker-Regular.ttf", "Permanent Marker"), ("SpecialElite-Regular.ttf", "Special Elite (machine à écrire)")]


def clock_fonts():
    """Polices disponibles sur ce cadre pour l'heure : [(chemin, nom)]."""
    found = [(path, label) for path, label in FONT_CANDIDATES if Path(path).is_file()]
    found += [(str(BASE_DIR / "static" / "fonts" / name), label) for name, label in PROJECT_FONTS
              if (BASE_DIR / "static" / "fonts" / name).is_file()]
    return found


PROFILE_DEFAULTS = {"video_light_above_mb", "video_night_above_mb"}


def current_values(config=None):
    config = config or load_config()
    values = {}
    admin = is_admin()
    for key, (kind, _options, default) in SETTINGS.items():
        if key in ADMIN_ONLY and not admin:
            continue
        value = config.get(key, default)
        if key.startswith("active_") and key not in config:  # anciens réglages (mêmes heures toute la semaine)
            value = config.get("active_start" if "start" in key else "active_end", default)
        if key == "immich_max_photos":
            value = (config.get("max_photos_to_download") or {}).get("immich", default)
        if key in PROFILE_DEFAULTS and key not in config:  # valeur du profil matériel tant qu'on ne l'a pas changée
            from utils import hardware_profile
            value = hardware_profile.setting(config, key)
        if kind == "choice" and value is not None:
            value = str(value)
        values[key] = value
    return values


@app.route('/api/settings', methods=['GET'])
@login_required
def settings_api():
    return jsonify({"success": True, "values": current_values()})


@app.route('/api/settings', methods=['POST'])
@login_required
def settings_save_api():
    changes = request.get_json(silent=True)
    if not isinstance(changes, dict) or not changes:
        return jsonify({"success": False, "message": _("Aucun réglage à enregistrer.")}), 400
    cleaned = {}
    for key, value in changes.items():
        if key not in SETTINGS or (key in ADMIN_ONLY and not is_admin()):
            return jsonify({"success": False, "message": _("Réglage inconnu : %(key)s", key=str(key)[:60])}), 400
        try:
            cleaned[key] = clean(key, value)
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": _("Valeur invalide pour « %(key)s ».", key=key), "key": key}), 400
    config = load_config()
    previous = copy.deepcopy(config)
    if "immich_max_photos" in cleaned:  # réglage imbriqué
        limits = dict(config.get("max_photos_to_download") or {})
        limits["immich"] = cleaned.pop("immich_max_photos")
        cleaned["max_photos_to_download"] = limits
    config = dict(config, **cleaned)
    resized = False
    if {"screen_orientation", "display_width", "display_height"} & set(cleaned):
        # Dimensions dans l'orientation en vigueur (paysage, portrait ou automatique), comme l'interface classique
        from utils import screen_rotation
        config["display_width"], config["display_height"] = screen_rotation.sized(
            config, int(config.get("display_width") or 1920), int(config.get("display_height") or 1080))
        resized = (config["display_width"], config["display_height"]) != (previous.get("display_width"), previous.get("display_height"))
    save_config(config)
    from web.routes_history import log
    log("settings", _("Réglages modifiés"), {"type": "restore_config", "data": previous}, merge=True)
    if resized:  # les photos sont repréparées aux nouvelles dimensions, le diaporama continue pendant ce temps
        from web.workers import reprepare_all_sources
        threading.Thread(target=reprepare_all_sources, daemon=True, name="reprepare").start()
    schedule_slideshow_restart()
    return jsonify({"success": True, "message": _("Enregistré"), "values": current_values(config)})


@app.route('/api/gpio_button', methods=['GET'])
@login_required
def gpio_button_api():
    """État du bouton physique : bibliothèque GPIO présente, broche surveillée, dernier appui."""
    from utils import gpio_button
    state = dict(gpio_button.STATE)
    if state["available"] is None:  # surveillance pas encore lancée
        state["available"] = gpio_button.load_gpio() is not None
    return jsonify({"success": True, **state})


# --- Dispositions : formats et thèmes de compositions activés, disposition du moment ---

@app.route('/api/compositions', methods=['GET'])
@login_required
def compositions_api():
    from utils.compositions import FORMATS, MESSAGE_FORMATS, SEASONAL, THEME_KEYS, enabled_formats
    from utils.layout_engine import choice_options
    config = load_config()
    translate = _  # libellés marqués N_() dans les modules de compositions
    formats = [{"key": "unique", "label": translate("Photo unique"), "theme": False, "seasonal": False, "messages": True,
                "message_only": False, "preview": url_for("static", filename="composition_previews/unique.jpg")}]
    for key, value in FORMATS.items():
        formats.append({"key": key, "label": translate(value[0]), "theme": key in THEME_KEYS, "seasonal": key in SEASONAL,
                        "messages": bool(value[3]), "message_only": key in MESSAGE_FORMATS, "preview": url_for("static", filename=f"composition_previews/{key}.jpg")})
    enabled = enabled_formats(config) + (["unique"] if config.get("unique_enabled", True) else [])
    choices = [{"value": value, "label": translate(label), "group": group} for value, label, group in choice_options()]
    return jsonify({"success": True, "formats": formats, "enabled": enabled, "layout": config.get("layout_override", "auto"),
                    "choices": choices})


@app.route('/api/compositions', methods=['POST'])
@login_required
def compositions_save_api():
    from utils.compositions import FORMATS
    data = request.get_json(silent=True) or {}
    enabled = data.get("enabled")
    if not isinstance(enabled, list) or not all(isinstance(k, str) for k in enabled):
        return jsonify({"success": False, "message": _("Liste invalide.")}), 400
    chosen = set(enabled)
    if not chosen & (set(FORMATS) | {"unique"}):
        return jsonify({"success": False, "message": _("Gardez au moins une disposition.")}), 400
    config = load_config()
    previous = copy.deepcopy(config)
    config = dict(config, compositions_disabled=[k for k in FORMATS if k not in chosen], unique_enabled="unique" in chosen,
                  compositions_enabled=True)
    config.pop("compositions_styles", None)
    save_config(config)
    from web.routes_history import log
    log("settings", _("Réglages modifiés"), {"type": "restore_config", "data": previous}, merge=True)
    schedule_slideshow_restart()
    return jsonify({"success": True, "message": _("Enregistré")})


@app.route('/api/secrets', methods=['GET'])
@admin_required
def secrets_api():
    """Quels secrets sont définis (jamais leur valeur)."""
    config = load_config()
    return jsonify({"success": True, "secrets": {key: bool(config.get(key)) for key in SECRETS}})


@app.route('/api/secrets', methods=['POST'])
@admin_required
def secrets_save_api():
    data = request.get_json(silent=True) or {}
    key, value = data.get("key"), data.get("value")
    if key not in SECRETS or not isinstance(value, str) or len(value) > 500 or any(c in value for c in "\r\n\x00"):
        return jsonify({"success": False, "message": _("Valeur invalide.")}), 400
    config = dict(load_config())
    config[key] = value.strip()
    save_config(config)  # pas d'annulation : l'ancien secret ne doit pas être gardé dans l'historique
    schedule_slideshow_restart()
    return jsonify({"success": True, "message": _("Enregistré") if value.strip() else _("Supprimé.")})


@app.route('/api/settings/fonts', methods=['GET'])
@login_required
def settings_fonts_api():
    return jsonify({"success": True, "fonts": [{"value": path, "label": label} for path, label in clock_fonts()]})


# --- Sources affichées dans le diaporama ---

MANAGED_SOURCES = {"citation", "voyages", "cadres"}  # ajoutées par leurs propres réglages (citation du jour, voyages...)


def source_choices():
    from utils import members
    translate = _
    choices = [("immich", translate("Photos Immich")), ("usb", translate("Photos USB")), ("samba", translate("Photos Samba")),
               ("gdrive", translate("Photos Google Drive")), ("smartphone", translate("Photos Smartphone")),
               ("telegram", translate("Photos reçues par Telegram")), ("invités", translate("Photos des invités (validées)")),
               ("cloud", translate("Autres clouds (Dropbox, OneDrive...)")), ("icloud", translate("Albums partagés iCloud")),
               ("whatsapp", translate("WhatsApp et partages depuis le téléphone")), ("email", translate("Photos reçues par e-mail")),
               ("personnes", translate("Photos des personnes suivies (Immich)"))]
    names = [u["username"] for u in user_manager.list_users()] + [session.get("username") or ""]
    choices += [(source, translate("Envois de %(name)s", name=members.label(source, names))) for source in members.sources()]
    party_config = load_config().get("party") or {}
    for folder in sorted((BASE_DIR / "static" / "photos").glob("fete_*")):  # albums des fêtes (mode fête)
        if folder.is_dir():
            day = folder.name[5:]
            name = party_config.get("name") if party_config.get("source") == folder.name else ""
            label = f"{day[6:8]}/{day[4:6]}/{day[:4]}" if len(day) == 8 and day.isdigit() else day
            choices.append((folder.name, translate("Fête : %(name)s", name=f"{name} ({label})" if name else label)))
    choices.append(("messages", translate("Messages")))
    return choices


@app.route('/api/display_sources', methods=['GET'])
@login_required
def display_sources_api():
    selected = load_config().get("display_sources") or []
    return jsonify({"success": True, "selected": [s for s in selected if s not in MANAGED_SOURCES],
                    "choices": [{"key": k, "label": label} for k, label in source_choices()]})


@app.route('/api/display_sources', methods=['POST'])
@login_required
def display_sources_save_api():
    wanted = (request.get_json(silent=True) or {}).get("selected")
    known = {k for k, _label in source_choices()}
    if not isinstance(wanted, list) or not all(isinstance(s, str) and s in known for s in wanted):
        return jsonify({"success": False, "message": _("Source inconnue.")}), 400
    config = load_config()
    previous = copy.deepcopy(config)
    kept = [s for s in config.get("display_sources") or [] if s in MANAGED_SOURCES or s not in known]  # sources gérées ailleurs
    config = dict(config, display_sources=list(dict.fromkeys(wanted + kept)))
    save_config(config)
    from web.routes_history import log
    log("settings", _("Réglages modifiés"), {"type": "restore_config", "data": previous}, merge=True)
    schedule_slideshow_restart()
    return jsonify({"success": True, "message": _("Enregistré")})


# --- Google Drive : dossiers choisis, compte de service ---

@app.route('/api/gdrive/setup', methods=['GET'])
@login_required
def gdrive_setup_api():
    config = load_config()
    return jsonify({"success": True, "remotes": list_rclone_remotes(), "service_email": get_service_account_email(),
                    "folders": [{"id": f.get("id"), "name": f.get("name")} for f in config.get("gdrive_folders") or []]})


@app.route('/api/gdrive/selected_folders', methods=['POST'])
@login_required
def gdrive_selected_folders_api():
    folders = (request.get_json(silent=True) or {}).get("folders")
    if not isinstance(folders, list):
        return jsonify({"success": False, "message": _("Liste invalide.")}), 400
    config = load_config()
    backend = resolve_backend_name(config)
    config = dict(config, gdrive_folders=[{"id": str(f.get("id", ""))[:300], "name": str(f.get("name", ""))[:300], "backend": backend}
                                          for f in folders[:200] if isinstance(f, dict) and f.get("id")])
    save_config(config)
    return jsonify({"success": True, "message": _("Enregistré")})


@app.route('/api/gdrive/service_account', methods=['POST'])
@admin_required
def gdrive_service_account_api():
    try:
        save_service_account_key(parse_service_account_key(str((request.get_json(silent=True) or {}).get("key") or "")))
    except ValueError as e:
        return jsonify({"success": False, "message": _("Clé Google Drive non enregistrée : %(error)s", error=str(e))}), 400
    return jsonify({"success": True, "message": _("Enregistré"), "service_email": get_service_account_email()})


# --- Profil matériel (Raspberry Pi 2, 3, 4, 5) ---

@app.route('/api/hardware_profile', methods=['GET'])
@login_required
@admin_required
def hardware_profile_api():
    from utils import hardware_profile as hp
    config = load_config()
    translate = _  # appel indirect : l'extracteur ne doit pas prendre les clés « label » pour des textes
    key = hp.current(config)
    limits = hp.PROFILES[key]
    return jsonify({"success": True, "model": hp.model() or _("Ordinateur (pas un Raspberry Pi)"), "ram_mb": hp.memory_mb(),
                    "detected": hp.detect(), "selected": config.get("hardware_profile", "auto"), "current": key,
                    "profiles": [{"key": k, "label": translate(p["label"])} for k, p in hp.PROFILES.items()],
                    "limits": {"gif_budget_mb": limits["gif_budget_mb"], "gif_items": limits["gif_items"],
                               "compositions_ahead": limits["compositions_ahead"], "videos_always_light": limits["videos_always_light"],
                               "video_light_above_mb": hp.setting(config, "video_light_above_mb"),
                               "video_night_above_mb": hp.setting(config, "video_night_above_mb")},
                    "recommended": [dict(r, label=translate(r["label"])) for r in hp.recommended(config, current_values(config))]})


@app.route('/api/hardware_profile/apply', methods=['POST'])
@login_required
@admin_required
def hardware_profile_apply_api():
    """Applique les réglages conseillés pour le profil (ceux qui diffèrent seulement)."""
    from utils import hardware_profile as hp
    config = load_config()
    changes = {r["key"]: clean(r["key"], r["recommended"]) for r in hp.recommended(config, current_values(config))}
    if not changes:
        return jsonify({"success": True, "message": _("Les réglages sont déjà ceux conseillés.")})
    previous = copy.deepcopy(config)
    save_config(dict(config, **changes))
    from web.routes_history import log
    log("settings", _("Réglages conseillés appliqués"), {"type": "restore_config", "data": previous}, merge=True)
    schedule_slideshow_restart()
    return jsonify({"success": True, "message": _("%(count)s réglage(s) adapté(s) au Raspberry Pi.", count=len(changes))})
