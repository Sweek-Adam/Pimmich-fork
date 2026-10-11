"""Réactions des invités sur la photo affichée, et livre d'or."""
import io

import pytest
from PIL import Image

from utils import guestbook, reactions

SAME = {"Sec-Fetch-Site": "same-origin"}


@pytest.fixture
def stores(monkeypatch, tmp_path):
    monkeypatch.setattr(reactions, "STORE", tmp_path / "reactions.json")
    monkeypatch.setattr(reactions, "EVENT_FILE", tmp_path / "event.json")
    monkeypatch.setattr(guestbook, "STORE", tmp_path / "guestbook.json")
    monkeypatch.setattr(guestbook, "IMAGES_DIR", tmp_path / "gb")
    return tmp_path


def test_reactions_are_counted(stores):
    reactions.add("prepared/gdrive/a.jpg", "love", "Léa")
    reactions.add("prepared/gdrive/a.jpg", "love")
    reactions.add("prepared/gdrive/b.jpg", "bravo")
    assert reactions.counts("prepared/gdrive/a.jpg") == {"love": 2}
    assert reactions.most_loved()[0] == ("prepared/gdrive/a.jpg", 2)
    assert reactions.recent()[0]["kind"] == "bravo"
    assert reactions.latest_event(0)["photo"] == "prepared/gdrive/b.jpg" and reactions.latest_event(10 ** 12) is None
    with pytest.raises(ValueError):
        reactions.add("prepared/gdrive/a.jpg", "colère")


def test_guestbook_keeps_entries(stores):
    image = stores / "m.jpg"
    Image.new("RGB", (1920, 1080), (200, 100, 50)).save(image)
    guestbook.archive({"id": "abcdef123456", "title": "Coucou", "body": "", "signature": "Léa", "created": "2026-10-11 10:00"}, image)
    assert guestbook.entries()[0]["signature"] == "Léa" and (stores / "gb" / "abcdef123456.jpg").exists()
    assert guestbook.delete("abcdef123456") and guestbook.entries() == []


def test_guest_routes(client, admin_client, stores, sandbox, monkeypatch):
    from web import routes_guests
    photo = sandbox / "static" / "prepared" / "gdrive" / "vue.jpg"
    photo.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (40, 30)).save(photo)
    current = stores / "current.txt"
    current.write_text("prepared/gdrive/vue.jpg")
    monkeypatch.setattr(routes_guests, "CURRENT_PHOTO_FILE", str(current))
    monkeypatch.setattr(routes_guests, "is_slideshow_running", lambda: True)
    from utils.config_manager import load_config, save_config
    original = dict(load_config())
    save_config(dict(original, guest_reactions_enabled=True))
    try:
        now = client.get("/upload/now").get_json()
        assert now["photo"] == "prepared/gdrive/vue.jpg" and "love" in now["kinds"]
        r = client.post("/upload/react", json={"photo": now["photo"], "kind": "love"}, headers=SAME).get_json()
        assert r["success"] and r["counts"] == {"love": 1}
        assert client.post("/upload/react", json={"photo": "../config/config.json", "kind": "love"}, headers=SAME).status_code == 404
        current.write_text("prepared/messages/abc.jpg")
        assert client.get("/upload/now").get_json()["photo"] is None  # un message n'est pas une photo à commenter
        assert client.get("/upload/guestbook").status_code == 200
        assert admin_client.get("/api/reactions").get_json()["most_loved"][0][0] == "prepared/gdrive/vue.jpg"
    finally:
        photo.unlink()
        save_config(original)
