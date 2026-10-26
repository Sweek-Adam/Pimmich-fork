"""Commentaires des invités : envoyés sur la photo affichée, montrés en bandeau, supprimables depuis la bibliothèque."""
import pytest

from utils import photo_comments

SAME = {"Sec-Fetch-Site": "same-origin"}


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(photo_comments, "STORE", tmp_path / "comments.json")
    monkeypatch.setattr(photo_comments, "EVENT_FILE", tmp_path / "event.json")


def test_guest_comment_on_the_photo_on_screen(client, admin_client, monkeypatch):
    from utils.config_manager import load_config
    from web import routes_guests
    monkeypatch.setattr(routes_guests, "load_config", lambda: dict(load_config(), guest_reactions_enabled=True))
    monkeypatch.setattr(routes_guests, "_now_showing", lambda: "prepared/gdrive/plage.jpg")
    guest = client.application.test_client()
    assert guest.post("/upload/comment", json={"photo": "prepared/gdrive/autre.jpg", "text": "Super"}, headers=SAME).status_code == 409
    assert guest.post("/upload/comment", json={"photo": "prepared/gdrive/plage.jpg", "text": "   "}, headers=SAME).status_code == 400
    r = guest.post("/upload/comment", json={"photo": "prepared/gdrive/plage.jpg", "text": "Quel  souvenir !" + "x" * 200, "name": "Tonton"},
                   headers=SAME).get_json()
    assert r["success"]
    comments = admin_client.get("/api/photo_comments?photo=prepared/gdrive/plage.jpg").get_json()["comments"]
    assert comments[0]["name"] == "Tonton" and comments[0]["text"].startswith("Quel souvenir !") and len(comments[0]["text"]) == 120
    assert photo_comments.latest_event(0)["photo"] == "prepared/gdrive/plage.jpg"
    assert admin_client.delete("/api/photo_comments", json={"photo": "prepared/gdrive/plage.jpg", "at": comments[0]["at"]}, headers=SAME).get_json()["success"]
    assert photo_comments.for_photo("prepared/gdrive/plage.jpg") == []


def test_slideshow_shows_the_banner(monkeypatch):
    pygame = pytest.importorskip("pygame")
    import local_slideshow as ls
    shown = []
    monkeypatch.setattr(ls, "comment_banner", lambda screen, bg, text, name="", seconds=6.0: shown.append((text, name)))
    screen = pygame.Surface((320, 180))
    photo_comments.add("prepared/gdrive/plage.jpg", "Bravo", "Léa")
    since, done = ls.check_comment(screen, "/x/static/prepared/gdrive/plage.jpg", 0, False, 0, {})
    assert shown == [("Bravo", "Léa")] and done
    # Photo qui repasse plus tard : son dernier commentaire revient une fois
    shown.clear()
    since, done = ls.check_comment(screen, "/x/static/prepared/gdrive/plage.jpg", since, False, 0, {})
    assert shown == [("Bravo", "Léa")] and done
    assert ls.check_comment(screen, "/x/static/prepared/gdrive/plage.jpg", since, True, 0, {}) == (since, True) and len(shown) == 1
