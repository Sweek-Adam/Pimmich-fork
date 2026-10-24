"""Profils matériels : détection du Raspberry Pi, limites internes, réglages conseillés (jamais imposés)."""
from pathlib import Path

import pytest

from utils import hardware_profile as hp

SAME = {"Sec-Fetch-Site": "same-origin"}


@pytest.mark.parametrize("model, ram, expected", [
    ("Raspberry Pi 2 Model B Rev 1.1", 924, "leger"),
    ("Raspberry Pi Zero 2 W Rev 1.0", 427, "leger"),
    ("Raspberry Pi Model B Rev 2", 427, "leger"),
    ("Raspberry Pi 3 Model B Plus Rev 1.3", 905, "standard"),
    ("Raspberry Pi 4 Model B Rev 1.1", 924, "standard"),   # Pi 4 avec 1 Go
    ("Raspberry Pi 4 Model B Rev 1.4", 3796, "complet"),
    ("Raspberry Pi 5 Model B Rev 1.0", 8000, "complet"),
    (None, 16000, "complet"),                              # ordinateur
])
def test_detection(model, ram, expected):
    assert hp.detect(model or "", ram) == expected


def test_user_settings_win_over_the_profile(monkeypatch):
    monkeypatch.setattr(hp, "detect", lambda *a: "leger")
    assert hp.current({}) == "leger" and hp.current({"hardware_profile": "complet"}) == "complet"
    assert hp.setting({}, "video_night_above_mb") == 20
    assert hp.setting({"video_night_above_mb": 300}, "video_night_above_mb") == 300
    diff = hp.recommended({}, {"pan_zoom_enabled": True, "weather_animation": "off", "smart_crop": True})
    assert {d["key"] for d in diff} >= {"pan_zoom_enabled", "smart_crop"} and "weather_animation" not in {d["key"] for d in diff}


def test_small_pi_prepares_every_video_in_720p(tmp_path, monkeypatch):
    from utils import prepare_all_photos as prep
    monkeypatch.setattr(hp, "detect", lambda *a: "leger")
    monkeypatch.setattr(prep, "load_config", lambda: {})
    monkeypatch.setattr(prep, "get_pi_model", lambda: 2)
    monkeypatch.setattr(prep, "video_duration", lambda p: None)
    commands = []
    monkeypatch.setattr(prep, "run_ffmpeg", lambda c, d=None, p=None: (commands.append(c), Path(c[-1]).write_bytes(b"ok"), (0, ""))[2])
    import subprocess
    monkeypatch.setattr(prep.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""))
    (tmp_path / "photos" / "s").mkdir(parents=True)
    (tmp_path / "prepared" / "s").mkdir(parents=True)
    video = tmp_path / "photos" / "s" / "petite.mp4"
    video.write_bytes(b"x" * 1000)  # petite vidéo : allégée quand même sur un petit Pi
    prep.prepare_video(str(video), str(tmp_path / "prepared" / "s" / "petite.mp4"), 1920, 1080)
    assert "1280:720" in " ".join(commands[-1])


def test_profile_api_and_apply(admin_client, monkeypatch):
    from utils.config_manager import load_config, save_config
    original = dict(load_config())
    try:
        save_config(dict(original, pan_zoom_enabled=True, hardware_profile="leger"))
        data = admin_client.get("/api/hardware_profile").get_json()
        assert data["current"] == "leger" and data["limits"]["videos_always_light"]
        assert any(r["key"] == "pan_zoom_enabled" for r in data["recommended"])
        r = admin_client.post("/api/hardware_profile/apply", headers=SAME).get_json()
        assert r["success"] and load_config()["pan_zoom_enabled"] is False
        assert admin_client.get("/api/hardware_profile").get_json()["recommended"] == []
        assert admin_client.get("/api/settings").get_json()["values"]["video_night_above_mb"] == 20
    finally:
        save_config(original)


def test_profile_api_is_admin_only(user_client):
    assert user_client.get("/api/hardware_profile").status_code in (302, 401, 403)
