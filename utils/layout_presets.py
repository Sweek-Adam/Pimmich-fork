"""
Configurations de dispositions enregistrées : un nom, les dispositions cochées, la photo unique et le rythme
des compositions. On en active une d'un clic (Écran > Dispositions, ou le sélecteur de disposition).
"""
import secrets

from utils.message_renderer import N_

from utils import compositions

FIELDS = ("formats", "unique", "every")


def _list(config):
    presets = config.get("layout_presets") or []
    return [p for p in presets if isinstance(p, dict) and p.get("id")]


def from_config(config):
    """Réglages de dispositions actuels, sous forme de configuration."""
    try:
        every = max(0, int(config.get("compositions_every", 5)))
    except (TypeError, ValueError):
        every = 5
    return {"formats": compositions.enabled_formats(config), "unique": bool(config.get("unique_enabled", True)), "every": every}


def matches(preset, config):
    current = from_config(config)
    return (set(preset.get("formats", [])) == set(current["formats"]) and bool(preset.get("unique")) == current["unique"]
            and int(preset.get("every", 5)) == current["every"])


def listing(config):
    """Configurations, avec celle qui correspond aux réglages actuels (« active »)."""
    presets = _list(config)
    active = next((p["id"] for p in presets if matches(p, config)), None) if config.get("layout_override", "auto") == "auto" else None
    return [dict(p, active=p["id"] == active, count=len(p.get("formats", [])) + (1 if p.get("unique") else 0)) for p in presets]


def clean_selection(selection):
    """Sélection envoyée par l'interface (cases cochées) -> configuration valide, sinon None."""
    if not isinstance(selection, dict):
        return None
    formats = [k for k in selection.get("formats") or [] if k in compositions.FORMATS]
    try:
        every = max(0, min(100, int(selection.get("every", 5))))
    except (TypeError, ValueError):
        every = 5
    return {"formats": formats, "unique": bool(selection.get("unique")) or not formats, "every": every}


def save(config, name, preset_id=None, selection=None):
    """Enregistre la sélection (ou les réglages actuels) sous ce nom, ou met à jour une configuration existante."""
    name = (name or "").strip()[:60]
    if not name and not preset_id:
        raise ValueError(N_("Nom manquant."))
    config = dict(config)
    presets = [dict(p) for p in _list(config)]
    values = clean_selection(selection) or from_config(config)
    if preset_id:
        for p in presets:
            if p["id"] == preset_id:
                p.update(values, name=name or p["name"])
                break
        else:
            raise ValueError(N_("Configuration introuvable."))
    else:
        if any(p["name"].lower() == name.lower() for p in presets):
            raise ValueError(N_("Ce nom existe déjà."))
        presets.append(dict(values, id=secrets.token_hex(4), name=name))
    config["layout_presets"] = presets
    return config


def activate(config, preset_id):
    """Applique une configuration : ses dispositions, la photo unique et le rythme des compositions."""
    preset = next((p for p in _list(config) if p["id"] == preset_id), None)
    if preset is None:
        raise ValueError(N_("Configuration introuvable."))
    formats = [k for k in preset.get("formats", []) if k in compositions.FORMATS]
    config = dict(config)
    config["compositions_disabled"] = [k for k in compositions.FORMATS if k not in formats]
    config["compositions_enabled"] = True
    config["unique_enabled"] = bool(preset.get("unique")) or not formats  # jamais aucune disposition
    config["compositions_every"] = int(preset.get("every", 5))
    config["layout_override"] = "auto"  # « selon mes réglages » : la configuration s'applique
    return config


def delete(config, preset_id):
    config = dict(config)
    config["layout_presets"] = [p for p in _list(config) if p["id"] != preset_id]
    return config
