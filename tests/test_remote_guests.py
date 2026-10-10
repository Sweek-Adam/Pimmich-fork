"""Invités hors de la maison : seule la page invités est joignable depuis internet, et seulement avec le lien secret."""
import pytest

from utils import remote_guests

REMOTE = {remote_guests.REMOTE_HEADER: "1"}
SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}


@pytest.fixture()
def remote_on(app_module):
    from utils.config_manager import load_config, save_config
    config = dict(load_config())
    config.update(remote_guests_enabled=True, guest_link_token="secret-123")
    save_config(config)
    yield
    config.update(remote_guests_enabled=False, guest_link_token="")
    save_config(config)


def test_remote_requests_are_refused_when_disabled(client):
    assert client.get("/upload?k=x", headers=REMOTE).status_code == 404


def test_only_the_guest_page_with_the_secret_link(client, remote_on):
    assert client.get("/upload", headers=REMOTE).status_code == 403  # sans le lien
    assert client.get("/upload?k=mauvais", headers=REMOTE).status_code == 403
    assert client.get("/upload?k=secret-123", headers=REMOTE).status_code == 200
    assert client.get("/upload", headers=REMOTE).status_code == 200  # lien déjà ouvert : mémorisé
    for path in ("/login", "/configure", "/api/health", "/static/prepared/gdrive/photo.jpg", "/api/guest_qr.png", "/static/vendor/fontawesome/css/all.min.css"):
        assert client.get(path, headers=REMOTE).status_code == 404, path
    assert client.get("/static/vendor/tailwind/tailwind.min.css", headers=REMOTE).status_code in (200, 304)


def test_lan_requests_are_unchanged(client, remote_on):
    assert client.get("/upload").status_code == 200  # sur le Wi-Fi : pas de lien secret nécessaire


def test_admin_controls(admin_client, monkeypatch):
    from web import routes_guests
    from utils.config_manager import load_config
    monkeypatch.setattr(remote_guests, "tailscale_status", lambda: {"installed": True, "connected": True, "dns_name": "cadre.tail1234.ts.net", "funnel": False})
    calls = []
    monkeypatch.setattr(remote_guests, "set_funnel", lambda enabled: calls.append(enabled) or (True, ""))
    monkeypatch.setattr(routes_guests, "_remote_entry_ready", lambda: False)
    assert admin_client.post("/api/remote_guests", json={"enabled": True}, headers=SAME_ORIGIN).status_code == 409  # script pas lancé
    monkeypatch.setattr(routes_guests, "_remote_entry_ready", lambda: True)
    assert admin_client.post("/api/remote_guests", json={"enabled": True}, headers=SAME_ORIGIN).get_json()["success"] and calls == [True]
    token = load_config()["guest_link_token"]
    data = admin_client.get("/api/remote_guests").get_json()
    assert data["link"] == f"https://cadre.tail1234.ts.net/upload?k={token}" and len(token) >= 20
    admin_client.post("/api/remote_guests/new_link", headers=SAME_ORIGIN)
    assert load_config()["guest_link_token"] != token
    assert admin_client.get("/api/guest_qr.png?remote=1").status_code == 200
    admin_client.post("/api/remote_guests", json={"enabled": False}, headers=SAME_ORIGIN)
    assert calls == [True, False] and not load_config()["remote_guests_enabled"]
