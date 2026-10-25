"""Amélioration automatique : photos sombres ou ternes corrigées, photos correctes et nuits voulues laissées telles quelles."""
import random

from PIL import Image, ImageDraw, ImageStat

from utils import auto_enhance


def photo(lo, hi, seed=1, size=(200, 150), background=None):
    """Une « photo » faite de formes de luminosités entre lo et hi."""
    rng = random.Random(seed)
    bg = lo if background is None else background
    img = Image.new("RGB", size, (bg, bg, bg))
    draw = ImageDraw.Draw(img)
    for _ in range(60):
        v = rng.randint(lo, hi)
        x, y = rng.randint(0, size[0]), rng.randint(0, size[1])
        draw.ellipse([x, y, x + 40, y + 30], fill=(v, max(0, v - 10), max(0, v - 20)))
    return img


def brightness(img):
    return ImageStat.Stat(img.convert("L")).mean[0]


def test_dark_and_dull_photos_are_corrected():
    dark = photo(5, 90)
    better, steps = auto_enhance.auto(dark)
    assert "gamma" in steps and brightness(better) > brightness(dark) + 15
    dull = photo(90, 170)
    better, steps = auto_enhance.auto(dull)
    assert "stretch" in steps
    assert ImageStat.Stat(better.convert("L")).stddev[0] > ImageStat.Stat(dull.convert("L")).stddev[0]


def test_good_photos_and_wanted_nights_are_left_alone():
    good = photo(0, 255, background=130)
    assert auto_enhance.auto(good)[1] == {}
    night = photo(0, 40)
    ImageDraw.Draw(night).ellipse([80, 60, 110, 90], fill=(255, 250, 230))  # une lumière vive dans la nuit
    assert auto_enhance.plan(auto_enhance.measure(night)) == {} or auto_enhance.measure(night)["high"] < 235
    flat = Image.new("RGB", (100, 100), (10, 20, 30))
    assert auto_enhance.auto(flat) == (flat, {})
