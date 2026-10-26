"""Légendes proposées automatiquement (voir utils/auto_captions.py) : réglages, essai, travail de la nuit."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from utils import auto_captions

_running = threading.Event()


def _library_keys():
    from utils import photo_index
    return [k for k in photo_index.load() if k.split("/", 1)[0] != "messages" and (PREPARED_DIR / k).is_file()]


def run_batch(config, limit=auto_captions.PER_NIGHT, stop=None):
    """Propose des légendes pour les photos qui n'en ont pas encore ; retourne le nombre de photos traitées."""
    if _running.is_set():
        return 0
    _running.set()
    done = 0
    try:
        keys = _library_keys()
        if config.get("auto_captions_mode") == "claude":
            if not config.get("anthropic_api_key"):
                return 0
            import anthropic
            client = anthropic.Anthropic(api_key=config["anthropic_api_key"])
            for key in auto_captions.pending(keys, how="claude")[:limit]:
                if stop and stop():
                    break
                try:
                    result = auto_captions.claude_caption(config, PREPARED_DIR / key, client=client)
                except anthropic.APIStatusError as e:
                    logger.warning(f"[Légendes] Claude refuse la requête ({e.status_code}) : arrêt pour cette nuit")
                    break
                except anthropic.APIConnectionError:
                    logger.info("[Légendes] Claude injoignable : arrêt pour cette nuit")
                    break
                if result:
                    caption, tags = result
                    auto_captions.store({key: {"caption": caption, "tags": tags, "how": "claude"}})
                done += 1
        else:
            found = auto_captions.immich_tags(config, keys)
            auto_captions.store(found)
            done = len(found)
    finally:
        _running.clear()
    return done


@app.route('/api/auto_captions', methods=['GET', 'PUT'])
@admin_required
def auto_captions_api():
    config = load_config()
    if request.method == 'PUT':
        data = request.get_json(silent=True) or {}
        config = dict(config)
        if "enabled" in data:
            config["auto_captions_enabled"] = bool(data["enabled"])
        if data.get("mode") in ("immich", "claude"):
            config["auto_captions_mode"] = data["mode"]
        if data.get("api_key"):
            config["anthropic_api_key"] = str(data["api_key"]).strip()[:300]
        save_config(config)
        return jsonify({"success": True, "message": _("Légendes automatiques enregistrées.")})
    from utils import immich_search
    data = auto_captions.load()
    return jsonify({"success": True, "enabled": bool(config.get("auto_captions_enabled")), "mode": config.get("auto_captions_mode", "immich"),
                    "has_key": bool(config.get("anthropic_api_key")), "immich": immich_search.available(config),
                    "done": len(data), "described": sum(1 for e in data.values() if e.get("caption")), "running": _running.is_set()})


@app.route('/api/auto_captions/run', methods=['POST'])
@admin_required
def auto_captions_run_api():
    """Essai tout de suite, sur quelques photos (Claude) ou toute la bibliothèque (Immich)."""
    config = load_config()
    if config.get("auto_captions_mode") == "claude" and not config.get("anthropic_api_key"):
        return jsonify({"success": False, "message": _("Saisissez d'abord la clé d'API d'Anthropic.")}), 400
    if _running.is_set():
        return jsonify({"success": False, "message": _("Des légendes sont déjà en cours de création.")}), 409
    threading.Thread(target=run_batch, args=(config, 10), daemon=True, name="auto-captions").start()
    return jsonify({"success": True, "message": _("C'est parti : les propositions apparaissent dans la bibliothèque au fur et à mesure.")})
