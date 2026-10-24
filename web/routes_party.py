"""Mode fête : lancer, suivre et arrêter (QR code à l'écran, photos des invités affichées aussitôt)."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from utils import party


def _payload(config):
    data = party.state(config)
    info = {"active": party.active(config), "name": data.get("name", ""), "until": data.get("until"), "started": data.get("started"),
            "only_party": data.get("only_party", True), "auto_approve": data.get("auto_approve", True), "source": data.get("source")}
    info.update(party.stats(config) if data.get("source") else {"photos": 0})
    return info


@app.route('/api/party', methods=['GET'])
@login_required
def party_api():
    return jsonify({"success": True, **_payload(load_config())})


@app.route('/api/party/start', methods=['POST'])
@login_required
def party_start_api():
    data = request.get_json(silent=True) or {}
    try:
        hours = int(data.get("hours", 6))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": _("Durée invalide.")}), 400
    config = party.start(load_config(), data.get("name"), hours, bool(data.get("only_party", True)), bool(data.get("auto_approve", True)))
    save_config(config)
    from web.routes_history import log
    log("party", _("Mode fête : %(name)s", name=config["party"]["name"]))
    restart_slideshow_for_update()
    return jsonify({"success": True, "message": _("C'est la fête ! Le QR code est à l'écran : les photos des invités s'affichent aussitôt."),
                    **_payload(config)})


@app.route('/api/party/stop', methods=['POST'])
@login_required
def party_stop_api():
    config = party.stop(load_config())
    save_config(config)
    restart_slideshow_for_update()
    return jsonify({"success": True, "message": _("Fin de la fête : le diaporama habituel reprend. L'album de la fête reste dans les sources."),
                    **_payload(config)})


def party_worker():
    """Fin automatique de la fête à l'heure prévue."""
    while True:
        try:
            config = load_config()
            data = party.state(config)
            if data.get("active") and not party.active(config):
                save_config(party.stop(config))
                logger.info(f"[Fête] « {data.get('name')} » terminée (heure prévue atteinte)")
                restart_slideshow_for_update()
        except Exception as e:
            logger.warning(f"[Fête] {e}")
        time.sleep(30)
