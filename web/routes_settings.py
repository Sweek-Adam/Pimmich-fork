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
    # Vidéos
    "slideshow_video_enabled": ("bool", None, True),
    "video_audio_enabled": ("bool", None, False),
    "video_hwdec_enabled": ("bool", None, False),
    "video_audio_output": ("choice", ["auto", "hdmi", "jack"], "auto"),
    "video_audio_volume": ("int", (0, 100), 100),
    "music_duck_videos": ("bool", None, True),
    # Télévision
    "cec_enabled": ("bool", None, False),
}


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
    if kind == "time_or_sunset":
        if value != "sunset" and not TIME.match(str(value)):
            raise ValueError
        return str(value)
    raise ValueError


def current_values(config=None):
    config = config or load_config()
    values = {}
    for key, (kind, _options, default) in SETTINGS.items():
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
        if key not in SETTINGS:
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
