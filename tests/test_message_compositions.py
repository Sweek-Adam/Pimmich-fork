"""Dispositions construites autour d'un message : rendu (texte, dessin, portrait) et seulement quand un message est là."""
import random

from PIL import Image, ImageDraw

from utils import compositions, layout_engine, message_compositions, message_renderer


def photos(n):
    return [Image.new("RGB", (800, 600) if i % 2 else (600, 800), (40 * i % 255, 120, 160)) for i in range(n)]


def test_every_message_layout_renders(monkeypatch, tmp_path):
    drawings = tmp_path / "cache" / "drawings"
    drawings.mkdir(parents=True)
    image = Image.new("RGB", (640, 360), (255, 253, 246))
    ImageDraw.Draw(image).line([(50, 50), (590, 300)], fill=(229, 57, 53), width=10)
    image.save(drawings / "abc123abc123.png")
    monkeypatch.setattr(message_renderer, "PROJECT_DIR", tmp_path)
    text = {"id": "t1", "title": "Coucou", "body": "Gros bisous", "signature": "Léa", "style": "pastel"}
    drawing = {"id": "abc123abc123", "kind": "drawing", "title": "", "body": "", "signature": "Tom"}
    japanese = {"id": "t2", "title": "おめでとう", "body": "", "signature": ""}
    assert len(message_compositions.FORMATS) >= 30
    for key, (_label, low, high, accepts, render) in message_compositions.FORMATS.items():
        assert accepts and key in compositions.FORMATS and key in compositions.MESSAGE_FORMATS
        for size, message, count in (((960, 540), text, high), ((540, 960), drawing, low), ((960, 540), japanese, low)):
            assert render(photos(count), message, *size, random.Random(1)).size == size, key


def test_only_with_a_message():
    paths = []
    assert compositions.compose("msg_bureau", paths, [], 960, 540, random.Random(1)) is None
    assert compositions.compose("msg_bureau", paths, [{"kind": "voice", "id": "v"}], 960, 540, random.Random(1)) is None
    plan = layout_engine.LayoutPlan(False, ["mosaique", "msg_bureau"], 5, True)
    _wanted, used = layout_engine.plan_for_slide(plan, "/static/prepared/gdrive/a.jpg", 10)
    assert used.formats == ["mosaique"]  # une photo : pas de disposition à message
    _wanted, used = layout_engine.plan_for_slide(plan, "/static/prepared/messages/abc.jpg", 0)
    assert "msg_bureau" in used.formats  # un message arrive : elles sont proposées
    only = layout_engine.LayoutPlan(False, ["msg_bureau"], 5, True)
    assert layout_engine.plan_for_slide(only, "/static/prepared/gdrive/a.jpg", 10)[1].formats == ["msg_bureau"]
