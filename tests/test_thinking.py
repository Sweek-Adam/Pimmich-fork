"""« Je pense à toi » : envoyé à tous les cadres de la famille, des cœurs s'envolent à l'arrivée."""
import time

import pytest

from utils import thinking

SAME = {"Sec-Fetch-Site": "same-origin"}


@pytest.fixture(autouse=True)
def event_file(tmp_path, monkeypatch):
    monkeypatch.setattr(thinking, "EVENT_FILE", tmp_path / "thinking.json")


def test_received_heart_is_pending_once():
    start = time.time() - 1
    thinking.receive("Mamie")
    event = thinking.pending(start)
    assert event["name"] == "Mamie"
    assert thinking.pending(event["at"]) is None


def test_heart_goes_to_every_family_frame(admin_client, monkeypatch):
    from test_frames import restore_config  # noqa: F401
    from utils.config_manager import load_config, save_config
    from web import routes_frames
    original = dict(load_config())
    remote = admin_client.application.test_client()
    try:
        token = admin_client.post("/api/frame/pairing", json={}, headers=SAME).get_json()["codes"][-1]["token"]
        assert remote.post("/api/frame/heart", json={"from": "x"}).status_code == 401  # code exigé
        save_config(dict(load_config(), simple_name="Mamie",
                         family_frames=[{"id": "a1", "url": "https://100.1.2.3", "token": token}, {"id": "b2", "url": "https://100.1.2.4", "token": token}]))

        class Response:
            def __init__(self, r):
                self.ok = r.status_code < 400

        calls = []

        def fake_call(frame, method, path, **kwargs):
            calls.append(frame["id"])
            return Response(remote.post(path, json=kwargs.get("json"), headers={routes_frames.TOKEN_HEADER: frame["token"]}))
        monkeypatch.setattr(routes_frames, "_call", fake_call)
        assert routes_frames.send_heart_to_all() == 2 and calls == ["a1", "b2"]
        assert thinking.pending(0)["name"] == "Mamie"
    finally:
        save_config(original)


def test_slideshow_shows_hearts(monkeypatch):
    pygame = pytest.importorskip("pygame")
    import local_slideshow as ls
    seen = []
    monkeypatch.setattr(ls, "reaction_burst", lambda screen, bg, kind, seconds=2.5: seen.append(kind))
    monkeypatch.setattr(ls, "comment_banner", lambda screen, bg, text, name="", seconds=6.0, quoted=True: seen.append(text))
    thinking.receive("Mamie")
    since = ls.check_thinking(pygame.Surface((320, 180)), 0)
    assert seen == ["love", "Mamie pense à vous"] and since > 0
    assert ls.check_thinking(pygame.Surface((320, 180)), since) == since
