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


def test_compositions_api(admin_client, app_module):
    from web import routes_settings
    config = routes_settings.load_config()
    saved = {k: config.get(k) for k in ("compositions_disabled", "unique_enabled", "compositions_enabled")}
    try:
        data = admin_client.get("/api/compositions").get_json()
        keys = [f["key"] for f in data["formats"]]
        assert keys[0] == "unique" and len(keys) > 10 and any(f["theme"] for f in data["formats"])
        assert any(c["value"] == "auto" for c in data["choices"])
        chosen = ["unique", keys[1]]
        assert admin_client.post("/api/compositions", json={"enabled": chosen}, headers=H).get_json()["success"]
        assert sorted(admin_client.get("/api/compositions").get_json()["enabled"]) == sorted(chosen)
        assert admin_client.post("/api/compositions", json={"enabled": []}, headers=H).status_code == 400
        assert admin_client.post("/api/compositions", json={"enabled": "x"}, headers=H).status_code == 400
    finally:
        config = dict(routes_settings.load_config())
        for key, value in saved.items():
            if value is None:
                config.pop(key, None)
            else:
                config[key] = value
        routes_settings.save_config(config)


def test_media_mode(admin_client, app_module, sandbox, monkeypatch):
    from web import routes_slideshow
    monkeypatch.setattr(routes_slideshow, "is_slideshow_running", lambda: False)
    config = routes_slideshow.load_config()
    saved = config.get("media_mode"), config.get("display_sources")
    folder = sandbox / "static" / "prepared" / "videotest"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "a.mp4").write_bytes(b"x")
    (folder / "b.jpg").write_bytes(b"x")
    try:
        routes_slideshow.save_config(dict(config, display_sources=["videotest"]))
        assert admin_client.get("/api/slideshow/media_mode").get_json()["videos"] == 1
        assert admin_client.post("/api/slideshow/media_mode", json={"mode": "videos"}, headers=H).get_json()["success"]
        assert routes_slideshow.load_config()["media_mode"] == "videos"
        assert admin_client.post("/api/slideshow/media_mode", json={"mode": "photos!"}, headers=H).status_code == 400
        assert admin_client.get("/api/history").get_json()["undo"]
    finally:
        config = dict(routes_slideshow.load_config())
        config["media_mode"], config["display_sources"] = saved[0] or "all", saved[1]
        routes_slideshow.save_config(config)
        import shutil
        shutil.rmtree(folder)


def test_secrets_are_write_only(admin_client, user_client, app_module):
    from web import routes_settings
    before = routes_settings.load_config().get("weather_api_key")
    try:
        assert admin_client.post("/api/secrets", json={"key": "weather_api_key", "value": "abc123"}, headers=H).get_json()["success"]
        data = admin_client.get("/api/secrets").get_json()
        assert data["secrets"]["weather_api_key"] is True and "abc123" not in str(data)
        assert "abc123" not in admin_client.get("/api/settings").get_data(as_text=True)
        assert admin_client.post("/api/secrets", json={"key": "secret_key", "value": "x"}, headers=H).status_code == 400
        assert admin_client.post("/api/secrets", json={"key": "weather_api_key", "value": "a\nb"}, headers=H).status_code == 400
        assert user_client.get("/api/secrets").status_code in (302, 403)
        assert "telegram_authorized_users" not in user_client.get("/api/settings").get_json()["values"]
        assert user_client.post("/api/settings", json={"telegram_authorized_users": "1"}, headers=H).status_code == 400
    finally:
        config = dict(routes_settings.load_config())
        config["weather_api_key"] = before or ""
        routes_settings.save_config(config)


def test_wifi_api(admin_client, user_client, app_module, monkeypatch):
    from web import routes_system
    applied = []
    monkeypatch.setattr(routes_system, "set_wifi_config", lambda *a: applied.append(a))  # jamais le vrai Wi-Fi
    config = routes_system.load_config()
    saved = {k: config.get(k) for k in ("wifi_ssid", "wifi_password", "wifi_country")}
    try:
        assert admin_client.post("/api/wifi", json={"ssid": "", "country": "FR"}, headers=H).status_code == 400
        assert admin_client.post("/api/wifi", json={"ssid": "Maison", "password": "motdepasse", "country": "FR"}, headers=H).get_json()["success"]
        data = admin_client.get("/api/wifi").get_json()
        assert data["ssid"] == "Maison" and data["has_password"] and "motdepasse" not in str(data)
        admin_client.post("/api/wifi", json={"ssid": "Maison", "country": "BE"}, headers=H)
        assert applied[-1] == ("Maison", "motdepasse", "BE")  # mot de passe gardé
        assert user_client.get("/api/wifi").status_code in (302, 403)
    finally:
        config = dict(routes_system.load_config())
        for key, value in saved.items():
            if value is None:
                config.pop(key, None)
            else:
                config[key] = value
        routes_system.save_config(config)


