"""Connexion, déconnexion, mot de passe et comptes utilisateurs."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from utils import login_throttle
from web.core import _


@app.route('/')
def home():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        ip = login_throttle.client_ip(request)
        wait = login_throttle.seconds_locked(username, ip)
        if wait:
            logger.warning(f"[Sécurité] Connexion refusée (trop de tentatives) pour '{username}' depuis {ip}")
            flash(_("Trop de tentatives de connexion. Réessayez dans %(minutes)s minute(s).", minutes=(wait + 59) // 60), "error")
            return render_template('login.html.jinja'), 429
        role = None
        if username and password:
            role = 'admin' if check_credentials(username, password) else user_manager.authenticate(username, password)
        if role:
            login_throttle.register_success(username, ip)
            session['logged_in'] = True
            session['username'] = username
            session['role'] = role
            flash(_("Connexion réussie"), "success")
            return redirect(url_for('configure'))
        else:
            login_throttle.register_failure(username, ip)
            logger.warning(f"[Sécurité] Échec de connexion pour '{username}' depuis {ip}")
            flash(_("Identifiants invalides"), "error")
    return render_template('login.html.jinja')


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('role', None)
    flash(_("Déconnexion réussie"), "success")
    return redirect(url_for('login'))


# --- Comptes : chaque action renvoie (succès, message) ; utilisée par les formulaires classiques et par l'API JSON ---

def _change_own_password(new_password, confirm_password):
    if not new_password or not confirm_password:
        return False, _("Les deux champs de mot de passe sont requis.")
    if new_password != confirm_password:
        return False, _("Les mots de passe ne correspondent pas.")
    if len(new_password) < 6:
        return False, _("Le mot de passe doit contenir au moins 6 caractères.")
    try:
        username = session.get('username')
        if username and username != load_credentials().get('username'):
            user_manager.set_password(username, new_password)
        else:
            change_password(new_password)
    except Exception as e:
        return False, _("Erreur lors du changement de mot de passe : %(error)s", error=e)
    return True, _("Mot de passe mis à jour avec succès. Il sera nécessaire pour votre prochaine connexion.")


def _create_user(username, password, role):
    try:
        user_manager.create_user(username, password, role or 'user', reserved_names=(load_credentials().get('username', 'admin'),))
    except ValueError as e:
        return False, str(e)
    return True, _("Compte « %(name)s » créé.", name=(username or '').strip())


def _delete_user(username):
    if username == session.get('username'):
        return False, _("Vous ne pouvez pas supprimer votre propre compte.")
    try:
        user_manager.delete_user(username)
    except ValueError as e:
        return False, str(e)
    return True, _("Compte « %(name)s » supprimé.", name=username)


def _reset_password(username, password):
    try:
        user_manager.set_password(username, password)
    except ValueError as e:
        return False, str(e)
    return True, _("Mot de passe de « %(name)s » modifié.", name=username)


def _set_role(username, role):
    if username == session.get('username'):
        return False, _("Vous ne pouvez pas modifier votre propre rôle.")
    try:
        user_manager.set_role(username, role)
    except ValueError as e:
        return False, str(e)
    return True, _("Rôle de « %(name)s » modifié.", name=username)


def _flash_back(result, error_category="error"):
    ok, message = result
    flash(message, "success" if ok else error_category)
    return redirect(url_for('configure'))


@app.route('/change_password', methods=['POST'])
@login_required
def change_password_route():
    """Gère la modification du mot de passe de l'interface."""
    return _flash_back(_change_own_password(request.form.get('new_password'), request.form.get('confirm_password')), "danger")


@app.route('/users/create', methods=['POST'])
@admin_required
def create_user_route():
    """Crée un compte utilisateur (réservé aux administrateurs)."""
    return _flash_back(_create_user(request.form.get('username'), request.form.get('password'), request.form.get('role', 'user')))


@app.route('/users/<username>/delete', methods=['POST'])
@admin_required
def delete_user_route(username):
    return _flash_back(_delete_user(username))


@app.route('/users/<username>/password', methods=['POST'])
@admin_required
def reset_user_password_route(username):
    return _flash_back(_reset_password(username, request.form.get('password')))


@app.route('/users/<username>/role', methods=['POST'])
@admin_required
def set_user_role_route(username):
    return _flash_back(_set_role(username, request.form.get('role')))


# --- Même chose en JSON (nouvelle interface) ---

def _json(result):
    ok, message = result
    return jsonify({"success": ok, "message": message}), (200 if ok else 400)


@app.route('/api/accounts', methods=['GET'])
@login_required
def accounts_api():
    """Mon compte, et la liste des comptes pour un administrateur (jamais les mots de passe)."""
    users = [{"username": u["username"], "role": u.get("role", "user"), "created": u.get("created", "")}
             for u in user_manager.list_users()] if is_admin() else []
    return jsonify({"success": True, "me": session.get('username') or "", "admin": bool(is_admin()),
                    "main_admin": load_credentials().get('username', 'admin'), "users": users})


@app.route('/api/accounts/password', methods=['POST'])
@login_required
def account_password_api():
    data = request.get_json(silent=True) or {}
    return _json(_change_own_password(data.get('new_password'), data.get('confirm_password')))


@app.route('/api/accounts', methods=['POST'])
@admin_required
def account_create_api():
    data = request.get_json(silent=True) or {}
    return _json(_create_user(data.get('username'), data.get('password'), data.get('role', 'user')))


@app.route('/api/accounts/<username>', methods=['DELETE'])
@admin_required
def account_delete_api(username):
    return _json(_delete_user(username))


@app.route('/api/accounts/<username>/password', methods=['POST'])
@admin_required
def account_reset_password_api(username):
    return _json(_reset_password(username, (request.get_json(silent=True) or {}).get('password')))


@app.route('/api/accounts/<username>/role', methods=['POST'])
@admin_required
def account_role_api(username):
    return _json(_set_role(username, (request.get_json(silent=True) or {}).get('role')))
