"""
Compositions à thème : Noël, Halloween, Pâques, vacances, Islande, Japon, France, montagne, mer, plage.
Décors entièrement dessinés par programme. Les thèmes de saison (Noël, Halloween, Pâques) peuvent
n'apparaître que pendant leur période, et plus souvent à ce moment-là.
"""
import math
from datetime import date, timedelta

from PIL import Image, ImageDraw, ImageFilter, ImageChops

from utils.message_renderer import N_, _font, _gradient, _textured, _vignette, render_note, _paste_with_shadow
from utils import compositions as base

MARKER, HAND, HAND2, SANS_BOLD, SERIF_BI = "PermanentMarker-Regular.ttf", "PatrickHand-Regular.ttf", "Caveat-Regular.ttf", \
    "DejaVuSans-Bold.ttf", "DejaVuSerif-BoldItalic.ttf"

_translate = lambda text: text  # remplacé par la fonction de traduction du diaporama


def set_translator(function):
    global _translate
    _translate = function


# --- Saisons ---

def easter(year):
    """Date de Pâques (algorithme de Meeus/Jones/Butcher, calendrier grégorien)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def in_season(theme, today=None):
    today = today or date.today()
    if theme == "noel":
        return (today.month == 12) or (today.month == 1 and today.day <= 6)
    if theme == "halloween":
        return (today.month == 10 and today.day >= 15) or (today.month == 11 and today.day <= 2)
    if theme == "paques":
        return abs((today - easter(today.year)).days) <= 14
    if theme == "nouvel_an":
        return (today.month == 12 and today.day >= 26) or (today.month == 1 and today.day <= 7)
    md = (today.month, today.day)
    if theme == "printemps":
        return (3, 20) <= md <= (6, 20)
    if theme == "automne":
        return (9, 22) <= md <= (12, 20)
    if theme == "hiver":
        return md >= (12, 21) or md <= (3, 19)
    return True


SEASONAL = {"noel", "halloween", "paques", "printemps", "automne", "hiver", "nouvel_an"}


# --- Outils de dessin ---

def _title(canvas, text, font_name, size, color, center, glow=None, shadow=True, max_width=None):
    if any(ord(c) > 0x2FF and c not in "–—’…«»€" for c in text):
        return  # écriture non latine (ex. japonais) : aucune police installée ne la contient, on n'affiche pas de titre
    draw = ImageDraw.Draw(canvas)
    font = _font(font_name, size)
    while max_width and draw.textlength(text, font=font) > max_width and size > 12:
        size = int(size * 0.9)
        font = _font(font_name, size)
    width = draw.textlength(text, font=font)
    x, y = center[0] - width / 2, center[1] - size * 0.6
    if glow or shadow:
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((x + (0 if glow else size * 0.05), y + (0 if glow else size * 0.06)), text, font=font,
                                   fill=(glow or (0, 0, 0)) + (200 if glow else 110,))
        canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(size * (0.18 if glow else 0.06))))
    draw.text((x, y), text, font=font, fill=color)


def _shape_mask(w, h, shape):
    """Masque d'une forme (cercle, œuf), dessiné en double résolution pour des bords lisses."""
    mask = Image.new("L", (w * 2, h * 2), 0)
    draw = ImageDraw.Draw(mask)
    if shape == "egg":
        points = []
        for i in range(120):
            t = 2 * math.pi * i / 120
            points.append((w * (1 + 0.96 * math.cos(t) * (1 + 0.14 * math.sin(t)) / 1.14), h * (1 + 0.98 * math.sin(t))))
        draw.polygon(points, fill=255)
    else:
        draw.ellipse([0, 0, w * 2 - 1, h * 2 - 1], fill=255)
    return mask.resize((w, h), Image.LANCZOS)


def _fill_shape(photo, w, h, shape):
    """
    Contenu d'une forme. En mode photos entières, la photo complète tient dans le plus grand rectangle inscrit
    dans la forme, sur un fond flou d'elle-même ; sinon elle est recadrée pour remplir la forme.
    """
    if not base.FULL_PHOTOS:
        return base.cover(photo, w, h)
    content = base.blurred_fill(photo, w, h)
    a, b = w / 2 * (0.9 if shape == "egg" else 0.97), h / 2 * (0.9 if shape == "egg" else 0.97)
    r = photo.width / photo.height
    half_h = 1 / math.sqrt((r / a) ** 2 + (1 / b) ** 2)  # rectangle de proportions r inscrit dans l'ellipse
    fitted = photo.resize((max(1, int(2 * half_h * r)), max(1, int(2 * half_h))), Image.LANCZOS)
    content.paste(fitted, ((w - fitted.width) // 2, (h - fitted.height) // 2 + (int(h * 0.04) if shape == "egg" else 0)))
    return content


def _shaped(photo, size, shape, ring=0, ring_colors=None):
    """Photo dans une forme (cercle, œuf), avec éventuellement un contour de couleur."""
    w, h = size
    inner = _fill_shape(photo, w, h, shape).convert("RGBA")
    inner.putalpha(_shape_mask(w, h, shape))
    if not ring:
        return inner
    outer = Image.new("RGBA", (w + 2 * ring, h + 2 * ring), (0, 0, 0, 0))
    outer.paste(_gradient(outer.width, outer.height, *ring_colors).convert("RGBA"), (0, 0), _shape_mask(outer.width, outer.height, shape))
    outer.alpha_composite(inner, (ring, ring))
    return outer


def _snow(canvas, count, rng, size_range=(2, 6), alpha=200):
    draw = ImageDraw.Draw(canvas)
    w, h = canvas.size
    for _ in range(count):
        r = rng.uniform(*size_range)
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, int(alpha * rng.uniform(0.4, 1))))


