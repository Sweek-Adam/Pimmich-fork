"""Dessins d'invités (à main levée, avec autocollants) : envoi, rendu plein écran, nettoyage."""
import io

import pytest
from PIL import Image, ImageDraw

from utils import messages_manager as mm


def drawing_png(size=(1280, 720)):
    image = Image.new("RGB", size, (255, 253, 246))
    ImageDraw.Draw(image).line([(100, 100), (1100, 600)], fill=(229, 57, 53), width=12)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def guest_messages_on():
    from utils.config_manager import load_config, save_config
    original = dict(load_config())
    save_config(dict(original, guest_messages_enabled=True))
    yield
    save_config(original)


def test_guest_drawing_is_shown_like_a_message(client, sandbox, monkeypatch, tmp_path):
    monkeypatch.setattr(mm, "PRIORITY_FILE", tmp_path / "priority.json")
    html = client.get("/upload").get_data(as_text=True)
    assert 'id="dr-canvas"' in html and "dessin" in html.lower()
    resp = client.post("/upload/drawing", data={"drawing": (io.BytesIO(drawing_png()), "dessin.png"), "signature": "Léa"},
                       content_type="multipart/form-data", headers={"Sec-Fetch-Site": "same-origin"})
    result = resp.get_json()
    assert resp.status_code == 200 and result["success"]
    message = next(m for m in mm.list_messages() if m.get("kind") == "drawing")
    try:
        assert message["guest"] and message["expires"] and message["signature"] == "Léa"
        with Image.open(mm.image_path(message["id"])) as shown:
            assert shown.size[0] > 100  # rendu à la taille de l'écran
            assert shown.getpixel((shown.width // 2, shown.height // 2)) != (0, 0, 0)
        assert mm.pop_priority()  # affiché tout de suite
        assert mm.ensure_images(640, 360) >= 1  # nouvelle taille d'écran : redessiné depuis le dessin d'origine
        with Image.open(mm.image_path(message["id"])) as shown:
            assert shown.size == (640, 360)
    finally:
        mm.delete_message(message["id"])
    assert not (mm.DRAWINGS_DIR / f"{message['id']}.png").exists()


def test_bad_drawings_are_refused(client):
    for data in ({"drawing": (io.BytesIO(b"pas une image"), "x.png")}, {}, {"drawing": (io.BytesIO(drawing_png((20, 20))), "x.png")}):
        resp = client.post("/upload/drawing", data=data, content_type="multipart/form-data", headers={"Sec-Fetch-Site": "same-origin"})
        assert resp.status_code == 400


def test_render_drawing_with_and_without_signature(monkeypatch, tmp_path):
    monkeypatch.setattr(mm, "DRAWINGS_DIR", tmp_path)
    Image.open(io.BytesIO(drawing_png())).save(tmp_path / "abc.png")
    for signature in ("", "Papi"):
        image = mm.render_drawing("abc", signature, 1920, 1080)
        assert image.size == (1920, 1080)


def test_blank_drawing_is_refused():
    import pytest
    from utils import messages_manager
    image = Image.new("RGB", (1280, 720), (47, 59, 51))  # ardoise avec un trait de la même couleur : rien de visible
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    with pytest.raises(ValueError):
        messages_manager.create_drawing(buffer.getvalue(), "Léo", "", 1920, 1080)


def test_drawing_in_every_composition(monkeypatch, tmp_path):
    """Un dessin d'invité apparaît comme un dessin (pas comme une carte de texte vide) dans les dispositions qui posent un message."""
    import random
    from utils import compositions, message_renderer
    drawings = tmp_path / "cache" / "drawings"
    drawings.mkdir(parents=True)
    (drawings / "abc123abc123.png").write_bytes(drawing_png())
    monkeypatch.setattr(message_renderer, "PROJECT_DIR", tmp_path)
    message = {"id": "abc123abc123", "kind": "drawing", "title": "", "body": "", "signature": "Léo", "style": "nuit"}
    tile = compositions.message_tile(message, 400, 300)
    pixels = tile.convert("RGB").getcolors(400 * 300)
    reds = sum(n for n, (r, g, b) in pixels if r > 180 and g < 100 and b < 100)
    assert reds > 200  # le trait rouge du dessin est bien là
    photos = [Image.new("RGB", (800, 600), (90, 120, 160)) for _ in range(4)]
    for style in ("mosaique", "mur", "magazine"):
        if style in compositions.FORMATS:
            image = compositions.FORMATS[style][4](photos[:3], message, 1280, 720, random.Random(1))
            assert image.size == (1280, 720)


def test_drawing_editor_has_fullscreen_and_new_tools(client, sandbox, monkeypatch):
    html = client.get("/upload").get_data(as_text=True)
    for marker in ('id="dr-full"', 'id="dr-redo"', 'data-mode="marker"', 'data-mode="text"', 'id="dr-size"', 'id="dr-custom"', "requestFullscreen"):
        assert marker in html, marker
