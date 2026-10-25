"""Film de l'année : segments par photo (fondu), titres des mois, musique, vidéo MP4 lisible."""
import shutil
import subprocess

import pytest
from PIL import Image

from utils import year_film

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg absent")


def test_film_with_music(tmp_path, monkeypatch):
    monkeypatch.setattr(year_film, "WIDTH", 320)
    monkeypatch.setattr(year_film, "HEIGHT", 180)
    monkeypatch.setattr(year_film, "PHOTO_SECONDS", 1.2)
    monkeypatch.setattr(year_film, "CARD_SECONDS", 1.0)
    (tmp_path / "static" / "photos" / "essai").mkdir(parents=True)
    index = {}
    for i, month in enumerate((1, 1, 3)):
        Image.new("RGB", (300, 400), (60 * i, 120, 200)).save(tmp_path / "static" / "photos" / "essai" / f"p{i}.jpg")
        index[f"essai/p{i}.jpg"] = {"date": f"2025-{month:02d}-{i + 1:02d}T10:00:00", "q": {"s": 300}}
    music = tmp_path / "musique.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", str(music)], check=True)
    seen = []
    seconds = year_film.build(index, 2025, tmp_path / "film.mp4", tmp_path, music=music, progress=lambda d, t: seen.append((d, t)))
    # titre (2 s) + janvier (1 s) + 2 photos + mars (1 s) + 1 photo
    assert seconds == round(2.0 + 1.0 + 1.2 * 2 + 1.0 + 1.2)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(tmp_path / "film.mp4")],
                           capture_output=True, text=True).stdout.split()
    assert sorted(probe) == ["audio", "video"] and seen[-1][0] == seen[-1][1]
    assert year_film.build(index, 2031, tmp_path / "rien.mp4", tmp_path) == 0
