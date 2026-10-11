"""Le soir et la nuit : soleil et lune calculés sur le cadre, baisse de luminosité, horloge de nuit."""
from datetime import date, datetime, timedelta, timezone

from utils import night, sky

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}
PARIS_SUMMER = timezone(timedelta(hours=2))


def test_sun_times_paris():
    sunrise, sunset = sky.sun_times(48.8566, 2.3522, date(2025, 6, 21), PARIS_SUMMER)
    assert (sunrise.hour, abs(sunrise.minute - 47) <= 3) == (5, True)  # 5 h 47
    assert (sunset.hour, abs(sunset.minute - 58) <= 3) == (21, True)  # 21 h 58
    assert sky.sun_times(78.2, 15.6, date(2025, 6, 21)) == (None, None)  # Svalbard : jour polaire


def test_moon_phases():
    full = sky.moon(datetime(2024, 4, 23, 23, 49, tzinfo=timezone.utc))
    assert full["phase"] == "full" and full["illumination"] > 0.98
    new = sky.moon(datetime(2024, 4, 8, 18, 21, tzinfo=timezone.utc))
    assert new["phase"] == "new" and new["illumination"] < 0.02
    assert sky.moon(datetime(2024, 4, 15, 19, 13, tzinfo=timezone.utc))["phase"] == "first_quarter"


def test_location(monkeypatch, tmp_path):
    monkeypatch.setattr(sky, "LOCATION_FILE", tmp_path / "location.json")
    assert sky.location({}) is None
    sky.remember_location(43.48, -1.56)
    assert sky.location({}) == (43.48, -1.56) and sky.location({"latitude": "45", "longitude": "5"}) == (45.0, 5.0)
    assert "sunset" in sky.today({}) and "moon" in sky.today({})


def test_evening_brightness_ramps_then_returns_in_the_morning():
    config = {"dim_enabled": True, "dim_start": "21:00", "dim_level": 40, "active_start_weekday": "07:00"}
    at = lambda h, m=0: datetime(2025, 10, 13, h, m)  # un lundi
    assert night.brightness(config, at(20, 59)) == 1.0
    assert 0.65 < night.brightness(config, at(21, 22)) < 0.75  # à mi-chemin
    assert night.brightness(config, at(23, 30)) == 0.4
    assert night.brightness(dict(config), datetime(2025, 10, 14, 6, 30)) == 0.4  # la nuit, jusqu'au matin
    assert night.brightness(config, datetime(2025, 10, 14, 7, 0)) == 1.0
    assert night.brightness(dict(config, dim_enabled=False), at(23)) == 1.0
    sunset = datetime(2025, 10, 13, 19, 10)
    assert night.brightness(dict(config, dim_start="sunset"), at(20, 30), sunset=sunset) == 0.4


def test_night_clock_helpers():
    assert night.clock_at_night({"night_mode": "clock"}) and not night.clock_at_night({})
    assert night.clock_color({"night_brightness": 100, "night_color": "red"}) == (255, 60, 40)
    assert max(night.clock_color({"night_brightness": 20})) <= 60
    positions = {night.drift(datetime(2025, 1, 1, 3, m), 1920, 1080, 800, 400) for m in range(0, 60)}
    assert len(positions) > 10 and all(0 <= x <= 1120 and 0 <= y <= 680 for x, y in positions)


def test_settings_are_saved(admin_client):
    from utils.config_manager import load_config, save_config
    original = dict(load_config())
    try:
        form = {"night_form": "1", "dim_enabled": "on", "dim_start": "sunset", "dim_level": "5", "night_mode": "clock",
                "night_color": "violet", "night_brightness": "30"}
        admin_client.post("/configure", data=form, headers=dict(SAME_ORIGIN, **{"X-Autosave": "1"}))
        config = load_config()
        assert config["dim_enabled"] and config["dim_start"] == "sunset" and config["dim_level"] == 10
        assert config["night_mode"] == "clock" and config["night_color"] == "amber" and config["night_brightness"] == 30
        assert config["night_show_date"] is False
    finally:
        save_config(original)
