"""Écran (orientation, dimensions) et prise connectée dans la nouvelle interface : vérification et effets."""
import time

import pytest

H = {"Sec-Fetch-Site": "same-origin"}
KEYS = ("screen_orientation", "display_width", "display_height", "screen_height_percent", "smart_plug_enabled",
        "smart_plug_on_url", "smart_plug_off_url", "smart_plug_status_url", "smart_plug_on_delay")


@pytest.fixture
def display_config(app_module, monkeypatch):
    from web import routes_settings, workers
    calls = []
    monkeypatch.setattr(workers, "reprepare_all_sources", lambda: calls.append("reprepare"))
    before = dict(routes_settings.load_config())
    yield routes_settings, calls
    config = dict(routes_settings.load_config())
    for key in KEYS:
        if key in before:
            config[key] = before[key]
        else:
            config.pop(key, None)
    routes_settings.save_config(config)


def test_orientation_swaps_dimensions_and_reprepares(admin_client, display_config):
    settings, calls = display_config
    admin_client.post("/api/settings", json={"screen_orientation": "landscape", "display_width": 1920, "display_height": 1080}, headers=H)
    time.sleep(0.3)  # repréparation éventuelle de cette mise en place
    calls.clear()
    data = admin_client.post("/api/settings", json={"screen_orientation": "portrait"}, headers=H).get_json()
    assert data["success"] and (data["values"]["display_width"], data["values"]["display_height"]) == (1080, 1920)
    for _ in range(50):  # repréparation lancée en arrière-plan
        if calls:
            break
        time.sleep(0.02)
    assert calls == ["reprepare"]
    calls.clear()
    admin_client.post("/api/settings", json={"screen_height_percent": 90}, headers=H)
    assert calls == []  # même taille : rien à repréparer
    for bad in ({"screen_orientation": "diagonal"}, {"display_width": 10}, {"screen_height_percent": 5}):
        assert admin_client.post("/api/settings", json=bad, headers=H).status_code == 400, bad


def test_smart_plug_urls(admin_client, display_config):
    data = admin_client.post("/api/settings", json={"smart_plug_enabled": True, "smart_plug_on_url": " http://192.168.1.50/cm?cmnd=Power%20On ",
                                                     "smart_plug_status_url": "", "smart_plug_on_delay": 8}, headers=H).get_json()
    assert data["values"]["smart_plug_on_url"] == "http://192.168.1.50/cm?cmnd=Power%20On" and data["values"]["smart_plug_on_delay"] == 8
    for bad in ({"smart_plug_on_url": "ftp://x"}, {"smart_plug_on_url": "javascript:alert(1)"}, {"smart_plug_off_url": "http://a b"},
                {"smart_plug_off_url": "http://" + "a" * 600}, {"smart_plug_on_delay": 99}, {"home_assistant_token": "x"}):
        assert admin_client.post("/api/settings", json=bad, headers=H).status_code == 400, bad


def test_smart_plug_test_needs_http_url(admin_client, monkeypatch):
    from web import routes_integrations
    monkeypatch.setattr(routes_integrations.requests, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("pas d'appel")))
    for url in ("", "file:///etc/passwd", None):
        assert admin_client.post("/api/test_smart_plug", json={"url": url}, headers=H).get_json()["success"] is False
