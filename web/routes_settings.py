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
    "memories_every_minutes": ("int", (5, 1440), 30),
    "agenda_slide": ("bool", None, True),
    "agenda_every_minutes": ("int", (5, 1440), 30),
    # Vidéos
    "slideshow_video_enabled": ("bool", None, True),
    "media_mode": ("choice", ["all", "videos"], "all"),
    "video_audio_enabled": ("bool", None, False),
    "video_hwdec_enabled": ("bool", None, False),
    "video_audio_output": ("choice", ["auto", "hdmi", "jack"], "auto"),
    "video_audio_volume": ("int", (0, 100), 100),
    "music_duck_videos": ("bool", None, True),
    # Télévision
    "cec_enabled": ("bool", None, False),
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
ADMIN_ONLY = {"telegram_authorized_users"}

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
    config = dict(config, **cleaned)
    save_config(config)
    from web.routes_history import log
    log("settings", _("Réglages modifiés"), {"type": "restore_config", "data": previous}, merge=True)
    schedule_slideshow_restart()
    return jsonify({"success": True, "message": _("Enregistré"), "values": current_values(config)})


# --- Dispositions : formats et thèmes de compositions activés, disposition du moment ---

@app.route('/api/compositions', methods=['GET'])
@login_required
def compositions_api():
    from utils.compositions import FORMATS, SEASONAL, THEME_KEYS, enabled_formats
    from utils.layout_engine import choice_options
    config = load_config()
    translate = _  # libellés marqués N_() dans les modules de compositions
    formats = [{"key": "unique", "label": translate("Photo unique"), "theme": False, "seasonal": False, "messages": True,
                "preview": url_for("static", filename="composition_previews/unique.jpg")}]
    for key, value in FORMATS.items():
        formats.append({"key": key, "label": translate(value[0]), "theme": key in THEME_KEYS, "seasonal": key in SEASONAL,
                        "messages": bool(value[3]), "preview": url_for("static", filename=f"composition_previews/{key}.jpg")})
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
