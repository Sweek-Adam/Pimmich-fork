"""Citation du jour : réglages, mots de la famille, aperçu."""
import io

from flask import send_file
from flask_babel import force_locale

from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from utils import quotes


def refresh_quote(config=None):
    """Prépare l'image du jour dans la langue du cadre."""
    config = config or load_config()
    with app.app_context(), force_locale(config.get("language") or "fr"):
        translate = _
        return quotes.refresh(config, translate)


def _set_source(config, enabled):
    sources = [s for s in config.get("display_sources", []) if s != quotes.SOURCE]
    config["display_sources"] = sources + ([quotes.SOURCE] if enabled else [])


@app.route('/api/quotes', methods=['GET'])
@login_required
def quotes_api():
    config = load_config()
    today = quotes.of_the_day(config)
    return jsonify({"success": True, "enabled": config.get("quote_enabled", False), "mode": config.get("quote_mode", "all"),
                    "style": config.get("quote_style", "auto"), "family": quotes.family(config), "today": today,
                    "styles": list(quotes.STYLES)})


@app.route('/api/quotes', methods=['POST'])
@login_required
def quotes_save_api():
    data = request.get_json(silent=True) or {}
    config = dict(load_config())
    if "enabled" in data:
        config["quote_enabled"] = bool(data["enabled"])
        _set_source(config, config["quote_enabled"])
    if data.get("mode") in quotes.MODES:
        config["quote_mode"] = data["mode"]
    if data.get("style") in quotes.STYLES + ("auto",):
        config["quote_style"] = data["style"]
    if isinstance(data.get("family"), list):
        config["quotes_family"] = [{"text": str(q.get("text", "")).strip()[:300], "author": str(q.get("author", "")).strip()[:80]}
                                   for q in data["family"] if isinstance(q, dict) and str(q.get("text", "")).strip()][:200]
    save_config(config)
    threading.Thread(target=refresh_quote, args=(config,), daemon=True, name="quote").start()
    return jsonify({"success": True, "message": _("Citation du jour enregistrée.")})


@app.route('/api/quotes/preview', methods=['GET'])
@login_required
def quotes_preview_api():
    config = dict(load_config(), display_width=960, display_height=540)
    translate = _
    image = quotes.render(config, 960, 540, translate)
    if image is None:
        abort(404)
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=85)
    buffer.seek(0)
    return send_file(buffer, mimetype="image/jpeg", max_age=0)
