"""
Jeu « Où et quand ? » : page /jeu pour les téléphones (Wi-Fi de la maison), comme la page des invités.
Le cadre affiche la partie (local_slideshow.run_game) ; ici, on crée la partie, on s'inscrit et on répond.
"""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from utils import family_game, rate_limit

COOKIE = "pimmich_player"


def _labels():
    from utils import members, user_manager
    names = [u["username"] for u in user_manager.list_users()]
    return {source: members.label(source, names) for source in members.sources()}


def _disabled():
    if not load_config().get("family_game_enabled", True):
        return jsonify({"success": False, "message": _("Le jeu est désactivé sur ce cadre.")}), 403
    return None


@app.route('/jeu')
def game_page():
    return render_template('game.html.jinja', enabled=load_config().get("family_game_enabled", True))


@app.route('/jeu/state')
def game_state_api():
    view = family_game.public_view(family_game.current(), request.cookies.get(COOKIE))
    translate = _
    if view.get("kind"):
        view["question"] = translate(family_game.QUESTIONS[view["kind"]])
    view["max_year"] = datetime.now().year
    return jsonify({"success": True, **view})


@app.route('/jeu/new', methods=['POST'])
def game_new_api():
    disabled = _disabled()
    if disabled:
        return disabled
    if not rate_limit.allow(("game", request.remote_addr), 6, 3600):
        return jsonify({"success": False, "message": _("Trop de parties lancées : réessayez dans un moment.")}), 429
    if family_game.running():
        return jsonify({"success": False, "message": _("Une partie est déjà en cours.")}), 409
    from utils import photo_index
    data = request.get_json(silent=True) or {}
    try:
        rounds = max(3, min(12, int(data.get("rounds", 6))))
    except (TypeError, ValueError):
        rounds = 6
    state = family_game.new_game(photo_index.load(), _labels(), rounds)
    if not state:
        return jsonify({"success": False, "message": _("Pas assez de photos datées pour jouer.")}), 400
    return jsonify({"success": True, "message": _("Partie créée : entrez votre prénom pour jouer.")})


@app.route('/jeu/join', methods=['POST'])
def game_join_api():
    disabled = _disabled()
    if disabled:
        return disabled
    data = request.get_json(silent=True) or {}
    player = family_game.join(data.get("name"), request.cookies.get(COOKIE))
    if not player:
        return jsonify({"success": False, "message": _("Impossible de rejoindre la partie (prénom manquant ou partie complète).")}), 400
    response = jsonify({"success": True})
    response.set_cookie(COOKIE, player, max_age=6 * 3600, httponly=True, samesite="Lax")
    return response


@app.route('/jeu/start', methods=['POST'])
def game_start_api():
    if not family_game.start():
        return jsonify({"success": False, "message": _("La partie ne peut pas commencer (aucun joueur ?).")}), 400
    return jsonify({"success": True})


@app.route('/jeu/answer', methods=['POST'])
def game_answer_api():
    data = request.get_json(silent=True) or {}
    if not family_game.answer(request.cookies.get(COOKIE), data.get("value")):
        return jsonify({"success": False, "message": _("Réponse non prise en compte (trop tard ou déjà répondu).")}), 400
    return jsonify({"success": True})


@app.route('/api/game/stop', methods=['POST'])
@login_required
def game_stop_api():
    family_game.stop()
    return jsonify({"success": True, "message": _("Partie arrêtée : le diaporama reprend.")})
