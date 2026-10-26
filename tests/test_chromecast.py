"""Diffusion Chromecast : photos envoyées une à une à la télé (télé simulée), arrêt, adresses des photos."""
import time
from types import SimpleNamespace

from utils import chromecast

SAME = {"Sec-Fetch-Site": "same-origin"}


class FakeCast:
    def __init__(self):
        self.played, self.quit = [], False
        self.cast_info = SimpleNamespace(friendly_name="Télé du salon")
        self.media_controller = SimpleNamespace(play_media=lambda url, mime, **k: self.played.append((url, mime)),
                                                block_until_active=lambda timeout=None: None)

    def quit_app(self):
        self.quit = True


def wait_for(condition, seconds=3):
    end = time.time() + seconds
    while time.time() < end and not condition():
        time.sleep(0.02)
    return condition()


def test_photos_loop_until_stopped():
    cast = FakeCast()
    items = [("http://192.168.1.30/static/prepared/a/1.jpg", "image/jpeg", ""), ("http://192.168.1.30/static/prepared/a/2.jpg", "image/jpeg", "")]
    chromecast.start("00000000-0000-0000-0000-000000000001", items, seconds=0.05, connect=lambda uuid: cast)
    assert wait_for(lambda: len(cast.played) >= 3)  # en boucle
    assert chromecast.STATE["name"] == "Télé du salon" and chromecast.running()
    chromecast.stop()
    assert not chromecast.running() and cast.quit


def test_film_plays_once():
    cast = FakeCast()
    chromecast.start("00000000-0000-0000-0000-000000000002", [("http://x/static/prepared/films/film_2026.mp4", "video/mp4", "Film")],
                     mode="film", connect=lambda uuid: cast)
    assert wait_for(lambda: not chromecast.running())
    assert cast.played == [("http://x/static/prepared/films/film_2026.mp4", "video/mp4")] and not cast.quit


def test_photo_items_are_url_encoded():
    items = chromecast.photo_items("http://192.168.1.30", ["invités/été 2025.jpg", "a/vidéo.mp4"])
    assert items == [("http://192.168.1.30/static/prepared/invit%C3%A9s/%C3%A9t%C3%A9%202025.jpg", "image/jpeg", "")]


def test_routes(admin_client, monkeypatch):
    started = []
    monkeypatch.setattr(chromecast, "available", lambda: True)
    monkeypatch.setattr(chromecast, "discover", lambda timeout=6: [{"uuid": "11111111-2222-3333-4444-555555555555", "name": "Salon", "model": "Chromecast"}])
    monkeypatch.setattr(chromecast, "start", lambda device, items, seconds=10, mode="photos": started.append((device, mode, len(items))))
    assert admin_client.get("/api/chromecast/devices").get_json()["devices"][0]["name"] == "Salon"
    assert admin_client.post("/api/chromecast/start", json={"uuid": "pas-un-uuid"}, headers=SAME).status_code == 400
    assert admin_client.post("/api/chromecast/start", json={"uuid": "11111111-2222-3333-4444-555555555555", "mode": "film", "film": "../x.mp4"},
                             headers=SAME).status_code == 404
