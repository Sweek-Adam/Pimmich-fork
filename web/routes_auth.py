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


@app.route('/change_password', methods=['POST'])
@login_required
def change_password_route():
    """Gère la modification du mot de passe de l'interface."""
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not new_password or not confirm_password:
        flash(_("Les deux champs de mot de passe sont requis."), "danger")
        return redirect(url_for('configure'))

    if new_password != confirm_password:
        flash(_("Les mots de passe ne correspondent pas."), "danger")
        return redirect(url_for('configure'))
    
    if len(new_password) < 6:
        flash(_("Le mot de passe doit contenir au moins 6 caractères."), "warning")
        return redirect(url_for('configure'))

    try:
        username = session.get('username')
        if username and username != load_credentials().get('username'):
            user_manager.set_password(username, new_password)
        else:
            change_password(new_password)
        flash(_("Mot de passe mis à jour avec succès. Il sera nécessaire pour votre prochaine connexion."), "success")
    except Exception as e:
        flash(_("Erreur lors du changement de mot de passe : %(error)s", error=e), "danger")

    return redirect(url_for('configure'))


@app.route('/users/create', methods=['POST'])
@admin_required
def create_user_route():
    """Crée un compte utilisateur (réservé aux administrateurs)."""
    try:
        user_manager.create_user(request.form.get('username'), request.form.get('password'), request.form.get('role', 'user'),
                                 reserved_names=(load_credentials().get('username', 'admin'),))
        flash(_("Compte « %(name)s » créé.", name=request.form.get('username', '').strip()), "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for('configure'))


@app.route('/users/<username>/delete', methods=['POST'])
@admin_required
def delete_user_route(username):
    if username == session.get('username'):
        flash(_("Vous ne pouvez pas supprimer votre propre compte."), "error")
        return redirect(url_for('configure'))
    try:
        user_manager.delete_user(username)
        flash(_("Compte « %(name)s » supprimé.", name=username), "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for('configure'))


@app.route('/users/<username>/password', methods=['POST'])
@admin_required
def reset_user_password_route(username):
    try:
        user_manager.set_password(username, request.form.get('password'))
        flash(_("Mot de passe de « %(name)s » modifié.", name=username), "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for('configure'))


@app.route('/users/<username>/role', methods=['POST'])
@admin_required
def set_user_role_route(username):
    if username == session.get('username'):
        flash(_("Vous ne pouvez pas modifier votre propre rôle."), "error")
        return redirect(url_for('configure'))
    try:
        user_manager.set_role(username, request.form.get('role'))
        flash(_("Rôle de « %(name)s » modifié.", name=username), "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for('configure'))
