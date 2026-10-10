"""Compositions de plusieurs photos et styles de messages."""
import random

import pytest
from PIL import Image, ImageDraw

from utils import compositions as comp
from utils.message_renderer import STYLES, render_message, render_note

W, H = 640, 360
MESSAGE = {"title": "Coucou", "body": "Bisous de Lyon", "signature": "Léa", "style": "pastel"}


@pytest.fixture(scope="module")
def photos(tmp_path_factory):
    folder = tmp_path_factory.mktemp("photos")
    paths = []
    for i in range(14):
        size = (300, 400) if i % 3 == 0 else (400, 300)
        image = Image.new("RGB", size, ((i * 40) % 255, (i * 90) % 255, (i * 150) % 255))
        ImageDraw.Draw(image).ellipse([50, 50, 150, 150], fill=(255, 255, 255))
        path = folder / f"p{i}.jpg"
        image.save(path)
        paths.append(str(path))
    return paths


@pytest.mark.parametrize("style", list(comp.FORMATS))
@pytest.mark.parametrize("with_message", [False, True])
def test_every_format_renders_at_screen_size(photos, style, with_message):
    image = None
    for seed in range(6):  # le message n'est inclus qu'au hasard : plusieurs essais
        image = comp.compose(style, photos, [MESSAGE] if with_message else [], W, H, random.Random(seed))
        if image is not None:
            break
    assert image is not None and image.size == (W, H)


def test_not_enough_photos_returns_none(photos):
    assert comp.compose("photomaton", photos[:3], [], W, H, random.Random(1)) is None


def test_random_choice_uses_only_enabled_formats(photos):
    for seed in range(5):
        style, image = comp.compose_random(["duo", "mosaique"], photos, [], W, H, rng=random.Random(seed))
        assert style in ("duo", "mosaique") and image.size == (W, H)
    assert comp.compose_random([], photos, [], W, H) == (None, None)


def test_original_photo_is_preferred(tmp_path, monkeypatch):
    monkeypatch.setattr(comp, "PHOTOS_DIR", tmp_path / "photos")
    (tmp_path / "photos" / "gdrive").mkdir(parents=True)
    original = tmp_path / "photos" / "gdrive" / "vacances.jpg"
    original.write_bytes(b"x")
    prepared = tmp_path / "prepared" / "gdrive" / "vacances_polaroid.jpg"
    assert comp.original_for(str(prepared)) == original


@pytest.mark.parametrize("style", list(STYLES))
@pytest.mark.parametrize("size", [(W, H), (H, W)])
def test_every_message_style_renders(style, size):
    image = render_message("Titre", "Un message un peu long pour voir le retour à la ligne", "Moi", style, *size)
    assert image.size == size and image.mode == "RGB"


@pytest.mark.parametrize("kind", ["postit", "fiche"])
def test_notes_for_compositions(kind):
    note = render_note(MESSAGE, 200, 180, kind, seed=1)
    assert note.size == (200, 180) and note.mode == "RGBA"


def test_composition_settings_are_saved(admin_client):
    from utils.config_manager import load_config
    admin_client.post("/configure", data={"compositions_form": "1", "compositions_enabled": "on", "compositions_every": "7",
                                          "compositions_styles": ["liege", "inconnu"]}, headers={"Sec-Fetch-Site": "same-origin"})
    config = load_config()
    assert config["compositions_every"] == 7 and config["compositions_styles"] == ["liege"]
    assert config["compositions_enabled"] and not config["compositions_include_messages"]
