"""Plusieurs réseaux Wi-Fi mémorisés, point d'accès de secours et heure non synchronisée (sans nmcli réel)."""
from pathlib import Path

from utils import clock_sync, hotspot, wifi_networks

H = {"Sec-Fetch-Site": "same-origin"}
UUID1, UUID2 = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"


class FakeNmcli:
    def __init__(self, show="", device=""):
        self.calls, self.show, self.device = [], show, device

    def __call__(self, cmd, capture_output=True, text=True, timeout=None):
        self.calls.append(cmd)
        args = cmd[3:]
        out = self.show if args[-2:] == ["connection", "show"] else (self.device if args[-1:] == ["device"] else "")
        return type("R", (), {"returncode": 0, "stdout": out, "stderr": ""})()


SHOW = (f"Maison:{UUID1}:802-11-wireless:yes:10:yes\n"
        f"Chez Mamie\\: étage:{UUID2}:802-11-wireless:yes:30:no\n"
        "Wired connection 1:33333333-3333-3333-3333-333333333333:802-3-ethernet:yes:0:no\n"
        "pimmich-hotspot:44444444-4444-4444-4444-444444444444:802-11-wireless:no:0:no\n")


def test_saved_networks_sorted_by_preference():
    networks = wifi_networks.saved(FakeNmcli(SHOW))
    assert [n["name"] for n in networks] == ["Chez Mamie: étage", "Maison"]  # priorité 30 puis 10 ; ni câble ni secours
    assert networks[1]["active"] and not networks[0]["active"]


def test_add_out_of_range_network_and_reorder():
    fake = FakeNmcli(SHOW)
    assert wifi_networks.add("Camping", "motdepasse", hidden=True, runner=fake)[0]
    add = fake.calls[-1]
    assert add[3:8] == ["connection", "add", "type", "wifi", "con-name"] and "wlan0" in add
    assert add[add.index("802-11-wireless.hidden") + 1] == "yes" and add[add.index("connection.autoconnect-priority") + 1] == "40"
    assert add[add.index("wifi-sec.psk") + 1] == "motdepasse"
    wifi_networks.add("Maison", "", runner=fake)  # déjà connu, sans nouveau mot de passe : modifié, mot de passe gardé
    assert fake.calls[-1][3:6] == ["connection", "modify", "uuid"] and "wifi-sec.psk" not in fake.calls[-1]
    wifi_networks.reorder([UUID1, UUID2], runner=fake)
    assert [c[-1] for c in fake.calls[-2:]] == ["20", "10"]
    assert wifi_networks.check("", "") == "ssid" and wifi_networks.check("x" * 33, "") == "ssid"
    assert wifi_networks.check("Ok", "court") == "password" and wifi_networks.check("Ok", "") is None


def test_online_ignores_the_hotspot():
    assert wifi_networks.online(FakeNmcli(device="wlan0:wifi:connected:Maison\nlo:loopback:connected (externally):lo"))
    assert not wifi_networks.online(FakeNmcli(device="wlan0:wifi:connected:pimmich-hotspot\neth0:ethernet:unavailable:"))


def test_fallback_opens_then_retries_known_networks():
    now = [0.0]
    events = []
    actions = {"start": lambda key: events.append(("start", key)) or (True, ""), "stop": lambda: events.append("stop"),
               "clients": lambda: 0, "wait": lambda s: events.append(("wait", s)), "online": lambda: False}
    f = hotspot.Fallback(clock=lambda: now[0])
    assert f.step(True, True, "k", actions) == "idle"
    assert f.step(True, False, "k", actions) == "waiting"
    now[0] = hotspot.OFFLINE_DELAY
    assert f.step(True, False, "k", actions) == "started" and events == [("start", "k")]
    now[0] += 60
    assert f.step(True, False, "k", actions) == "kept"
    now[0] += hotspot.RETRY_EVERY
    assert f.step(True, False, "k", actions) == "restarted"  # personne dessus, toujours aucun réseau connu
    actions["online"] = lambda: True
    now[0] += hotspot.RETRY_EVERY
    assert f.step(True, False, "k", actions) == "back_online"
    assert f.step(False, False, "k", actions) == "idle"  # désactivé : jamais de point d'accès


def test_wifi_qr_payload_is_escaped():
    assert hotspot.qr_payload("Cadre;Pimmich", 'a"b') == r'WIFI:T:WPA;S:Cadre\;Pimmich;P:a\"b;;'


def test_unsynced_clock_is_not_trusted(monkeypatch, tmp_path):
    run = lambda out: (lambda *a, **k: type("R", (), {"stdout": out})())
    monkeypatch.setattr(clock_sync, "_cache", {"at": -1e9, "value": True})
    assert clock_sync.trusted(run("no\n"), rtc=tmp_path / "pas-de-rtc", ttl=0) is False
    assert clock_sync.trusted(run("yes\n"), rtc=tmp_path / "pas-de-rtc", ttl=0) is True
    assert clock_sync.trusted(run("no\n"), rtc=tmp_path, ttl=0) is True  # horloge sur pile (Pi 5) : fiable


def test_wifi_api_validation(admin_client, monkeypatch):
    monkeypatch.setattr(wifi_networks, "nmcli", lambda *a, **k: (True, ""))
    for bad in ({"ssid": ""}, {"ssid": "Maison", "password": "court"}):
        assert admin_client.post("/api/wifi/networks", json=bad, headers=H).status_code == 400
    assert admin_client.post("/api/wifi/networks", json={"ssid": "Maison", "password": "motdepasse"}, headers=H).get_json()["success"]
    assert admin_client.delete("/api/wifi/networks/pas-un-uuid", headers=H).status_code == 400
    assert admin_client.post("/api/wifi/networks/order", json={"uuids": ["x"]}, headers=H).status_code == 400
    assert admin_client.post("/api/wifi/country", json={"country": "France"}, headers=H).status_code == 400
    data = admin_client.get("/api/wifi/networks").get_json()
    assert data["success"] and data["hotspot"]["ssid"] == "Cadre-Pimmich"
