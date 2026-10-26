"""Mode fête : QR code « rejoindre le Wi-Fi » (mot de passe lu dans NetworkManager, jamais enregistré)."""
import subprocess

import pytest

from utils import wifi_networks


def fake_nmcli(cmd, **kwargs):
    args = cmd[3:]
    if args[:3] == ["-t", "-f", "NAME,UUID,TYPE,AUTOCONNECT,AUTOCONNECT-PRIORITY,ACTIVE"]:
        out = "Maison:1111:802-11-wireless:yes:10:yes\nVoisin:2222:802-11-wireless:yes:0:no\n"
    elif "802-11-wireless.ssid,802-11-wireless-security.psk" in args and "1111" in args:
        out = "Maison\\:Box\nmot;de:passe\n"
    else:
        out = ""
    return subprocess.CompletedProcess(cmd, 0, out, "")


def test_join_payload_from_the_active_network():
    ssid, payload = wifi_networks.join_payload(runner=fake_nmcli)
    assert ssid == "Maison:Box"
    assert payload == "WIFI:T:WPA;S:Maison\\:Box;P:mot\;de\\:passe;;"
    assert wifi_networks.join_payload(runner=lambda cmd, **k: subprocess.CompletedProcess(cmd, 0, "", "")) is None


def test_party_keeps_the_choice_and_the_password_is_not_saved():
    from utils import party
    config = party.start({}, "Mariage", 4, wifi_qr=True)
    assert config["party"]["wifi_qr"] is True
    assert "mot;de:passe" not in str(config)


def test_qr_drawn_next_to_the_upload_qr(monkeypatch):
    pygame = pytest.importorskip("pygame")
    import local_slideshow as ls
    monkeypatch.setattr(wifi_networks, "join_payload", lambda: ("Maison", "WIFI:T:WPA;S:Maison;P:x;;"))
    pygame.font.init()
    ls._wifi_qr_cache.update(read=0, height=None, surface=None)
    surface = ls._wifi_qr_surface(200)
    assert surface is not None and surface.get_height() <= 200
