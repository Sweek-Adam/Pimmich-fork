"""
Dispositions des moments de famille : anniversaire au prénom (avec l'âge), anniversaire de mariage, naissance,
rentrée, Saint-Valentin, fête des mères et des pères. Elles n'apparaissent qu'au bon moment (voir utils/occasions.py).
"""
import math

from PIL import Image, ImageDraw

from utils import compositions as base
from utils import occasions
from utils import themed_compositions as themed
from utils.message_renderer import N_, _gradient, _textured, _vignette, _font, soft_blur, _paste_with_shadow
from utils.themed_compositions import _title, _shaped, _place_row, _message_note, _photo_size, MARKER, HAND, HAND2, SANS_BOLD, SERIF_BI
from utils.themed_compositions_extra import _flower, birthday as _birthday_scene


def _t(text, **values):
    text = themed._translate(text)
    return text % values if values else text


def _badge(canvas, center, text, sub, size, fill, color=(255, 255, 255)):
    """Pastille ronde (ex. « 10 » / « ans »)."""
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cx, cy, r = center[0], center[1], size / 2
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill + (255,))
    draw.ellipse([cx - r * 0.9, cy - r * 0.9, cx + r * 0.9, cy + r * 0.9], outline=color + (200,), width=max(2, int(r * 0.04)))
    big = _font(SANS_BOLD, int(size * (0.42 if len(text) < 3 else 0.32)))
    small = _font(HAND, int(size * 0.24))
    draw.text((cx, cy - r * 0.08), text, font=big, fill=color + (255,), anchor="mm")
    if sub:
        draw.text((cx, cy + r * 0.45), sub, font=small, fill=color + (255,), anchor="mm")
    _paste_with_shadow(canvas, layer.crop((int(cx - r - 4), int(cy - r - 4), int(cx + r + 4), int(cy + r + 4))), (cx, cy))


def personal_birthday(photos, message, W, H, rng):
    occasion = occasions.for_theme("anniversaire_perso") or {}
    name = occasion.get("name")
    title = _t(N_("Joyeux anniversaire %(name)s !"), name=name) if name else None
    canvas = _birthday_scene(photos, message, W, H, rng, title=title).convert("RGBA")
    if occasion.get("years"):
        _badge(canvas, (W * 0.86, H * 0.2), str(occasion["years"]), _t(N_("ans")), H * 0.2, (255, 160, 40))
    return canvas.convert("RGB")


def _rings(draw, cx, cy, r, color, width):
    for dx in (-r * 0.55, r * 0.55):
        draw.ellipse([cx + dx - r, cy - r, cx + dx + r, cy + r], outline=color, width=width)


