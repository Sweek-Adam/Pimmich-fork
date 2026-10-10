"""File d'attente du diaporama : publication et réorganisation par glisser-déposer."""
import pytest

from utils import play_queue as pq

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}


def test_published_state_wraps_around_the_playlist():
    pq.publish_state(["a", "b", "c", "d"], 2)
    state = pq.read_state()
    assert state["current"] == "c" and state["upcoming"] == ["d", "a", "b"]


def test_requested_order_comes_first_then_the_rest_of_the_loop():
    playlist = ["a", "b", "c", "d", "e"]
    pq.request_order(["e", "c", "inconnu"])
    new, index = pq.apply_requested_order(playlist, 2)  # « c » allait être affichée
    assert index == 0
    assert new == ["e", "c", "d", "a", "b"]
    assert pq.apply_requested_order(new, 0) == (new, 0)  # demande consommée


def test_duplicates_from_favorites_are_moved_once():
    pq.request_order(["b"])
    new, _ = pq.apply_requested_order(["a", "b", "c", "b"], 0)
    assert new == ["b", "a", "c", "b"]


def test_no_request_keeps_the_playlist():
    assert pq.apply_requested_order(["a", "b"], 1) == (["a", "b"], 1)


@pytest.fixture()
def running_slideshow(app_module, monkeypatch, sandbox):
    from web import routes_slideshow
    monkeypatch.setattr(routes_slideshow, "is_slideshow_running", lambda: True)
    signals = []
    monkeypatch.setattr(routes_slideshow, "_send_slideshow_signal", lambda sig: signals.append(sig))
    folder = sandbox / "static" / "prepared" / "test"
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in ("p1.jpg", "p2.jpg", "p3.jpg", "film.mp4", "film_thumbnail.jpg"):
        (folder / name).write_bytes(b"x")
    paths = [str(folder / n) for n in ("p1.jpg", "p2.jpg", "p3.jpg", "film.mp4")]
    pq.publish_state(paths, 0)
    return paths, signals


def test_queue_api_lists_upcoming_media(admin_client, running_slideshow):
    data = admin_client.get("/api/slideshow/queue").get_json()
    assert data["running"] and data["current"]["name"] == "p1.jpg"
    assert [i["name"] for i in data["upcoming"]] == ["p2.jpg", "p3.jpg", "film.mp4"]
    video = data["upcoming"][-1]
    assert video["video"] and video["thumb"].endswith("film_thumbnail.jpg") and video["source"] == "test"


def test_queue_api_reorders_and_can_play_now(admin_client, running_slideshow):
    paths, signals = running_slideshow
    resp = admin_client.post("/api/slideshow/queue", json={"order": ["prepared/test/p3.jpg", "prepared/test/p2.jpg"]}, headers=SAME_ORIGIN)
    assert resp.get_json()["success"] and signals == []
    new, _ = pq.apply_requested_order(paths, 1)
    assert [p.rsplit("/", 1)[1] for p in new] == ["p3.jpg", "p2.jpg", "film.mp4", "p1.jpg"]
    admin_client.post("/api/slideshow/queue", json={"order": ["prepared/test/film.mp4"], "play_now": True}, headers=SAME_ORIGIN)
    assert len(signals) == 1


@pytest.mark.parametrize("order", [[], "pas une liste", ["../../etc/passwd"], ["prepared/test/absent.jpg"], ["/etc/hostname"]])
def test_queue_api_refuses_invalid_orders(admin_client, running_slideshow, order):
    resp = admin_client.post("/api/slideshow/queue", json={"order": order}, headers=SAME_ORIGIN)
    assert resp.status_code == 400
    assert not pq.ORDER_FILE.exists()


def test_composition_on_screen_skips_its_photos():
    pq.publish_state(["a", "b", "c", "d", "e"], 1, "compo.jpg", consumed=3)  # b, c, d dans la composition
    state = pq.read_state()
    assert state["current"] == "compo.jpg" and state["upcoming"] == ["e", "a"]


def test_queue_api_groups_upcoming_compositions(admin_client, running_slideshow, sandbox):
    paths, _ = running_slideshow
    compo = sandbox / "static" / "compositions" / "composition_1.jpg"
    compo.parent.mkdir(parents=True, exist_ok=True)
    compo.write_bytes(b"x")
    pq.publish_state(paths, 0, compositions=[{"at": 0, "count": 2, "style": "hokusai", "image": str(compo)}])
    slots = admin_client.get("/api/slideshow/queue").get_json()["slots"]
    assert [s["type"] for s in slots] == ["composition", "photo"]
    assert [i["name"] for i in slots[0]["items"]] == ["p2.jpg", "p3.jpg"] and not slots[0]["pending"]
    assert slots[0]["image"].endswith("composition_1.jpg") and slots[0]["label"] != "Composition"
    pq.publish_state(paths, 0, compositions=[{"at": 1, "count": None, "style": None, "image": None}])
    slots = admin_client.get("/api/slideshow/queue").get_json()["slots"]
    assert [s["type"] for s in slots] == ["photo", "composition", "photo"] and slots[1]["pending"]


def test_slideshow_predicts_where_compositions_fall(monkeypatch):
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pytest.importorskip("pygame")
    import local_slideshow as ls
    from utils import layout_engine
    plan = layout_engine.resolve({"layout_override": "auto", "unique_enabled": True, "compositions_every": 2,
                                  "composition_formats": ["mosaique"]})
    playlist = [f"p{i}.jpg" for i in range(10)]
    monkeypatch.setitem(ls._composition, "target", (id(playlist), 3))
    monkeypatch.setitem(ls._composition, "ready", ("compo.jpg", 4))
    monkeypatch.setitem(ls._composition, "style", "mosaique")
    # compteur à 1 : p2 seule, la composition prête commence à p3 (4 photos), puis 2 photos seules avant la suivante
    found = ls.upcoming_compositions(plan, playlist, 2, 1)
    assert found[0] == {"at": 1, "count": 4, "style": "mosaique", "image": "compo.jpg"}
    assert found[1] == {"at": 7, "count": None, "style": None, "image": None}
