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
    admin_client.post("/configure", data={"compositions_form": "1", "compositions_enabled": "on", "compositions_every": "7", "compositions_full_photos": "on",
                                          "compositions_styles": ["liege", "inconnu"]}, headers={"Sec-Fetch-Site": "same-origin"})
    config = load_config()
    from utils.compositions import enabled_formats
    assert config["compositions_every"] == 7 and enabled_formats(config) == ["liege"]
    assert config["compositions_enabled"] and not config["compositions_include_messages"] and not config["compositions_seasonal"]
    assert config["compositions_full_photos"]


from datetime import date

from utils import themed_compositions as themed


@pytest.mark.parametrize("year,expected", [(2024, date(2024, 3, 31)), (2025, date(2025, 4, 20)), (2026, date(2026, 4, 5)), (2027, date(2027, 3, 28))])
def test_easter_dates(year, expected):
    assert themed.easter(year) == expected


@pytest.mark.parametrize("theme,today,expected", [
    ("noel", date(2026, 12, 15), True), ("noel", date(2027, 1, 6), True), ("noel", date(2026, 7, 1), False),
    ("halloween", date(2026, 10, 31), True), ("halloween", date(2026, 12, 1), False),
    ("paques", date(2026, 4, 1), True), ("paques", date(2026, 6, 1), False),
    ("hiver", date(2026, 1, 15), True), ("printemps", date(2026, 5, 1), True), ("automne", date(2026, 10, 1), True),
    ("automne", date(2026, 5, 1), False), ("japon", date(2026, 5, 1), True),
])
def test_seasons(theme, today, expected):
    assert themed.in_season(theme, today) is expected


def test_seasonal_themes_only_in_their_period(photos, monkeypatch):
    chosen = []
    monkeypatch.setattr(comp, "compose", lambda style, *a, **k: chosen.append(style) or Image.new("RGB", (W, H)))
    for seed in range(40):
        comp.compose_random(["noel", "japon"], photos, [], W, H, rng=random.Random(seed), today=date(2026, 7, 1))
    assert set(chosen) == {"japon"}
    chosen.clear()
    for seed in range(400):
        comp.compose_random(["noel", "japon"], photos, [], W, H, rng=random.Random(seed), today=date(2026, 12, 20))
    assert chosen.count("noel") > chosen.count("japon") * 2  # trois fois plus fréquent en saison
    chosen.clear()
    comp.compose_random(["noel"], photos, [], W, H, rng=random.Random(1), seasonal=False, today=date(2026, 7, 1))
    assert chosen == ["noel"]


def test_enabled_formats_include_new_ones_and_migrate_old_setting():
    assert comp.enabled_formats({}) == list(comp.FORMATS)
    assert "hokusai" in comp.enabled_formats({"compositions_disabled": ["liege"]})
    old = comp.enabled_formats({"compositions_styles": ["liege", "duo"]})  # ancien réglage : formats de base cochés
    assert "liege" in old and "mosaique" not in old and "fuji" in old


def test_titles_in_unsupported_scripts_are_skipped():
    canvas = Image.new("RGBA", (200, 100), (0, 0, 0, 255))
    themed._title(canvas, "メリークリスマス", themed.HAND2, 40, (255, 255, 255), (100, 50))
    assert canvas.getbbox() == (0, 0, 200, 100) and canvas.convert("L").getextrema() == (0, 0)
    themed._title(canvas, "Joyeux Noël – fête", themed.HAND2, 40, (255, 255, 255), (100, 50))
    assert canvas.convert("L").getextrema()[1] > 0


@pytest.fixture()
def full_photos():
    comp.set_full_photos(True)
    yield
    comp.set_full_photos(True)


def test_print_photo_keeps_the_whole_photo(full_photos):
    portrait = Image.new("RGB", (300, 400), (200, 0, 0))
    out = comp.print_photo(portrait, 400, 300)
    assert abs(out.width / out.height - 0.75) < 0.02           # proportions conservées : rien n'est coupé
    assert 0.8 < (out.width * out.height) / (400 * 300) < 1.05  # surface comparable à la boîte
    comp.set_full_photos(False)
    assert comp.print_photo(portrait, 400, 300).size == (400, 300)  # mode recadrage


def test_cell_photo_shows_whole_photo_on_blurred_fill(full_photos):
    photo = Image.new("RGB", (400, 300), (0, 0, 255))
    cell = comp.cell_photo(photo, 300, 400)
    assert cell.size == (300, 400)
    assert cell.getpixel((150, 200)) == (0, 0, 255)       # la photo est au centre, entière (300 × 225)
    assert cell.getpixel((150, 50)) != (0, 0, 255)        # au-dessus : fond flou assombri


def test_proportional_widths(full_photos):
    photos = [Image.new("RGB", (300, 400)), Image.new("RGB", (800, 400))]
    widths = comp.proportional_widths(photos, 1000, 400)
    assert abs(sum(widths) - 1000) < 1 and widths[1] > widths[0] * 2
