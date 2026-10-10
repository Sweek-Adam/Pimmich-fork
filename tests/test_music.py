"""Musique : enceinte Bluetooth (bluetoothctl simulé) et compte Spotify."""
import pytest

from utils import bluetooth_control as bt

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}

SHOW = "Controller B8:27:EB:76:7E:0B (public)\n\tName: Cadre-photo\n\tPowered: yes\n\tDiscoverable: no\n\tPairable: no\n"


@pytest.fixture()
def fake_bluetoothctl(monkeypatch):
    calls = []
    answers = {
        ("show",): SHOW,
        ("devices", "Paired"): "Device 11:22:33:44:55:66 Pixel de Léa\nDevice AA:BB:CC:DD:EE:FF Galaxy\n",
        ("info", "11:22:33:44:55:66"): "Device 11:22:33:44:55:66\n\tConnected: yes\n",
        ("info", "AA:BB:CC:DD:EE:FF"): "Device AA:BB:CC:DD:EE:FF\n\tConnected: no\n",
        ("discoverable", "on"): "Changing discoverable on succeeded\n",
        ("remove", "AA:BB:CC:DD:EE:FF"): "Device has been removed\n",
    }

    def ctl(*args, timeout=8):
        calls.append(args)
        return answers.get(args, "")
    monkeypatch.setattr(bt, "_ctl", ctl)
    return calls


def test_bluetooth_status_lists_paired_phones(fake_bluetoothctl):
    state = bt.status()
    assert state["available"] and state["powered"] and not state["discoverable"]
    assert state["devices"] == [{"mac": "11:22:33:44:55:66", "name": "Pixel de Léa", "connected": True},
                                {"mac": "AA:BB:CC:DD:EE:FF", "name": "Galaxy", "connected": False}]


def test_pairing_window_and_forget(fake_bluetoothctl):
    assert bt.open_pairing()
    assert ("discoverable-timeout", str(bt.PAIRING_SECONDS)) in fake_bluetoothctl
    assert bt.forget("AA:BB:CC:DD:EE:FF")
    with pytest.raises(ValueError):
        bt.forget("AA:BB; reboot")  # jamais d'argument arbitraire passé à bluetoothctl


def test_bluetooth_api(admin_client, fake_bluetoothctl, monkeypatch):
    from web import routes_music
    monkeypatch.setattr(routes_music, "_service_active", lambda name: True)
    data = admin_client.get("/api/bluetooth").get_json()
    assert data["service"] and len(data["devices"]) == 2
    assert admin_client.post("/api/bluetooth/pair", headers=SAME_ORIGIN).get_json()["success"]
    assert admin_client.post("/api/bluetooth/forget", json={"mac": "AA:BB:CC:DD:EE:FF"}, headers=SAME_ORIGIN).get_json()["success"]
    assert admin_client.post("/api/bluetooth/forget", json={"mac": "../../x"}, headers=SAME_ORIGIN).status_code == 400
    monkeypatch.setattr(routes_music, "_service_active", lambda name: False)
    assert admin_client.post("/api/bluetooth/pair", headers=SAME_ORIGIN).status_code == 400


def test_bluetooth_receiver_maps_avrcp_tracks():
    pytest.importorskip("dbus")
    from utils import bluetooth_receiver
    assert bluetooth_receiver.track_fields({"Title": "Titre", "Artist": "Artiste"})["title"] == "Titre"
