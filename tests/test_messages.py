"""Messages texte affichés comme des photos."""
from datetime import date, timedelta

import pytest
from PIL import Image

from utils import messages_manager as mm

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}


@pytest.fixture(autouse=True)
def no_messages():
    mm.delete_all_messages()
    yield
    mm.delete_all_messages()


def publish(client, **fields):
    data = {"title": "Bonjour", "body": "Un petit mot", "signature": "Moi", "style": "nuit", **fields}
    return client.post("/api/messages", json=data, headers=SAME_ORIGIN)


def test_publish_creates_screen_sized_image_and_enables_source(app_module, user_client):
    from utils.config_manager import load_config
    resp = publish(user_client)
    assert resp.status_code == 200 and resp.get_json()["success"]
    item = resp.get_json()["item"]
    assert item["author"] == "marie"
    config = load_config()
    with Image.open(mm.image_path(item["id"])) as image:
        assert image.size == (config.get("display_width", 1920), config.get("display_height", 1080))
    assert "messages" in config["display_sources"]
    listed = user_client.get("/api/messages").get_json()["messages"]
    assert [m["id"] for m in listed] == [item["id"]]


def test_preview_returns_an_image(user_client):
    resp = user_client.post("/api/messages/preview", json={"body": "Test", "style": "festif"}, headers=SAME_ORIGIN)
    assert resp.status_code == 200 and resp.mimetype == "image/jpeg"


@pytest.mark.parametrize("fields", [
    {"title": "", "body": ""},
    {"body": "x" * (mm.MAX_BODY + 1)},
    {"expires": (date.today() - timedelta(days=1)).isoformat()},
    {"expires": "pas une date"},
])
def test_invalid_messages_are_refused(user_client, fields):
    assert publish(user_client, **fields).status_code == 400
    assert mm.list_messages() == []


def test_expired_messages_are_purged():
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    kept = mm.create_message("A", "a", "", "clair", None, "admin", 320, 180)
    expiring = mm.create_message("B", "b", "", "clair", tomorrow, "admin", 320, 180)
    assert mm.purge_expired(today=date.today()) == 0
    assert mm.purge_expired(today=date.today() + timedelta(days=2)) == 1
    assert not mm.image_path(expiring["id"]).exists()
    assert [m["id"] for m in mm.list_messages()] == [kept["id"]]


def test_delete_from_messages_tab_and_from_preview(user_client):
    first = publish(user_client).get_json()["item"]
    second = publish(user_client, title="Deux").get_json()["item"]
    assert user_client.delete(f"/api/messages/{first['id']}", headers=SAME_ORIGIN).status_code == 200
    assert not mm.image_path(first["id"]).exists()
    # Suppression depuis l'onglet Aperçu
    assert user_client.delete(f"/delete_photo/messages/{second['id']}.jpg", headers=SAME_ORIGIN).status_code == 204
    assert mm.list_messages() == []
    assert user_client.delete("/api/messages/inconnu", headers=SAME_ORIGIN).status_code == 404


def test_rerender_follows_screen_resolution():
    message = mm.create_message("A", "a", "", "carte", None, "admin", 320, 180)
    mm.rerender_all(180, 320)
    with Image.open(mm.image_path(message["id"])) as image:
        assert image.size == (180, 320)


def test_new_messages_are_shown_first_newest_first():
    mm.pop_priority()
    first = mm.create_message("A", "a", "", "nuit", None, "admin", 320, 180)
    second = mm.create_message("B", "b", "", "nuit", None, "invité", 320, 180, guest=True)
    assert mm.pop_priority() == [str(mm.image_path(second["id"])), str(mm.image_path(first["id"]))]
    assert mm.pop_priority() == []  # prioritaires une seule fois


def test_slideshow_puts_priority_media_first(tmp_path):
    import local_slideshow as ls
    photos = [str(tmp_path / f"{n}.jpg") for n in ("p1", "p2", "msg_old", "msg_new")]
    playlist = [photos[0], photos[2], photos[1], photos[3], photos[0]]  # favoris répétés possibles
    queue = [photos[3], photos[2], str(tmp_path / "absent.jpg")]
    result = ls.apply_priority(playlist, photos, queue)
    assert result[:2] == [photos[3], photos[2]]
    assert result.count(photos[3]) == 1 and result.count(photos[2]) == 1
    assert result[2:] == [photos[0], photos[1], photos[0]]
    assert ls.apply_priority(playlist, photos, []) == playlist


def test_hide_and_show_message_without_deleting(user_client):
    item = publish(user_client).get_json()["item"]
    resp = user_client.post(f"/api/messages/{item['id']}/visibility", json={"hidden": True}, headers=SAME_ORIGIN)
    assert resp.get_json()["item"]["hidden"]
    assert not mm.image_path(item["id"]).exists()            # plus dans le dossier lu par le diaporama
    assert mm.image_path(item["id"], hidden=True).exists()   # mais conservé
    assert [m["id"] for m in mm.list_messages()] == [item["id"]]
    user_client.post(f"/api/messages/{item['id']}/visibility", json={"hidden": False}, headers=SAME_ORIGIN)
    assert mm.image_path(item["id"]).exists() and not mm.image_path(item["id"], hidden=True).exists()


def test_hidden_message_image_is_regenerated_in_hidden_place():
    message = mm.create_message("A", "a", "", "nuit", None, "admin", 320, 180)
    mm.set_hidden(message["id"], True)
    mm.image_path(message["id"], hidden=True).unlink()
    assert mm.ensure_images(320, 180) == 1
    assert mm.image_path(message["id"], hidden=True).exists() and not mm.image_path(message["id"]).exists()


def test_admin_can_change_or_remove_expiry(user_client):
    item = publish(user_client).get_json()["item"]
    later = (date.today() + timedelta(days=30)).isoformat()
    resp = user_client.post(f"/api/messages/{item['id']}/expires", json={"expires": later}, headers=SAME_ORIGIN)
    assert resp.get_json()["item"]["expires"] == later
    resp = user_client.post(f"/api/messages/{item['id']}/expires", json={"expires": None}, headers=SAME_ORIGIN)
    assert resp.get_json()["item"]["expires"] is None
    past = (date.today() - timedelta(days=1)).isoformat()
    assert user_client.post(f"/api/messages/{item['id']}/expires", json={"expires": past}, headers=SAME_ORIGIN).status_code == 400
    assert user_client.post("/api/messages/000000000000/expires", json={}, headers=SAME_ORIGIN).status_code == 400


def test_deleting_hidden_message_removes_its_image():
    message = mm.create_message("A", "a", "", "nuit", None, "admin", 320, 180)
    mm.set_hidden(message["id"], True)
    mm.delete_message(message["id"])
    assert not mm.image_path(message["id"], hidden=True).exists()
