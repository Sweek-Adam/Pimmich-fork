"""Messages vocaux : envoi depuis le téléphone, conversion, carte dans le diaporama."""
import io
import math
import shutil
import struct
import wave

import pytest
from PIL import Image

from utils import messages_manager as mm

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")


def wav(seconds=2.0):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(i / 10))) for i in range(int(16000 * seconds))))
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def guest_messages_on():
    from utils.config_manager import load_config, save_config
    original = dict(load_config())
    save_config(dict(original, guest_messages_enabled=True))
    yield
    save_config(original)


@needs_ffmpeg
def test_voice_message(client, sandbox, monkeypatch, tmp_path):
    monkeypatch.setattr(mm, "PRIORITY_FILE", tmp_path / "priority.json")
    assert 'id="voice-box"' in client.get("/upload").get_data(as_text=True)
    r = client.post("/upload/voice", data={"voice": (io.BytesIO(wav()), "message"), "signature": "Mamie"},
                    content_type="multipart/form-data", headers={"Sec-Fetch-Site": "same-origin"}).get_json()
    assert r["success"]
    message = next(m for m in mm.list_messages() if m.get("kind") == "voice")
    try:
        assert message["seconds"] == 2 and mm.voice_path(message["id"]).exists()
        with Image.open(mm.image_path(message["id"])) as card:
            assert card.size[0] > 100
    finally:
        mm.delete_message(message["id"])
    assert not mm.voice_path(message["id"]).exists()


@needs_ffmpeg
def test_bad_audio_is_refused(client):
    for data in ({"voice": (io.BytesIO(b"pas du son"), "x")}, {}, {"voice": (io.BytesIO(wav(0.2)), "x")}):
        r = client.post("/upload/voice", data=data, content_type="multipart/form-data", headers={"Sec-Fetch-Site": "same-origin"})
        assert r.status_code == 400


def test_voice_card_renders():
    card = mm.render_voice_card({"signature": "Papi", "seconds": 75}, 960, 540)
    assert card.size == (960, 540)
