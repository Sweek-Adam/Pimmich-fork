"""Tri automatique : photos floues, sombres, captures d'écran, rafales."""
import random

from PIL import Image, ImageDraw, ImageFilter

from utils import photo_quality as pq

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}


def _scene(path, blur=0, dark=False):
    rng = random.Random(4)
    image = Image.new("RGB", (800, 600), (30, 30, 30) if dark else (200, 180, 150))
    draw = ImageDraw.Draw(image)
    for _ in range(120):  # beaucoup de détails
        x, y = rng.randrange(800), rng.randrange(600)
        color = (rng.randrange(40), rng.randrange(40), rng.randrange(40)) if dark else (rng.randrange(256), rng.randrange(256), rng.randrange(256))
        draw.rectangle([x, y, x + rng.randrange(5, 60), y + rng.randrange(5, 60)], fill=color)
    if blur:
        image = image.filter(ImageFilter.GaussianBlur(blur))
    image.save(path, "JPEG", quality=90)
    return path


def test_measures_separate_sharp_blurry_and_dark(tmp_path):
    sharp, blurry, dark = pq.measure(_scene(tmp_path / "a.jpg")), pq.measure(_scene(tmp_path / "b.jpg", blur=4)), pq.measure(_scene(tmp_path / "c.jpg", dark=True))
    assert sharp["s"] > pq.BLURRY > blurry["s"]
    assert dark["b"] < pq.DARK < sharp["b"]
    assert pq.reasons({"q": dict(blurry, shot=False)}) == ["blurry"]
    assert pq.reasons({"q": dict(sharp, shot=False)}) == []
    assert pq.reasons({"q": dict(blurry, shot=False)}, {"filter_blurry": False}) == []


def test_screenshots():
    assert pq.is_screenshot("x.jpg", "Screenshot_20240714-210533.png")
    assert pq.is_screenshot("x.jpg", "Capture d’écran 2024-07-14.png")
    assert pq.is_screenshot("x.jpg", "IMG_1234.PNG", has_camera=False)
    assert not pq.is_screenshot("x.jpg", "IMG_1234.PNG", has_camera=True)
    assert not pq.is_screenshot("x.jpg", "IMG-20240714-WA0001.jpg")


def test_bursts_keep_the_sharpest():
    index = {"gdrive/1.jpg": {"date": "2024-07-14T10:00:00", "how": "exif", "q": {"s": 40}},
             "gdrive/2.jpg": {"date": "2024-07-14T10:00:04", "how": "exif", "q": {"s": 90}},
             "gdrive/3.jpg": {"date": "2024-07-14T10:00:09", "how": "exif", "q": {"s": 60}},
             "gdrive/4.jpg": {"date": "2024-07-14T10:05:00", "how": "exif", "q": {"s": 50}},  # 5 min plus tard : autre scène
             "gdrive/5.jpg": {"date": "2024-07-14T10:05:03", "how": "name", "q": {"s": 2}}}  # heure du nom : pas fiable
    hashes = {"gdrive/1.jpg": 0b1010, "gdrive/2.jpg": 0b1011, "gdrive/3.jpg": 0b1110, "gdrive/4.jpg": 0b1010, "gdrive/5.jpg": 0b1010}
    assert pq.bursts(index, hashes) == {"gdrive/1.jpg", "gdrive/3.jpg"}
    excluded = pq.excluded(index, {"quality_keep": ["gdrive/3.jpg"]}, hashes)
    assert set(excluded) == {"gdrive/1.jpg", "gdrive/5.jpg"} and excluded["gdrive/5.jpg"] == ["blurry"]
    assert pq.excluded(index, {"auto_filter_enabled": False}, hashes) == {}


def test_quality_api(admin_client, sandbox, monkeypatch):
    from utils import photo_index
    from utils.config_manager import load_config
    folder = sandbox / "static" / "prepared" / "gdrive"
    folder.mkdir(parents=True, exist_ok=True)
    _scene(folder / "floue.jpg", blur=8)
    monkeypatch.setattr(photo_index, "load", lambda: {"gdrive/floue.jpg": {"q": {"s": 3, "b": 120, "shot": False}}})
    data = admin_client.get("/api/quality").get_json()
    assert [(i["path"], i["reasons"]) for i in data["excluded"]] == [("gdrive/floue.jpg", ["blurry"])]
    assert admin_client.post("/api/quality/keep", json={"path": "gdrive/floue.jpg"}, headers=SAME_ORIGIN).get_json()["success"]
    assert "gdrive/floue.jpg" in load_config()["quality_keep"]
    assert admin_client.get("/api/quality").get_json()["excluded"] == []
    assert admin_client.post("/api/quality/keep", json={"path": "../../config/config.json"}, headers=SAME_ORIGIN).status_code == 404
