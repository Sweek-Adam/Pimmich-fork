"""
Ambiances : préréglages qui changent plusieurs réglages d'un coup (dispositions, rythme, transitions...).
Les valeurs d'origine sont mémorisées à la première ambiance appliquée, pour pouvoir revenir à « Mes réglages ».
"""
from utils.message_renderer import N_

ALL_FORMATS = None  # rempli à la demande (évite une importation circulaire au chargement)


def _formats():
    from utils.compositions import FORMATS
    return list(FORMATS)


def _only(*keys):
    """Réglage qui n'active que ces formats de composition."""
    return [k for k in _formats() if k not in keys]


AMBIANCES = {
    "classique": {
        "label": N_("Classique"), "icon": "fa-image",
        "description": N_("Une photo à la fois, transitions douces."),
        "settings": lambda: {"layout_override": "unique", "display_duration": 10, "transition_enabled": True,
                             "transition_type": "fade", "transition_duration": 1.0, "pan_zoom_enabled": False},
    },
    "fete": {
        "label": N_("Fête"), "icon": "fa-glass-cheers",
        "description": N_("Rythme rapide, compositions festives, QR code et messages des invités."),
        "settings": lambda: {"layout_override": "auto", "unique_enabled": True, "compositions_enabled": True,
                             "compositions_disabled": _only("anniversaire", "annees80", "polaroids", "mosaique", "bd", "liege", "scrapbook"),
                             "compositions_every": 2, "display_duration": 7, "show_guest_qr": True, "guest_messages_enabled": True},
    },
    "souvenirs": {
        "label": N_("Souvenirs"), "icon": "fa-history",
        "description": N_("Anciennes photos et favoris mis en avant, albums et polaroïds."),
        "settings": lambda: {"layout_override": "auto", "unique_enabled": True, "compositions_enabled": True,
                             "compositions_disabled": _only("album", "polaroids", "carnet", "mur", "pellicule", "annees70"),
                             "compositions_every": 4, "display_duration": 12, "anniversary_boost_enabled": True, "pan_zoom_enabled": True},
    },
    "voyage": {
        "label": N_("Voyage"), "icon": "fa-plane",
        "description": N_("Carnets de voyage et paysages : vacances, Japon, Islande, mer..."),
        "settings": lambda: {"layout_override": "auto", "unique_enabled": True, "compositions_enabled": True,
                             "compositions_disabled": _only("vacances", "carnet", "islande", "japon", "fuji", "hokusai", "france",
                                                            "montagne", "mer", "plage", "pellicule"),
                             "compositions_every": 3, "display_duration": 10},
    },
    "zen": {
        "label": N_("Zen"), "icon": "fa-leaf",
        "description": N_("Une photo à la fois, lente, avec un léger mouvement."),
        "settings": lambda: {"layout_override": "unique", "display_duration": 20, "transition_enabled": True,
                             "transition_type": "fade", "transition_duration": 2.5, "pan_zoom_enabled": True},
    },
}
MINE = "perso"


def apply(config, key):
    """Applique une ambiance à une copie de la configuration et la retourne. `MINE` restaure les réglages d'origine."""
    config = dict(config)
    backup = dict(config.get("ambiance_backup") or {})
    if key == MINE:
        for name, value in backup.items():
            if value is None:
                config.pop(name, None)  # réglage absent à l'origine : la valeur par défaut s'applique
            else:
                config[name] = value
        config["ambiance_backup"] = {}
        config["ambiance"] = MINE
        return config
    if key not in AMBIANCES:
        raise ValueError("Ambiance inconnue.")
    changes = AMBIANCES[key]["settings"]()
    for name in changes:  # mémoriser la valeur d'origine de chaque réglage, une seule fois
        if name not in backup:
            backup[name] = config.get(name)
    config.update(changes)
    config["ambiance_backup"] = backup
    config["ambiance"] = key
    return config


def listing(current):
    return [{"key": k, "label": v["label"], "icon": v["icon"], "description": v["description"], "active": k == current}
            for k, v in AMBIANCES.items()]
