"""Marées et partition de la carte SD dans la nouvelle interface (sans appel réseau ni commande système réels)."""
import json

import pytest

H = {"Sec-Fetch-Site": "same-origin"}
TIDE_KEYS = ("show_tides", "tide_latitude", "tide_longitude", "stormglass_api_key", "tide_offset_x", "tide_offset_y")


def lsblk(disk, *parts):
    devices = [{"name": "mmcblk0", "size": disk, "type": "disk", "mountpoint": None, "pkname": None}]
    for i, (size, mount) in enumerate(parts, 1):
        devices.append({"name": f"mmcblk0p{i}", "size": size, "type": "part", "mountpoint": mount, "pkname": "mmcblk0"})
    devices.append({"name": "zram0", "size": 10 ** 9, "type": "disk", "mountpoint": "[SWAP]", "pkname": None})
    return json.dumps({"blockdevices": devices})


def test_rootfs_space():
    from utils import reliability
    full = reliability.rootfs_space(lsblk(127865454592, (536870912, "/boot/firmware"), (127320195072, "/")))
    assert full["known"] and not full["expandable"] and full["unallocated"] == 8388608
    room = reliability.rootfs_space(lsblk(64 * 10 ** 9, (536870912, "/boot/firmware"), (5 * 10 ** 9, "/")))
    assert room["expandable"] and room["partition"] == 5 * 10 ** 9 and room["disk"] == 64 * 10 ** 9
    for bad in ("pas du json", json.dumps({"blockdevices": []})):
        assert reliability.rootfs_space(bad) == {"known": False, "expandable": False}


def test_filesystem_api(admin_client, monkeypatch):
    from utils import reliability
    from web import routes_system
    calls = []
    monkeypatch.setattr(routes_system.subprocess, "run", lambda *a, **k: calls.append(a) or type("R", (), {"returncode": 0})())
    monkeypatch.setattr(reliability, "rootfs_space", lambda: {"known": True, "partition": 1, "disk": 2, "unallocated": 0, "expandable": False})
    assert admin_client.get("/api/filesystem").get_json()["expandable"] is False
    assert admin_client.post("/api/filesystem/expand", headers=H).status_code == 400 and not calls  # rien à agrandir
    monkeypatch.setattr(reliability, "rootfs_space", lambda: {"known": True, "expandable": True})
    data = admin_client.post("/api/filesystem/expand", headers=H).get_json()
    assert data["success"] and calls and calls[0][0][1].endswith("utils/expand_filesystem.sh")


def test_filesystem_api_requires_admin(client):
    assert client.post("/api/filesystem/expand", headers=H).status_code in (302, 401, 403)


@pytest.fixture
def tide_config(app_module):
    from web import routes_settings
    before = dict(routes_settings.load_config())
    yield routes_settings
    config = dict(routes_settings.load_config())
    for key in TIDE_KEYS:
        if key in before:
            config[key] = before[key]
        else:
            config.pop(key, None)
    routes_settings.save_config(config)


def test_tide_settings(admin_client, tide_config):
    data = admin_client.post("/api/settings", json={"show_tides": True, "tide_latitude": " 48,3904 ", "tide_longitude": "-4.4861",
                                                     "tide_offset_y": -20}, headers=H).get_json()
    assert data["success"] and data["values"]["tide_latitude"] == "48.3904" and data["values"]["tide_offset_y"] == -20
    assert admin_client.post("/api/settings", json={"tide_latitude": ""}, headers=H).get_json()["values"]["tide_latitude"] == ""
    for bad in ({"tide_latitude": "abc"}, {"tide_latitude": "91"}, {"tide_longitude": "-181"}, {"tide_latitude": "nan"},
                {"tide_latitude": True}, {"stormglass_api_key": "k"}):
        assert admin_client.post("/api/settings", json=bad, headers=H).status_code == 400, bad


def test_stormglass_test_uses_saved_key(admin_client, tide_config, monkeypatch):
    from web import routes_integrations
    config = dict(tide_config.load_config(), stormglass_api_key="cle-enregistree", tide_latitude="48.39", tide_longitude="-4.48")
    tide_config.save_config(config)
    seen = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        seen.update(headers=headers, params=params)
        return type("R", (), {"status_code": 200})()
    monkeypatch.setattr(routes_integrations.requests, "get", fake_get)
    data = admin_client.post("/test-stormglass-api", json={}, headers=H).get_json()
    assert data["success"] and seen["headers"]["Authorization"] == "cle-enregistree" and seen["params"]["lat"] == "48.39"


def test_tide_info_gives_raw_values(admin_client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "cache").mkdir()
    (tmp_path / "cache" / "tides.json").write_text(json.dumps({"timestamp": "2026-10-11T10:00:00", "data": [
        {"time": "2030-01-01T06:00:00+00:00", "type": "high", "height": 1.234},
        {"time": "2030-01-01T12:10:00+00:00", "type": "low", "height": -0.5}]}))
    data = admin_client.get("/api/tide_info").get_json()
    assert data["success"] and not data["cooldown"] and data["updated"] == "2026-10-11T10:00:00"
    assert [t["high"] for t in data["tides"]] == [True, False] and data["tides"][0]["meters"] == 1.23 and data["tides"][1]["iso"]
