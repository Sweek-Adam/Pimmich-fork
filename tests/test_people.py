"""Personnes (Immich) : liste, photos de chacun retrouvées sur le cadre, import des personnes suivies, playlist."""
import pytest

from utils import people

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}
CONFIG = {"immich_url": "http://immich.local:2283/", "immich_token": "cle"}


class Response:
    def __init__(self, payload=None, content=b"", status=200):
        self.payload, self.content, self.status_code = payload, content, status

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise people.requests.HTTPError(str(self.status_code))

    def iter_content(self, size):
        yield self.content

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeImmich:
    """Léo : 3 photos (dont 2 sur 2 pages), Mamie : 1 photo, un visage sans nom et un masqué."""
    ASSETS = {"p-leo": [{"id": "a1", "originalFileName": "IMG_0001.HEIC"}, {"id": "a2", "originalFileName": "IMG_0002.jpg"},
                        {"id": "a3", "originalFileName": "clip.mov", "type": "VIDEO"}],
              "p-mamie": [{"id": "b1", "originalFileName": "noel.jpg"}]}

    def __init__(self):
        self.downloads = []

    def get(self, url, params=None, headers=None, timeout=None, stream=False):
        assert headers["x-api-key"] == "cle" and "//api" not in url
        if url.endswith("/api/people"):
            return Response({"people": [{"id": "p-leo", "name": "Léo"}, {"id": "p-mamie", "name": "Mamie "}, {"id": "p-x", "name": ""},
                                        {"id": "p-h", "name": "Caché", "isHidden": True}]})
        if url.endswith("/thumbnail"):
            return Response(content=b"\xff\xd8face")
        if url.endswith("/original"):
            self.downloads.append(url)
            return Response(content=b"original")
        raise AssertionError(url)

    def post(self, url, json=None, headers=None, timeout=None):
        person, page = json["personIds"][0], json["page"]
        items = self.ASSETS[person]
        chunk = items[:2] if page == 1 else items[2:]
        return Response({"assets": {"items": chunk, "nextPage": "2" if page == 1 and len(items) > 2 else None}})


@pytest.fixture
def frame(monkeypatch, tmp_path):
    for name, sub in (("INDEX_FILE", "people.json"), ("THUMBS_DIR", "thumbs"), ("PREPARED_DIR", "prepared"), ("PEOPLE_DIR", "photos/personnes")):
        monkeypatch.setattr(people, name, tmp_path / sub)
    immich = tmp_path / "prepared" / "immich"
    immich.mkdir(parents=True)
    for name in ("IMG_0001.jpg", "IMG_0001_polaroid.jpg", "clip.mp4", "clip_thumbnail.jpg", "autre.jpg"):
        (immich / name).write_bytes(b"x")
    return tmp_path


def test_people_and_their_photos_on_the_frame(frame):
    immich = FakeImmich()
    assert people.people(CONFIG, immich) == [{"id": "p-leo", "name": "Léo"}, {"id": "p-mamie", "name": "Mamie"}]
    assert [a["id"] for a in people.person_assets(CONFIG, "p-leo", immich)] == ["a1", "a2", "a3"]  # les deux pages
    assert people.refresh(CONFIG, immich) == {"people": 2, "downloaded": 0}
    index = people.load()
    assert index["p-leo"]["files"] == ["immich/IMG_0001.jpg", "immich/clip.mp4"] and index["p-leo"]["count"] == 3
    assert index["p-mamie"]["files"] == []
    assert people.by_photo()["immich/IMG_0001.jpg"] == ["Léo"]
    assert (frame / "thumbs" / "p-leo.jpg").read_bytes() == b"\xff\xd8face"


def test_followed_person_photos_are_imported_then_removed(frame):
    immich = FakeImmich()
    result = people.refresh(dict(CONFIG, people_followed=["p-mamie"]), immich)
    assert result["downloaded"] == 1 and immich.downloads == ["http://immich.local:2283/api/assets/b1/original"]
    imported = frame / "photos" / "personnes" / "b1_noel.jpg"
    assert imported.read_bytes() == b"original"
    # Une fois préparée, la photo est rattachée à Mamie (sans rappeler Immich)
    (frame / "prepared" / "personnes").mkdir()
    (frame / "prepared" / "personnes" / "b1_noel.jpg").write_bytes(b"x")
    assert people.reindex()["p-mamie"]["files"] == ["personnes/b1_noel.jpg"]
    assert people.refresh(dict(CONFIG, people_followed=["p-mamie"]), immich)["downloaded"] == 0  # déjà là
    people.refresh(CONFIG, immich)  # plus suivie : ses photos importées partent
    assert not imported.exists()


def test_not_configured():
    with pytest.raises(ValueError):
        people.people({}, FakeImmich())


def test_people_api_and_playlist(admin_client, frame, monkeypatch):
    from web import routes_people, routes_slideshow
    from utils.config_manager import load_config, save_config
    from utils.playlist_manager import load_playlists, save_playlists
    original_config, original_playlists = dict(load_config()), load_playlists()
    monkeypatch.setattr(people.requests, "Session", FakeImmich)
    monkeypatch.setattr(routes_people, "PREPARED_DIR", frame / "prepared", raising=False)
    started = []
    monkeypatch.setattr(routes_slideshow, "start_photo_playlist", lambda pid: (started.append(pid), (True, "ok", 200))[1])
    try:
        save_config(dict(original_config, **CONFIG))
        r = admin_client.post("/api/people/refresh", headers=SAME_ORIGIN).get_json()
        assert r["success"] and "2" in r["message"]
        data = admin_client.get("/api/people").get_json()
        assert data["configured"] and [p["name"] for p in data["people"]] == ["Léo", "Mamie"] and data["people"][0]["on_frame"] == 2
        assert admin_client.get(data["people"][0]["thumb"]).status_code == 200
        r = admin_client.post("/api/people/p-leo/play", headers=SAME_ORIGIN).get_json()
        assert r["success"] and started == ["person-p-leo"]
        playlist = next(p for p in load_playlists() if p["id"] == "person-p-leo")
        assert playlist["name"] == "Photos de Léo" and playlist["photos"] == ["immich/IMG_0001.jpg", "immich/clip.mp4"]
        assert admin_client.post("/api/people/inconnu/play", headers=SAME_ORIGIN).status_code == 404
        monkeypatch.setattr(routes_people, "run_people_refresh", lambda config=None: None)
        r = admin_client.post("/api/people/p-mamie/follow", json={"follow": True}, headers=SAME_ORIGIN).get_json()
        assert r["success"] and load_config()["people_followed"] == ["p-mamie"]
    finally:
        save_config(original_config)
        save_playlists(original_playlists)
