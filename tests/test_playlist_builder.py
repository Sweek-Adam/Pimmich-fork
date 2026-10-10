"""Composeur de playlist : bibliothèque complète, création et enregistrement en une fois."""
from PIL import Image

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}


def _photos(sandbox):
    folder = sandbox / "static" / "prepared" / "gdrive"
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("IMG-20250714-WA0001.jpg", "IMG-20240101-WA0002.jpg", "sans_date.jpg", "IMG-20250714-WA0001_polaroid.jpg"):
        Image.new("RGB", (20, 15)).save(folder / name)
    (sandbox / "static" / "prepared" / "messages").mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (20, 15)).save(sandbox / "static" / "prepared" / "messages" / "m.jpg")


def test_library_lists_photos_with_dates(admin_client, sandbox, monkeypatch):
    from utils import photo_index
    _photos(sandbox)
    monkeypatch.setattr(photo_index, "load", lambda: {"gdrive/IMG-20250714-WA0001.jpg": {"date": "2025-07-14T12:00:00"},
                                                       "gdrive/IMG-20240101-WA0002.jpg": {"date": "2024-01-01T12:00:00"}})
    items = admin_client.get("/api/library").get_json()["items"]
    paths = [i["path"] for i in items]
    assert paths[:2] == ["gdrive/IMG-20250714-WA0001.jpg", "gdrive/IMG-20240101-WA0002.jpg"]  # plus récentes d'abord
    assert "gdrive/sans_date.jpg" in paths and not any("polaroid" in p or p.startswith("messages/") for p in paths)


def test_create_and_set_photos_in_one_go(admin_client, sandbox):
    _photos(sandbox)
    resp = admin_client.post("/api/playlists", json={"name": "Été 2025", "photos": ["gdrive/IMG-20250714-WA0001.jpg", "gdrive/sans_date.jpg"]}, headers=SAME_ORIGIN)
    playlist = resp.get_json()["playlist"]
    assert playlist["photos"] == ["gdrive/IMG-20250714-WA0001.jpg", "gdrive/sans_date.jpg"]
    resp = admin_client.put(f"/api/playlists/{playlist['id']}/photos", json={"photos": ["gdrive/sans_date.jpg", "gdrive/IMG-20250714-WA0001.jpg"]}, headers=SAME_ORIGIN)
    assert resp.get_json()["count"] == 2
    stored = next(p for p in admin_client.get("/api/playlists").get_json() if p["id"] == playlist["id"])
    assert stored["photos"] == ["gdrive/sans_date.jpg", "gdrive/IMG-20250714-WA0001.jpg"]  # ordre choisi
    for bad in (["../../config/credentials.json"], ["gdrive/absente.jpg"], "pas une liste"):
        assert admin_client.put(f"/api/playlists/{playlist['id']}/photos", json={"photos": bad}, headers=SAME_ORIGIN).status_code == 400
