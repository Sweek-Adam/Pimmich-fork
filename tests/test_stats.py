"""Statistiques : affichages additionnés depuis la mémoire vive, photos les plus vues, répartition par source."""
import time

from PIL import Image

from utils import history, stats


def test_collect_and_summary(monkeypatch, tmp_path):
    monkeypatch.setattr(history, "DISPLAYED", tmp_path / "displayed.json")
    monkeypatch.setattr(stats, "STORE", tmp_path / "views.json")
    monkeypatch.setattr(stats, "PREPARED_DIR", tmp_path / "prepared")
    for source, names in (("gdrive", ("a.jpg", "b.jpg", "c_thumbnail.jpg")), ("usb", ("v.mp4",)), ("messages", ("m.jpg",))):
        (tmp_path / "prepared" / source).mkdir(parents=True)
        for name in names:
            Image.new("RGB", (8, 8)).save(tmp_path / "prepared" / source / name, "JPEG") if name.endswith(".jpg") else (tmp_path / "prepared" / source / name).write_bytes(b"v")
    for path in ("prepared/gdrive/a.jpg", "prepared/gdrive/a.jpg", "prepared/gdrive/b.jpg", "prepared/messages/m.jpg", "compositions/c.jpg"):
        history.displayed(path)
    assert stats.collect() == 5 and stats.collect() == 0  # pas compté deux fois
    data = stats.summary()
    assert data["top"][0] == ("gdrive/a.jpg", 2) and data["total_views"] == 3 and data["viewed"] == 2
    assert data["sources"] == {"gdrive": {"photos": 2, "videos": 0, "bytes": data["sources"]["gdrive"]["bytes"]}, "usb": {"photos": 0, "videos": 1, "bytes": 1}}
    assert data["per_day"][-1]["views"] == 3


def test_stats_api(admin_client):
    data = admin_client.get("/api/stats/photos").get_json()
    assert data["success"] and "sources" in data and len(data["per_day"]) == 14
