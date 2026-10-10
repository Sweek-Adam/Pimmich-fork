"""Radios internet et podcasts : lecture par mpv (simulé), favoris, flux RSS."""
import pytest

from utils import now_playing, radio

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}
FEED = b"""<?xml version="1.0"?><rss><channel><title>Les Pieds sur terre</title>
<item><title>Episode 2</title><enclosure url="https://media.example/ep2.mp3" type="audio/mpeg"/></item>
<item><title>Episode 1</title><enclosure url="https://media.example/ep1.mp3" type="audio/mpeg"/></item></channel></rss>"""


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "STATE_FILE", tmp_path / "radio.json")
    monkeypatch.setattr(now_playing, "STATE_FILE", tmp_path / "np.json")
    monkeypatch.setattr(radio, "_start_poller", lambda: None)


class FakeResponse:
    def __init__(self, content=b"", data=None):
        self.content, self._data = content, data
        self.raw = type("Raw", (), {"read": lambda _self, n, decode_content=True: content[:n]})()

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def test_play_and_stop_with_a_fake_player(tmp_path):
    fake = tmp_path / "mpv"
    fake.write_text("#!/bin/sh\nsleep 30\n")
    fake.chmod(0o755)
    radio.play("https://icecast.radiofrance.fr/fip-hifi.aac", "FIP", mpv=str(fake))
    assert radio.playing()["name"] == "FIP" and now_playing.current()["source"] == "radio"
    assert now_playing.external_playing()  # la musique du diaporama se met en pause
    radio.stop()
    assert radio.playing() is None and now_playing.current() is None
    with pytest.raises(ValueError):
        radio.play("file:///etc/passwd", "x")


def test_latest_podcast_episode(monkeypatch):
    monkeypatch.setattr(radio.requests, "get", lambda *a, **k: FakeResponse(FEED))
    assert radio.latest_episode("https://feeds.example/pst.xml") == {"title": "Episode 2", "url": "https://media.example/ep2.mp3", "show": "Les Pieds sur terre"}
    monkeypatch.setattr(radio.requests, "get", lambda *a, **k: FakeResponse(b'<!DOCTYPE x [<!ENTITY a "aaaa">]><rss/>'))
    with pytest.raises(ValueError):
        radio.latest_episode("https://feeds.example/bomb.xml")


def test_radio_api(admin_client, monkeypatch):
    played = []
    monkeypatch.setattr(radio, "play", lambda url, name, kind="radio", volume=80: played.append((url, name, kind)))
    monkeypatch.setattr(radio.requests, "get", lambda url, **k: FakeResponse(FEED, [
        {"name": "RTL", "url_resolved": "https://streaming.radio.rtl.fr/rtl-1-44-128", "tags": "news,talk", "countrycode": "FR"},
        {"name": "Cassée", "url": "javascript:alert(1)"}]))
    data = admin_client.get("/api/radio").get_json()
    assert any(s["name"] == "FIP" for s in data["stations"])
    found = admin_client.get("/api/radio/search?q=rtl").get_json()["stations"]
    assert [s["name"] for s in found] == ["RTL"] and found[0]["genre"] == "news"  # adresses douteuses écartées
    assert admin_client.post("/api/radio/play", json={"url": found[0]["url"], "name": "RTL"}, headers=SAME_ORIGIN).get_json()["success"]
    r = admin_client.post("/api/radio/favorites", json={"url": found[0]["url"], "name": "RTL"}, headers=SAME_ORIGIN).get_json()
    assert r["favorites"] == [{"name": "RTL", "url": found[0]["url"]}]
    r = admin_client.post("/api/podcasts", json={"feed": "https://feeds.example/pst.xml"}, headers=SAME_ORIGIN).get_json()
    assert r["podcasts"] == [{"name": "Les Pieds sur terre", "feed": "https://feeds.example/pst.xml"}]
    assert admin_client.post("/api/podcast/play", json={"feed": "https://feeds.example/pst.xml"}, headers=SAME_ORIGIN).get_json()["success"]
    assert played[-1] == ("https://media.example/ep2.mp3", "Les Pieds sur terre — Episode 2", "podcast")
    assert admin_client.post("/api/podcast/play", json={"feed": "https://inconnu"}, headers=SAME_ORIGIN).status_code == 404