def _mountains(canvas, layers, rng, top=0.45, snow=False):
    w, h = canvas.size
    draw = ImageDraw.Draw(canvas)
    for i, color in enumerate(layers):
        base_y = h * (top + i * (1 - top) / (len(layers) + 1))
        peaks = [(0, h)]
        x = -w * 0.1
        while x < w * 1.1:
            peaks.append((x, base_y - rng.uniform(0.05, 0.25) * h * (1 - i * 0.15)))
            x += rng.uniform(w * 0.08, w * 0.2)
            peaks.append((x, base_y + rng.uniform(0, 0.05) * h))
            x += rng.uniform(w * 0.05, w * 0.12)
        peaks.append((w, h))
        draw.polygon(peaks, fill=color)
        if snow and i == 0:
            for j in range(1, len(peaks) - 2, 2):
                px, py = peaks[j]
                draw.polygon([(px, py), (px - w * 0.03, py + h * 0.06), (px + w * 0.03, py + h * 0.06)], fill=(240, 245, 250, 255))


def _place_row(canvas, elements, y_center, rng, spread=0.86, jitter=0.06, tilt=6):
    w, h = canvas.size
    n = len(elements)
    for i, element in enumerate(elements):
        element = base.rotated(element, rng.uniform(-tilt, tilt)) if tilt else element
        cx = w * ((1 - spread) / 2 + spread * (i + 0.5) / n)
        cy = y_center + rng.uniform(-jitter, jitter) * h
        _paste_with_shadow(canvas, element, base._inside((cx, cy), element, w, h, 0.03))


def _message_note(canvas, message, rng, kind="postit", where=(0.86, 0.78), size=0.24):
    if not message:
        return
    w, h = canvas.size
    side = int(min(w, h) * size)
    note = base.rotated(render_note(message, side, side, kind, seed=rng.random()), rng.uniform(-8, 8))
    _paste_with_shadow(canvas, note, base._inside((w * where[0], h * where[1]), note, w, h))


def _star(cx, cy, r_out, r_in, points=5, rotation=-math.pi / 2):
    pts = []
    for i in range(points * 2):
        r = r_out if i % 2 == 0 else r_in
        a = rotation + i * math.pi / points
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _photo_size(W, H, count, factor=1.0):
    return int(min(W / (count + 0.6), H * 0.55) * factor)


# --- Thèmes ---

