"""Photos animées des téléphones (Samsung / Google : vidéo dans le JPEG ; iPhone : .MOV à côté)."""
import io
import os
import shutil
import struct
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from utils import animated, motion_photos
from utils import prepare_all_photos as prep


def box(kind, payload=b""):
    return struct.pack(">I4s", 8 + len(payload), kind) + payload


FAKE_MP4 = box(b"ftyp", b"isom\x00\x00\x02\x00isomiso2mp41") + box(b"free") + box(b"mdat", b"\x00" * 400) + box(b"moov", b"\x01" * 100)


def motion_jpeg(path, size=(320, 240)):
    """Photo animée façon Samsung : JPEG, vidéo MP4, puis le bloc de fin « MotionPhoto_Data »."""
    buffer = io.BytesIO()
    Image.new("RGB", size, (200, 100, 50)).save(buffer, "JPEG")
    path.write_bytes(buffer.getvalue() + FAKE_MP4 + b"\x00\x00MotionPhoto_Data" + b"SEFT" * 4)
    return path


def fake_ffmpeg(command, **kwargs):
    """Remplace ffmpeg : vérifie le clip extrait et écrit une animation WebP de 3 images au bon format."""
    clip = Path(command[command.index("-i") + 1])
    assert clip.read_bytes()[:4] == FAKE_MP4[:4] or clip.suffix.lower() == ".mov"
    graph = command[command.index("-vf") + 1]
    width, height = (int(v) for v in graph.split("crop=")[1].split(":"))
    frames = [Image.new("RGB", (width, height), (200, 100 + i * 20, 50)) for i in range(3)]
    frames[0].save(command[-1], save_all=True, append_images=frames[1:], duration=66, loop=0)
    return subprocess.CompletedProcess(command, 0, "", "")


def test_embedded_video_is_found_exactly(tmp_path):
    photo = motion_jpeg(tmp_path / "20260125_195055.jpg")
    start, end = motion_photos.embedded_video(photo)
    assert photo.read_bytes()[start:end] == FAKE_MP4
    plain = tmp_path / "plain.jpg"
    Image.new("RGB", (64, 64)).save(plain)
    assert motion_photos.embedded_video(plain) is None and not motion_photos.has_motion(plain)
    # Un « ftyp » au hasard dans les données de l'image ne suffit pas
    broken = tmp_path / "broken.jpg"
    broken.write_bytes(plain.read_bytes() + b"\x00" * 2000 + struct.pack(">I", 20) + b"ftypisom" + b"\x00" * 50)
    assert motion_photos.embedded_video(broken) is None


def test_live_photo_pair(tmp_path):
    photo = tmp_path / "IMG_0001.JPG"
    Image.new("RGB", (64, 48)).save(photo)
    clip = tmp_path / "IMG_0001.MOV"
    clip.write_bytes(b"\x00" * 1000)
    alone = tmp_path / "Film.MOV"
    alone.write_bytes(b"\x00" * 1000)
    assert motion_photos.companion_video(photo) == clip
    assert motion_photos.is_live_photo_video(clip) and not motion_photos.is_live_photo_video(alone)


@pytest.fixture()
def source(sandbox, monkeypatch):
    folder, prepared = Path("static/photos/tel"), Path("static/prepared/tel")
    for d in (folder, prepared, motion_photos.CACHE_DIR / "tel"):
        shutil.rmtree(d, ignore_errors=True)
    folder.mkdir(parents=True)
    monkeypatch.setattr(motion_photos, "SCAN_FILE", motion_photos.CACHE_DIR / "tel" / "scan.json")
    monkeypatch.setitem(motion_photos._scan, "data", None)
    monkeypatch.setattr(prep, "load_config", lambda: {"smart_crop": False})
    yield folder, prepared
    for d in (folder, prepared, motion_photos.CACHE_DIR / "tel"):
        shutil.rmtree(d, ignore_errors=True)


def test_motion_photo_gets_an_animation_over_its_prepared_photo(source, monkeypatch):
    folder, prepared = source
    motion_jpeg(folder / "anim.jpg")
    Image.new("RGB", (320, 240)).save(folder / "fixe.jpg")
    list(prep.prepare_all_photos_with_progress(640, 360, "tel"))
    assert motion_photos.pending(640, 360, ["tel"]) == [("tel", "anim.jpg")]
    monkeypatch.setattr(motion_photos.subprocess, "run", fake_ffmpeg)
    assert motion_photos.run(motion_photos.pending(640, 360, ["tel"])) == 1
    items = animated.read(prepared / "anim.jpg")
    assert len(items) == 1 and items[0]["motion"] and items[0]["box"] == [80, 0, 480, 360]
    with Image.open(items[0]["gif"]) as webp:
        assert webp.n_frames == 3 and abs(webp.width / webp.height - 4 / 3) < 0.02
    assert motion_photos.pending(640, 360, ["tel"]) == []
    # Photo préparée à nouveau (autre écran) : l'animation existante est réutilisée sans ffmpeg
    os.utime(items[0]["gif"], None)
    prep.prepare_photo(str(folder / "anim.jpg"), str(prepared / "anim.jpg"), 640, 360)
    monkeypatch.setattr(motion_photos.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ffmpeg relancé")))
    assert motion_photos.run(motion_photos.pending(640, 360, ["tel"])) == 1


def test_live_photo_video_is_not_a_separate_slide(source, monkeypatch):
    folder, prepared = source
    Image.new("RGB", (320, 240)).save(folder / "IMG_0002.JPG")
    (folder / "IMG_0002.MOV").write_bytes(b"\x00" * 1000)
    prepared.mkdir(parents=True, exist_ok=True)
    (prepared / "IMG_0002.mp4").write_bytes(b"ancienne video")
    called = []
    monkeypatch.setattr(prep, "prepare_video", lambda *a, **k: called.append(a))
    list(prep.prepare_all_photos_with_progress(640, 360, "tel"))
    assert not called and not (prepared / "IMG_0002.mp4").exists() and (prepared / "IMG_0002.jpg").exists()
    assert [i["name"] for i in prep.media_inventory("tel", 640, 360)] == ["IMG_0002.JPG"]


def test_failed_animation_is_not_retried_every_night(source, monkeypatch):
    folder, _prepared = source
    motion_jpeg(folder / "rate.jpg")
    list(prep.prepare_all_photos_with_progress(640, 360, "tel"))
    monkeypatch.setattr(motion_photos, "FAILED_FILE", motion_photos.CACHE_DIR / "tel" / "failed.json")
    monkeypatch.setattr(motion_photos.subprocess, "run", lambda c, **k: subprocess.CompletedProcess(c, 1, "", "codec inconnu"))
    assert motion_photos.run(motion_photos.pending(640, 360, ["tel"])) == 0
    assert motion_photos.pending(640, 360, ["tel"]) == []
