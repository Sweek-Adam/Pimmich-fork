"""
Profils matériels : Pimmich s'adapte au Raspberry Pi qui le fait tourner (détection automatique, ou choix manuel
dans Maintenance). Le profil règle des limites internes (mémoire des GIF animés, compositions préparées d'avance,
vidéos en 720p sur les petits modèles...) et sert de valeur par défaut aux réglages de poids des vidéos tant qu'ils
n'ont pas été modifiés. Il propose aussi des « réglages conseillés », appliqués seulement si on le demande.
"""
import re
from pathlib import Path

from utils.message_renderer import N_

PROFILES = {
    "leger": {
        "label": N_("Léger (Raspberry Pi Zero, 1, 2)"),
        "gif_budget_mb": 24, "gif_items": 1, "compositions_ahead": 1, "videos_always_light": True,
        "video_light_above_mb": 0, "video_night_above_mb": 20,
    },
    "standard": {
        "label": N_("Standard (Raspberry Pi 3, Pi 4 avec 1 Go)"),
        "gif_budget_mb": 48, "gif_items": 2, "compositions_ahead": 2, "videos_always_light": False,
        "video_light_above_mb": 150, "video_night_above_mb": 50,
    },
    "complet": {
        "label": N_("Complet (Raspberry Pi 4 et 5, ordinateur)"),
        "gif_budget_mb": 160, "gif_items": 3, "compositions_ahead": 3, "videos_always_light": False,
        "video_light_above_mb": 600, "video_night_above_mb": 400,
    },
}
CHOICES = ["auto", *PROFILES]

# Réglages visibles conseillés pour chaque profil (proposés dans Maintenance, jamais imposés)
RECOMMENDED = {
    "leger": {"pan_zoom_enabled": False, "weather_animation": "off", "smart_crop": False, "compositions_every": 10,
              "transition_type": "fade", "short_videos_in_layouts": False, "heavy_videos_at_night": True},
    "standard": {"pan_zoom_enabled": False, "weather_animation": "start", "compositions_every": 5, "heavy_videos_at_night": True},
    "complet": {"heavy_videos_at_night": False},
}
LABELS = {
    "pan_zoom_enabled": N_("Zoom lent sur les photos"), "weather_animation": N_("Météo animée"),
    "smart_crop": N_("Recadrage selon les visages"), "compositions_every": N_("Une composition toutes les N photos"),
    "transition_type": N_("Transition"), "short_videos_in_layouts": N_("Courtes vidéos dans les dispositions"),
    "heavy_videos_at_night": N_("Grosses vidéos préparées la nuit seulement"),
}


def model(proc=Path("/proc")):
    try:
        return (proc / "device-tree" / "model").read_text().strip().strip("\x00")
    except OSError:
        return None


def memory_mb():
    try:
        import psutil
        return int(psutil.virtual_memory().total / (1024 * 1024))
    except Exception:
        return None


def detect(model_name=None, ram_mb=None):
    """Profil conseillé pour ce matériel."""
    model_name = model_name if model_name is not None else model()
    ram_mb = ram_mb if ram_mb is not None else memory_mb()
    if not model_name or "Raspberry Pi" not in model_name:
        return "complet"  # ordinateur (essais, développement)
    match = re.search(r"Raspberry Pi (\d)", model_name)
    number = int(match.group(1)) if match else 1
    if "Zero 2" in model_name:
        return "leger"
    if "Zero" in model_name or number <= 2:
        return "leger"
    if number == 3 or (ram_mb and ram_mb < 1800):
        return "standard"
    return "complet"


def current(config):
    chosen = (config or {}).get("hardware_profile", "auto")
    return chosen if chosen in PROFILES else detect()


def value(config, name):
    return PROFILES[current(config)][name]


def setting(config, key):
    """Réglage de l'utilisateur s'il l'a fixé, sinon la valeur du profil (ex. poids des vidéos)."""
    if config and key in config:
        return config[key]
    return value(config, key)


def recommended(config, current_values):
    """Écarts entre les réglages actuels et ceux conseillés pour le profil : [{key, label, current, recommended}]."""
    out = []
    for key, wanted in RECOMMENDED[current(config)].items():
        if current_values.get(key) != wanted:
            out.append({"key": key, "label": LABELS[key], "current": current_values.get(key), "recommended": wanted})
    return out
