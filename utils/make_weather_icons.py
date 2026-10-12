"""
Dessine les icônes météo manquantes (codes OpenWeatherMap) dans static/weather_icons/, dans le style plat des
icônes existantes : soleil orange, lune gris foncé, nuages blancs, pluie, orage, neige, brume.
Dessins originaux (aucune image téléchargée). Les icônes déjà présentes ne sont pas remplacées (sauf --all).
Usage : python utils/make_weather_icons.py [--all]
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "static" / "weather_icons"
SIZE = 100
K = 4  # dessin en 4x puis réduction : bords lisses
SUN = (236, 110, 76, 255)
MOON = (72, 72, 74, 255)
CLOUD = (242, 242, 241, 255)
DARK_CLOUD = (72, 72, 74, 255)
RAIN = (96, 160, 220, 255)
BOLT = (250, 196, 50, 255)
SNOW = (200, 225, 245, 255)
MIST = (190, 190, 196, 255)


def s(*values):
    return [v * K for v in values]


def disc(draw, cx, cy, r, color):
    draw.ellipse(s(cx - r, cy - r, cx + r, cy + r), fill=color)


def cloud(draw, cx, cy, w, color):
    """Nuage centré en (cx, cy), de largeur w : une base arrondie et deux bosses."""
    h = w * 0.36
    draw.rounded_rectangle(s(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), radius=h / 2 * K, fill=color)
    disc(draw, cx - w * 0.14, cy - h * 0.55, w * 0.22, color)
    disc(draw, cx + w * 0.13, cy - h * 0.35, w * 0.17, color)


def sky(draw, night, cx, cy, r):
    disc(draw, cx, cy, r, MOON if night else SUN)


def drops(draw, cx, top, count=3, color=RAIN):
    for i in range(count):
        x = cx + (i - (count - 1) / 2) * 11
        draw.line(s(x + 3, top, x - 2, top + 11), fill=color, width=4 * K)


def flakes(draw, cx, top):
    for i, dy in zip(range(3), (0, 7, 0)):
        x, y = cx + (i - 1) * 13, top + 5 + dy
        for dx, dyy in ((4, 0), (0, 4), (3, 3), (3, -3)):
            draw.line(s(x - dx, y - dyy, x + dx, y + dyy), fill=SNOW, width=2 * K)


def bolt(draw, cx, top):
    draw.polygon(s(cx + 2, top, cx - 7, top + 15, cx, top + 15, cx - 3, top + 27, cx + 9, top + 9, cx + 2, top + 9), fill=BOLT)


def icon(code):
    image = Image.new("RGBA", (SIZE * K, SIZE * K), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    kind, night = code[:2], code.endswith("n")
    if kind == "01":
        sky(draw, night, 50, 50, 25)
    elif kind == "02":
        sky(draw, night, 62, 40, 16)
        cloud(draw, 46, 58, 56, CLOUD)
    elif kind == "03":
        cloud(draw, 50, 55, 58, CLOUD)
    elif kind == "04":
        cloud(draw, 60, 45, 46, DARK_CLOUD)
        cloud(draw, 46, 58, 56, CLOUD)
    elif kind == "09":  # averses
        cloud(draw, 60, 38, 42, DARK_CLOUD)
        cloud(draw, 47, 48, 54, CLOUD)
        drops(draw, 47, 62, 4)
    elif kind == "10":  # pluie (avec soleil ou lune)
        sky(draw, night, 62, 32, 13)
        cloud(draw, 47, 48, 54, CLOUD)
        drops(draw, 47, 62, 3)
    elif kind == "11":  # orage
        cloud(draw, 60, 36, 42, DARK_CLOUD)
        cloud(draw, 47, 46, 54, CLOUD)
        bolt(draw, 49, 58)
    elif kind == "13":  # neige
        cloud(draw, 50, 46, 56, CLOUD)
        flakes(draw, 50, 60)
    elif kind == "50":  # brume
        for i, (x0, x1) in enumerate(((22, 70), (30, 80), (20, 74), (32, 78))):
            y = 34 + i * 11
            draw.line(s(x0, y, x1, y), fill=MIST, width=6 * K)
            draw.ellipse(s(x0 - 3, y - 3, x0 + 3, y + 3), fill=MIST)
            draw.ellipse(s(x1 - 3, y - 3, x1 + 3, y + 3), fill=MIST)
    return image.resize((SIZE, SIZE), Image.LANCZOS)


CODES = [f"{n}{t}" for n in ("01", "02", "03", "04", "09", "10", "11", "13", "50") for t in ("d", "n")]


def main():
    replace = "--all" in sys.argv[1:]
    OUT.mkdir(parents=True, exist_ok=True)
    for code in CODES:
        path = OUT / f"{code}.png"
        if path.exists() and not replace:
            continue
        icon(code).save(path, optimize=True)
        print("icône", code)


if __name__ == "__main__":
    main()
