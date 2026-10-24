"""Gagner de la place : originaux énormes déjà préparés remplacés par une version réduite (même nom, même date)."""
import os
import shutil
from pathlib import Path

import piexif
import pytest
from PIL import Image

from utils import space_saver
from utils import prepare_all_photos as prep

SAME = {"Sec-Fetch-Site": "same-origin"}


@pytest.fixture()
def library(sandbox, monkeypatch):
    folder, prepared = Path("static/photos/gros"), Path("static/prepared/gros")
    for d in (folder, prepared):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
    monkeypatch.setattr(space_saver, "REGISTRY", Path("cache") / "space_saver_test.json")
    space_saver.REGISTRY.unlink(missing_ok=True)
    monkeypatch.setattr(space_saver, "PHOTO_MAX_SIDE", 400)
    monkeypatch.setattr(space_saver, "PHOTO_MIN_BYTES", 1000)
    yield folder, prepared
    for d in (folder, prepared):
        shutil.rmtree(d, ignore_errors=True)


def big_photo(path, size=(1600, 1200)):
    import random
    rnd = random.Random(1)
    image = Image.frombytes("RGB", size, bytes(rnd.getrandbits(8) for _ in range(size[0] * size[1] * 3)))
    exif = piexif.dump({"0th": {piexif.ImageIFD.Orientation: 6}, "Exif": {piexif.ExifIFD.DateTimeOriginal: b"2025:07:14 12:00:00"}})
    image.save(path, quality=95, exif=exif)
    os.utime(path, (1_700_000_000, 1_700_000_000))


def mark_prepared(prepared, name, width=64, height=36):
    Image.new("RGB", (width, height)).save(prepared / (os.path.splitext(name)[0] + ".jpg"))


def test_big_prepared_photo_is_a_candidate_and_reduced_in_place(library):
    folder, prepared = library
    big_photo(folder / "pano.jpg")
    big_photo(folder / "pas_prete.jpg")          # pas encore préparée : jamais touchée
    Image.new("RGB", (300, 200)).save(folder / "petite.jpg")
    mark_prepared(prepared, "pano.jpg")
    mark_prepared(prepared, "petite.jpg")
    found = space_saver.candidates(64, 36, ["gros"])
    assert [c["name"] for c in found] == ["pano.jpg"] and found[0]["cloud_copy"] is False
    before = (folder / "pano.jpg").stat().st_size
    result = space_saver.request([("gros", "pano.jpg")], now_ok_for_videos=False)
    assert result["photos"] == 1 and result["saved"] > 0
    with Image.open(folder / "pano.jpg") as image:
        assert max(image.size) == 400
        exif = piexif.load(image.info["exif"])
        assert exif["0th"][piexif.ImageIFD.Orientation] == 6 and exif["Exif"][piexif.ExifIFD.DateTimeOriginal] == b"2025:07:14 12:00:00"
    assert int((folder / "pano.jpg").stat().st_mtime) == 1_700_000_000 and (folder / "pano.jpg").stat().st_size < before
    assert space_saver.candidates(64, 36, ["gros"]) == []   # déjà réduite
    assert space_saver.summary()["count"] == 1


def test_videos_wait_for_the_night(library, monkeypatch):
    folder, prepared = library
    video = folder / "film.mov"
    video.write_bytes(b"x" * 2000)
    (prepared / "film.mp4").write_bytes(b"ok")
    monkeypatch.setattr(space_saver, "VIDEO_MIN_BYTES", 1000)
    monkeypatch.setattr(space_saver, "_probe_video", lambda path, cache: (2160, 0.001))
    assert [c["name"] for c in space_saver.candidates(64, 36, ["gros"])] == ["film.mov"]
    result = space_saver.request([("gros", "film.mov")], now_ok_for_videos=False)
    assert result["videos_later"] == 1 and space_saver.queued() == [("gros", "film.mov")]
    assert space_saver.candidates(64, 36, ["gros"])[0]["queued"]

    def fake_ffmpeg(command):
        Path(command[-1]).write_bytes(b"y" * 500)
        return 0, ""
    monkeypatch.setattr(prep, "run_ffmpeg", fake_ffmpeg)
    saved = space_saver.run_videos(space_saver.queued())
    assert saved == 1500 and video.read_bytes() == b"y" * 500 and space_saver.queued() == []


def test_reduce_api_only_touches_candidates(admin_client, library):
    folder, prepared = library
    from web import routes_media
    big_photo(folder / "pano.jpg")
    mark_prepared(prepared, "pano.jpg", *routes_media._screen())
    (folder / "autre.jpg").write_bytes(b"x")
    data = admin_client.get("/api/media/space").get_json()
    assert [i["name"] for i in data["items"]] == ["pano.jpg"]
    r = admin_client.post("/api/media/reduce", json={"items": [{"source": "gros", "name": "autre.jpg"}, {"source": "../x", "name": "pano.jpg"}]}, headers=SAME)
    assert r.status_code == 400 and (folder / "autre.jpg").read_bytes() == b"x"
    r = admin_client.post("/api/media/reduce", json={"items": [{"source": "gros", "name": "pano.jpg"}]}, headers=SAME)
    assert r.get_json()["success"]
    with Image.open(folder / "pano.jpg") as image:
        assert max(image.size) == 400
