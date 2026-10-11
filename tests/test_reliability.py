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
