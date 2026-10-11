"""Dessins et messages vocaux dans les compositions : le dessin apparaît dans sa note, le vocal reste seul."""
import random

import pytest
from PIL import Image, ImageDraw

from utils import compositions, layout_engine, messages_manager


@pytest.fixture
def media(sandbox, tmp_path, monkeypatch):
    drawings = sandbox / "cache" / "drawings"
    drawings.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (640, 360), (255, 253, 246))
    ImageDraw.Draw(image).ellipse([200, 80, 440, 280], fill=(230, 40, 60))
    image.save(drawings / "d00000000001.png")
    folder = sandbox / "static" / "prepared" / "messages"
    folder.mkdir(parents=True, exist_ok=True)
    photos = []
    for i, color in enumerate(((90, 140, 200), (120, 180, 90), (200, 160, 80), (150, 90, 160))):
        path = tmp_path / f"p{i}.jpg"
        Image.new("RGB", (800, 600), color).save(path)
        photos.append(str(path))
    for mid in ("d00000000001", "v00000000001"):
        Image.new("RGB", (1920, 1080), (30, 30, 60)).save(folder / f"{mid}.jpg")
    messages = {"d00000000001": {"id": "d00000000001", "kind": "drawing", "title": "", "body": "", "signature": "Léa"},
                "v00000000001": {"id": "v00000000001", "kind": "voice", "title": "", "body": "", "signature": "Mamie"}}
    yield photos, str(folder / "d00000000001.jpg"), str(folder / "v00000000001.jpg"), messages
    (drawings / "d00000000001.png").unlink()


def test_drawing_note_shows_the_drawing(media):
    from utils.message_renderer import render_note
    _photos, _d, _v, messages = media
    note = render_note(messages["d00000000001"], 300, 220)
    reds = sum(1 for p in note.convert("RGB").get_flattened_data() if p[0] > 200 and p[1] < 80)
    assert reds > 1000  # le dessin (rond rouge) est bien dans la note


def test_every_layout_accepts_a_drawing(media):
    photos, drawing, _voice, messages = media
    for style, (_label, _min, max_n, accepts, _render) in compositions.FORMATS.items():
        if not accepts or style in compositions.OCCASION_THEMES:
            continue
        image, used = layout_engine.render_chunk(style, photos[:max_n] + [drawing], messages, 640, 360, True, random.Random(1))
        if image is not None:
            assert image.size == (640, 360), style


def test_voice_message_is_always_shown_alone(media):
    photos, _drawing, voice, messages = media
    for style in ("mosaique", "halloween", "noel"):
        assert layout_engine.render_chunk(style, [voice] + photos, messages, 640, 360, True, random.Random(1)) == (None, 0)
        image, used = layout_engine.render_chunk(style, photos[:2] + [voice] + photos[2:], messages, 640, 360, True, random.Random(1))
        assert used <= 2  # la composition s'arrête avant le message vocal
