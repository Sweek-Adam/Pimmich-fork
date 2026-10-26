"""
Mode grands-parents : une page très simple pour le téléphone, à très gros boutons (photo affichée, suivante, pause,
❤️, un mot écrit ou dit à voix haute, allumer ou éteindre le cadre).

On l'ouvre avec un lien spécial (créé par un administrateur, à ajouter à l'écran d'accueil du téléphone) : le
téléphone est alors reconnu pendant un an, sans mot de passe. Réseau de la maison seulement (la page n'est jamais
publiée sur internet) ; le lien peut être changé à tout moment, l'ancien cesse alors de marcher.
"""
import secrets
from functools import wraps

from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from utils import messages_manager


def _token_ok(given):
    token = load_config().get("simple_link_token") or ""
    return bool(token and given and secrets.compare_digest(str(given), token))


COOKIE = "pimmich_simple"
COOKIE_DAYS = 365


def _allowed():
    """Compte connecté, ou téléphone reconnu par le lien (cookie à part : les sessions des comptes ne changent pas)."""
    return bool(session.get("logged_in")) or _token_ok(request.cookies.get(COOKIE))


def simple_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if _allowed():
            return view(*args, **kwargs)
        return jsonify({"success": False, "message": _("Ouvrez d'abord le lien du cadre.")}), 401
    return wrapper


@app.route('/simple')
def simple_page():
    given = request.args.get("k")
    if given:
        if not _token_ok(given):
            return render_template("guest_link_invalid.html.jinja"), 401
        response = redirect(url_for("simple_page"))
        response.set_cookie(COOKIE, given, max_age=COOKIE_DAYS * 86400, httponly=True, samesite="Lax", secure=request.is_secure)
        return response
    if not _allowed():
        return render_template("guest_link_invalid.html.jinja"), 401
    config = load_config()
    return render_template("simple.html.jinja", name=config.get("simple_name") or "", has_frames=bool(config.get("family_frames")))


@app.route('/simple/now')
@simple_required
def simple_now_api():
    try:
        photo = Path(CURRENT_PHOTO_FILE).read_text().strip()
    except OSError:
        photo = ""
    running = is_slideshow_running()
    show = running and photo.startswith(("prepared/", "compositions/"))
    return jsonify({"success": True, "running": running, "photo": photo if show else None,
                    "url": url_for("static", filename=photo) if show else None})


@app.route('/simple/action', methods=['POST'])
@simple_required
def simple_action_api():
    from utils import reactions, slideshow_commands
    action = (request.get_json(silent=True) or {}).get("action")
    running = is_slideshow_running()
    if action in ("next", "previous", "pause"):
        if not running:
            return jsonify({"success": False, "message": _("Le cadre est éteint.")}), 409
        try:
            slideshow_commands.send(action)
        except (OSError, ValueError):
            return jsonify({"success": False, "message": _("Le cadre ne répond pas.")}), 409
        return jsonify({"success": True})
    if action == "love":
        try:
            photo = Path(CURRENT_PHOTO_FILE).read_text().strip()
        except OSError:
            photo = ""
        if not running or not photo:
            return jsonify({"success": False, "message": _("Le cadre est éteint.")}), 409
        reactions.add(photo, "love", who=load_config().get("simple_name") or "")
        return jsonify({"success": True, "message": "❤️"})
    if action == "heart":
        from web.routes_frames import send_heart_to_all
        count = send_heart_to_all()
        if not count:
            return jsonify({"success": False, "message": _("Les autres cadres ne répondent pas.")}), 502
        return jsonify({"success": True, "message": _("Des cœurs s'envolent sur %(count)s cadre(s) de la famille.", count=count)})
    if action in ("sleep", "wake"):
        if (action == "sleep") == running:
            from web.routes_slideshow import toggle_sleep
            threading.Thread(target=toggle_sleep, daemon=True, name="simple-sleep").start()
        return jsonify({"success": True, "message": _("Le cadre s'éteint.") if action == "sleep" else _("Le cadre s'allume.")})
    return jsonify({"success": False, "message": _("Action inconnue.")}), 400


def _publish():
    config = load_config()
    if messages_manager.SOURCE_NAME not in config.get("display_sources", []):
        save_config(dict(config, display_sources=list(config.get("display_sources", [])) + [messages_manager.SOURCE_NAME]))
    if is_slideshow_running():
        restart_slideshow_for_update()


@app.route('/simple/message', methods=['POST'])
@simple_required
def simple_message_api():
    data = request.get_json(silent=True) or {}
    config = load_config()
    name = config.get("simple_name") or ""
    try:
        messages_manager.create_message("", str(data.get("text") or "")[:300], name, "pastel", None, name or _("Mode simple"),
                                        int(config.get("display_width", 1920)), int(config.get("display_height", 1080)))
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    _publish()
    return jsonify({"success": True, "message": _("Votre mot s'affiche sur le cadre.")})


@app.route('/simple/voice', methods=['POST'])
@simple_required
def simple_voice_api():
    config = load_config()
    name = config.get("simple_name") or ""
    file = request.files.get("voice")
    try:
        messages_manager.create_voice(file.read() if file else b"", name, name or _("Mode simple"),
                                      int(config.get("display_width", 1920)), int(config.get("display_height", 1080)), guest=False)
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    _publish()
    return jsonify({"success": True, "message": _("Votre message sera lu par le cadre.")})


@app.route('/api/simple_link', methods=['GET', 'POST', 'DELETE'])
@admin_required
def simple_link_api():
    """Lien du mode grands-parents : le créer (ou le changer), le supprimer, régler le prénom affiché."""
    config = dict(load_config())
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        if "name" in data:
            config["simple_name"] = str(data["name"] or "").strip()[:40]
        if data.get("renew") or not config.get("simple_link_token"):
            config["simple_link_token"] = secrets.token_urlsafe(18)
        save_config(config)
    elif request.method == 'DELETE':
        config.pop("simple_link_token", None)
        save_config(config)
    token = config.get("simple_link_token")
    return jsonify({"success": True, "name": config.get("simple_name") or "", "link": _link(token) if token else None})


def _link(token):
    """Adresse du cadre sur le Wi-Fi de la maison (comme le QR code des invités)."""
    from utils.platform_info import guest_base_url
    from web.routes_home import _local_ip
    return f"{guest_base_url(_local_ip())}/simple?k={token}"


@app.route('/api/simple_link/qr.png')
@admin_required
def simple_link_qr():
    import io
    import qrcode
    from flask import send_file
    token = load_config().get("simple_link_token")
    if not token:
        abort(404)
    qr = qrcode.QRCode(border=2, box_size=10)
    qr.add_data(_link(token))
    qr.make(fit=True)
    buffer = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buffer, "PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png", max_age=0)
