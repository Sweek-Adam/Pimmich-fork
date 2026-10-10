"""Présence : arrivée d'un téléphone de la famille sur le Wi-Fi."""
import pytest

from utils import presence

LEA = {"mac": "AA:BB:CC:DD:EE:01", "name": "Léa", "playlist": None}
SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(presence, "STATE_FILE", tmp_path / "presence.json")


def test_arrival_only_after_an_absence():
    t = 1_000_000
    assert presence.tick([LEA], now=t, seen={"aa:bb:cc:dd:ee:01": "192.168.1.30"}) == []  # premier passage : pas d'accueil
    assert presence.tick([LEA], now=t + 60, seen={}) == []
    assert presence.status([LEA])[0]["present"]  # absente depuis 1 min seulement : toujours là
    presence.tick([LEA], now=t + 25 * 60, seen={})  # 25 min sans la voir : partie
    assert not presence.status([LEA])[0]["present"]
    assert presence.tick([LEA], now=t + 26 * 60, seen={"aa:bb:cc:dd:ee:01": "192.168.1.30"}) == []  # partie < 30 min : pas une arrivée
    presence.tick([LEA], now=t + 50 * 60, seen={})
    presence.tick([LEA], now=t + 80 * 60, seen={})
    assert presence.tick([LEA], now=t + 90 * 60, seen={"aa:bb:cc:dd:ee:01": "192.168.1.31"}) == [LEA]  # vraie arrivée


def test_neighbors_parsing(monkeypatch):
    out = ("192.168.1.30 dev wlan0 lladdr aa:bb:cc:dd:ee:01 REACHABLE\n192.168.1.1 dev wlan0 lladdr 11:22:33:44:55:66 STALE\n"
           "192.168.1.99 dev wlan0  FAILED\n")
    monkeypatch.setattr(presence.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": out})())
    assert [n["mac"] for n in presence.neighbors()] == ["aa:bb:cc:dd:ee:01", "11:22:33:44:55:66"]


def test_presence_api(admin_client, monkeypatch):
    from utils.config_manager import load_config
    monkeypatch.setattr(presence, "neighbors", lambda: [{"ip": "192.168.1.30", "mac": "aa:bb:cc:dd:ee:01", "state": "REACHABLE"}])
    monkeypatch.setattr(presence, "hostname", lambda ip: "iPhone-de-Lea")
    assert admin_client.get("/api/presence").get_json()["detected"][0]["name"] == "iPhone-de-Lea"
    r = admin_client.post("/api/presence", json={"enabled": True, "devices": [LEA]}, headers=SAME_ORIGIN).get_json()
    assert r["success"] and load_config()["presence_devices"][0]["mac"] == "aa:bb:cc:dd:ee:01"
    assert admin_client.get("/api/presence").get_json()["detected"] == []  # déjà suivi
    assert admin_client.post("/api/presence", json={"devices": [{"mac": "rm -rf /"}]}, headers=SAME_ORIGIN).status_code == 400


def test_arrival_greets_and_wakes_the_frame(app_module, monkeypatch):
    from web import workers
    from utils.config_manager import load_config
    created, started = [], []
    monkeypatch.setattr(workers.messages_manager, "create_message", lambda *a, **k: created.append(a[1]) or {"id": "m1"})
    monkeypatch.setattr(workers, "is_slideshow_running", lambda: False)
    monkeypatch.setattr(workers, "set_display_power", lambda on: None)
    monkeypatch.setattr(workers, "start_slideshow", lambda: started.append(1))
    monkeypatch.setattr(workers.time, "sleep", lambda s: None)
    with app_module.app.app_context():
        workers.handle_arrival(LEA, load_config())
    assert created == ["Bienvenue à la maison, Léa !"] and started
    config = load_config()
    assert config["manual_override"] == "start" and config["presence_wake_until"]
    config.update(manual_override=None)
    config.pop("presence_wake_until")
    from utils.config_manager import save_config
    save_config(config)
