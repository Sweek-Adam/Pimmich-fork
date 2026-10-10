"""Messages écrits par les invités depuis la page publique, et QR code du diaporama."""
from datetime import date, timedelta

import pytest

from utils import messages_manager as mm

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}


@pytest.fixture(autouse=True)
def clean():
    from utils.config_manager import load_config, save_config
    mm.delete_all_messages()
    config = dict(load_config()); config["guest_messages_enabled"] = True; save_config(config)
    yield
    mm.delete_all_messages()


def send(client, device="192.168.1.50", **fields):
    data = {"title": "Coucou", "body": "Bisous de Lyon", "signature": "Léa", "style": "festif", **fields}
    return client.post("/upload/message", json=data, headers={**SAME_ORIGIN, "X-Real-IP": device})


def test_guest_can_publish_without_account(client):
    assert "Écrire un message sur le cadre" in client.get("/upload").get_data(as_text=True)
    resp = send(client)
    assert resp.status_code == 200 and resp.get_json()["success"]
    [message] = mm.list_messages()
    assert message["guest"] and message["author"].endswith("Léa")
    assert mm.image_path(message["id"]).exists()


def test_guest_messages_always_expire_within_7_days(client):
    send(client, expires=(date.today() + timedelta(days=60)).isoformat())
    send(client)
    limit = (date.today() + timedelta(days=mm.GUEST_MAX_DAYS)).isoformat()
    assert [m["expires"] for m in mm.list_messages()] == [limit, limit]


def test_guest_messages_are_limited_per_device(client):
    from web.routes_guests import GUEST_MESSAGES_PER_HOUR
    for _ in range(GUEST_MESSAGES_PER_HOUR):
        assert send(client).status_code == 200
    assert send(client).status_code == 429
    assert send(client, device="192.168.1.60").status_code == 200  # un autre appareil peut encore écrire


def test_guest_preview_and_validation(client):
    resp = client.post("/upload/message/preview", json={"body": "Test"}, headers=SAME_ORIGIN)
    assert resp.status_code == 200 and resp.mimetype == "image/jpeg"
    assert send(client, title="", body="").status_code == 400


def test_guest_messages_can_be_disabled(client):
    from utils.config_manager import load_config, save_config
    config = dict(load_config()); config["guest_messages_enabled"] = False; save_config(config)
    assert send(client).status_code == 403
    assert "Écrire un message sur le cadre" not in client.get("/upload").get_data(as_text=True)


def test_guest_message_from_another_site_is_refused(client):
    resp = client.post("/upload/message", json={"body": "spam"}, headers={"Sec-Fetch-Site": "cross-site"})
    assert resp.status_code == 403


def test_slideshow_draws_guest_qr_code(sandbox, monkeypatch):
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame = pytest.importorskip("pygame")
    import local_slideshow as ls
    pygame.init()
    monkeypatch.setattr(ls, "get_local_ip", lambda: "192.168.1.21")
    def white_pixels(surface, x0, y0):
        return sum(surface.get_at((x, y))[:3] == (255, 255, 255) for x in range(x0, x0 + 200, 4) for y in range(y0, y0 + 200, 4))

    screen = pygame.Surface((1920, 1080))
    ls.draw_guest_qr(screen, 1920, 1080, {"show_guest_qr": True, "guest_qr_position": "bottom_right"})
    assert white_pixels(screen, 1720, 880) > 100   # QR code (fond blanc) en bas à droite
    assert white_pixels(screen, 0, 0) == 0          # rien en haut à gauche
    blank = pygame.Surface((1920, 1080))
    ls.draw_guest_qr(blank, 1920, 1080, {"show_guest_qr": False})
    assert white_pixels(blank, 1720, 880) == 0
