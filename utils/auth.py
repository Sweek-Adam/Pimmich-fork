from functools import wraps
from flask import session, redirect, url_for, request, jsonify, flash
from flask_babel import _

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def is_admin():
    # Les sessions ouvertes avant l'ajout des rôles appartiennent forcément au compte admin principal
    return session.get('role', 'admin') == 'admin'

def admin_required(f):
    """Réserve une route aux comptes administrateurs."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        if not is_admin():
            message = _("Action réservée aux administrateurs.")
            if request.path.startswith('/api/') or request.is_json or request.method == 'DELETE':
                return jsonify({"success": False, "message": message}), 403
            flash(message, "error")
            return redirect(url_for('configure'))
        return f(*args, **kwargs)
    return decorated_function

def login_or_internal_required(f):
    """Route accessible aux comptes connectés et aux processus locaux de Pimmich (commande vocale, bouton)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from utils.security import is_internal_request
        if not session.get('logged_in') and not is_internal_request(request):
            if request.path.startswith('/api/'):
                return jsonify({"success": False, "message": "Authentification requise."}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
