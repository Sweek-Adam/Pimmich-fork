"""
Mode jukebox et karaoké : pendant la musique, le cadre montre la pochette en grand (sur un fond flou tiré d'elle),
le titre et l'artiste ; en karaoké, les paroles défilent en rythme (Spotify : position de lecture connue).
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from utils.message_renderer import _font, SANS, SANS_BOLD

MODES = ("off", "jukebox", "karaoke")


def background(info, width, height):
    """Fond : la pochette agrandie, floutée et assombrie (dégradé sombre sans pochette)."""
    cover = _cover(info)
    if cover is None:
        base = Image.new("RGB", (width, height), (24, 22, 40))
        ImageDraw.Draw(base).rectangle([0, height // 2, width, height], fill=(36, 24, 56))
        return base.filter(ImageFilter.GaussianBlur(60))
    small = ImageOps.fit(cover, (max(1, width // 10), max(1, height // 10))).filter(ImageFilter.GaussianBlur(3))
    blurred = small.resize((width, height), Image.BILINEAR)
    return Image.blend(blurred, Image.new("RGB", (width, height), (0, 0, 0)), 0.55)


def _cover(info):
    path = (info or {}).get("cover")
    if not path or not Path(path).is_file():
        return None
    try:
        with Image.open(path) as image:
            return image.convert("RGB")
    except OSError:
        return None


def _fit_text(draw, text, font_name, size, max_width, min_size=14):
    font = _font(font_name, size)
    while size > min_size and draw.textlength(text, font=font) > max_width:
        size = int(size * 0.92)
        font = _font(font_name, size)
    return font


def _wrap(draw, text, font, max_width, max_lines=2):
    words, lines, line = text.split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines[:max_lines]


def _progress(draw, x, y, width, t, duration, height):
    if t is None or not duration:
        return
    ratio = max(0.0, min(1.0, t / duration))
    bar = max(4, int(height * 0.006))
    draw.rounded_rectangle([x, y, x + width, y + bar], radius=bar // 2, fill=(110, 110, 125, 255))
    draw.rounded_rectangle([x, y, x + max(bar, int(width * ratio)), y + bar], radius=bar // 2, fill=(245, 245, 250, 255))
    small = _font(SANS, int(height * 0.022))
    for value, anchor, px in ((t, "la", x), (duration, "ra", x + width)):
        draw.text((px, y + bar * 3), f"{int(value // 60)}:{int(value % 60):02d}", font=small, fill=(220, 220, 230), anchor=anchor)


def frame(bg, info, width, height, mode="jukebox", lines=None, t=None):
    """Image complète de l'écran (Pillow, RGB)."""
    image = bg.copy().convert("RGBA")
    draw = ImageDraw.Draw(image)
    cover = _cover(info)
    title, artist = (info or {}).get("title", ""), (info or {}).get("artist", "")
    duration = ((info or {}).get("duration_ms") or 0) / 1000
    if mode == "karaoke" and lines:
        return _karaoke(image, draw, cover, title, artist, lines, t, width, height)
    size = int(height * 0.58)
    x0, y0 = int(width * 0.08), (height - size) // 2
    if cover is not None:
        art = ImageOps.fit(cover, (size, size))
        shadow = Image.new("RGBA", (size + 60, size + 60), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rectangle([30, 36, size + 30, size + 36], fill=(0, 0, 0, 140))
        image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)), (x0 - 30, y0 - 30))
        image.paste(art, (x0, y0))
    else:
        draw.rounded_rectangle([x0, y0, x0 + size, y0 + size], radius=size // 12, fill=(255, 255, 255, 30))
        draw.text((x0 + size / 2, y0 + size / 2), "♪", font=_font(SANS_BOLD, size // 2), fill=(255, 255, 255, 160), anchor="mm")
    tx = x0 + size + int(width * 0.05)
    text_width = width - tx - int(width * 0.06)
    title_font = _fit_text(draw, title, SANS_BOLD, int(height * 0.075), text_width * 2)
    y = y0 + size * 0.22
    for line in _wrap(draw, title, title_font, text_width):
        draw.text((tx, y), line, font=title_font, fill=(255, 255, 255))
        y += title_font.size * 1.15
    if artist:
        draw.text((tx, y + height * 0.015), artist, font=_fit_text(draw, artist, SANS, int(height * 0.045), text_width), fill=(215, 215, 230))
    _progress(draw, tx, y0 + size - int(height * 0.06), text_width, t, duration, height)
    return image.convert("RGB")


def _karaoke(image, draw, cover, title, artist, lines, t, width, height):
    from utils.lyrics import line_index
    margin = int(height * 0.05)
    thumb = int(height * 0.13)
    if cover is not None:
        image.paste(ImageOps.fit(cover, (thumb, thumb)), (margin, margin))
    head = _font(SANS_BOLD, int(height * 0.035))
    draw.text((margin + thumb + margin // 2, margin + thumb * 0.2), title, font=head, fill=(255, 255, 255))
    draw.text((margin + thumb + margin // 2, margin + thumb * 0.62), artist, font=_font(SANS, int(height * 0.028)), fill=(210, 210, 225))
    index = line_index(lines, t if t is not None else 0)
    max_width = width * 0.86
    center = height * 0.56
    for offset, (size, color) in {-1: (0.045, (170, 170, 190)), 0: (0.075, (255, 230, 120)), 1: (0.045, (200, 200, 215)),
                                  2: (0.04, (150, 150, 170))}.items():
        i = index + offset
        if i < 0 or i >= len(lines):
            continue
        text = lines[i][1] or "♪"
        font = _fit_text(draw, text, SANS_BOLD, int(height * size), max_width)
        y = center + offset * height * 0.13 - (height * 0.02 if offset == 0 else 0)
        draw.text((width / 2, y), text, font=font, fill=color, anchor="mm")
    return image.convert("RGB")
