"""Outil de vérification (non collecté par pytest) : enregistre le HTML rendu de /configure (admin et utilisateur)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import conftest  # noqa: E402  (prépare la copie isolée du projet)

out_dir = Path(sys.argv[1])
import app as app_module  # noqa: E402
from utils import user_manager  # noqa: E402
app_module.app.config["TESTING"] = True
Path(user_manager.USERS_PATH).unlink(missing_ok=True)
user_manager.create_user("marie", "secret123", "user")
for name, (user, password) in {"admin": (conftest.ADMIN_USERNAME, conftest.ADMIN_PASSWORD), "user": ("marie", "secret123")}.items():
    c = app_module.app.test_client()
    conftest.login(c, user, password)
    html = c.get("/configure").get_data(as_text=True)
    (out_dir / f"{name}.html").write_text(html)
    print(name, len(html))
