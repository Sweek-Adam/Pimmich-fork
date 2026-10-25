"""Mur de cadres : découpe de la photo entre les écrans, morceaux reçus et affichés à l'heure dite."""
import io
import time

import pytest
from PIL import Image

from utils import frame_wall

SAME = {"Sec-Fetch-Site": "same-origin"}


@pytest.fixture(autouse=True)
def wall_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(frame_wall, "WALL_DIR", tmp_path / "wall")


def test_split_accounts_for_the_gap_between_screens():
    image = Image.new("RGB", (900, 200))
    for x in range(900):  # dégradé horizontal : la position de chaque morceau se lit dans sa couleur
        image.paste((x * 255 // 899, 0, 0), (x, 0, x + 1, 200))
    tiles = frame_wall.split(image, 3, screen=(160, 90), gap=0.25)
    assert [t.size for t in tiles] == [(160, 90)] * 3
    left, middle, right = (t.getpixel((80, 45))[0] for t in tiles)
    assert left < middle < right
    # Le bord droit du premier morceau et le bord gauche du suivant ne se touchent pas : l'espace (bordures) est sauté
    assert tiles[1].getpixel((0, 45))[0] - tiles[0].getpixel((159, 45))[0] > 10


def test_pending_tiles_in_order():
    now = time.time()
    frame_wall.receive(b"b", now + 20, now + 30)
    frame_wall.receive(b"a", now + 5, now + 20)
    path, show_at, until = frame_wall.pending(now)
    assert path.read_bytes() == b"a" and show_at == pytest.approx(now + 5, abs=0.01)
    frame_wall.done(path)
    assert frame_wall.pending(now)[0].read_bytes() == b"b"
    assert frame_wall.pending(now + 40) is None  # passé : oublié


def test_wall_api_and_step(admin_client, monkeypatch):
    from test_frames import restore_config  # noqa: F401
    from utils.config_manager import load_config, save_config
    from web import routes_frames
    original = dict(load_config())
    remote = admin_client.application.test_client()
    try:
        token = admin_client.post("/api/frame/pairing", json={}, headers=SAME).get_json()["codes"][-1]["token"]
        # Côté cadre qui reçoit : le code est exigé, et l'horaire doit être proche
        tile = {"tile": (io.BytesIO(b"jpeg"), "t.jpg"), "show_at": str(time.time() + 3), "until": str(time.time() + 13)}
        assert remote.post("/api/frame/wall", data=tile, content_type="multipart/form-data").status_code == 401
        tile = {"tile": (io.BytesIO(b"jpeg"), "t.jpg"), "show_at": str(time.time() + 3), "until": str(time.time() + 13)}
        assert remote.post("/api/frame/wall", data=tile, headers={"X-Pimmich-Frame-Token": token}, content_type="multipart/form-data").get_json()["success"]
        late = {"tile": (io.BytesIO(b"jpeg"), "t.jpg"), "show_at": str(time.time() + 3600), "until": str(time.time() + 3610)}
        assert remote.post("/api/frame/wall", data=late, headers={"X-Pimmich-Frame-Token": token}, content_type="multipart/form-data").status_code == 400
        frame_wall.done(frame_wall.pending()[0])
        # Côté cadre qui pilote : un seul écran ne fait pas un mur
        save_config(dict(load_config(), family_frames=[{"id": "abcd", "url": "https://100.1.2.3", "token": token, "name": "Salon"}]))
        r = admin_client.put("/api/frames/wall", json={"order": ["self"], "enabled": True}, headers=SAME).get_json()
        assert not r["wall"]["enabled"]
        r = admin_client.put("/api/frames/wall", json={"order": ["self", "abcd", "inconnu"], "seconds": 2, "enabled": True}, headers=SAME).get_json()
        assert r["wall"]["order"] == ["self", "abcd"] and r["wall"]["seconds"] == 5 and r["wall"]["enabled"]
        sent = []
        monkeypatch.setattr(routes_frames, "_call", lambda frame, method, path, **kw: sent.append((frame["id"], path, kw["data"])))
        from pathlib import Path
        Path("static/photos/essai").mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1200, 400), (10, 120, 200)).save("static/photos/essai/large.jpg")
        from utils import photo_index
        monkeypatch.setattr(photo_index, "load", lambda: {"essai/large.jpg": {}})
        show_at = time.time() + 5
        assert routes_frames.wall_step(routes_frames.wall_settings(), show_at, []) == "essai/large.jpg"
        assert sent and sent[0][0] == "abcd" and sent[0][2]["show_at"] == show_at
        assert frame_wall.pending()[1] == pytest.approx(show_at, abs=0.01)  # le morceau de ce cadre-ci
    finally:
        save_config(original)
        import shutil
        shutil.rmtree("static/photos/essai", ignore_errors=True)
