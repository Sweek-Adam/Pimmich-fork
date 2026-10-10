"""
Rendu d'un message texte (titre, texte, signature) en image plein écran pour le diaporama.
La taille du texte est calculée pour occuper au mieux l'écran sans déborder.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT_DIRS = [Path("/usr/share/fonts/truetype/dejavu"), Path("/usr/share/fonts/truetype/liberation")]

# Chaque style : couleurs du fond (dégradé vertical), du texte, des accents, et polices utilisées
STYLES = {
    "nuit": {"label": "Nuit", "bg": ((16, 24, 48), (44, 30, 80)), "text": (245, 245, 250), "accent": (255, 214, 120),
             "title_font": "DejaVuSans-Bold.ttf", "body_font": "DejaVuSans.ttf", "sign_font": "DejaVuSerif-Italic.ttf"},
    "clair": {"label": "Clair", "bg": ((250, 248, 242), (232, 228, 218)), "text": (40, 40, 48), "accent": (180, 90, 60),
              "title_font": "DejaVuSans-Bold.ttf", "body_font": "DejaVuSans.ttf", "sign_font": "DejaVuSerif-Italic.ttf"},
    "carte": {"label": "Carte postale", "bg": ((244, 232, 204), (226, 208, 170)), "text": (70, 52, 36), "accent": (150, 60, 50),
              "title_font": "DejaVuSerif-BoldItalic.ttf", "body_font": "DejaVuSerif-Italic.ttf", "sign_font": "DejaVuSerif-Italic.ttf",
              "frame": True},
    "festif": {"label": "Festif", "bg": ((214, 51, 108), (255, 145, 77)), "text": (255, 255, 255), "accent": (255, 240, 160),
               "title_font": "DejaVuSans-Bold.ttf", "body_font": "DejaVuSans-Bold.ttf", "sign_font": "DejaVuSerif-BoldItalic.ttf",
               "shadow": True},
}
DEFAULT_STYLE = "nuit"


def _font(name, size):
    for directory in FONT_DIRS:
        path = directory / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def _gradient(width, height, top, bottom):
    gradient = Image.new("RGB", (1, height))
    for y in range(height):
        t = y / max(height - 1, 1)
        gradient.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    return gradient.resize((width, height))


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
    # Un mot plus large que la zone : on le coupe
    result = []
    for line in lines:
        while line and draw.textlength(line, font=font) > max_width:
            cut = len(line)
            while cut > 1 and draw.textlength(line[:cut], font=font) > max_width:
                cut -= 1
            result.append(line[:cut])
            line = line[cut:]
        result.append(line)
    return result


def _layout(draw, style, title, body, signature, size, max_width):
    """Retourne la liste des lignes (texte, police, couleur, espacement après) pour une taille de base donnée."""
    blocks = []
    if title:
        f = _font(style["title_font"], int(size * 1.35))
        blocks += [(l, f, style["accent"], int(size * 0.25)) for l in _wrap(draw, title, f, max_width)]
        blocks[-1] = blocks[-1][:3] + (int(size * 0.9),)
    if body:
        f = _font(style["body_font"], size)
        blocks += [(l, f, style["text"], int(size * 0.35)) for l in _wrap(draw, body, f, max_width)]
    if signature:
        f = _font(style["sign_font"], int(size * 0.8))
        if blocks:
            blocks[-1] = blocks[-1][:3] + (int(size * 0.9),)
        blocks += [(l, f, style["accent"], int(size * 0.2)) for l in _wrap(draw, f"— {signature}", f, max_width)]
    return blocks


def _height(draw, blocks):
    total = 0
    for i, (line, font, _, spacing) in enumerate(blocks):
        ascent, descent = font.getmetrics()
        total += ascent + descent + (spacing if i < len(blocks) - 1 else 0)
    return total


def render_message(title, body, signature="", style_name=DEFAULT_STYLE, width=1920, height=1080):
    """Crée l'image du message aux dimensions de l'écran."""
    style = STYLES.get(style_name, STYLES[DEFAULT_STYLE])
    title, body, signature = (title or "").strip(), (body or "").strip(), (signature or "").strip()
    image = _gradient(width, height, *style["bg"])
    draw = ImageDraw.Draw(image)

    margin_x, margin_y = int(width * 0.1), int(height * 0.12)
    if style.get("frame"):
        inset = int(min(width, height) * 0.04)
        draw.rectangle([inset, inset, width - inset, height - inset], outline=style["accent"], width=max(3, inset // 8))
        draw.rectangle([inset * 1.4, inset * 1.4, width - inset * 1.4, height - inset * 1.4], outline=style["accent"], width=max(1, inset // 20))
    max_width, max_height = width - 2 * margin_x, height - 2 * margin_y

    # Plus grande taille de texte qui tient dans la zone (recherche par dichotomie)
    low, high = 12, int(height * 0.12)
    while low < high:
        mid = (low + high + 1) // 2
        blocks = _layout(draw, style, title, body, signature, mid, max_width)
        if _height(draw, blocks) <= max_height and all(draw.textlength(l, font=f) <= max_width for l, f, _, _ in blocks):
            low = mid
        else:
            high = mid - 1
    blocks = _layout(draw, style, title, body, signature, low, max_width)

    # Position de chaque ligne, centrée horizontalement, le bloc entier centré verticalement
    positions, y = [], (height - _height(draw, blocks)) // 2
    for line, font, color, spacing in blocks:
        positions.append(((width - draw.textlength(line, font=font)) / 2, y, line, font, color))
        ascent, descent = font.getmetrics()
        y += ascent + descent + spacing

    if style.get("shadow"):
        shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        offset = max(2, low // 18)
        for x, y, line, font, _ in positions:
            shadow_draw.text((x + offset, y + offset), line, font=font, fill=(0, 0, 0, 120))
        image = Image.alpha_composite(image.convert("RGBA"), shadow.filter(ImageFilter.GaussianBlur(offset))).convert("RGB")
        draw = ImageDraw.Draw(image)
    for x, y, line, font, color in positions:
        draw.text((x, y), line, font=font, fill=color)
    return image