def wedding(photos, message, W, H, rng):
    occasion = occasions.for_theme("mariage") or {}
    canvas = _vignette(_textured(_gradient(W, H, (252, 248, 240), (238, 228, 214)), rng, 8), 0.25).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    gold = (196, 160, 90, 255)
    inset = int(min(W, H) * 0.035)
    draw.rectangle([inset, inset, W - inset, H - inset], outline=gold, width=max(2, H // 300))
    draw.rectangle([inset * 1.4, inset * 1.4, W - inset * 1.4, H - inset * 1.4], outline=gold, width=1)
    for _ in range(60):  # pétales
        x, y, s = rng.uniform(0, W), rng.uniform(0, H), H * rng.uniform(0.006, 0.012)
        draw.ellipse([x, y, x + s * 1.6, y + s], fill=(240, 190, 200, 180))
    size = _photo_size(W, H, len(photos), 0.85)
    elements = [_shaped(p, (int(size * 0.82), size), "egg", max(5, size // 40), ((230, 200, 130), (170, 130, 60))) for p in photos]
    _place_row(canvas, elements, H * 0.58, rng, 0.74, 0.03, 3)
    _rings(draw, W / 2, H * 0.12, H * 0.035, gold, max(3, H // 220))
    years = occasion.get("years")
    title = _t(N_("Joyeux anniversaire de mariage")) if years else _t(N_("Vive les mariés !"))
    _title(canvas, title, SERIF_BI, int(H * 0.07), (150, 110, 50), (W / 2, H * 0.23), shadow=False, max_width=W * 0.8)
    subtitle = " ".join(p for p in (occasion.get("name", ""), _t(N_("%(years)s ans"), years=years) if years else "") if p)
    if subtitle:
        _title(canvas, subtitle, HAND2, int(H * 0.055), (120, 90, 50), (W / 2, H * 0.9), shadow=False, max_width=W * 0.8)
    _message_note(canvas, message, rng, "fiche", (0.88, 0.8), 0.18)
    return canvas.convert("RGB")


def newborn(photos, message, W, H, rng):
    occasion = occasions.for_theme("naissance") or {}
    canvas = _textured(_gradient(W, H, (232, 244, 250), (252, 240, 246)), rng, 6).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    for _ in range(9):  # nuages
        cx, cy, s = rng.uniform(0, W), rng.uniform(H * 0.05, H * 0.95), H * rng.uniform(0.04, 0.08)
        for dx, dy, k in ((-1, 0, 1), (0, -0.5, 1.3), (1, 0, 1), (0.4, 0.2, 0.9)):
            draw.ellipse([cx + dx * s - s * k, cy + dy * s - s * k * 0.7, cx + dx * s + s * k, cy + dy * s + s * k * 0.7], fill=(255, 255, 255, 170))
    for _ in range(40):  # étoiles
        x, y, r = rng.uniform(0, W), rng.uniform(0, H), H * rng.uniform(0.005, 0.012)
        draw.polygon(themed._star(x, y, r, r * 0.45), fill=(255, 214, 120, 220))
    # Mobile : fil et lune
    moon_r = H * 0.05
    draw.ellipse([W * 0.08 - moon_r, H * 0.14 - moon_r, W * 0.08 + moon_r, H * 0.14 + moon_r], fill=(255, 226, 140, 255))
    draw.ellipse([W * 0.08 - moon_r * 0.4, H * 0.14 - moon_r * 1.05, W * 0.08 + moon_r * 1.4, H * 0.14 + moon_r * 0.75], fill=(234, 244, 250, 255))
    size = _photo_size(W, H, len(photos), 0.85)
    elements = [base.framed(base.print_photo(p, size, size), max(8, size // 22), (255, 255, 255), bottom=max(8, size // 22) * 3) for p in photos]
    _place_row(canvas, elements, H * 0.58, rng, 0.72, 0.05, 6)
    name = occasion.get("name")
    title = _t(N_("Bienvenue %(name)s !"), name=name) if name else _t(N_("Bienvenue bébé !"))
    _title(canvas, title, HAND2, int(H * 0.1), (110, 140, 190), (W / 2, H * 0.13), shadow=False, max_width=W * 0.7)
    if occasion.get("date"):
        _title(canvas, occasion["date"].strftime("%d/%m/%Y"), HAND, int(H * 0.045), (150, 130, 170), (W / 2, H * 0.92), shadow=False)
    _message_note(canvas, message, rng, "postit", (0.9, 0.86), 0.14)
    return canvas.convert("RGB")


def back_to_school(photos, message, W, H, rng):
    from utils.message_renderer import _chalkboard
    board = _chalkboard(W, H, rng).convert("RGBA")
    draw = ImageDraw.Draw(board)
    frame = int(H * 0.035)
    draw.rectangle([0, 0, W, H], outline=(150, 100, 55, 255), width=frame)  # cadre en bois
    # Crayons de couleur en bas
    for k in range(7):
        x, y, length, width = W * (0.06 + k * 0.035), H * 0.9, H * 0.16, H * 0.025
        color = [(230, 60, 60), (250, 170, 40), (250, 220, 60), (90, 190, 90), (70, 140, 230), (150, 90, 210), (240, 120, 170)][k]
        draw.rectangle([x, y - length, x + width, y], fill=color + (255,))
        draw.polygon([(x, y - length), (x + width, y - length), (x + width / 2, y - length - width * 1.2)], fill=(240, 210, 160, 255))
        draw.polygon([(x + width * 0.3, y - length - width * 0.75), (x + width * 0.7, y - length - width * 0.75), (x + width / 2, y - length - width * 1.2)], fill=color + (255,))
    size = _photo_size(W, H, len(photos), 0.8)
    elements = [base.framed(base.print_photo(p, size, size), max(6, size // 24), (250, 250, 245), bottom=max(6, size // 24) * 3) for p in photos]
    _place_row(board, elements, H * 0.56, rng, 0.7, 0.05, 7)
    _title(board, _t(N_("C'est la rentrée !")), HAND2, int(H * 0.1), (245, 245, 235), (W / 2, H * 0.14), shadow=False, max_width=W * 0.8)
    _message_note(board, message, rng, "postit", (0.88, 0.84), 0.15)
    return board.convert("RGB")


def _heart(cx, cy, size):
    points = []
    for i in range(80):
        t = 2 * math.pi * i / 80
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        points.append((cx + x * size / 34, cy - y * size / 34))
    return points


def valentine(photos, message, W, H, rng):
    canvas = _vignette(_gradient(W, H, (150, 20, 50), (230, 80, 110)), 0.45).convert("RGBA")
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for _ in range(45):
        size = H * rng.uniform(0.02, 0.07)
        draw.polygon(_heart(rng.uniform(0, W), rng.uniform(0, H), size), fill=(255, 190, 200, int(rng.uniform(60, 160))))
    canvas.alpha_composite(soft_blur(layer, 1))
    size = _photo_size(W, H, len(photos), 0.9)
    elements = [_shaped(p, (size, size), "heart", max(5, size // 35), ((255, 230, 235), (240, 160, 180))) for p in photos]
    _place_row(canvas, elements, H * 0.56, rng, 0.74, 0.04, 6)
    _title(canvas, _t(N_("Joyeuse Saint-Valentin")), HAND2, int(H * 0.1), (255, 240, 245), (W / 2, H * 0.13), glow=(255, 120, 150), max_width=W * 0.8)
    _message_note(canvas, message, rng, "fiche", (0.88, 0.84), 0.16)
    return canvas.convert("RGB")


def mothers_day(photos, message, W, H, rng):
    canvas = _textured(_gradient(W, H, (255, 238, 242), (250, 226, 236)), rng, 6).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    for _ in range(26):
        x, y = rng.choice([rng.uniform(0, W * 0.16), rng.uniform(W * 0.84, W)]), rng.uniform(0, H)
        r = H * rng.uniform(0.018, 0.035)
        petal = rng.choice([(240, 120, 160), (250, 170, 190), (230, 90, 130), (255, 200, 120)])
        _flower(draw, x, y, r, petal + (255,), (255, 220, 120, 255), rng.choice([5, 6, 8]), rng.uniform(0, 1))
    size = _photo_size(W, H, len(photos), 0.85)
    elements = [base.framed(base.print_photo(p, size, size), max(8, size // 22), (255, 255, 255), bottom=max(8, size // 22) * 3) for p in photos]
    _place_row(canvas, elements, H * 0.57, rng, 0.62, 0.04, 6)
    _title(canvas, _t(N_("Bonne fête Maman !")), HAND2, int(H * 0.1), (200, 60, 110), (W / 2, H * 0.13), shadow=False, max_width=W * 0.7)
    _message_note(canvas, message, rng, "postit", (0.5, 0.9), 0.14)
    return canvas.convert("RGB")


def _tie(draw, cx, cy, size, color):
    draw.polygon([(cx - size * 0.18, cy), (cx + size * 0.18, cy), (cx + size * 0.08, cy + size * 0.2), (cx - size * 0.08, cy + size * 0.2)], fill=color)
    draw.polygon([(cx - size * 0.08, cy + size * 0.2), (cx + size * 0.08, cy + size * 0.2), (cx + size * 0.22, cy + size * 0.85),
                  (cx, cy + size), (cx - size * 0.22, cy + size * 0.85)], fill=color)


def fathers_day(photos, message, W, H, rng):
    canvas = _vignette(_textured(_gradient(W, H, (28, 52, 86), (16, 30, 54)), rng, 10), 0.4).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    for k in range(14):  # cravates à motifs
        x, y = rng.choice([rng.uniform(W * 0.02, W * 0.13), rng.uniform(W * 0.87, W * 0.98)]), rng.uniform(H * 0.05, H * 0.85)
        _tie(draw, x, y, H * rng.uniform(0.08, 0.13), rng.choice([(200, 70, 60), (230, 180, 60), (90, 160, 220), (120, 190, 120)]) + (255,))
    size = _photo_size(W, H, len(photos), 0.85)
    elements = [base.framed(base.print_photo(p, size, size), max(8, size // 22), (245, 245, 240), bottom=max(8, size // 22) * 3) for p in photos]
    _place_row(canvas, elements, H * 0.57, rng, 0.62, 0.04, 5)
    _title(canvas, _t(N_("Bonne fête Papa !")), MARKER, int(H * 0.09), (245, 210, 110), (W / 2, H * 0.13), shadow=True, max_width=W * 0.7)
    _message_note(canvas, message, rng, "fiche", (0.5, 0.9), 0.14)
    return canvas.convert("RGB")


THEMES = {
    "anniversaire_perso": (N_("Anniversaire au prénom"), 3, 3, True, personal_birthday),
    "mariage": (N_("Mariage"), 3, 3, True, wedding),
    "naissance": (N_("Naissance"), 3, 3, True, newborn),
    "rentree": (N_("Rentrée"), 3, 3, True, back_to_school),
    "saint_valentin": (N_("Saint-Valentin"), 3, 3, True, valentine),
    "fete_meres": (N_("Fête des mères"), 3, 3, True, mothers_day),
    "fete_peres": (N_("Fête des pères"), 3, 3, True, fathers_day),
}
