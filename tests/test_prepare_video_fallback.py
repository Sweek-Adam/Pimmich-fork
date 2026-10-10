"""Vidéos : si l'encodeur matériel du Raspberry Pi échoue (ex. HEVC sur Pi 3), nouvel essai en logiciel."""
import types

from utils import prepare_all_photos as prep


def test_hardware_encoder_failure_falls_back_to_software(tmp_path, monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[:2] == ["ffmpeg", "-encoders"]:
            return types.SimpleNamespace(returncode=0, stdout="V..... h264_v4l2m2m", stderr="")
        if "h264_v4l2m2m" in command:
            return types.SimpleNamespace(returncode=253, stdout="", stderr="Error encoding a frame: No such process")
        out = command[command.index("-y") + 1]
        open(out, "wb").write(b"video")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(prep.subprocess, "run", fake_run)
    monkeypatch.setattr(prep, "get_pi_model", lambda: 3)
    (tmp_path / "photos" / "gdrive").mkdir(parents=True)
    source = tmp_path / "photos" / "gdrive" / "film.mp4"
    source.write_bytes(b"hevc")
    dest = tmp_path / "prepared" / "gdrive" / "film.mp4"
    dest.parent.mkdir(parents=True)
    prep.prepare_video(str(source), str(dest), 1920, 1080)
    encodes = [c for c in calls if "-c:v" in c]
    assert "h264_v4l2m2m" in encodes[0] and "libx264" in encodes[1] and dest.read_bytes() == b"video"
