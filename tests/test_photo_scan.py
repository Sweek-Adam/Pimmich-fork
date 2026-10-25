"""Scanner de photos papier : bords du tirage trouvés, perspective redressée, couleurs ravivées."""
import io

import pytest
from PIL import Image, ImageDraw

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")
from utils import photo_scan  # noqa: E402


def snapshot_of_a_print():
    """Un tirage 600×400 (jauni) posé de travers sur une table sombre, vu en légère perspective."""
    print_ = Image.new("RGB", (600, 400), (235, 215, 160))
    draw = ImageDraw.Draw(print_)
    draw.ellipse([200, 80, 400, 320], fill=(170, 120, 80))
    draw.rectangle([40, 300, 560, 380], fill=(90, 120, 70))
    table = np.full((1000, 1200, 3), (40, 32, 28), dtype=np.uint8)
    src = np.array([[0, 0], [599, 0], [599, 399], [0, 399]], dtype="float32")
    dst = np.array([[260, 220], [900, 160], [960, 640], [230, 700]], dtype="float32")
    warped = cv2.warpPerspective(np.array(print_), cv2.getPerspectiveTransform(src, dst), (1200, 1000))
    mask = cv2.warpPerspective(np.full((400, 600), 255, np.uint8), cv2.getPerspectiveTransform(src, dst), (1200, 1000))
    table[mask > 0] = warped[mask > 0]
    buffer = io.BytesIO()
    Image.fromarray(table).save(buffer, "JPEG", quality=95)
    return buffer.getvalue(), dst


def test_corners_are_found():
    data, expected = snapshot_of_a_print()
    corners = photo_scan.find_corners(np.array(Image.open(io.BytesIO(data)).convert("RGB")))
    assert corners is not None and np.abs(corners - expected).max() < 25


def test_scan_straightens_and_revives():
    data, _expected = snapshot_of_a_print()
    out, found = photo_scan.scan(data)
    image = Image.open(io.BytesIO(out))
    assert found and 1.3 < image.width / image.height < 1.7  # le tirage 3:2 retrouvé
    r, g, b = image.convert("RGB").resize((1, 1)).getpixel((0, 0))
    assert abs(r - b) < 60  # le jaunissement est corrigé (bleu remonté)


def test_full_frame_photo_is_left_as_is():
    buffer = io.BytesIO()
    Image.new("RGB", (800, 600), (120, 140, 160)).save(buffer, "JPEG")
    out, found = photo_scan.scan(buffer.getvalue())
    assert not found and Image.open(io.BytesIO(out)).size == (800, 600)


def test_scan_api_preview_then_keep(admin_client):
    import shutil
    from pathlib import Path
    from utils.config_manager import load_config, save_config
    same = {"Sec-Fetch-Site": "same-origin"}
    original = dict(load_config())
    data, _expected = snapshot_of_a_print()
    try:
        r = admin_client.post("/api/scan", data={"photo": (io.BytesIO(data), "tirage.jpg")}, headers=same, content_type="multipart/form-data").get_json()
        assert r["success"] and r["found"]
        assert admin_client.get(f"/api/scan/{r['id']}.jpg").status_code == 200
        assert admin_client.get("/api/scan/..%2Fx.jpg").status_code == 404
        assert admin_client.post(f"/api/scan/{r['id']}", json={"rotate": 90}, headers=same).get_json()["success"]
        kept = list(Path("static/photos/scans").glob("scan_*.jpg"))
        assert len(kept) == 1 and Image.open(kept[0]).height > Image.open(kept[0]).width  # tourné d'un quart de tour
        assert "scans" in load_config()["display_sources"]
        assert admin_client.post(f"/api/scan/{r['id']}", json={}, headers=same).status_code == 404  # déjà ajoutée
    finally:
        save_config(original)
        shutil.rmtree("static/photos/scans", ignore_errors=True)
