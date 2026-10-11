"""Réglages en JSON (nouvelle interface) : valeurs par défaut, vérification stricte, enregistrement annulable."""
import pytest

H = {"Sec-Fetch-Site": "same-origin"}
KEYS = ("display_duration", "dim_start", "transition_type", "night_mode", "pan_zoom_factor", "dim_enabled", "clock_color", "weather_city")


@pytest.fixture
def saved_config(app_module):
    from web import routes_settings
    before = {k: routes_settings.load_config().get(k) for k in KEYS}
    yield routes_settings
    config = dict(routes_settings.load_config())
    for key, value in before.items():
        if value is None:
            config.pop(key, None)
        else:
            config[key] = value
    routes_settings.save_config(config)


def test_settings_defaults(admin_client, saved_config):
    values = admin_client.get("/api/settings").get_json()["values"]
    assert set(saved_config.SETTINGS) == set(values)
    assert isinstance(values["display_duration"], int) and values["transition_fps"] in ("auto", "30", "60")


def test_settings_save_and_validate(admin_client, saved_config):
    r = admin_client.post("/api/settings", json={"display_duration": 25, "dim_start": "sunset", "transition_type": "iris",
                                                  "pan_zoom_factor": 1.3, "dim_enabled": True}, headers=H)
    data = r.get_json()
    assert data["success"] and data["values"]["display_duration"] == 25 and data["values"]["dim_start"] == "sunset"
    config = saved_config.load_config()
    assert config["transition_type"] == "iris" and config["pan_zoom_factor"] == 1.3
    for bad in ({"display_duration": 1}, {"display_duration": "abc"}, {"dim_enabled": "yes"}, {"transition_type": "boum"},
                {"dim_start": "25:00"}, {"secret_key": "x"}, {"immich_token": "x"}, {}, {"clock_color": "red"},
                {"clock_color": "#12345"}, {"weather_city": "x" * 81}, {"weather_city": "Paris\nLyon"}, {"weather_api_key": "k"}):
        assert admin_client.post("/api/settings", json=bad, headers=H).status_code == 400, bad
    assert saved_config.load_config()["display_duration"] == 25  # rien n'a changé après les refus
    data = admin_client.post("/api/settings", json={"clock_color": "#00000080", "weather_city": " Lyon "}, headers=H).get_json()
    assert data["values"]["clock_color"] == "#00000080" and data["values"]["weather_city"] == "Lyon"


def test_settings_undo(admin_client, saved_config):
    admin_client.post("/api/settings", json={"display_duration": 42}, headers=H)
    history = admin_client.get("/api/history").get_json()
    assert history["undo"] and history["events"][0]["kind"] == "settings"


def test_settings_requires_login(client):
    assert client.get("/api/settings").status_code in (302, 401)
