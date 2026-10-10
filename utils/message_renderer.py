"""
Rendu d'un message texte (titre, texte, signature) en image plein écran pour le diaporama,
et de « notes » (post-it, fiche) utilisées dans les compositions de plusieurs photos.

Chaque style définit un fond, éventuellement une carte posée dessus (post-it, bulle de BD),
les polices, les couleurs et des effets (ombre, lueur néon, craie). La taille du texte est calculée
pour occuper au mieux la zone disponible sans déborder.
"""
import math
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

PROJECT_DIR = Path(__file__).resolve().parent.parent
FONT_DIRS = [PROJECT_DIR / "static" / "fonts", Path("/usr/share/fonts/truetype/dejavu"), Path("/usr/share/fonts/truetype/liberation")]


def N_(text):
    """Marque un libellé pour la traduction (traduit à l'affichage dans les templates)."""
    return text


SANS, SANS_BOLD, SANS_LIGHT = "DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans-ExtraLight.ttf"
SERIF_ITALIC, SERIF_BOLD_ITALIC = "DejaVuSerif-Italic.ttf", "DejaVuSerif-BoldItalic.ttf"
HAND, HAND2, MARKER, TYPEWRITER = "PatrickHand-Regular.ttf", "Caveat-Regular.ttf", "PermanentMarker-Regular.ttf", "SpecialElite-Regular.ttf"

# bg : fond (dégradé, ou peintre nommé) ; card : carte posée sur le fond ; fonts : titre / texte / signature
STYLES = {
    "nuit": {"label": N_("Nuit"), "bg": ((16, 24, 48), (44, 30, 80)), "text": (245, 245, 250), "accent": (255, 214, 120),
             "fonts": (SANS_BOLD, SANS, SERIF_ITALIC)},
    "clair": {"label": N_("Clair"), "bg": ((250, 248, 242), (232, 228, 218)), "text": (40, 40, 48), "accent": (180, 90, 60),
              "fonts": (SANS_BOLD, SANS, SERIF_ITALIC)},
    "carte": {"label": N_("Carte postale"), "bg": ((244, 232, 204), (226, 208, 170)), "text": (70, 52, 36), "accent": (150, 60, 50),
              "fonts": (SERIF_BOLD_ITALIC, SERIF_ITALIC, SERIF_ITALIC), "frame": True},
    "festif": {"label": N_("Festif"), "bg": ((214, 51, 108), (255, 145, 77)), "text": (255, 255, 255), "accent": (255, 240, 160),
               "fonts": (SANS_BOLD, SANS_BOLD, SERIF_BOLD_ITALIC), "shadow": True},
    "postit": {"label": N_("Post-it"), "bg": ((214, 222, 230), (184, 196, 208)), "text": (50, 50, 60), "accent": (30, 60, 140),
               "fonts": (MARKER, HAND, HAND), "title_scale": 1.05, "card": {"color": ((255, 236, 120), (250, 222, 90)), "size": (0.7, 0.84), "tilt": 3}},
    "ardoise": {"label": N_("Ardoise"), "bg": "chalkboard", "text": (240, 240, 232), "accent": (250, 226, 140),
                "fonts": (MARKER, HAND2, HAND2), "title_scale": 1.1, "chalk": True},
    "neon": {"label": N_("Néon"), "bg": "bricks", "text": (255, 120, 220), "accent": (90, 230, 255),
             "fonts": (MARKER, HAND, HAND), "title_scale": 1.1, "glow": True},
    "lettre": {"label": N_("Lettre"), "bg": "lined_paper", "text": (28, 48, 120), "accent": (28, 48, 120),
               "fonts": (HAND2, HAND2, HAND2), "align": "left"},
    "machine": {"label": N_("Machine à écrire"), "bg": "old_paper", "text": (40, 34, 30), "accent": (120, 30, 30),
                "fonts": (TYPEWRITER, TYPEWRITER, TYPEWRITER), "align": "left"},
    "pastel": {"label": N_("Pastel"), "bg": "watercolor", "text": (60, 56, 80), "accent": (150, 80, 130),
               "fonts": (HAND2, HAND, HAND2)},
    "bulle": {"label": N_("Bulle de BD"), "bg": "halftone", "text": (20, 20, 20), "accent": (200, 30, 40),
              "fonts": (MARKER, HAND, HAND), "title_scale": 1.05, "card": {"shape": "bubble", "color": ((255, 255, 255), (255, 255, 255)), "size": (0.8, 0.82), "tilt": 0}},
    "minimal": {"label": N_("Minimal"), "bg": ((255, 255, 255), (246, 246, 246)), "text": (30, 30, 30), "accent": (30, 30, 30),
                "fonts": (SANS_LIGHT, SANS_LIGHT, SANS_LIGHT), "spacious": True},
}
DEFAULT_STYLE = "nuit"


