"""Home Assistant (MQTT) : réglages et pont entre MQTT et le cadre."""
import os
import signal
import threading
from datetime import date

from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from utils import ambiances, messages_manager

_bridge = {"bridge": None, "thread": None}


def _actions():
    def slideshow(on):
        config = dict(load_config())
        config["manual_override"] = "start" if on else "stop"
        save_config(config)
        if on and not is_slideshow_running():
            set_display_power(on=True)
            start_slideshow()
        elif not on and is_slideshow_running():
            stop_slideshow()

    def next_photo():
        try:
            os.kill(int(open("/tmp/pimmich_slideshow.pid").read()), signal.SIGUSR1)
        except (OSError, ValueError):
            pass

    def ambiance(key):
        save_config(ambiances.apply(load_config(), key))
        restart_slideshow_process()

    def alert(text):
        with app.app_context():
            config = load_config()
            messages_manager.create_message(_("Alerte de la maison"), text, "Home Assistant", "festif", date.today().isoformat(),
                                            "Home Assistant", int(config.get("display_width", 1920)), int(config.get("display_height", 1080)))
        if messages_manager.SOURCE_NAME not in load_config().get("display_sources", []):
            config = dict(load_config())
            config["display_sources"] = config.get("display_sources", []) + [messages_manager.SOURCE_NAME]
            save_config(config)
        if is_slideshow_running():
            restart_slideshow_for_update()
    return {"slideshow": slideshow, "next": next_photo, "ambiance": ambiance, "alert": alert}


def _state():
    from utils import now_playing
    config = load_config()
    try:
        photo = open(CURRENT_PHOTO_FILE).read().strip().rsplit("/", 1)[-1]
    except OSError:
        photo = ""
    playing = now_playing.current(())
    return {"slideshow": is_slideshow_running(), "ambiance": config.get("ambiance") or "", "ambiances": list(ambiances.AMBIANCES),
            "photo": photo, "music": " — ".join(p for p in ((playing or {}).get("title"), (playing or {}).get("artist")) if p)}


def restart_bridge():
    """(Re)lance le pont MQTT selon les réglages (arrêté s'il est désactivé)."""
    from utils import mqtt_bridge
    if _bridge["bridge"]:
        _bridge["bridge"].stop()
        _bridge["bridge"] = None
    config = load_config()
    if not config.get("mqtt_enabled") or not config.get("mqtt_host"):
        return False
    bridge = mqtt_bridge.Bridge(config, _actions(), _state)
    thread = threading.Thread(target=bridge.run, daemon=True, name="mqtt")
    thread.start()
    _bridge.update(bridge=bridge, thread=thread)
    return True


@app.route('/api/homeassistant', methods=['GET'])
@admin_required
def homeassistant_api():
    config = load_config()
    bridge = _bridge["bridge"]
    return jsonify({"success": True, "enabled": config.get("mqtt_enabled", False), "host": config.get("mqtt_host", ""),
                    "port": config.get("mqtt_port", 1883), "user": config.get("mqtt_user", ""), "has_password": bool(config.get("mqtt_password")),
                    "device_name": config.get("mqtt_device_name", "Pimmich"), "connected": bool(bridge and bridge.connected)})


@app.route('/api/homeassistant', methods=['POST'])
@admin_required
def homeassistant_save_api():
    data = request.get_json(silent=True) or {}
    config = dict(load_config())
    for key, field in (("host", "mqtt_host"), ("user", "mqtt_user"), ("device_name", "mqtt_device_name")):
        if key in data:
            config[field] = str(data[key] or "").strip()[:120]
    if data.get("password"):
        config["mqtt_password"] = str(data["password"])[:200]
    try:
        config["mqtt_port"] = max(1, min(65535, int(data.get("port", config.get("mqtt_port", 1883)))))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": _("Port invalide.")}), 400
    config["mqtt_enabled"] = bool(data.get("enabled", config.get("mqtt_enabled")))
    save_config(config)
    started = restart_bridge()
    return jsonify({"success": True, "message": _("Connexion à Home Assistant lancée.") if started else _("Home Assistant désactivé.")})
