"""Livre photo de l'année : choix des photos, mise en page, PDF lisible."""
import shutil
import time
from datetime import datetime
from pathlib import Path

from PIL import Image

from utils import photo_book

SAME = {"Sec-Fetch-Site": "same-origin"}


def _index(n=10, year=2025):
    index = {}
    for i in range(n):
        month = 1 + i % 3
        index[f"essai/p{i}.jpg"] = {"date": f"{year}-{month:02d}-{1 + i:02d}T12:00:00", "q": {"s": 100 + i, "shot": False}}
    index["essai/capture.jpg"] = {"date": f"{year}-01-05T10:00:00", "q": {"s": 900, "shot": True}}
    index["essai/vieille.jpg"] = {"date": "2019-06-01T10:00:00", "q": {"s": 500}}
    index["messages/mot.jpg"] = {"date": f"{year}-02-02T10:00:00", "q": {"s": 500}}
    return index


def test_years_and_selection():
    index = _index()
    assert photo_book.years(index) == {2025: 11, 2019: 1}
    chosen = photo_book.select(index, 2025, excluded={"essai/p3.jpg"}, loved={"essai/p0.jpg": 4}, limit=6)
    keys = [k for k, _w in chosen]
    assert "essai/capture.jpg" not in keys and "essai/p3.jpg" not in keys and "messages/mot.jpg" not in keys
    assert "essai/p0.jpg" in keys and {w.month for _k, w in chosen} == {1, 2, 3}
    assert [w for _k, w in chosen] == sorted(w for _k, w in chosen)  # ordre chronologique


def test_build_writes_a_pdf(tmp_path):
    base = tmp_path
    (base / "static" / "photos" / "essai").mkdir(parents=True)
    index = _index(6)
    for i in range(6):
        Image.new("RGB", (400, 300), (40 * i, 120, 200)).save(base / "static" / "photos" / "essai" / f"p{i}.jpg")
    seen = []
    pages = photo_book.build(index, 2025, tmp_path / "livre.pdf", base, progress=lambda d, t: seen.append((d, t)))
    data = (tmp_path / "livre.pdf").read_bytes()
    assert pages == 5 and data.startswith(b"%PDF-1.4") and data.rstrip().endswith(b"%%EOF")  # couverture, 3 mois, bilan
    assert data.count(b"/Type /Page ") == 5 and b"/Count 5" in data and seen[-1] == (5, 5)
    assert photo_book.build(index, 2031, tmp_path / "vide.pdf", base) == 0


def test_photobook_api(admin_client, monkeypatch):
    from utils import photo_index
    from web import routes_photobook
    folder = Path("static/photos/essai")
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(4):
        Image.new("RGB", (300, 200), (60 * i, 80, 160)).save(folder / f"p{i}.jpg")
    monkeypatch.setattr(photo_index, "load", lambda: _index(4))
    try:
        data = admin_client.get("/api/photobook").get_json()
        assert data["years"]["2025"] == 5 and not data["job"]["running"]
        assert admin_client.post("/api/photobook", json={"year": "x"}, headers=SAME).status_code == 400
        assert admin_client.post("/api/photobook", json={"year": 2025}, headers=SAME).get_json()["success"]
        for _ in range(300):
            if not routes_photobook._job["running"]:
                break
            time.sleep(0.05)
        job = admin_client.get("/api/photobook").get_json()
        assert job["job"]["pages"] == 5 and job["books"][0]["year"] == 2025
        pdf = admin_client.get("/api/photobook/2025.pdf")
        assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF")
        assert admin_client.get("/api/photobook/2024.pdf").status_code == 404
    finally:
        shutil.rmtree(folder, ignore_errors=True)
        shutil.rmtree(routes_photobook.OUTPUT_DIR, ignore_errors=True)