def _font(name, size):
    for directory in FONT_DIRS:
        path = directory / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


# --- Fonds ---

def _gradient(width, height, top, bottom):
    gradient = Image.new("RGB", (1, height))
    for y in range(height):
        t = y / max(height - 1, 1)
        gradient.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    return gradient.resize((width, height))


def _noise(width, height, amount, rng, blur=1.0):
    """Bruit gris centré sur 128 (texture), à fusionner avec ImageChops.overlay/soft_light."""
    small = Image.effect_noise((max(1, width // 2), max(1, height // 2)), amount * 255 / 100)
    return small.resize((width, height)).filter(ImageFilter.GaussianBlur(blur))


def _textured(base, rng, amount=18):
    noise = _noise(*base.size, amount, rng).convert("RGB")
    return ImageChops.soft_light(base, noise)


def _vignette(image, strength=0.45):
    w, h = image.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse([-w * 0.25, -h * 0.25, w * 1.25, h * 1.25], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(min(w, h) * 0.12))
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(image, Image.blend(image, dark, strength), mask)


def _chalkboard(w, h, rng):
    board = _textured(_gradient(w, h, (40, 54, 48), (30, 42, 38)), rng, 22)
    draw = ImageDraw.Draw(board)
    for _ in range(18):  # traces de craie effacée
        x, y = rng.randrange(w), rng.randrange(h)
        draw.ellipse([x, y, x + rng.randrange(w // 6, w // 2), y + rng.randrange(h // 20, h // 8)], fill=(60, 74, 68))
    board = board.filter(ImageFilter.GaussianBlur(min(w, h) // 90))
    frame = max(10, min(w, h) // 30)
    draw = ImageDraw.Draw(board)
    draw.rectangle([0, 0, w - 1, h - 1], outline=(122, 84, 48), width=frame)
    draw.rectangle([frame, frame, w - frame - 1, h - frame - 1], outline=(92, 62, 34), width=max(2, frame // 6))
    return _textured(board, rng, 10)


def _bricks(w, h, rng):
    wall = Image.new("RGB", (w, h), (24, 16, 18))
    draw = ImageDraw.Draw(wall)
    bh = max(18, h // 18)
    bw = bh * 3
    for row, y in enumerate(range(0, h, bh)):
        offset = (row % 2) * bw // 2
        for x in range(-bw, w + bw, bw):
            shade = rng.randrange(-12, 12)
            draw.rectangle([x + offset + 3, y + 3, x + offset + bw - 3, y + bh - 3], fill=(70 + shade, 34 + shade // 2, 30 + shade // 2))
    return _vignette(_textured(wall, rng, 25), 0.6)


def _lined_paper(w, h, rng):
    paper = _textured(_gradient(w, h, (252, 250, 240), (246, 242, 228)), rng, 8)
    draw = ImageDraw.Draw(paper)
    step = max(24, h // 16)
    for y in range(int(h * 0.14), h, step):
        draw.line([(0, y), (w, y)], fill=(170, 196, 228), width=max(1, step // 22))
    margin = int(w * 0.09)
    draw.line([(margin, 0), (margin, h)], fill=(226, 120, 120), width=max(2, step // 14))
    return paper


def _old_paper(w, h, rng):
    paper = _textured(_gradient(w, h, (238, 226, 196), (222, 204, 166)), rng, 20)
    draw = ImageDraw.Draw(paper)
    for _ in range(6):  # taches
        x, y, r = rng.randrange(w), rng.randrange(h), rng.randrange(min(w, h) // 20, min(w, h) // 7)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(214, 194, 150))
    paper = paper.filter(ImageFilter.GaussianBlur(min(w, h) // 120))
    return _vignette(_textured(paper, rng, 12), 0.35)


def _watercolor(w, h, rng):
    paper = Image.new("RGB", (w, h), (250, 247, 242))
    colors = [(255, 200, 210), (200, 225, 255), (210, 245, 220), (255, 230, 190), (225, 210, 255)]
    layer = Image.new("RGB", (w, h), (250, 247, 242))
    draw = ImageDraw.Draw(layer)
    for _ in range(9):
        r = rng.randrange(min(w, h) // 5, min(w, h) // 2)
        x, y = rng.randrange(-r // 2, w + r // 2), rng.randrange(-r // 2, h + r // 2)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=rng.choice(colors))
    layer = layer.filter(ImageFilter.GaussianBlur(min(w, h) // 12))
    return _textured(Image.blend(paper, layer, 0.85), rng, 10)


def _halftone(w, h, rng):
    bg = Image.new("RGB", (w, h), (255, 216, 64))
    draw = ImageDraw.Draw(bg)
    step = max(14, min(w, h) // 40)
    for y in range(0, h + step, step):
        for x in range((y // step % 2) * step // 2, w + step, step):
            r = step * (0.18 + 0.22 * (x / max(w, 1)))
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(240, 160, 30))
    return bg


PAINTERS = {"chalkboard": _chalkboard, "bricks": _bricks, "lined_paper": _lined_paper, "old_paper": _old_paper,
            "watercolor": _watercolor, "halftone": _halftone}


def _background(style, w, h, rng):
    bg = style["bg"]
    if isinstance(bg, str):
        return PAINTERS[bg](w, h, rng)
    return _gradient(w, h, *bg)


# --- Mise en page du texte ---

def _wrap(draw, text, font, max_width):
    """Découpe le texte en lignes tenant dans max_width (les retours à la ligne saisis sont conservés)."""
    lines = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if draw.textlength(candidate, font=font) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    result = []
    for line in lines:  # un mot plus large que la zone est coupé
        while line and draw.textlength(line, font=font) > max_width:
            cut = len(line)
            while cut > 1 and draw.textlength(line[:cut], font=font) > max_width:
                cut -= 1
            result.append(line[:cut])
            line = line[cut:]
        result.append(line)
    return result


def _layout(draw, style, title, body, signature, size, max_width):
    """Liste des lignes (texte, police, couleur, espacement après, rôle) pour une taille de base donnée."""
    title_font, body_font, sign_font = style["fonts"]
    gap = 0.6 if style.get("spacious") else 0.35
    blocks = []
    if title:
        f = _font(title_font, int(size * style.get("title_scale", 1.35)))
        blocks += [(l, f, style["accent"], int(size * 0.25), "title") for l in _wrap(draw, title, f, max_width)]
        blocks[-1] = blocks[-1][:3] + (int(size * 0.9),) + blocks[-1][4:]
    if body:
        f = _font(body_font, size)
        blocks += [(l, f, style["text"], int(size * gap), "body") for l in _wrap(draw, body, f, max_width)]
    if signature:
        f = _font(sign_font, int(size * 0.85))
        if blocks:
            blocks[-1] = blocks[-1][:3] + (int(size * 0.9),) + blocks[-1][4:]
        blocks += [(l, f, style["accent"], int(size * 0.2), "signature") for l in _wrap(draw, f"— {signature}", f, max_width)]
    return blocks


def _height(blocks):
    total = 0
    for i, (_, font, _, spacing, _) in enumerate(blocks):
        ascent, descent = font.getmetrics()
        total += ascent + descent + (spacing if i < len(blocks) - 1 else 0)
    return total


def _fit(draw, style, title, body, signature, box_w, box_h):
    """Plus grande taille de texte qui tient dans la zone (recherche par dichotomie)."""
    low, high = 10, max(12, int(box_h * 0.2))
    while low < high:
        mid = (low + high + 1) // 2
        blocks = _layout(draw, style, title, body, signature, mid, box_w)
        if _height(blocks) <= box_h and all(draw.textlength(l, font=f) <= box_w for l, f, *_ in blocks):
            low = mid
        else:
            high = mid - 1
    return low, _layout(draw, style, title, body, signature, low, box_w)


def _draw_text(image, style, title, body, signature, box):
    """Dessine le texte dans la boîte (x, y, largeur, hauteur) de l'image RGB(A), avec les effets du style."""
    x0, y0, box_w, box_h = box
    draw = ImageDraw.Draw(image)
    size, blocks = _fit(draw, style, title, body, signature, box_w, box_h)
    align = style.get("align", "center")
    positions, y = [], y0 + (box_h - _height(blocks)) // 2
    for line, font, color, spacing, role in blocks:
        width = draw.textlength(line, font=font)
        if align == "left" and role != "title":
            x = x0 + (box_w - width if role == "signature" else 0)
        else:
            x = x0 + (box_w - width) / 2
        positions.append((x, y, line, font, color))
        ascent, descent = font.getmetrics()
        y += ascent + descent + spacing

    mode = image.mode
    if style.get("shadow") or style.get("glow"):
        layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        layer_draw = ImageDraw.Draw(layer)
        radius = max(2, size // (5 if style.get("glow") else 18))
        for x, y, line, font, color in positions:
            if style.get("glow"):
                layer_draw.text((x, y), line, font=font, fill=color + (255,))
            else:
                layer_draw.text((x + radius, y + radius), line, font=font, fill=(0, 0, 0, 120))
        blurred = layer.filter(ImageFilter.GaussianBlur(radius))
        base = image.convert("RGBA")
        base.alpha_composite(blurred)
        if style.get("glow"):
            base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(max(1, radius // 3))))
        image.paste(base.convert(mode))
        draw = ImageDraw.Draw(image)

    if style.get("chalk"):
        # Craie : le texte est « troué » par un grain aléatoire
        mask = Image.new("L", image.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        colors = []
        for x, y, line, font, color in positions:
            mask_draw.text((x, y), line, font=font, fill=235)
            colors.append(color)
        grain = Image.effect_noise(image.size, 90).point(lambda v: 255 if v > 70 else 120)
        mask = ImageChops.multiply(mask, grain).filter(ImageFilter.GaussianBlur(0.6))
        image.paste(Image.new(mode, image.size, style["text"] + ((255,) if mode == "RGBA" else ())), (0, 0), mask)
        return
    for x, y, line, font, color in positions:
        if style.get("glow"):
            color = tuple(min(255, c + 110) for c in color)  # cœur du néon plus clair
        draw.text((x, y), line, font=font, fill=color)


# --- Cartes (post-it, bulle) ---

def _card(style, card_w, card_h, title, body, signature):
    """Carte RGBA (post-it, bulle) avec le texte, avant rotation."""
    spec = style["card"]
    card = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    if spec.get("shape") == "bubble":
        body_h = int(card_h * 0.8)
        draw = ImageDraw.Draw(card)
        outline = max(4, card_w // 120)
        tail = [(int(card_w * 0.28), body_h - outline * 6), (int(card_w * 0.18), card_h - 1), (int(card_w * 0.42), body_h - outline * 8)]
        draw.polygon(tail, fill=(20, 20, 20))
        draw.ellipse([0, 0, card_w - 1, body_h], fill=(20, 20, 20))
        inner = [outline, outline, card_w - 1 - outline, body_h - outline]
        draw.ellipse(inner, fill=spec["color"][0] + (255,))
        draw.polygon([(tail[0][0] + outline, tail[0][1] - outline), (tail[1][0] + outline * 2, tail[1][1] - outline * 3),
                      (tail[2][0] - outline, tail[2][1] - outline)], fill=spec["color"][0] + (255,))
        box = (int(card_w * 0.15), int(body_h * 0.16), int(card_w * 0.7), int(body_h * 0.68))
    else:
        paper = _gradient(card_w, card_h, *spec["color"]).convert("RGBA")
        card.paste(paper, (0, 0))
        fold = card_h // 9  # bande collante plus sombre en haut du post-it
        ImageDraw.Draw(card).rectangle([0, 0, card_w, fold], fill=tuple(int(c * 0.93) for c in spec["color"][0]) + (255,))
        margin = int(min(card_w, card_h) * 0.1)
        box = (margin, fold + margin // 2, card_w - 2 * margin, card_h - fold - int(margin * 1.5))
    _draw_text(card, style, title, body, signature, box)
    return card


def _paste_with_shadow(background, element, center, shadow=True):
    x = int(center[0] - element.width / 2)
    y = int(center[1] - element.height / 2)
    if shadow:
        alpha = element.getchannel("A")
        offset = max(4, element.width // 60)
        shade = Image.new("RGBA", element.size, (0, 0, 0, 0))
        shade.putalpha(alpha.point(lambda a: a * 0.45))
        shade = shade.filter(ImageFilter.GaussianBlur(offset))
        background.alpha_composite(shade, (x + offset, y + offset * 2))
    background.alpha_composite(element, (x, y))


def render_message(title, body, signature="", style_name=DEFAULT_STYLE, width=1920, height=1080, seed=None):
    """Crée l'image du message aux dimensions de l'écran."""
    style = STYLES.get(style_name, STYLES[DEFAULT_STYLE])
    title, body, signature = (title or "").strip(), (body or "").strip(), (signature or "").strip()
    rng = random.Random(seed if seed is not None else f"{title}|{body}|{signature}|{style_name}")
    image = _background(style, width, height, rng)

    if style.get("card"):
        spec = style["card"]
        portrait = height > width
        card_w = int(width * (spec["size"][1] if portrait else spec["size"][0] * height / width * 1.3))
        card_w = min(card_w, int(width * 0.86))
        card_h = int(min(height * spec["size"][1], card_w * (1.15 if portrait else 0.95)))
        card = _card(style, card_w, card_h, title, body, signature)
        tilt = spec.get("tilt", 0)
        if tilt:
            card = card.rotate(rng.uniform(-tilt, tilt), resample=Image.BICUBIC, expand=True)
        canvas = image.convert("RGBA")
        _paste_with_shadow(canvas, card, (width / 2, height / 2), shadow=spec.get("shape") != "bubble")
        return canvas.convert("RGB")

    if style.get("frame"):
        draw = ImageDraw.Draw(image)
        inset = int(min(width, height) * 0.04)
        draw.rectangle([inset, inset, width - inset, height - inset], outline=style["accent"], width=max(3, inset // 8))
        draw.rectangle([inset * 1.4, inset * 1.4, width - inset * 1.4, height - inset * 1.4], outline=style["accent"], width=max(1, inset // 20))
    margin_x = int(width * (0.16 if style.get("spacious") else (0.13 if style.get("align") == "left" else 0.1)))
    margin_y = int(height * (0.18 if style.get("spacious") else 0.12))
    _draw_text(image, style, title, body, signature, (margin_x, margin_y, width - 2 * margin_x, height - 2 * margin_y))
    return image


def render_note(message, width, height, kind="postit", seed=None):
    """
    Note RGBA (sans fond) représentant un message, à poser dans une composition :
    « postit » (papier jaune) ou « fiche » (bristol blanc ligné).
    """
    rng = random.Random(seed)
    if kind == "fiche":
        style = dict(STYLES["lettre"], card={"color": ((255, 255, 252), (246, 244, 236)), "size": (1, 1)}, align="center")
    else:
        palette = [((255, 236, 120), (250, 222, 90)), ((255, 190, 210), (250, 170, 196)), ((180, 230, 255), (160, 216, 250)),
                   ((200, 245, 180), (180, 232, 160))]
        style = dict(STYLES["postit"], card={"color": rng.choice(palette), "size": (1, 1)})
    card = _card(style, width, height, message.get("title", ""), message.get("body", ""), message.get("signature", ""))
    if kind == "fiche":
        draw = ImageDraw.Draw(card)
        draw.line([(0, height // 7), (width, height // 7)], fill=(226, 120, 120, 255), width=max(2, height // 120))
    return card
