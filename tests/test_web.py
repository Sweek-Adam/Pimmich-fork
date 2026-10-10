"""Tests de l'application web : authentification, rôles, secrets, CSRF et inventaire des routes."""
import json
import re
from pathlib import Path

import pytest

from conftest import ADMIN_USERNAME, login

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}
PUBLIC_RULES = {"/", "/login", "/logout", "/upload", "/handle_upload", "/rebooting", "/api/ping", "/static/<path:filename>"}
SNAPSHOT = Path(__file__).with_name("routes_snapshot.json")


def all_routes(app_module):
    return sorted((r.rule, sorted(r.methods - {"HEAD", "OPTIONS"})) for r in app_module.app.url_map.iter_rules())


def concrete_url(rule):
    """Remplace les paramètres d'une route (<x>) par une valeur factice."""
    return re.sub(r"<[^>]+>", "test", rule)


def test_routes_match_snapshot(app_module):
    """Le découpage du code ne doit perdre ni ajouter de route par accident."""
    current = [[rule, methods] for rule, methods in all_routes(app_module)]
    expected = json.loads(SNAPSHOT.read_text())
    assert current == expected


def test_every_non_public_route_requires_login(app_module, client):
    for rule, methods in all_routes(app_module):
        if rule in PUBLIC_RULES:
            continue
        for method in methods:
            resp = client.open(concrete_url(rule), method=method, headers=SAME_ORIGIN)
            assert resp.status_code in (302, 401), f"{method} {rule} accessible sans connexion ({resp.status_code})"
            if resp.status_code == 302:
                assert "/login" in resp.headers["Location"]


def test_login_with_main_admin(client):
    assert login(client, ADMIN_USERNAME, "mauvais").status_code == 200  # page de connexion réaffichée
    assert client.get("/configure").status_code == 302
    login(client, ADMIN_USERNAME, "admin-test-pass")
    assert client.get("/configure").status_code == 200


def test_admin_sees_accounts_and_system_tabs(admin_client):
    html = admin_client.get("/configure").get_data(as_text=True)
    assert "openTab(event, 'tab-network')" in html
    assert "Créer un compte" in html


def test_user_has_limited_access(user_client):
    html = user_client.get("/configure").get_data(as_text=True)
    assert "openTab(event, 'tab-network')" not in html
    assert "Créer un compte" not in html
    for method, url in [("POST", "/restart_app"), ("POST", "/users/create"), ("POST", "/shutdown"),
                        ("POST", "/api/switch_to_desktop"), ("GET", "/api/backup_settings")]:
        resp = user_client.open(url, method=method, headers=SAME_ORIGIN)
        assert resp.status_code in (302, 403), f"{method} {url} accessible à un utilisateur"
        if resp.status_code == 302:
            assert "réservée aux administrateurs" in user_client.get("/configure").get_data(as_text=True)


def test_user_cannot_read_or_change_secrets(app_module, user_client):
    from utils.config_manager import load_config, save_config
    config = load_config()
    config["weather_api_key"] = "CLE-METEO-SECRETE"
    save_config(config)
    html = user_client.get("/configure").get_data(as_text=True)
    assert "CLE-METEO-SECRETE" not in html
    user_client.post("/configure", data={"weather_api_key": "PIRATE"}, headers=SAME_ORIGIN)
    assert load_config()["weather_api_key"] == "CLE-METEO-SECRETE"


def test_deleted_user_is_logged_out(admin_client, user_client):
    admin_client.post("/users/marie/delete", headers=SAME_ORIGIN)
    assert user_client.get("/configure").status_code == 302


@pytest.mark.parametrize("headers", [
    {"Sec-Fetch-Site": "cross-site"},
    {"Sec-Fetch-Site": "same-site"},
    {"Origin": "http://evil.example"},
    {"Origin": "null"},
])
def test_cross_site_requests_are_refused(admin_client, headers):
    assert admin_client.post("/restart_app", headers=headers).status_code == 403
    assert admin_client.get("/import-gdrive", headers=headers).status_code == 403


def test_same_site_requests_are_accepted(admin_client):
    for headers in (SAME_ORIGIN, {"Origin": "http://localhost"}, {}):
        assert admin_client.get("/api/slideshow/status", headers=headers).status_code == 200


def test_internal_token_grants_api_access(app_module, client):
    from utils.security import internal_headers, INTERNAL_TOKEN_HEADER
    assert client.get("/api/slideshow/status").status_code == 401
    assert client.get("/api/slideshow/status", headers=internal_headers()).status_code == 200
    assert client.get("/api/slideshow/status", headers={INTERNAL_TOKEN_HEADER: "faux"}).status_code == 401
    # Le jeton interne ne donne pas accès aux pages d'administration
    assert client.get("/configure", headers=internal_headers()).status_code == 302


def test_shutdown_api_requires_admin_or_internal_token(user_client):
    assert user_client.post("/api/system/shutdown", headers=SAME_ORIGIN).status_code == 403


def test_session_key_is_never_the_public_default(app_module):
    assert app_module.app.secret_key != "supersecretkey_fallback_should_be_changed"


@pytest.mark.parametrize("lang,expected", [
    ("en", "User accounts"), ("es", "Cuentas de usuario"), ("de", "Benutzerkonten"), ("ja", "ユーザーアカウント"),
    ("en", "Write a message"), ("de", "Nachricht schreiben"), ("en", "Free up space automatically"),
])
def test_new_texts_are_translated(admin_client, lang, expected):
    html = admin_client.get(f"/configure?lang={lang}").get_data(as_text=True)
    assert expected in html
    assert "Comptes utilisateurs" not in html


def test_guest_upload_page_is_installable_and_accepts_files(app_module, client):
    import io
    html = client.get("/upload").get_data(as_text=True)
    assert 'rel="manifest"' in html and 'accept="image/*,video/*"' in html
    manifest = client.get("/static/pwa/manifest.json").get_json()
    assert manifest["start_url"] == "/upload"
    for icon in manifest["icons"]:
        assert client.get(icon["src"]).status_code == 200
    resp = client.post("/handle_upload", data={"photos": (io.BytesIO(b"\xff\xd8\xff fake jpeg"), "vacances.jpg")},
                       content_type="multipart/form-data", headers=SAME_ORIGIN)
    assert resp.status_code == 302
    assert any(p.name.startswith("vacances_") for p in app_module.PENDING_UPLOADS_DIR.iterdir())


def test_session_cookie_is_secure_only_over_https(client):
    from conftest import ADMIN_PASSWORD
    resp = client.post("/login", data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
                       headers={"Sec-Fetch-Site": "same-origin", "X-Forwarded-Proto": "https"})
    assert "Secure" in resp.headers["Set-Cookie"]
    resp = client.post("/login", data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}, headers=SAME_ORIGIN)
    assert "Secure" not in resp.headers["Set-Cookie"]


def test_https_origin_is_accepted(admin_client):
    # Création de compte invalide : refusée par la validation (302), pas par la protection CSRF (403), et sans effet
    assert admin_client.post("/users/create", data={"username": "x"}, headers={"Origin": "https://localhost"}).status_code == 302
