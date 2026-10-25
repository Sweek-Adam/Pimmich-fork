"""Souvenirs vocaux : enregistrés sur une photo depuis la bibliothèque, lus par le cadre quand la photo passe."""
import io
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from utils import photo_voice

SAME = {"Sec-Fetch-Site": "same-origin"}
pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg absent")


def recording(tmp_path, seconds=2):
    out = tmp_path / "voix.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=300:duration={seconds}", str(out)], check=True)
    return out.read_bytes()


@pytest.fixture()
def photo(monkeypatch, tmp_path):
    monkeypatch.setattr(photo_voice, "VOICE_DIR", tmp_path / "voices")
    monkeypatch.setattr(photo_voice, "INDEX_FILE", tmp_path / "voices" / "index.json")
    folder = Path("static/prepared/essai")
    folder.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 36)).save(folder / "plage.jpg")
    yield "essai/plage.jpg"
    shutil.rmtree(folder, ignore_errors=True)


def test_record_listen_and_delete(admin_client, photo, tmp_path):
    data = {"path": photo, "voice": (io.BytesIO(recording(tmp_path)), "souvenir")}
    r = admin_client.post("/api/photo_voice", data=data, headers=SAME, content_type="multipart/form-data").get_json()
    assert r["success"] and r["seconds"] == 2
    assert admin_client.get(f"/api/photo_voice/listen?path={photo}").status_code == 200
    bad = {"path": "../config/config.json", "voice": (io.BytesIO(b"x"), "v")}
    assert admin_client.post("/api/photo_voice", data=bad, headers=SAME, content_type="multipart/form-data").status_code == 400
    # Un nouvel enregistrement remplace l'ancien (un seul fichier reste)
    data = {"path": photo, "voice": (io.BytesIO(recording(tmp_path, 3)), "souvenir")}
    assert admin_client.post("/api/photo_voice", data=data, headers=SAME, content_type="multipart/form-data").get_json()["seconds"] == 3
    assert len(list(photo_voice.VOICE_DIR.glob("*.ogg"))) == 1
    assert admin_client.delete("/api/photo_voice", json={"path": photo}, headers=SAME).get_json()["success"]
    assert admin_client.get(f"/api/photo_voice/listen?path={photo}").status_code == 404


def test_slideshow_plays_the_memory(photo, tmp_path, monkeypatch):
    import local_slideshow as ls
    photo_voice.save(photo, recording(tmp_path))
    played = []
    real_popen = subprocess.Popen

    def fake_popen(cmd, **kwargs):  # seule la lecture (mpv) est simulée ; la mesure de la durée reste réelle
        if cmd[0] != "mpv":
            return real_popen(cmd, **kwargs)
        played.append(cmd)
        return type("P", (), {"wait": lambda self, timeout=None: 0})()
    monkeypatch.setattr(ls.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(ls, "apply_audio_output", lambda *a: None)
    monkeypatch.setattr(ls, "duck_music", lambda *a, **k: None)
    ls._voice_played.clear()
    seconds = ls.play_voice_message(str(Path("static/prepared") / photo), {})
    assert seconds > 2 and played and played[0][-1].endswith(".ogg")
    assert ls.play_voice_message(str(Path("static/prepared") / photo), {}) == 0  # pas relu tout de suite
    ls._voice_played.clear()
    assert ls.play_voice_message(str(Path("static/prepared") / photo), {"photo_voices_enabled": False}) == 0
