"""Accueil : ambiances, santé du cadre, assistant, son, disposition immédiate, enregistrement automatique."""
import json

import pytest

from utils import ambiances, health

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}


def test_ambiance_applies_and_restores_my_settings():
    original = {"display_duration": 15, "layout_override": "auto"}
    config = ambiances.apply(original, "zen")
    assert config["display_duration"] == 20 and config["layout_override"] == "unique" and config["ambiance"] == "zen"
    config = ambiances.apply(config, "fete")  # la sauvegarde garde les valeurs d'origine, pas celles de « zen »
    assert config["display_duration"] == 7
    restored = ambiances.apply(config, ambiances.MINE)
    assert restored["display_duration"] == 15 and restored["layout_override"] == "auto"
    assert "compositions_every" not in restored  # absent à l'origine : retour à la valeur par défaut
    with pytest.raises(ValueError):
        ambiances.apply(original, "inconnue")


def test_health_reports_only_real_problems(monkeypatch):
    monkeypatch.setattr(health, "_prepared_count", lambda: 0)
    monkeypatch.setattr(health, "_pending_guest_photos", lambda: 3)
    monkeypatch.setattr(health, "_gdrive_denied_count", lambda: 0)
    items = health.checks({"_active_hours": True}, slideshow_running=False, is_admin=False,
                          worker_messages={"Google Drive": "Erreur Google Drive : timeout", "Samba": "En attente..."})
    titles = [i["title"] for i in items]
    assert "Aucune photo à afficher" in titles and "Le diaporama est arrêté" in titles
    assert "Problème de synchronisation" in titles and "Photos d'invités à valider" in titles
    assert not any("Samba" in i["detail"] for i in items)
    monkeypatch.setattr(health, "_prepared_count", lambda: 10)
    monkeypatch.setattr(health, "_pending_guest_photos", lambda: 0)
    assert health.checks({"_active_hours": False}, slideshow_running=False, is_admin=False) == []


def test_home_apis(admin_client):
    data = admin_client.get("/api/health").get_json()
    assert data["success"] and isinstance(data["items"], list)
    setup = admin_client.get("/api/setup").get_json()
    assert setup["total"] == len(setup["steps"]) >= 5
    admin_client.post("/api/setup/dismiss", json={"dismissed": True}, headers=SAME_ORIGIN)
    assert admin_client.get("/api/setup").get_json()["dismissed"]
    listing = admin_client.get("/api/ambiances").get_json()
    assert {a["key"] for a in listing["ambiances"]} >= {"classique", "fete", "souvenirs", "voyage", "zen"}


def test_apply_ambiance_api(admin_client):
    from utils.config_manager import load_config
    resp = admin_client.post("/api/ambiance", json={"ambiance": "voyage"}, headers=SAME_ORIGIN)
    assert resp.get_json()["success"] and load_config()["ambiance"] == "voyage"
    assert admin_client.post("/api/ambiance", json={"ambiance": "?"}, headers=SAME_ORIGIN).status_code == 400
    admin_client.post("/api/ambiance", json={"ambiance": "perso"}, headers=SAME_ORIGIN)


def test_sound_api(admin_client, sandbox):
    music = sandbox / "static" / "music"
    music.mkdir(parents=True, exist_ok=True)
    (music / "douce.mp3").write_bytes(b"ID3")
    data = admin_client.get("/api/sound").get_json()
    assert "douce.mp3" in data["files"] and set(data["receivers"]) == {"spotify", "airplay", "bluetooth"}
    resp = admin_client.post("/api/sound", json={"background_music": "douce.mp3", "music_volume": 150}, headers=SAME_ORIGIN)
    assert resp.get_json()["success"]
    from utils.config_manager import load_config
    assert load_config()["background_music"] == "douce.mp3" and load_config()["music_volume"] == 100
    assert admin_client.post("/api/sound", json={"background_music": "../../etc/passwd"}, headers=SAME_ORIGIN).status_code == 400


def test_force_layout_now(admin_client, monkeypatch, tmp_path):
    from web import routes_home
    signals = []
    monkeypatch.setattr(routes_home, "FORCE_LAYOUT_FILE", tmp_path / "force.json")
    monkeypatch.setattr(routes_home, "_send_slideshow_signal", lambda sig: signals.append(sig))
    monkeypatch.setattr(routes_home, "is_slideshow_running", lambda: True)
    resp = admin_client.post("/api/slideshow/layout/now", json={"layout": "hokusai"}, headers=SAME_ORIGIN)
    assert resp.get_json()["success"] and json.loads((tmp_path / "force.json").read_text())["layout"] == "hokusai" and signals
    assert admin_client.post("/api/slideshow/layout/now", json={"layout": "auto"}, headers=SAME_ORIGIN).status_code == 400


def test_guest_qr_code(admin_client):
    resp = admin_client.get("/api/guest_qr.png")
    assert resp.status_code == 200 and resp.mimetype == "image/png" and resp.headers["X-Guest-Url"].endswith("/upload")


def test_autosave_returns_json_without_flash(admin_client):
    from utils.config_manager import load_config
    resp = admin_client.post("/configure", data={"display_duration": "17"}, headers={**SAME_ORIGIN, "X-Autosave": "1"})
    assert resp.status_code == 200 and resp.get_json()["success"]
    assert load_config()["display_duration"] == 17
    html = admin_client.get("/configure").get_data(as_text=True)
    assert "Configuration enregistrée" not in html  # pas de message en attente


def test_new_home_layout_is_rendered(admin_client):
    html = admin_client.get("/configure").get_data(as_text=True)
    for marker in ('id="tab-accueil"', 'id="app-bottomnav"', 'id="settings-search"', 'id="layout-picker"', 'id="tab-son"', 'id="tab-invites"'):
        assert marker in html