def christmas(photos, message, W, H, rng):
    canvas = _vignette(_textured(_gradient(W, H, (16, 70, 50), (8, 36, 26)), rng, 14), 0.45).convert("RGBA")
    _snow(canvas, int(W * H / 9000), rng)
    draw = ImageDraw.Draw(canvas)
    # Guirlande lumineuse
    wire = [(x, H * 0.07 + math.sin(x / W * math.pi * 3) * H * 0.03) for x in range(0, W + 20, 20)]
    draw.line(wire, fill=(30, 30, 30), width=max(2, H // 300))
    bulbs = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(bulbs)
    for i, (x, y) in enumerate(wire[::3]):
        color = [(255, 70, 70), (255, 210, 60), (90, 200, 255), (120, 255, 120)][i % 4]
        r = H * 0.012
        bdraw.ellipse([x - r, y, x + r, y + r * 2.6], fill=color + (255,))
    canvas.alpha_composite(bulbs.filter(ImageFilter.GaussianBlur(H * 0.012)))
    canvas.alpha_composite(bulbs)
    # Sol enneigé
    ground = [(0, H)] + [(x, H * 0.9 + math.sin(x / W * 7) * H * 0.02) for x in range(0, W + 40, 40)] + [(W, H)]
    draw.polygon(ground, fill=(245, 248, 255, 255))
    # Photos en boules de Noël suspendues
    n = len(photos)
    d = min(_photo_size(W, H, n, 1.05), int(W * 0.8 / n * 0.86))
    for i, photo in enumerate(photos):
        cx = W * (0.1 + 0.8 * (i + 0.5) / n)
        cy = H * rng.uniform(0.36, 0.52)
        ball = _shaped(photo, (d, d), "circle", max(6, d // 22), ((255, 220, 120), (190, 140, 40)))
        draw.line([(cx, H * 0.08), (cx, cy - ball.height / 2)], fill=(200, 170, 90), width=max(2, H // 400))
        cap_w, cap_h = d * 0.22, d * 0.12
        draw.rectangle([cx - cap_w / 2, cy - ball.height / 2 - cap_h * 0.6, cx + cap_w / 2, cy - ball.height / 2 + cap_h * 0.4], fill=(210, 180, 90))
        _paste_with_shadow(canvas, ball, (cx, cy))
        shine = Image.new("RGBA", (d, d), (0, 0, 0, 0))
        ImageDraw.Draw(shine).ellipse([d * 0.18, d * 0.12, d * 0.42, d * 0.3], fill=(255, 255, 255, 70))
        canvas.alpha_composite(shine.filter(ImageFilter.GaussianBlur(d * 0.03)), (int(cx - d / 2), int(cy - d / 2)))
    _title(canvas, _translate(N_("Joyeux Noël")), HAND2, int(H * 0.11), (255, 225, 140), (W / 2, H * 0.8), glow=(255, 200, 80), max_width=W * 0.8)
    _message_note(canvas, message, rng, "fiche", (0.88, 0.78), 0.22)
    return canvas.convert("RGB")


def halloween(photos, message, W, H, rng):
    canvas = _vignette(_gradient(W, H, (26, 10, 46), (70, 24, 70)), 0.5).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    # Lune
    moon = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    r = H * 0.16
    mx, my = W * 0.84, H * 0.2
    ImageDraw.Draw(moon).ellipse([mx - r, my - r, mx + r, my + r], fill=(255, 240, 190, 255))
    canvas.alpha_composite(moon.filter(ImageFilter.GaussianBlur(r * 0.35)))
    canvas.alpha_composite(moon)
    # Toile d'araignée
    cx, cy, R = 0, 0, H * 0.32
    for k in range(7):
        a = k * (math.pi / 2) / 6
        draw.line([(cx, cy), (cx + R * math.cos(a), cy + R * math.sin(a))], fill=(220, 220, 230, 160), width=2)
    for ring in range(1, 6):
        rr = R * ring / 5.5
        pts = [(cx + rr * math.cos(k * (math.pi / 2) / 6), cy + rr * math.sin(k * (math.pi / 2) / 6)) for k in range(7)]
        draw.line(pts, fill=(220, 220, 230, 140), width=2)
    # Chauves-souris
    for _ in range(6):
        bx, by, s = rng.uniform(W * 0.35, W * 0.95), rng.uniform(H * 0.05, H * 0.35), rng.uniform(H * 0.025, H * 0.05)
        wing = [(bx, by), (bx - s, by - s * 0.6), (bx - s * 2, by - s * 0.2), (bx - s * 1.5, by + s * 0.1), (bx - s, by + s * 0.05),
                (bx - s * 0.5, by + s * 0.4), (bx, by + s * 0.2), (bx + s * 0.5, by + s * 0.4), (bx + s, by + s * 0.05),
                (bx + s * 1.5, by + s * 0.1), (bx + s * 2, by - s * 0.2), (bx + s, by - s * 0.6)]
        draw.polygon(wing, fill=(10, 6, 14, 255))
    # Citrouilles
    for i in range(4):
        px = W * (0.08 + i * 0.28) + rng.uniform(-W * 0.03, W * 0.03)
        pr = H * rng.uniform(0.07, 0.1)
        py = H - pr * 0.9
        glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([px - pr * 1.8, py - pr * 1.5, px + pr * 1.8, py + pr * 1.5], fill=(255, 140, 0, 90))
        canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(pr)))
        for k in (-0.55, 0.55, 0):
            draw.ellipse([px + k * pr - pr * 0.75, py - pr * 0.85, px + k * pr + pr * 0.75, py + pr * 0.85], fill=(235, 110, 20) if k else (250, 130, 30))
        draw.rectangle([px - pr * 0.08, py - pr * 1.15, px + pr * 0.08, py - pr * 0.8], fill=(70, 100, 30))
        draw.polygon(_star(px - pr * 0.35, py - pr * 0.2, pr * 0.16, pr * 0.16, 3), fill=(255, 230, 90))
        draw.polygon(_star(px + pr * 0.35, py - pr * 0.2, pr * 0.16, pr * 0.16, 3), fill=(255, 230, 90))
        draw.chord([px - pr * 0.5, py - pr * 0.3, px + pr * 0.5, py + pr * 0.5], 0, 180, fill=(255, 230, 90))
    # Photos dans des cadres sombres
    size = _photo_size(W, H, len(photos), 0.95)
    elements = [base.framed(base.framed(base.print_photo(p, size, size * 0.8), max(4, size // 40), (240, 120, 20)).convert("RGB"),
                            max(8, size // 18), (20, 14, 22)) for p in photos]
    _place_row(canvas, elements, H * 0.5, rng, 0.8, 0.05, 8)
    _title(canvas, _translate(N_("Joyeux Halloween")), MARKER, int(H * 0.085), (255, 150, 40), (W * 0.42, H * 0.12), glow=(255, 120, 0), max_width=W * 0.6)
    # Les messages flottent dans de petits fantômes (sans message : un fantôme décoratif)
    messages = [m for m in (message if isinstance(message, list) else [message]) if m][:len(GHOST_SPOTS)]
    for (gx, gy), msg in zip(GHOST_SPOTS, messages or [None]):
        ghost = base.rotated(_ghost(msg, int(H * (0.36 if msg else 0.15)), rng), rng.uniform(-7, 7))
        if not msg:
            gx, gy = DECOR_GHOST_SPOT
        _paste_glow(canvas, ghost, base._inside((W * gx, H * gy), ghost, W, H))
    return canvas.convert("RGB")


GHOST_SPOTS = [(0.87, 0.7), (0.13, 0.7), (0.09, 0.26)]  # centres (fractions de l'écran), dans l'ordre d'arrivée
DECOR_GHOST_SPOT = (0.64, 0.24)


def _ghost_text(message):
    title, body = (message.get("title") or "").strip(), (message.get("body") or "").strip()
    return (f"{title}\n{body}" if title and body else title or body), (message.get("signature") or "").strip()


def _ghost(message, height, rng):
    """Petit fantôme (RGBA) ; s'il porte un message, le texte est écrit sur son ventre."""
    width = int(height * 0.82)
    scale = 3  # dessin en grand puis réduit : contours lisses
    w, h = width * scale, height * scale
    body = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(body)
    head = w * 0.92
    left, right, top = (w - head) / 2, (w + head) / 2, h * 0.02
    draw.ellipse([left, top, right, top + head], fill=(250, 250, 255, 238))
    draw.rectangle([left, top + head / 2, right, h * 0.86], fill=(250, 250, 255, 238))
    waves = 4  # bas ondulé
    step = head / waves
    for k in range(waves):
        x0 = left + k * step
        draw.ellipse([x0, h * 0.8, x0 + step, h * 0.98 - (k % 2) * h * 0.04], fill=(250, 250, 255, 238))
    for k in range(1, waves, 2):  # creux entre les vagues
        x0 = left + k * step
        draw.ellipse([x0 + step * 0.1, h * 0.9, x0 + step * 0.9, h * 1.08], fill=(0, 0, 0, 0))
    # Yeux et bouche
    eye_y, eye_r = top + head * (0.3 if message else 0.36), head * (0.06 if message else 0.075)
    for ex in (w / 2 - head * 0.18, w / 2 + head * 0.18):
        draw.ellipse([ex - eye_r, eye_y - eye_r * 1.35, ex + eye_r, eye_y + eye_r * 1.35], fill=(30, 20, 40, 255))
        draw.ellipse([ex - eye_r * 0.35, eye_y - eye_r * 1.0, ex + eye_r * 0.15, eye_y - eye_r * 0.45], fill=(255, 255, 255, 230))
    mouth_y = top + head * (0.45 if message else 0.56)
    m = 0.045 if message else 0.06
    draw.ellipse([w / 2 - head * m, mouth_y - head * m * 0.8, w / 2 + head * m, mouth_y + head * m * 1.2], fill=(30, 20, 40, 255))
    if not message:
        for cx in (w / 2 - head * 0.3, w / 2 + head * 0.3):  # joues
            draw.ellipse([cx - head * 0.06, mouth_y - head * 0.06, cx + head * 0.06, mouth_y], fill=(255, 170, 190, 160))
    ghost = body.resize((width, height), Image.LANCZOS)
    if message:
        _ghost_write(ghost, message, rng)
    return ghost


def _ghost_write(ghost, message, rng):
    """Écrit le message sur le ventre du fantôme, en réduisant la police jusqu'à ce qu'il tienne."""
    from utils.message_renderer import _wrap
    text, signature = _ghost_text(message)
    if not text and not signature:
        return
    w, h = ghost.size
    box_w, box_top, box_bottom = w * 0.8, h * 0.47, h * 0.87
    draw = ImageDraw.Draw(ghost)
    color, sign_color = (70, 36, 100, 255), (200, 90, 20, 255)
    size = int(h * 0.12)
    while size > 9:
        font, sign_font = _font(HAND, size), _font(HAND2, max(9, int(size * 0.85)))
        lines = _wrap(draw, text, font, box_w) if text else []
        line_h = size * 1.08
        total = len(lines) * line_h + (size * 0.95 if signature else 0)
        if total <= box_bottom - box_top:
            break
        size -= 1
    else:  # trop long même en petit : on coupe
        font, sign_font = _font(HAND, 9), _font(HAND2, 9)
        lines, line_h = _wrap(draw, text, font, box_w)[:4], 10
        if lines:
            lines[-1] = lines[-1].rstrip(" .") + "…"
        total = len(lines) * line_h + (9 if signature else 0)
    y = box_top + (box_bottom - box_top - total) / 2
    for line in lines:
        draw.text((w / 2, y), line, font=font, fill=color, anchor="ma")
        y += line_h
    if signature:
        draw.text((w / 2, y + size * 0.05), f"— {signature}", font=sign_font, fill=sign_color, anchor="ma")


def _paste_glow(canvas, element, center):
    """Colle un fantôme (centré sur `center`) avec un halo bleuté plutôt qu'une ombre portée."""
    x, y = int(center[0] - element.width / 2), int(center[1] - element.height / 2)
    halo = Image.new("RGBA", element.size, (170, 200, 255, 0))
    halo.putalpha(element.getchannel("A").point(lambda a: int(a * 0.7)))
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer.paste(halo, (x, y), halo)
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(max(6, element.height // 14))))
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer.paste(element, (x, y), element)
    canvas.alpha_composite(layer)


def easter_theme(photos, message, W, H, rng):
    canvas = _textured(_gradient(W, H, (255, 246, 214), (226, 244, 220)), rng, 8).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    for _ in range(int(W / 3)):  # herbe
        x = rng.uniform(0, W)
        hgt = rng.uniform(H * 0.06, H * 0.16)
        lean = rng.uniform(-H * 0.03, H * 0.03)
        draw.polygon([(x - 6, H), (x + lean, H - hgt), (x + 6, H)], fill=(rng.randrange(90, 140), rng.randrange(170, 210), rng.randrange(70, 110)))
    colors = [((255, 182, 193), (255, 140, 170)), ((180, 220, 255), (130, 190, 250)), ((255, 230, 140), (250, 200, 80)),
              ((200, 240, 190), (150, 220, 140)), ((220, 200, 255), (180, 150, 250))]
    n = len(photos)
    ew = _photo_size(W, H, n, 0.85)
    elements = []
    for photo in photos:
        egg = _shaped(photo, (ew, int(ew * 1.3)), "egg", max(8, ew // 16), rng.choice(colors))
        d = ImageDraw.Draw(egg)
        for k in range(14):  # pois décoratifs sur la bordure
            a = 2 * math.pi * k / 14
            x = egg.width / 2 + (egg.width / 2 - ew // 32) * math.cos(a) * 0.97
            y = egg.height / 2 + (egg.height / 2 - ew // 32) * math.sin(a) * 0.98
            d.ellipse([x - ew // 60, y - ew // 60, x + ew // 60, y + ew // 60], fill=(255, 255, 255, 230))
        elements.append(egg)
    _place_row(canvas, elements, H * 0.5, rng, 0.84, 0.04, 7)
    for i in range(7):  # petits œufs dans l'herbe
        x, s = W * (i + 0.5) / 7 + rng.uniform(-30, 30), H * rng.uniform(0.04, 0.06)
        y = H - s * 1.2
        c = rng.choice(colors)
        draw.ellipse([x - s * 0.75, y - s, x + s * 0.75, y + s], fill=c[0])
        draw.line([(x - s * 0.7, y), (x + s * 0.7, y)], fill=c[1], width=max(2, int(s / 5)))
    _title(canvas, _translate(N_("Joyeuses Pâques")), HAND2, int(H * 0.1), (150, 80, 160), (W / 2, H * 0.12), shadow=False, max_width=W * 0.8)
    _message_note(canvas, message, rng, "postit", (0.88, 0.2), 0.2)
    return canvas.convert("RGB")


def holidays(photos, message, W, H, rng):
    canvas = base.texture("kraft", W, H).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    band = max(14, H // 40)  # bordure « par avion »
    for x in range(-H, W + H, band * 2):
        color = (200, 40, 50) if (x // (band * 2)) % 2 else (30, 70, 160)
        for y0, y1 in ((0, band), (H - band, H)):
            draw.polygon([(x, y0), (x + band, y0), (x + band + (y1 - y0), y1), (x + (y1 - y0), y1)], fill=color)
    for y in range(-W, H + W, band * 2):
        color = (200, 40, 50) if (y // (band * 2)) % 2 else (30, 70, 160)
        for x0, x1 in ((0, band), (W - band, W)):
            draw.polygon([(x0, y), (x0, y + band), (x1, y + band + (x1 - x0)), (x1, y + (x1 - x0))], fill=color)
    # Trajet en pointillés et avion
    path = [(W * 0.08 + t * W * 0.84, H * 0.86 - math.sin(t * math.pi) * H * 0.12) for t in [i / 60 for i in range(61)]]
    for i in range(0, len(path) - 1, 2):
        draw.line([path[i], path[i + 1]], fill=(60, 50, 40, 200), width=max(2, H // 300))
    px, py = path[-1]
    s = H * 0.04
    draw.polygon([(px + s, py), (px - s, py - s * 0.25), (px - s * 0.6, py), (px - s, py + s * 0.25)], fill=(40, 40, 50))
    draw.polygon([(px, py), (px - s * 0.5, py - s * 0.9), (px - s * 0.2, py), (px - s * 0.5, py + s * 0.9)], fill=(40, 40, 50))
    # Tampons
    for i in range(3):
        sx, sy, r = W * (0.72 + i * 0.08) + rng.uniform(-W * 0.02, W * 0.02), rng.uniform(H * 0.1, H * 0.2), H * 0.055
        stamp = Image.new("RGBA", (int(r * 3), int(r * 3)), (0, 0, 0, 0))
        sd = ImageDraw.Draw(stamp)
        color = rng.choice([(150, 40, 40, 150), (40, 60, 140, 150), (40, 110, 60, 150)])
        sd.ellipse([r * 0.2, r * 0.2, r * 2.8, r * 2.8], outline=color, width=max(3, int(r / 10)))
        sd.ellipse([r * 0.5, r * 0.5, r * 2.5, r * 2.5], outline=color, width=max(2, int(r / 16)))
        for k in range(4):
            sd.line([(r * 0.4, r * (1.1 + k * 0.25)), (r * 2.6, r * (1.1 + k * 0.25))], fill=color, width=max(2, int(r / 18)))
        canvas.alpha_composite(base.rotated(stamp, rng.uniform(-30, 30)), (int(sx - r * 1.5), int(sy - r * 1.5)))
    size = _photo_size(W, H, len(photos), 0.95)
    elements = [base.framed(base.print_photo(p, size, size * 0.8), max(8, size // 20), (252, 250, 244), bottom=max(8, size // 20) * 3) for p in photos]
    _place_row(canvas, elements, H * 0.5, rng, 0.84, 0.05, 9)
    _title(canvas, _translate(N_("Bonnes vacances !")), MARKER, int(H * 0.08), (40, 70, 150), (W * 0.38, H * 0.13), shadow=False, max_width=W * 0.6)
    _message_note(canvas, message, rng, "postit", (0.86, 0.8), 0.2)
    return canvas.convert("RGB")


def iceland(photos, message, W, H, rng):
    canvas = _gradient(W, H, (6, 12, 34), (14, 34, 60)).convert("RGBA")
    _snow(canvas, int(W * H / 4000), rng, (0.6, 1.8), 230)  # étoiles
    aurora = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    adraw = ImageDraw.Draw(aurora)
    for k, color in enumerate([(60, 255, 160), (40, 220, 200), (150, 90, 255)]):
        phase, amp, base_y = rng.uniform(0, 6), H * rng.uniform(0.05, 0.1), H * (0.22 + k * 0.08)
        pts = [(x, base_y + math.sin(x / W * 5 + phase) * amp) for x in range(0, W + 30, 30)]
        for t in range(0, int(H * 0.18), 6):  # rideau vertical qui s'estompe
            adraw.line([(x, y + t) for x, y in pts], fill=color + (int(190 * (1 - t / (H * 0.18))),), width=6)
    canvas.alpha_composite(aurora.filter(ImageFilter.GaussianBlur(H * 0.03)))
    _mountains(canvas, [(52, 66, 96, 255), (26, 34, 56, 255)], rng, 0.6, snow=True)
    size = _photo_size(W, H, len(photos), 0.9)
    elements = [base.framed(base.print_photo(p, size, size * 0.75), max(8, size // 22), (250, 252, 255)) for p in photos]
    _place_row(canvas, elements, H * 0.55, rng, 0.84, 0.03, 3)
    _title(canvas, _translate(N_("Islande")), "DejaVuSans-ExtraLight.ttf", int(H * 0.09), (230, 255, 245), (W / 2, H * 0.12), glow=(80, 255, 180), max_width=W * 0.6)
    _message_note(canvas, message, rng, "fiche", (0.88, 0.85), 0.18)
    return canvas.convert("RGB")


def japan(photos, message, W, H, rng):
    canvas = _textured(_gradient(W, H, (246, 238, 222), (236, 224, 202)), rng, 14).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    r = H * 0.22
    draw.ellipse([W * 0.12 - r, H * 0.3 - r, W * 0.12 + r, H * 0.3 + r], fill=(200, 40, 50))
    # Vagues seigaiha en bas
    rr = H * 0.06
    for row in range(4):
        y = H - row * rr * 0.5
        for col in range(-1, int(W / rr) + 2):
            x = col * rr + (row % 2) * rr / 2
            for k, c in enumerate([(40, 70, 130), (246, 238, 222), (40, 70, 130), (246, 238, 222)]):
                rk = rr * (1 - k * 0.22) / 1.0
                draw.pieslice([x - rk, y - rk, x + rk, y + rk], 180, 360, fill=c)
    # Branche de cerisier
    branch = [(W, H * 0.02), (W * 0.82, H * 0.1), (W * 0.7, H * 0.08), (W * 0.6, H * 0.16)]
    draw.line(branch, fill=(70, 46, 36), width=max(6, H // 90), joint="curve")
    draw.line([(W * 0.82, H * 0.1), (W * 0.78, H * 0.22)], fill=(70, 46, 36), width=max(4, H // 140))
    for _ in range(26):
        bx, by = rng.uniform(W * 0.58, W), rng.uniform(H * 0.0, H * 0.26)
        s = H * rng.uniform(0.012, 0.022)
        for k in range(5):
            a = k * 2 * math.pi / 5
            draw.ellipse([bx + math.cos(a) * s - s * 0.8, by + math.sin(a) * s - s * 0.8, bx + math.cos(a) * s + s * 0.8, by + math.sin(a) * s + s * 0.8],
                         fill=(255, rng.randrange(170, 200), rng.randrange(195, 215)))
        draw.ellipse([bx - s * 0.35, by - s * 0.35, bx + s * 0.35, by + s * 0.35], fill=(230, 90, 120))
    size = _photo_size(W, H, len(photos), 0.9)
    elements = [base.framed(base.framed(base.print_photo(p, size * 0.8, size), max(6, size // 26), (252, 250, 245)).convert("RGB"),
                            max(3, size // 80), (30, 30, 30)) for p in photos]
    _place_row(canvas, elements, H * 0.52, rng, 0.8, 0.02, 0)
    _title(canvas, _translate(N_("Japon")), SERIF_BI, int(H * 0.075), (60, 40, 40), (W * 0.5, H * 0.1), shadow=False)
    _message_note(canvas, message, rng, "fiche", (0.1, 0.78), 0.2)
    return canvas.convert("RGB")


def france(photos, message, W, H, rng):
    canvas = Image.new("RGB", (W, H), (250, 247, 240))
    draw = ImageDraw.Draw(canvas)
    for y in range(0, H, max(20, H // 22)):  # marinière discrète
        draw.rectangle([0, y, W, y + max(6, H // 90)], fill=(226, 232, 245))
    canvas = canvas.convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    for row, sag in enumerate((0.08, 0.15)):  # deux guirlandes de fanions
        pts = [(x, H * (0.02 + row * 0.03) + math.sin(x / W * math.pi) * H * sag) for x in range(0, W + 1, 10)]
        draw.line(pts, fill=(80, 80, 80), width=2)
        flag = W // 28
        for i, x in enumerate(range(flag // 2 + row * flag // 2, W, int(flag * 1.4))):
            y = H * (0.02 + row * 0.03) + math.sin(x / W * math.pi) * H * sag
            color = [(0, 85, 164), (255, 255, 255), (239, 65, 53)][i % 3]
            draw.polygon([(x - flag / 2, y), (x + flag / 2, y), (x, y + flag * 1.1)], fill=color, outline=(200, 200, 200))
    # Tour Eiffel (silhouette)
    tx, base_y, th = W * 0.9, H * 0.98, H * 0.6
    color = (60, 60, 75)
    draw.polygon([(tx - th * 0.22, base_y), (tx - th * 0.03, base_y - th * 0.95), (tx, base_y - th), (tx + th * 0.03, base_y - th * 0.95),
                  (tx + th * 0.22, base_y), (tx + th * 0.13, base_y), (tx, base_y - th * 0.2), (tx - th * 0.13, base_y)], fill=color)
    for f in (0.3, 0.55):
        wl = th * 0.22 * (1 - f) + th * 0.05
        draw.rectangle([tx - wl, base_y - th * f - th * 0.015, tx + wl, base_y - th * f + th * 0.01], fill=color)
    size = _photo_size(W, H, len(photos), 0.9)
    elements = []
    for p in photos:
        card = base.framed(base.print_photo(p, size, size * 0.72), max(8, size // 22), (255, 255, 255))
        cd = ImageDraw.Draw(card)
        sw = size * 0.16  # timbre
        sx, sy = card.width - sw * 1.15, sw * 0.15
        cd.rectangle([sx, sy, sx + sw, sy + sw * 1.2], fill=(255, 255, 255), outline=(200, 40, 50), width=max(2, int(sw / 14)))
        cd.rectangle([sx + sw * 0.15, sy + sw * 0.15, sx + sw * 0.85, sy + sw * 1.05], fill=(0, 85, 164))
        elements.append(card)
    _place_row(canvas, elements, H * 0.55, rng, 0.76, 0.05, 6)
    _title(canvas, _translate(N_("Vive la France")), HAND2, int(H * 0.1), (0, 60, 140), (W * 0.42, H * 0.3), shadow=False, max_width=W * 0.6)
    _message_note(canvas, message, rng, "postit", (0.1, 0.84), 0.2)
    return canvas.convert("RGB")


def mountain(photos, message, W, H, rng):
    canvas = _gradient(W, H, (255, 178, 120), (120, 150, 220)).convert("RGBA")
    sun = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    r = H * 0.1
    ImageDraw.Draw(sun).ellipse([W * 0.7 - r, H * 0.28 - r, W * 0.7 + r, H * 0.28 + r], fill=(255, 236, 200, 255))
    canvas.alpha_composite(sun.filter(ImageFilter.GaussianBlur(r * 0.4)))
    _mountains(canvas, [(150, 130, 190, 255), (100, 90, 150, 255), (60, 60, 100, 255)], rng, 0.38, snow=True)
    draw = ImageDraw.Draw(canvas)
    for _ in range(26):  # sapins
        x, s = rng.uniform(0, W), H * rng.uniform(0.06, 0.12)
        y = H - rng.uniform(0, H * 0.06)
        for k in range(3):
            draw.polygon([(x, y - s * (1 - k * 0.25)), (x - s * 0.35 * (1 + k * 0.2), y - s * 0.3 * k), (x + s * 0.35 * (1 + k * 0.2), y - s * 0.3 * k)],
                         fill=(24, 50, 40))
    size = _photo_size(W, H, len(photos), 0.9)
    elements = [base.framed(base.print_photo(p, size, size), max(8, size // 20), (250, 250, 246), bottom=max(8, size // 20) * 4) for p in photos]
    _place_row(canvas, elements, H * 0.52, rng, 0.82, 0.04, 8)
    _title(canvas, _translate(N_("La montagne")), MARKER, int(H * 0.08), (255, 255, 255), (W / 2, H * 0.1), max_width=W * 0.6)
    _message_note(canvas, message, rng, "fiche", (0.88, 0.84), 0.18)
    return canvas.convert("RGB")


def sea(photos, message, W, H, rng):
    canvas = _gradient(W, H, (14, 90, 150), (2, 24, 56)).convert("RGBA")
    rays = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    rd = ImageDraw.Draw(rays)
    for _ in range(7):  # rayons de lumière
        x = rng.uniform(0, W)
        rd.polygon([(x - W * 0.02, 0), (x + W * 0.02, 0), (x + W * 0.12, H), (x - W * 0.02, H)], fill=(180, 230, 255, 40))
    canvas.alpha_composite(rays.filter(ImageFilter.GaussianBlur(W * 0.01)))
    draw = ImageDraw.Draw(canvas)
    for _ in range(40):  # bulles
        x, y, r = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(H * 0.004, H * 0.015)
        draw.ellipse([x - r, y - r, x + r, y + r], outline=(200, 240, 255, 160), width=2)
    n = len(photos)
    d = min(_photo_size(W, H, n, 0.95), int(W * 0.84 / n * 0.8))
    elements = []
    for photo in photos:  # hublots en laiton
        hub = _shaped(photo, (d, d), "circle", max(10, d // 12), ((240, 200, 110), (150, 100, 40)))
        hd = ImageDraw.Draw(hub)
        c, R = hub.width / 2, hub.width / 2 - max(10, d // 12) / 2
        for k in range(8):
            a = k * math.pi / 4
            bx, by = c + R * math.cos(a), c + R * math.sin(a)
            br = max(3, d // 60)
            hd.ellipse([bx - br, by - br, bx + br, by + br], fill=(110, 80, 40, 255))
        elements.append(hub)
    _place_row(canvas, elements, H * 0.52, rng, 0.84, 0.08, 0)
    _title(canvas, _translate(N_("La mer")), HAND2, int(H * 0.11), (220, 245, 255), (W / 2, H * 0.12), glow=(120, 200, 255))
    _message_note(canvas, message, rng, "fiche", (0.88, 0.85), 0.18)
    return canvas.convert("RGB")


def beach(photos, message, W, H, rng):
    horizon = H * 0.3
    canvas = _gradient(W, H, (120, 200, 245), (210, 240, 255)).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, horizon, W, H * 0.42], fill=(30, 130, 190))
    sand = _textured(_gradient(W, int(H * 0.62), (240, 214, 160), (226, 192, 130)), rng, 22).convert("RGBA")
    wave = Image.new("L", sand.size, 255)
    ImageDraw.Draw(wave).polygon([(0, 0)] + [(x, H * 0.03 + math.sin(x / W * 9) * H * 0.012) for x in range(0, W + 20, 20)] + [(W, 0)], fill=0)
    canvas.paste(sand, (0, int(H * 0.38)), wave)
    r = H * 0.08
    draw.ellipse([W * 0.85 - r, H * 0.12 - r, W * 0.85 + r, H * 0.12 + r], fill=(255, 230, 120))
    for _ in range(5):  # étoiles de mer et coquillages
        x, y, s = rng.uniform(W * 0.05, W * 0.95), rng.uniform(H * 0.82, H * 0.95), H * rng.uniform(0.025, 0.04)
        if rng.random() < 0.5:
            draw.polygon(_star(x, y, s, s * 0.45, 5, rng.uniform(0, 1)), fill=(240, 130, 80))
        else:
            draw.pieslice([x - s, y - s, x + s, y + s], 200, 340, fill=(250, 220, 210))
            for k in range(5):
                a = math.radians(205 + k * 32)
                draw.line([(x, y), (x + s * math.cos(a), y + s * math.sin(a))], fill=(220, 170, 160), width=2)
    size = _photo_size(W, H, len(photos), 0.92)
    elements = [base.framed(base.print_photo(p, size, size), max(8, size // 20), (252, 252, 248), bottom=max(8, size // 20) * 4) for p in photos]
    _place_row(canvas, elements, H * 0.6, rng, 0.82, 0.05, 12)
    _title(canvas, _translate(N_("Vive la plage !")), MARKER, int(H * 0.075), (255, 255, 255), (W * 0.42, H * 0.12), max_width=W * 0.6)
    _message_note(canvas, message, rng, "postit", (0.88, 0.25), 0.18)
    return canvas.convert("RGB")


# clé : (libellé, photos min, max, accepte un message, fonction)
THEMES = {
    "noel": (N_("Noël"), 3, 4, True, christmas),
    "halloween": (N_("Halloween"), 3, 3, True, halloween),
    "paques": (N_("Pâques"), 3, 4, True, easter_theme),
    "vacances": (N_("Vacances"), 3, 4, True, holidays),
    "islande": (N_("Islande"), 3, 4, True, iceland),
    "japon": (N_("Japon"), 3, 4, True, japan),
    "france": (N_("France"), 3, 3, True, france),
    "montagne": (N_("Montagne"), 3, 4, True, mountain),
    "mer": (N_("Mer"), 3, 4, True, sea),
    "plage": (N_("Plage"), 3, 4, True, beach),
}
