"""Extraits des longues vidéos : le passage le plus animé est trouvé, noté à côté de la vidéo et lu seul par mpv."""
import shutil
import subprocess

import pytest

from utils import video_excerpt


def test_best_window_finds_the_busy_part():
    profile = [(s, 1.0) for s in range(1, 121)]
    for s in range(70, 85):
        profile[s - 1] = (s, 30.0)  # il se passe quelque chose vers 70-85 s
    start = video_excerpt.best_window(profile, 20, 120)
    assert 60 <= start <= 70  # le passage animé (70-84 s) tient dans l'extrait
    assert video_excerpt.best_window(profile, 200, 120) == 0.0  # vidéo plus courte que l'extrait


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg absent")
def test_make_and_read_sidecar(tmp_path):
    video = tmp_path / "longue.mp4"
    # 40 s : image fixe, puis une mire qui bouge de 25 à 35 s, puis de nouveau fixe
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=160x90:d=40:r=10",
                    "-f", "lavfi", "-i", "testsrc=s=160x90:d=10:r=10",
                    "-filter_complex", "[1]setpts=PTS+25/TB[m];[0][m]overlay=eof_action=pass",
                    "-g", "10", "-pix_fmt", "yuv420p", str(video)], check=True)
    data = video_excerpt.make(video, 40, length=8)
    assert data and 18 <= data["start"] <= 28 and data["length"] == 8
    assert video_excerpt.read(video) == data
    assert video_excerpt.make(video, 10, length=8) is None  # vidéo courte : pas d'extrait


def test_slideshow_uses_the_excerpt(tmp_path, monkeypatch):
    pytest.importorskip("pygame")
    import json
    import local_slideshow as ls
    video = tmp_path / "v.mp4"
    video.write_bytes(b"")
    video_excerpt.sidecar(video).write_text(json.dumps({"start": 42.0, "length": 20.0, "duration": 180.0}))
    assert ls.video_excerpt_for(str(video), {})["start"] == 42.0
    assert ls.video_excerpt_for(str(video), {"video_excerpts_enabled": False}) is None
