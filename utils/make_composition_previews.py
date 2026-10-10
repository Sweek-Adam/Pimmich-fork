"""
Génère les aperçus des formats de compositions (static/composition_previews/<format>.jpg)
à partir d'images d'exemple dessinées par programme (aucune photo personnelle).
Usage : venv/bin/python utils/make_composition_previews.py
"""
import random
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils import compositions  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "static" / "composition_previews"
PALETTES = [((90, 160, 230), (250, 200, 140), (60, 110, 70)), ((250, 140, 90), (255, 220, 160), (110, 70, 90)),
            ((40, 50, 110), (120, 120, 200), (30, 40, 60)), ((120, 200, 230), (240, 250, 255), (220, 190, 140)),
            ((200, 230, 200), (255, 250, 220), (90, 150, 80)), ((255, 170, 190), (255, 235, 220), (150, 100, 160))]


def sample_photo(i, portrait=False):
    rng = random.Random(i)
    w, h = (900, 1200) if portrait else (1200, 900)
    sky, light, ground = PALETTES[i % len(PALETTES)]
    image = Image.new("RGB", (w, h), sky)
    draw = ImageDraw.Draw(image)
    for y in range(h // 2):
        t = y / (h / 2)
        draw.line([(0, y), (w, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(sky, light)))
    r = rng.randrange(w // 12, w // 6)
    sx, sy = rng.randrange(r, w - r), rng.randrange(r, h // 3)
    draw.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(255, 240, 200))
    for k in range(3):
        base = h // 2 + k * h // 10
        points = [(0, h)] + [(x, base - rng.randrange(0, h // 5)) for x in range(0, w + 150, 150)] + [(w, h)]
        shade = tuple(max(0, c - 25 * k) for c in ground)
        draw.polygon(points, fill=shade)
    return image.filter(ImageFilter.GaussianBlur(1))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for i in range(14):
            path = Path(tmp) / f"exemple_{i}.jpg"
            sample_photo(i, portrait=i % 3 == 0).save(path, quality=90)
            paths.append(str(path))
        # « Photo unique » : une photo plein écran
        compositions.cover(sample_photo(1), 480, 270).save(OUT / "unique.jpg", quality=82, optimize=True)
        message = {"title": "Coucou !", "body": "Bisous de Lyon", "signature": "Léa", "style": "pastel"}
        for key in compositions.FORMATS:
            image = None
            for seed in range(10):
                image = compositions.compose(key, paths, [message], 1920, 1080, random.Random(seed))
                if image:
                    break
            image.resize((480, 270), Image.LANCZOS).save(OUT / f"{key}.jpg", quality=82, optimize=True)
            print("aperçu", key)


if __name__ == "__main__":
    main()
