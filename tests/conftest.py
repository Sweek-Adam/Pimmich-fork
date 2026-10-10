"""
Configuration des tests.

Les tests s'exécutent sur une copie temporaire du projet : la configuration, les comptes,
les jetons et les photos de l'installation réelle ne sont jamais lus ni modifiés.
Lancement (depuis la racine du projet, avec l'environnement de Pimmich) :
    venv/bin/python -m pytest
"""
import os
import sys
import json
import shutil
import tempfile
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
COPIED = ["app.py", "web", "utils", "templates", "translations", "babel.cfg", "voice_control.py", "local_slideshow.py"]
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin-test-pass"

_SANDBOX = Path(tempfile.mkdtemp(prefix="pimmich-tests-"))
for name in COPIED:
    src = PROJECT_DIR / name
    if src.is_dir():
        shutil.copytree(src, _SANDBOX / name, ignore=shutil.ignore_patterns("__pycache__"))
    elif src.exists():
        shutil.copy2(src, _SANDBOX / name)
(_SANDBOX / "static").mkdir()
shutil.copytree(PROJECT_DIR / "static" / "pwa", _SANDBOX / "static" / "pwa")
(_SANDBOX / "config").mkdir()

# Compte administrateur principal de test
from werkzeug.security import generate_password_hash  # noqa: E402
_CREDENTIALS = _SANDBOX / "credentials.json"
_CREDENTIALS.write_text(json.dumps({
    "username": ADMIN_USERNAME,
    "password_hash": generate_password_hash(ADMIN_PASSWORD),
    "flask_secret_key": "test-secret-key",
}))
os.environ["PIMMICH_CREDENTIALS_PATH"] = str(_CREDENTIALS)

os.chdir(_SANDBOX)
sys.path.insert(0, str(_SANDBOX))

# Flask 2.3 lit werkzeug.__version__, retiré de Werkzeug 3 : nécessaire au client de test uniquement
import werkzeug  # noqa: E402
if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3"


@pytest.fixture(scope="session")
def sandbox():
    return _SANDBOX


@pytest.fixture(scope="session")
def app_module():
    import app as app_module
    # Ne jamais redémarrer le vrai diaporama pendant les tests (dans tous les modules qui l'importent)
    for module in list(sys.modules.values()):
        if getattr(module, "restart_slideshow_process", None) is not None and module.__name__ != "utils.slideshow_manager":
            module.restart_slideshow_process = lambda: None
    app_module.app.config["TESTING"] = True
    return app_module


@pytest.fixture()
def users_file(sandbox):
    """Repart d'une liste de comptes vide pour chaque test."""
    from utils import user_manager
    path = Path(user_manager.USERS_PATH)
    path.unlink(missing_ok=True)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture()
def client(app_module, users_file):
    return app_module.app.test_client()


def login(client, username, password):
    return client.post("/login", data={"username": username, "password": password},
                       headers={"Sec-Fetch-Site": "same-origin"})


@pytest.fixture()
def admin_client(client):
    login(client, ADMIN_USERNAME, ADMIN_PASSWORD)
    return client


@pytest.fixture()
def user_client(app_module, users_file):
    from utils import user_manager
    user_manager.create_user("marie", "secret123", "user", reserved_names=(ADMIN_USERNAME,))
    c = app_module.app.test_client()
    login(c, "marie", "secret123")
    return c


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_SANDBOX, ignore_errors=True)


@pytest.fixture(autouse=True)
def reset_login_throttle():
    """Les échecs de connexion d'un test ne doivent pas bloquer les suivants."""
    from utils import login_throttle
    login_throttle.reset()
    yield
    login_throttle.reset()


@pytest.fixture(autouse=True)
def reset_rate_limits():
    from utils import rate_limit
    rate_limit.reset()
    yield
    rate_limit.reset()


@pytest.fixture(autouse=True)
def isolated_play_queue(tmp_path, monkeypatch):
    """Ne jamais lire ni modifier la file d'attente du vrai diaporama (fichiers dans /tmp du cadre)."""
    from utils import play_queue
    monkeypatch.setattr(play_queue, "STATE_FILE", tmp_path / "queue.json")
    monkeypatch.setattr(play_queue, "ORDER_FILE", tmp_path / "queue_order.json")
