"""Musique : enceinte Bluetooth, compte Spotify (association du cadre et pilotage depuis l'interface)."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from utils import bluetooth_control
from web.routes_home import _service_active


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
