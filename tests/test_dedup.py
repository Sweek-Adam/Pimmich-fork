"""Détection des photos en double entre sources."""
import random

import pytest
from PIL import Image, ImageDraw

from utils import dedup


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(dedup, "CACHE_FILE", tmp_path / "cache" / "hashes.json")


def make_photo(seed, size=(1920, 1080)):
    rng = random.Random(seed)
    image = Image.new("RGB", size, tuple(rng.randrange(256) for _ in range(3)))
    draw = ImageDraw.Draw(image)
    for _ in range(25):
        x, y = rng.randrange(size[0]), rng.randrange(size[1])
        draw.ellipse([x, y, x + rng.randrange(80, 600), y + rng.randrange(80, 600)], fill=tuple(rng.randrange(256) for _ in range(3)))
    return image


def test_recompressed_and_resized_copies_are_duplicates(tmp_path):
    original = make_photo(1)
    paths = {
        "drive": tmp_path / "drive.jpg", "telegram": tmp_path / "telegram.jpg",
        "petite": tmp_path / "petite.jpg", "autre": tmp_path / "autre.jpg",
    }
    original.save(paths["drive"], quality=95)
    original.save(paths["telegram"], quality=55)                      # recompression type Telegram
    original.resize((1280, 720)).save(paths["petite"], quality=80)    # autre résolution
    make_photo(2).save(paths["autre"], quality=90)                    # photo différente
    kept = dedup.remove_duplicates([str(p) for p in paths.values()])
    assert kept == [str(paths["drive"]), str(paths["autre"])]


def test_first_occurrence_wins_and_videos_are_kept(tmp_path):
    a, b = tmp_path / "a.jpg", tmp_path / "b.jpg"
    make_photo(3).save(a)
    make_photo(3).save(b)
    video = tmp_path / "film.mp4"
    video.write_bytes(b"pas une image")
    assert dedup.remove_duplicates([str(b), str(video), str(a)]) == [str(b), str(video)]


def test_hashes_are_cached_and_refreshed(tmp_path, monkeypatch):
    path = tmp_path / "photo.jpg"
    make_photo(4).save(path)
    first = dedup.hashes_for([str(path)])[str(path)]
    calls = []
    monkeypatch.setattr(dedup, "dhash", lambda p: calls.append(p) or 123)
    assert dedup.hashes_for([str(path)])[str(path)] == first and calls == []  # depuis le cache
    make_photo(5).save(path)
    assert dedup.hashes_for([str(path)])[str(path)] == 123 and calls == [str(path)]  # fichier modifié
