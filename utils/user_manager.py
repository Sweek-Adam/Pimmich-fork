"""
Gestion des comptes utilisateurs supplémentaires.

Le compte principal (admin) reste celui de /boot/firmware/credentials.json, créé par setup.sh.
Les autres comptes sont stockés dans config/users.json, avec leur mot de passe haché.
Rôles : 'admin' (accès complet) ou 'user' (pas de gestion des comptes ni d'actions système).
"""
import os
import re
import json
import threading
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

USERS_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'users.json')
ROLES = ('admin', 'user')
USERNAME_RE = re.compile(r'^[A-Za-z0-9_.-]{2,32}$')
MIN_PASSWORD_LENGTH = 6

_lock = threading.Lock()


def _load():
    try:
        with open(USERS_PATH, 'r') as f:
            return json.load(f).get('users', {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(users):
    os.makedirs(os.path.dirname(USERS_PATH), exist_ok=True)
    tmp = USERS_PATH + '.tmp'
    with open(tmp, 'w') as f:
        json.dump({'users': users}, f, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, USERS_PATH)


def list_users():
    """Retourne la liste des comptes supplémentaires (sans les hash), triée par nom."""
    return [{'username': name, 'role': u.get('role', 'user'), 'created': u.get('created', '')}
            for name, u in sorted(_load().items(), key=lambda item: item[0].lower())]


def authenticate(username, password):
    """Retourne le rôle du compte si les identifiants sont valides, sinon None."""
    user = _load().get(username)
    if user and check_password_hash(user.get('password_hash', ''), password):
        return user.get('role', 'user')
    return None


def _check_password(password):
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Le mot de passe doit contenir au moins {MIN_PASSWORD_LENGTH} caractères.")


def create_user(username, password, role, reserved_names=()):
    username = (username or '').strip()
    if not USERNAME_RE.match(username):
        raise ValueError("Nom d'utilisateur invalide (2 à 32 caractères : lettres, chiffres, '.', '_' ou '-').")
    if role not in ROLES:
        raise ValueError("Rôle invalide.")
    _check_password(password)
    with _lock:
        users = _load()
        if username in users or username in reserved_names:
            raise ValueError(f"Le compte '{username}' existe déjà.")
        users[username] = {
            'password_hash': generate_password_hash(password),
            'role': role,
            'created': datetime.now().strftime('%Y-%m-%d %H:%M'),
        }
        _save(users)


def delete_user(username):
    with _lock:
        users = _load()
        if username not in users:
            raise ValueError(f"Le compte '{username}' n'existe pas.")
        del users[username]
        _save(users)


def set_password(username, password):
    _check_password(password)
    with _lock:
        users = _load()
        if username not in users:
            raise ValueError(f"Le compte '{username}' n'existe pas.")
        users[username]['password_hash'] = generate_password_hash(password)
        _save(users)


def set_role(username, role):
    if role not in ROLES:
        raise ValueError("Rôle invalide.")
    with _lock:
        users = _load()
        if username not in users:
            raise ValueError(f"Le compte '{username}' n'existe pas.")
        users[username]['role'] = role
        _save(users)


def get_role(username):
    """Rôle actuel d'un compte supplémentaire, ou None s'il n'existe plus."""
    user = _load().get(username)
    return user.get('role', 'user') if user else None
