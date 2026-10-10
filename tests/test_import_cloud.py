"""Autres clouds : même synchronisation que Google Drive, dans la source « cloud »."""
import threading

import pytest

import utils.import_cloud as c
import utils.import_gdrive as g
from tests.test_import_gdrive import FakeDrive

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}


@pytest.fixture()
def cloud(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "TARGET_DIR", tmp_path / "photos" / "cloud")
    monkeypatch.setattr(c, "PREPARED_DIR", tmp_path / "prepared" / "cloud")
    monkeypatch.setattr(c, "MANIFEST_FILE", tmp_path / "photos" / "cloud" / ".cloud_manifest.json")
    monkeypatch.setattr(c, "_sync_lock", threading.Lock())
    monkeypatch.setattr(g, "TARGET_DIR", tmp_path / "photos" / "gdrive")  # Google Drive : jamais touché
    fake = FakeDrive({"x": "plage.jpg"})
    monkeypatch.setattr(c, "CloudBackend", lambda remote: fake)
    monkeypatch.setattr(c, "remotes", lambda: [{"name": "dropbox", "type": "dropbox", "label": "Dropbox"}])
    return fake, tmp_path


def test_sync_goes_to_the_cloud_source(cloud):
    fake, tmp = cloud
    config = {"cloud_rclone_remote": "dropbox", "cloud_folders": [{"id": "Photos", "name": "Photos"}], "cloud_trash_after_import": True}
    updates = list(c.import_cloud_photos(config))
    assert updates[-1]["type"] == "done" and "Dropbox" in updates[-1]["message"]
    assert (tmp / "photos" / "cloud" / "plage.jpg").exists() and (tmp / "photos" / "cloud" / ".cloud_manifest.json").exists()
    assert not (tmp / "photos" / "gdrive").exists()
    assert fake.trashed == ["plage.jpg"]


def test_add_remote_validates_the_token(monkeypatch):
    calls = []
    monkeypatch.setattr(c.subprocess, "run", lambda args, **k: calls.append(args) or type("R", (), {"returncode": 0, "stderr": ""})())
    with pytest.raises(ValueError):
        c.add_remote("dropbox", "dropbox", "pas du json")
    with pytest.raises(ValueError):
        c.add_remote("../x", "dropbox", '{"access_token": "a"}')
    c.add_remote("dropbox", "dropbox", '{"access_token": "a", "token_type": "bearer"}')
    assert calls[-1][:5] == ["rclone", "config", "create", "dropbox", "dropbox"]


def test_cloud_api(admin_client, cloud, monkeypatch):
    from utils.config_manager import load_config
    assert admin_client.get("/api/cloud").get_json()["remotes"][0]["label"] == "Dropbox"
    assert admin_client.post("/api/cloud", json={"remote": "inconnu"}, headers=SAME_ORIGIN).status_code == 400
    r = admin_client.post("/api/cloud", json={"remote": "dropbox", "folders": [{"id": "Photos", "name": "Photos"}], "auto": True}, headers=SAME_ORIGIN)
    config = load_config()
    assert r.get_json()["success"] and config["cloud_folders"] == [{"id": "Photos", "name": "Photos"}] and "cloud" in config["display_sources"]
    from web import routes_imports
    monkeypatch.setattr(routes_imports, "run_cloud_sync", lambda config: None)
    assert admin_client.post("/api/cloud/sync", headers=SAME_ORIGIN).get_json()["success"]
