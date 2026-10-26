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


# --- Photomaton : tirages 10 × 15 sur une imprimante Wi-Fi (utils/photobooth.py) ---

def _original_of(prepared_rel):
    """Fichier d'origine d'une photo préparée (chemin relatif à static/), sinon la photo préparée elle-même."""
    import glob
    path = BASE_DIR / "static" / prepared_rel
    if path.parent.parent.name == "prepared":
        folder = BASE_DIR / "static" / "photos" / path.parent.name
        for candidate in sorted(folder.glob(glob.escape(path.stem) + ".*")) if folder.is_dir() else []:
            if candidate.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"):
                return candidate
    return path


def print_photo(path, config=None):
    """Imprime un tirage de cette photo (ouverte, réduite, légendée) ; retourne l'identifiant du travail."""
    from PIL import Image
    from utils import photobooth
    config = config or load_config()
    with Image.open(path) as image:
        image.draft("RGB", (2400, 2400))
        image.load()
        title, subtitle = photobooth.caption(config)
        return photobooth.send(image.copy(), title, subtitle)


@app.route('/api/photobooth', methods=['GET', 'PUT'])
@admin_required
def photobooth_api():
    from utils import photobooth
    config = dict(load_config())
    if request.method == 'PUT':
        data = request.get_json(silent=True) or {}
        wanted = photobooth.settings(config)
        for key in ("enabled", "auto"):
            if key in data:
                wanted[key] = bool(data[key])
        for key in ("per_guest", "max_auto"):
            if key in data:
                try:
                    wanted[key] = int(data[key])
                except (TypeError, ValueError):
                    return jsonify({"success": False, "message": _("Valeur invalide.")}), 400
        if data.get("uri") and data["uri"] != wanted["uri"]:
            ok, error = photobooth.setup(str(data["uri"]))
            if not ok:
                return jsonify({"success": False, "message": _("Imprimante impossible à ajouter : %(error)s", error=error)}), 400
            wanted["uri"], wanted["name"] = str(data["uri"]), str(data.get("name") or "")[:80]
        config["photobooth"] = photobooth.settings(dict(config, photobooth=wanted))
        save_config(config)
        return jsonify({"success": True, "message": _("Photomaton enregistré."), "settings": config["photobooth"]})
    return jsonify({"success": True, "settings": photobooth.settings(config)})


@app.route('/api/photobooth/printers')
@admin_required
def photobooth_printers_api():
    from utils import photobooth
    return jsonify({"success": True, "printers": photobooth.discover()})


@app.route('/api/photobooth/test', methods=['POST'])
@admin_required
def photobooth_test_api():
    """Tirage d'essai : la photo affichée en ce moment (ou une photo de la bibliothèque)."""
    from utils import photobooth
    if not photobooth.settings(load_config())["uri"]:
        return jsonify({"success": False, "message": _("Choisissez d'abord l'imprimante.")}), 400
    try:
        photo = Path(CURRENT_PHOTO_FILE).read_text().strip()
    except OSError:
        photo = ""
    path = _original_of(photo) if photo.startswith("prepared/") else next(PREPARED_DIR.glob("*/*.jpg"), None)
    if not path or not Path(path).is_file():
        return jsonify({"success": False, "message": _("Aucune photo à imprimer.")}), 400
    try:
        job = print_photo(path)
    except Exception as e:
        return jsonify({"success": False, "message": _("Impression impossible : %(error)s", error=str(e)[:200])}), 502
    return jsonify({"success": True, "message": _("Tirage d'essai envoyé à l'imprimante (%(job)s).", job=job)})


@app.route('/upload/print', methods=['POST'])
def guest_print_api():
    """Invité pendant la fête : imprimer la photo affichée sur le cadre (quelques tirages par invité)."""
    from utils import photobooth, rate_limit
    from web.routes_guests import _guest_key, _now_showing
    config = load_config()
    booth = photobooth.settings(config)
    if not (booth["enabled"] and booth["uri"] and party.active(config)):
        return jsonify({"success": False, "message": _("Le photomaton n'est pas ouvert.")}), 403
    key, _limit = _guest_key()
    if not rate_limit.allow(("impression", key), 10, 3600):
        return jsonify({"success": False, "message": _("Doucement ! Réessayez dans un moment.")}), 429
    photo = _now_showing()
    if not photo or not photo.startswith("prepared/"):
        return jsonify({"success": False, "message": _("Attendez qu'une photo soit à l'écran.")}), 409
    if not photobooth.take(f"guest:{key}", booth["per_guest"]):
        return jsonify({"success": False, "message": _("Vous avez déjà imprimé vos %(count)s tirages.", count=booth["per_guest"])}), 429
    try:
        print_photo(_original_of(photo), config)
    except Exception as e:
        logger.warning(f"[Photomaton] {e}")
        return jsonify({"success": False, "message": _("L'imprimante ne répond pas.")}), 502
    return jsonify({"success": True, "message": _("C'est parti ! Votre photo sort de l'imprimante.")})


def auto_print(original):
    """Photo reçue pendant la fête : imprimée d'office si le photomaton automatique est activé (plafond par fête)."""
    from utils import photobooth
    config = load_config()
    booth = photobooth.settings(config)
    if not (booth["enabled"] and booth["auto"] and booth["uri"]) or not photobooth.take("auto", booth["max_auto"]):
        return
    try:
        print_photo(original, config)
        logger.info(f"[Photomaton] {Path(original).name} imprimée")
    except Exception as e:
        logger.warning(f"[Photomaton] {Path(original).name} non imprimée : {e}")
