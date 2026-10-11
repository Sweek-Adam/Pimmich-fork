"""Fiabilité : diaporama figé détecté (sans fausse alerte au démarrage ni pendant une vidéo), rotation des journaux."""
import gzip

from utils import reliability


def test_frozen_detection():
    now = 10_000
    assert not reliability.frozen(10, now, {"at": now - 60})
    assert reliability.frozen(10, now, {"at": now - 200})
    assert not reliability.frozen(10, now, {"at": now - 200, "grace": 900})  # pendant une vidéo
    assert not reliability.frozen(60, now, {"at": now - 200})  # photos affichées longtemps : on patiente plus
    assert not reliability.frozen(10, now, {"at": now - 5000}, started=now - 30)  # vieux battement, diaporama qui démarre
    assert reliability.frozen(10, now, {"at": now - 5000}, started=now - 400)


def test_beat(monkeypatch, tmp_path):
    monkeypatch.setattr(reliability, "HEARTBEAT", tmp_path / "hb.json")
    monkeypatch.setattr(reliability, "_last_beat", [0.0])
    reliability.beat()
    assert not reliability.frozen(10, heartbeat=None)
    first = (tmp_path / "hb.json").read_text()
    reliability.beat()  # moins de 10 s après : pas de nouvelle écriture
    assert (tmp_path / "hb.json").read_text() == first


def test_rotate_logs(tmp_path):
    log = tmp_path / "pimmich.log"
    log.write_bytes(b"x" * 2000)
    (tmp_path / "petit.log").write_bytes(b"ok")
    assert reliability.rotate_logs(tmp_path, max_bytes=1000) == ["pimmich.log"]
    assert log.stat().st_size == 0 and gzip.open(tmp_path / "pimmich.log.1.gz").read() == b"x" * 2000
    log.write_bytes(b"y" * 2000)
    reliability.rotate_logs(tmp_path, max_bytes=1000)
    assert gzip.open(tmp_path / "pimmich.log.2.gz").read() == b"x" * 2000 and gzip.open(tmp_path / "pimmich.log.1.gz").read() == b"y" * 2000


def test_admin_https_api(admin_client, monkeypatch):
    from utils import remote_guests
    monkeypatch.setattr(remote_guests, "tailscale_status", lambda: {"installed": True, "connected": True, "dns_name": "cadre.tail.ts.net", "funnel": False})
    monkeypatch.setattr(remote_guests, "admin_https_status", lambda: True)
    data = admin_client.get("/api/admin_https").get_json()
    assert data["enabled"] and data["link"] == "https://cadre.tail.ts.net:8443"
    calls = []
    monkeypatch.setattr(remote_guests, "set_admin_https", lambda enabled: calls.append(enabled) or (False, "Serve is not enabled.\nTo enable, visit:\n\n  https://login.tailscale.com/f/serve?node=x\n"))
    r = admin_client.post("/api/admin_https", json={"enabled": True}, headers={"Sec-Fetch-Site": "same-origin"})
    assert r.status_code == 409 and r.get_json()["activation_url"].startswith("https://login.tailscale.com/") and calls == [True]


def test_sd_protection(tmp_path):
    mounts = tmp_path / "mounts"
    mounts.write_text("/dev/mmcblk0p2 / ext4 rw 0 0\n")
    assert reliability.sd_protection(mounts, tmp_path / "none.conf") == {"log2ram": False, "journald_limited": False}
    mounts.write_text("/dev/mmcblk0p2 / ext4 rw 0 0\nlog2ram /var/log tmpfs rw 0 0\n")
    (tmp_path / "j.conf").write_text("[Journal]\n")
    assert reliability.sd_protection(mounts, tmp_path / "j.conf") == {"log2ram": True, "journald_limited": True}