def test_clock_and_interval_settings(admin_client, app_module):
    from web import routes_settings
    keys = ("clock_layout", "clock_background_style", "agenda_every_minutes", "memories_every_minutes", "clock_font_path")
    before = {k: routes_settings.load_config().get(k) for k in keys}
    try:
        data = admin_client.post("/api/settings", json={"clock_layout": "stacked", "clock_background_style": "box",
                                                         "agenda_every_minutes": 60, "memories_every_minutes": 15}, headers=H).get_json()
        assert data["success"] and data["values"]["agenda_every_minutes"] == 60
        assert admin_client.post("/api/settings", json={"agenda_every_minutes": 2}, headers=H).status_code == 400
        assert admin_client.post("/api/settings", json={"clock_font_path": "/etc/passwd"}, headers=H).status_code == 400
        fonts = admin_client.get("/api/settings/fonts").get_json()["fonts"]
        assert fonts and admin_client.post("/api/settings", json={"clock_font_path": fonts[0]["value"]}, headers=H).get_json()["success"]
    finally:
        config = dict(routes_settings.load_config())
        for key, value in before.items():
            if value is None:
                config.pop(key, None)
            else:
                config[key] = value
        routes_settings.save_config(config)


def test_special_slide_interval(app_module):
    import local_slideshow
    assert local_slideshow.special_every({}, "agenda_every_minutes") == 1800
    assert local_slideshow.special_every({"agenda_every_minutes": 60}, "agenda_every_minutes") == 3600
    assert local_slideshow.special_every({"agenda_every_minutes": 1}, "agenda_every_minutes") == 300
    assert local_slideshow.special_every({"agenda_every_minutes": "x"}, "agenda_every_minutes") == 1800


def test_sources_settings(admin_client, app_module, monkeypatch):
    from web import routes_settings
    keys = ("display_sources", "max_photos_to_download", "gdrive_folders")
    before = {k: routes_settings.load_config().get(k) for k in keys}
    try:
        routes_settings.save_config(dict(routes_settings.load_config(), display_sources=["gdrive", "citation", "voyages"]))
        data = admin_client.get("/api/display_sources").get_json()
        assert data["selected"] == ["gdrive"] and any(c["key"] == "messages" for c in data["choices"])
        assert admin_client.post("/api/display_sources", json={"selected": ["immich", "messages"]}, headers=H).get_json()["success"]
        assert routes_settings.load_config()["display_sources"] == ["immich", "messages", "citation", "voyages"]  # sources gérées gardées
        assert admin_client.post("/api/display_sources", json={"selected": ["../etc"]}, headers=H).status_code == 400
        assert admin_client.post("/api/settings", json={"immich_max_photos": 50}, headers=H).get_json()["values"]["immich_max_photos"] == 50
        assert routes_settings.load_config()["max_photos_to_download"]["immich"] == 50
        assert admin_client.post("/api/gdrive/selected_folders", json={"folders": [{"id": "abc", "name": "Photos"}]}, headers=H).get_json()["success"]
        assert routes_settings.load_config()["gdrive_folders"][0]["id"] == "abc"
        monkeypatch.setattr(routes_settings, "list_rclone_remotes", lambda: ["gdrive"])
        assert admin_client.get("/api/gdrive/setup").get_json()["folders"][0]["name"] == "Photos"
        assert admin_client.post("/api/gdrive/service_account", json={"key": "pas du json"}, headers=H).status_code == 400
    finally:
        config = dict(routes_settings.load_config())
        for key, value in before.items():
            if value is None:
                config.pop(key, None)
            else:
                config[key] = value
        routes_settings.save_config(config)
