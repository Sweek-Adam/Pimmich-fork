"""GIF animés : import, préparation (première image + animation), repérage dans les compositions, lecture."""
import os
import random

import numpy as np
import pytest
from PIL import Image, ImageChops, ImageDraw

from utils import animated
from utils import compositions as comp
from utils import layout_engine as le


def make_gif(path, size=(120, 90), count=4):
    """GIF animé de test : un fond dégradé (repérable) et un carré qui se déplace."""
    frames = []
    for i in range(count):
        frame = Image.new("RGB", size)
        draw = ImageDraw.Draw(frame)
        for x in range(size[0]):
            draw.line([(x, 0), (x, size[1])], fill=(40 + x * 180 // size[0], 90, 200 - x * 150 // size[0]))
        draw.rectangle([10 + i * 20, 20, 30 + i * 20, 40], fill=(250, 250, 40))
        frames.append(frame)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=[80, 120, 0, 100], loop=0)
    return path


def test_detection_and_frames(tmp_path):
    gif = make_gif(tmp_path / "a.gif")
    still = tmp_path / "b.gif"
    Image.new("RGB", (10, 10), (1, 2, 3)).save(still)
    assert animated.is_animated(gif) and not animated.is_animated(still)
    assert not animated.is_animated(tmp_path / "missing.gif")
    item = animated.single_item(gif, 5, 6, 240, 180)
    images = animated.frames(item)
    assert len(images) == 4 and images[0][0].size == (240, 180)
    assert [round(d, 2) for _i, d in images] == [0.08, 0.12, 0.1, 0.1]  # 0 ms : 0,1 s comme les navigateurs
    assert animated.frames(item, scale=0.5)[0][0].size == (120, 90)


def test_sidecar_roundtrip(tmp_path):
    gif = make_gif(tmp_path / "a.gif")
    shown = tmp_path / "a.jpg"
    animated.write(shown, [dict(animated.single_item(gif, 0, 0, 120, 90)), {"gif": str(gif), "box": [1, 2, 30, 20],
                    "affine": [1, 0, 0, 0, 1, 0], "mask": Image.new("L", (30, 20), 255)}])
    items = animated.read(shown)
    assert [i["box"] for i in items] == [[0, 0, 120, 90], [1, 2, 30, 20]]
    assert items[1]["mask"].name == "a_animation_1.png" and items[1]["mask"].is_file()
    animated.write(shown, [])
    assert animated.read(shown) == [] and not animated.sidecar(shown).exists()


def test_prepared_gif_shows_first_frame_and_keeps_animation(monkeypatch, tmp_path):
    from utils import prepare_all_photos
    monkeypatch.setattr(prepare_all_photos, "load_config", lambda: {"smart_crop": False})
    gif = make_gif(tmp_path / "anim.gif")
    dest = tmp_path / "anim.jpg"
    prepare_all_photos.prepare_photo(str(gif), str(dest), 640, 360)
    items = animated.read(dest)
    assert len(items) == 1 and items[0]["affine"] is None
    x, y, w, h = items[0]["box"]
    assert (w, h) == (480, 360) and (x, y) == (80, 0)
    with Image.open(dest) as prepared:
        assert prepared.size == (640, 360)
        assert animated.matches(items[0], prepared)
    # Une photo ordinaire n'a pas d'animation
    still = tmp_path / "still.png"
    Image.new("RGB", (64, 48), (10, 200, 10)).save(still)
    prepare_all_photos.prepare_photo(str(still), str(tmp_path / "still.jpg"), 640, 360)
    assert not animated.sidecar(tmp_path / "still.jpg").exists()


def test_filtered_photo_does_not_animate(tmp_path):
    gif = make_gif(tmp_path / "a.gif")
    item = animated.single_item(gif, 0, 0, 120, 90)
    first = animated.frames(item, limit=1)[0][0]
    assert animated.matches(item, first)
    assert not animated.matches(item, ImageChops.invert(first))  # photo retouchée depuis : la vraie image reste fixe


@pytest.fixture()
def library(monkeypatch, tmp_path):
    """Une source « test » : 3 photos et un GIF animé, préparés (fausses versions préparées : les originaux suffisent)."""
    photos, prepared = tmp_path / "photos" / "test", tmp_path / "prepared" / "test"
    photos.mkdir(parents=True)
    prepared.mkdir(parents=True)
    monkeypatch.setattr(comp, "PHOTOS_DIR", tmp_path / "photos")
    monkeypatch.setattr(comp.faces, "ENABLED", False, raising=False)
    paths = []
    for i, color in enumerate([(200, 30, 30), (30, 200, 30), (30, 30, 200)]):
        Image.new("RGB", (300, 200), color).save(photos / f"p{i}.jpg")
        Image.new("RGB", (64, 36), color).save(prepared / f"p{i}.jpg")
        paths.append(str(prepared / f"p{i}.jpg"))
    make_gif(photos / "g.gif", size=(240, 180))
    Image.new("RGB", (64, 36)).save(prepared / "g.jpg")
    paths.insert(1, str(prepared / "g.jpg"))
    return paths


@pytest.mark.parametrize("style", ["mosaique", "liege", "polaroids", "duo"])
def test_gif_is_located_in_compositions(library, style):
    rng = random.Random(7)
    state = rng.getstate()
    chunk = library[:2] if style == "duo" else library
    image, used = le.render_chunk(style, chunk, {}, 640, 360, False, rng)
    assert image is not None
    items = le.animations_for(style, chunk, {}, 640, 360, False, state, image, used)
    assert len(items) == 1, style
    item = items[0]
    x, y, w, h = item["box"]
    # La première image du GIF, rejouée à l'emplacement trouvé, recouvre bien ce qui est dessiné
    frame = animated.frames(dict(item, mask=None), limit=1)[0][0]
    drawn = image.crop((x, y, x + w, y + h))
    weight = np.asarray(item["mask"], dtype=np.float32) / 255
    gap = np.asarray(ImageChops.difference(frame, drawn).convert("L"), dtype=np.float32)
    assert (gap * weight).sum() / weight.sum() < 20, style
    assert getattr(comp._probe, "paths", None) == {}  # repérage terminé : les vraies photos reviennent


def test_composition_without_gif_has_no_animation(library):
    chunk = [p for p in library if not p.endswith("g.jpg")]
    rng = random.Random(3)
    state = rng.getstate()
    image, used = le.render_chunk("mosaique", chunk, {}, 640, 360, False, rng)
    assert le.animations_for("mosaique", chunk, {}, 640, 360, False, state, image, used) == []


def test_color_filtered_layout_stays_still(library, monkeypatch):
    """Disposition qui transforme les couleurs (ici : tout en gris) : le GIF reste immobile plutôt que faux."""
    _label, mn, mx, accepts, render = comp.FORMATS["mosaique"]
    monkeypatch.setitem(comp.FORMATS, "mosaique", (_label, mn, mx, accepts,
                        lambda *a, **k: render(*a, **k).convert("L").convert("RGB")))
    rng = random.Random(5)
    state = rng.getstate()
    image, used = le.render_chunk("mosaique", library, {}, 640, 360, False, rng)
    assert le.animations_for("mosaique", library, {}, 640, 360, False, state, image, used) == []


def test_player_plays_frames_in_place(monkeypatch, tmp_path):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pytest.importorskip("pygame")
    import pygame
    import local_slideshow as ls
    pygame.display.init()
    screen = pygame.display.set_mode((320, 180))
    gif = make_gif(tmp_path / "a.gif")
    shown = tmp_path / "shown.jpg"
    base = Image.new("RGB", (320, 180), (0, 0, 0))
    first = animated.frames(animated.single_item(gif, 100, 40, 120, 90), limit=1)[0][0]
    base.paste(first, (100, 40))
    base.save(shown, quality=95)
    animated.write(shown, [animated.single_item(gif, 100, 40, 120, 90)])
    surface = pygame.image.frombytes(base.tobytes(), base.size, "RGB")
    screen.blit(surface, (0, 0))
    pygame.draw.rect(screen, (255, 255, 255), (0, 0, 150, 50))  # l'heure, par-dessus le coin du GIF
    player = ls.GifPlayer(str(shown), surface, base)
    assert player.expected
    for _ in range(100):
        if player.ready:
            break
        pygame.time.wait(20)
    assert player.ready and len(player.tracks) == 1
    rects, _wait = player.step(screen, 1000.0)          # 1re image
    rects, _wait = player.step(screen, 1000.0 + 0.081)  # 2e image (le carré s'est déplacé)
    assert rects == [pygame.Rect(100, 40, 120, 90)]
    assert screen.get_at((140, 70))[:3] == (250, 250, 40) or screen.get_at((145, 70))[:3][0] > 200
    assert screen.get_at((120, 45))[:3] == (255, 255, 255)  # l'habillage reste au-dessus de l'animation
    ls.show_regions(screen, rects)
    # Sans fichier d'animation : rien à faire
    plain = ls.GifPlayer(str(tmp_path / "none.jpg"), surface, base)
    assert not plain.expected and plain.ready and plain.step(screen, 0) == ([], 0.1)
    pygame.display.quit()


def test_all_imports_accept_gif():
    from utils import import_email, import_gdrive, import_samba, import_usb_photos, import_whatsapp, photo_index
    assert ".gif" in import_gdrive.ALLOWED_EXTENSIONS and ".gif" in import_samba.ALLOWED_EXTENSIONS
    assert ".gif" in import_usb_photos.ALLOWED_EXTENSIONS and ".gif" in import_whatsapp.MEDIA_EXT
    assert ".gif" in import_email.MEDIA_EXT and ".gif" in photo_index.IMAGE_EXT
    from utils import import_icloud
    assert import_icloud._filename("tok12345", {"url": "https://x/y/abc.gif?z", "guid": "G1", "video": False}).endswith(".gif")


def test_video_to_gif(tmp_path):
    import shutil
    import subprocess
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg absent")
    video = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=160x120:rate=10", "-t", "1",
                    "-pix_fmt", "yuv420p", str(video)], check=True)
    out = animated.video_to_gif(video, tmp_path / "v.gif")
    assert animated.is_animated(out) and animated.frame_count(out) >= 10
