"""Albums partagés iCloud : lecture de l'album public, synchronisation, légendes, réglages."""
import json

import pytest

from utils import import_icloud

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}
TOKEN = "B0aGWZuqDGabcde"


class FakeResponse:
    def __init__(self, status=200, payload=None, body=b""):
        self.status_code, self._payload, self.body, self.headers = status, payload, body, {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise import_icloud.requests.HTTPError(str(self.status_code))

    def iter_content(self, size):
        yield self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeICloud:
    """Faux serveur iCloud : redirige d'abord vers un autre serveur (330), comme le vrai."""

    def __init__(self, photos):
        self.photos, self.hosts, self.downloads = photos, [], []

    def post(self, url, data, headers, timeout):
        host = url.split("/")[2]
        self.hosts.append(host)
        if host != "p42-sharedstreams.icloud.com":
            return FakeResponse(330, {"X-Apple-MMe-Host": "p42-sharedstreams.icloud.com"})
        if url.endswith("/webstream"):
            return FakeResponse(payload={"streamName": "Vacances", "photos": self.photos})
        guids = json.loads(data)["photoGuids"]
        items = {}
        for photo in self.photos:
            if photo["photoGuid"] in guids:
                for d in photo["derivatives"].values():
                    ext = "MP4" if photo.get("mediaAssetType") == "video" else "JPG"
                    items[d["checksum"]] = {"url_location": "cvws.icloud-content.com", "url_path": f"/{d['checksum']}/IMG.{ext}?o=1"}
        return FakeResponse(payload={"items": items})

    def get(self, url, stream, timeout):
        self.downloads.append(url)
        return FakeResponse(body=b"media:" + url.encode())


def photo(guid, caption="", video=False):
    derivatives = {"1024": {"checksum": f"{guid}s", "fileSize": "100"}, "2048": {"checksum": f"{guid}l", "fileSize": "900"}}
    if video:
        derivatives = {"PosterFrame": {"checksum": f"{guid}p", "fileSize": "99999"}, "720p": {"checksum": f"{guid}v", "fileSize": "5000"}}
    return {"photoGuid": guid, "caption": caption, "derivatives": derivatives, **({"mediaAssetType": "video"} if video else {})}


@pytest.fixture
def icloud_dirs(sandbox, monkeypatch, tmp_path):
    monkeypatch.setattr(import_icloud, "TARGET_DIR", tmp_path / "icloud")
    monkeypatch.setattr(import_icloud, "MANIFEST_FILE", tmp_path / "icloud" / ".icloud_manifest.json")
    monkeypatch.setattr(import_icloud, "CAPTIONS_FILE", tmp_path / "captions.json")
    monkeypatch.setattr(import_icloud, "CANCEL_FLAG", tmp_path / "cancel.flag")
    return tmp_path / "icloud"


def test_album_token_from_links():
    assert import_icloud.album_token(f"https://www.icloud.com/sharedalbum/#{TOKEN}") == TOKEN
    assert import_icloud.album_token(f"https://www.icloud.com/sharedalbum/fr-fr/#{TOKEN}/") == TOKEN
    assert import_icloud.album_token(TOKEN) == TOKEN
    for bad in ("", "https://example.com/#../../etc", "#abc"):
        with pytest.raises(ValueError):
            import_icloud.album_token(bad)
    assert import_icloud._host("B0aGW") == "p36-sharedstreams.icloud.com"
    assert import_icloud._host("A1xyz") == "p01-sharedstreams.icloud.com"


def test_album_follows_redirect_and_picks_best_version():
    server = FakeICloud([photo("g1", "Plage"), photo("g2", video=True)])
    content = import_icloud.album(TOKEN, server)
    assert server.hosts[0] != "p42-sharedstreams.icloud.com" and server.hosts[-1] == "p42-sharedstreams.icloud.com"
    assert content["name"] == "Vacances"
    by_guid = {i["guid"]: i for i in content["items"]}
    assert by_guid["g1"]["checksum"] == "g1l" and by_guid["g1"]["caption"] == "Plage"
    assert by_guid["g2"]["checksum"] == "g2v" and by_guid["g2"]["video"]  # la vidéo, pas son affiche


def test_sync_downloads_captions_and_removes(icloud_dirs):
    config = {"icloud_albums": [{"url": TOKEN}]}
    server = FakeICloud([photo("g1", "Plage"), photo("g2", video=True)])
    events = list(import_icloud.import_icloud_photos(config, server))
    assert events[-1]["type"] == "done" and events[-1]["changes"] == 2
    files = sorted(p.name for p in icloud_dirs.iterdir() if not p.name.startswith("."))
    assert files == [f"{TOKEN[:8]}_g1.jpg", f"{TOKEN[:8]}_g2.mp4"]
    assert import_icloud.captions() == {f"{TOKEN[:8]}_g1.jpg": "Plage"}
    # Deuxième passage : rien à télécharger
    server.downloads.clear()
    assert list(import_icloud.import_icloud_photos(config, server))[-1]["changes"] == 0 and server.downloads == []
    # Photo retirée de l'album : retirée du cadre
    server.photos = [photo("g2", video=True)]
    assert list(import_icloud.import_icloud_photos(config, server))[-1]["changes"] == 1
    assert not (icloud_dirs / f"{TOKEN[:8]}_g1.jpg").exists() and import_icloud.captions() == {}


def test_unreadable_album_keeps_photos(icloud_dirs):
    server = FakeICloud([photo("g1")])
    list(import_icloud.import_icloud_photos({"icloud_albums": [{"url": TOKEN}]}, server))

    class Down(FakeICloud):
        def post(self, *a, **k):
            return FakeResponse(404)
    events = list(import_icloud.import_icloud_photos({"icloud_albums": [{"url": TOKEN}]}, Down([])))
    assert events[-1]["type"] == "error"
    assert (icloud_dirs / f"{TOKEN[:8]}_g1.jpg").exists()


def test_icloud_api(admin_client, monkeypatch):
    from web import routes_imports
    from utils.config_manager import load_config, save_config
    monkeypatch.setattr(routes_imports, "run_icloud_sync", lambda config: None)
    monkeypatch.setattr(import_icloud, "album", lambda url: {"name": "Noël", "token": TOKEN, "items": [{}] * 3})
    original = dict(load_config())
    try:
        r = admin_client.post("/api/icloud/album", json={"url": TOKEN}, headers=SAME_ORIGIN).get_json()
        assert r["success"] and "Noël" in r["message"]
        config = load_config()
        assert config["icloud_albums"][0]["count"] == 3 and "icloud" in config["display_sources"]
        assert admin_client.get("/api/icloud").get_json()["albums"][0]["name"] == "Noël"
        admin_client.post("/api/icloud", json={"remove": TOKEN, "auto": False}, headers=SAME_ORIGIN)
        assert load_config()["icloud_albums"] == [] and load_config()["icloud_auto_update"] is False
        assert admin_client.post("/api/icloud/sync", headers=SAME_ORIGIN).status_code == 400

        def broken(url):
            raise ValueError("Lien invalide")
        monkeypatch.setattr(import_icloud, "album", broken)
        assert admin_client.post("/api/icloud/album", json={"url": "x"}, headers=SAME_ORIGIN).status_code == 400
    finally:
        save_config(original)
