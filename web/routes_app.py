"""
Nouvelle interface (Vue 3, compilée dans static/app/) : page /app et ses traductions.
Elle s'appuie sur les mêmes API JSON que l'interface classique ; les rubriques pas encore refaites renvoient vers
l'interface classique (/configure#tab-...). Sources : frontend/ (voir frontend/README.md).
"""
import json

from flask import make_response
from flask_babel import get_locale, gettext

from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from utils import babel_frontend

APP_INDEX = BASE_DIR / "static" / "app" / "index.html"


@app.route('/app', methods=['GET'])
@login_required
def new_interface():
    try:
        page = APP_INDEX.read_text(encoding="utf-8")
    except OSError:
        return redirect(url_for('configure'))  # interface pas encore compilée
    boot = {"lang": str(get_locale() or "fr"), "user": session.get("username") or "", "admin": bool(is_admin()),
            "classic": url_for('configure')}
    # « </ » échappé : le JSON ne peut pas fermer la balise <script>
    script = "<script>window.PIMMICH = " + json.dumps(boot, ensure_ascii=False).replace("</", "<\\/") + ";</script>"
    response = make_response(page.replace("<!--PIMMICH_BOOT-->", script, 1))
    response.headers["Cache-Control"] = "no-store"
    response.delete_cookie(UI_COOKIE)  # retour à la nouvelle interface : elle redevient celle par défaut
    return response


@app.after_request
def remember_classic_interface(response):
    """« Interface classique » choisie depuis la nouvelle : retenue dans ce navigateur."""
    if request.path == url_for('configure') and request.args.get("ui") == "classic":
        response.set_cookie(UI_COOKIE, "classic", max_age=365 * 24 * 3600, samesite="Lax", httponly=True)
    return response


@app.route('/api/i18n', methods=['GET'])
@login_required
def i18n_api():
    """Traductions des textes de la nouvelle interface dans la langue demandée (?lang=…) ou celle de la session."""
    lang = str(get_locale() or "fr")
    messages = {}
    if lang != "fr":
        for msgid in babel_frontend.frontend_msgids():
            translated = gettext(msgid)
            if translated and translated != msgid:
                messages[msgid] = translated
    return jsonify({"success": True, "lang": lang, "messages": messages})
