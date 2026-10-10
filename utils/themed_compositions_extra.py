"""
Compositions à thème, suite : Hokusai, mont Fuji, espace, années 80, années 70, printemps, automne, hiver,
anniversaire, cinéma, bande dessinée, carnet de voyage, album ancien, nouvel an.
"""
import math
from datetime import date

from PIL import Image, ImageDraw, ImageFilter

from utils.message_renderer import N_, _font, _gradient, _textured, _vignette, _paste_with_shadow
from utils import compositions as base
from utils.themed_compositions import (_title, _shaped, _place_row, _message_note, _snow, _mountains, _star, _photo_size,
                                       MARKER, HAND, HAND2, SERIF_BI)
import utils.themed_compositions as themed

INDIGO, INDIGO_MID, INDIGO_LIGHT, FOAM = (24, 48, 96), (52, 92, 140), (150, 182, 205), (248, 244, 232)


def _t(text):
    return themed._translate(text)


def _bezier(points, steps=40):
    """Courbe de Bézier (degré quelconque) échantillonnée."""
    out = []
    for i in range(steps + 1):
        t = i / steps
        pts = list(points)
        while len(pts) > 1:
            pts = [(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t) for a, b in zip(pts, pts[1:])]
        out.append(pts[0])
    return out


def _paper(W, H, rng, top=(240, 228, 198), bottom=(226, 210, 174), grain=16):
    return _vignette(_textured(_gradient(W, H, top, bottom), rng, grain), 0.3)


def _seal(canvas, x, y, size, text="P"):
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle([x, y, x + size, y + size], radius=size // 8, fill=(190, 40, 40, 235))
    font = _font(SERIF_BI, int(size * 0.62))
    w = draw.textlength(text, font=font)
    draw.text((x + (size - w) / 2, y + size * 0.12), text, font=font, fill=(250, 235, 225))


def _ukiyoe_print(photo, size, rng):
    """Photo en estampe : passe-partout beige et fin liseré indigo."""
    inner = base.framed(base.print_photo(photo, size * 0.78, size), max(4, size // 50), INDIGO).convert("RGB")
    return base.framed(inner, max(10, size // 16), (244, 234, 210))


def _breaking_wave(canvas, x0, base_y, width, height, rng, scale=1.0):
    """Vague déferlante stylisée : corps indigo, bandes claires, crête d'écume en « griffes »."""
    draw = ImageDraw.Draw(canvas)
    crest = (x0 + width * 0.55, base_y - height)
    tip = (x0 + width * 0.95, base_y - height * 0.62)
    outer = _bezier([(x0, base_y), (x0 + width * 0.05, base_y - height * 0.9), (crest[0] - width * 0.1, crest[1]), crest])
    curl = _bezier([crest, (crest[0] + width * 0.3, crest[1] - height * 0.05), (tip[0] + width * 0.05, tip[1] - height * 0.2), tip])
    inner = _bezier([tip, (crest[0] + width * 0.12, crest[1] + height * 0.35), (x0 + width * 0.5, base_y - height * 0.1), (x0 + width * 0.65, base_y)])
    body = outer + curl + inner
    draw.polygon(body, fill=INDIGO)
    for k, color in enumerate([INDIGO_MID, INDIGO_LIGHT]):  # bandes plus claires à l'intérieur
        shrink = 0.18 + k * 0.16
        band = _bezier([(x0 + width * (0.1 + shrink), base_y), (x0 + width * (0.12 + shrink), base_y - height * (0.75 - shrink)),
                        (crest[0] - width * 0.05, crest[1] + height * (0.15 + shrink)), (crest[0] + width * 0.18, crest[1] + height * (0.18 + shrink))])
        draw.line(band, fill=color, width=max(4, int(height * 0.035 * scale)))
    # Écume : petites griffes blanches le long de la crête
    for i, (x, y) in enumerate(curl[::2] + outer[-12::3]):
        r = max(3, height * rng.uniform(0.025, 0.045) * scale)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=FOAM)
        for f in range(3):
            a = math.radians(200 + f * 40 + rng.uniform(-10, 10))
            draw.polygon([(x, y), (x + r * 2.2 * math.cos(a) - r * 0.4, y + r * 2.2 * math.sin(a)), (x + r * 2.2 * math.cos(a) + r * 0.4, y + r * 2.2 * math.sin(a))], fill=FOAM)
    for _ in range(25):  # embruns
        x, y = rng.uniform(crest[0] - width * 0.1, tip[0] + width * 0.1), rng.uniform(crest[1] - height * 0.15, tip[1])
        r = max(2, height * 0.012)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=FOAM)


def hokusai(photos, message, W, H, rng):
    canvas = _paper(W, H, rng).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    # Petit Fuji à l'horizon
    fx, fy, fw = W * 0.62, H * 0.86, H * 0.28
    draw.polygon([(fx - fw, fy), (fx - fw * 0.12, fy - fw * 0.55), (fx + fw * 0.12, fy - fw * 0.55), (fx + fw, fy)], fill=INDIGO)
    draw.polygon([(fx - fw * 0.3, fy - fw * 0.38), (fx - fw * 0.12, fy - fw * 0.55), (fx + fw * 0.12, fy - fw * 0.55), (fx + fw * 0.3, fy - fw * 0.38),
                  (fx + fw * 0.15, fy - fw * 0.42), (fx, fy - fw * 0.36), (fx - fw * 0.15, fy - fw * 0.43)], fill=FOAM)
    # Mer et vagues
    draw.rectangle([0, H * 0.86, W, H], fill=INDIGO_MID)
    _breaking_wave(canvas, -W * 0.08, H * 1.02, W * 0.62, H * 0.82, rng, 1.0)
    _breaking_wave(canvas, W * 0.42, H * 1.02, W * 0.3, H * 0.3, rng, 0.6)
    # Cartouche de titre et sceau
    title = _t(N_("La Grande Vague"))
    font = _font(SERIF_BI, int(H * 0.04))
    tw = draw.textlength(title, font=font)
    bx, by = W * 0.06, H * 0.05
    draw.rectangle([bx, by, bx + tw + H * 0.04, by + H * 0.08], fill=(236, 222, 186), outline=INDIGO, width=max(2, H // 300))
    draw.text((bx + H * 0.02, by + H * 0.015), title, font=font, fill=INDIGO)
    _seal(canvas, int(bx + tw + H * 0.06), int(by), int(H * 0.08), "H")
    # Photos en estampes dans la partie calme
    size = int(min(H * 0.36, W * 0.4 / len(photos) * 1.1))
    elements = [_ukiyoe_print(p, size, rng) for p in photos]
    for i, element in enumerate(elements):
        cx = W * (0.6 + 0.36 * (i + 0.5) / len(elements))
        cy = H * (0.34 + (i % 2) * 0.2)
        _paste_with_shadow(canvas, element, base._inside((cx, cy), element, W, H, 0.03))
    _message_note(canvas, message, rng, "fiche", (0.9, 0.9), 0.16)
    return canvas.convert("RGB")


def fuji(photos, message, W, H, rng):
    canvas = _gradient(W, H, (250, 170, 120), (120, 90, 160)).convert("RGBA")
    sun = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    r = H * 0.13
    ImageDraw.Draw(sun).ellipse([W * 0.5 - r, H * 0.2 - r, W * 0.5 + r, H * 0.2 + r], fill=(255, 220, 170, 255))
    canvas.alpha_composite(sun.filter(ImageFilter.GaussianBlur(r * 0.25)))
    draw = ImageDraw.Draw(canvas)
    # Mont Fuji : flancs concaves, sommet aplati, calotte de neige dentelée
    cx, base_y, half = W * 0.5, H * 0.62, W * 0.42
    left = _bezier([(cx - half, base_y), (cx - half * 0.35, base_y - H * 0.08), (cx - half * 0.15, base_y - H * 0.36), (cx - half * 0.08, base_y - H * 0.42)])
    right = _bezier([(cx + half * 0.08, base_y - H * 0.42), (cx + half * 0.15, base_y - H * 0.36), (cx + half * 0.35, base_y - H * 0.08), (cx + half, base_y)])
    mountain = left + right
    draw.polygon(mountain, fill=(70, 70, 130))
    snow_line = base_y - H * 0.27
    cap = [p for p in left if p[1] <= snow_line]
    cap += [p for p in right if p[1] <= snow_line]
    jag = []
    for i in range(9):
        t = i / 8
        x = cap[-1][0] + (cap[0][0] - cap[-1][0]) * t
        jag.append((x, snow_line + (H * 0.04 if i % 2 else 0)))
    draw.polygon(cap + jag, fill=(250, 250, 255))
    # Lac et reflet
    draw.rectangle([0, base_y, W, H], fill=(70, 80, 140))
    reflection = canvas.crop((0, int(base_y - H * 0.42), W, int(base_y))).transpose(Image.FLIP_TOP_BOTTOM)
    reflection.putalpha(90)
    canvas.alpha_composite(reflection, (0, int(base_y)))
    for k in range(18):  # ondulations
        y = base_y + H * 0.02 + k * H * 0.02
        x = rng.uniform(0, W * 0.8)
        draw.line([(x, y), (x + rng.uniform(W * 0.05, W * 0.2), y)], fill=(200, 210, 240, 120), width=2)
    # Torii au premier plan
    tx, ty, tw = W * 0.12, H * 0.98, H * 0.42
    red = (200, 40, 40)
    draw.rectangle([tx - tw * 0.32, ty - tw, tx - tw * 0.24, ty], fill=red)
    draw.rectangle([tx + tw * 0.24, ty - tw, tx + tw * 0.32, ty], fill=red)
    draw.rectangle([tx - tw * 0.42, ty - tw * 0.82, tx + tw * 0.42, ty - tw * 0.76], fill=red)
    draw.polygon([(tx - tw * 0.55, ty - tw * 1.02), (tx + tw * 0.55, ty - tw * 1.02), (tx + tw * 0.48, ty - tw * 0.92), (tx - tw * 0.48, ty - tw * 0.92)], fill=(30, 20, 20))
    size = int(min(H * 0.34, W * 0.6 / len(photos)))
    elements = [base.framed(base.print_photo(p, size, size * 0.75), max(8, size // 22), (252, 248, 240)) for p in photos]
    for i, element in enumerate(elements):
        x = W * (0.3 + 0.62 * (i + 0.5) / len(elements))
        _paste_with_shadow(canvas, base.rotated(element, rng.uniform(-4, 4)), base._inside((x, H * 0.78), element, W, H))
    _title(canvas, _t(N_("Mont Fuji")), SERIF_BI, int(H * 0.07), (255, 245, 235), (W * 0.5, H * 0.07), glow=(255, 160, 100))
    _message_note(canvas, message, rng, "fiche", (0.9, 0.3), 0.16)
    return canvas.convert("RGB")


def space(photos, message, W, H, rng):
    canvas = Image.new("RGBA", (W, H), (6, 4, 18, 255))
    nebula = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    nd = ImageDraw.Draw(nebula)
    for _ in range(10):
        r = rng.uniform(H * 0.15, H * 0.4)
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        nd.ellipse([x - r, y - r * 0.6, x + r, y + r * 0.6], fill=rng.choice([(120, 40, 160, 90), (30, 90, 200, 90), (200, 60, 120, 70)]))
    canvas.alpha_composite(nebula.filter(ImageFilter.GaussianBlur(H * 0.08)))
    _snow(canvas, int(W * H / 2500), rng, (0.5, 2), 255)
    draw = ImageDraw.Draw(canvas)
    px, py, pr = W * 0.88, H * 0.18, H * 0.09  # planète à anneaux
    draw.ellipse([px - pr * 2.2, py - pr * 0.5, px + pr * 2.2, py + pr * 0.5], outline=(230, 200, 150, 200), width=max(3, int(pr / 10)))
    draw.ellipse([px - pr, py - pr, px + pr, py + pr], fill=(220, 170, 110))
    draw.arc([px - pr * 2.2, py - pr * 0.5, px + pr * 2.2, py + pr * 0.5], 0, 180, fill=(240, 210, 160), width=max(3, int(pr / 10)))
    n = len(photos)
    d = min(_photo_size(W, H, n, 0.95), int(W * 0.8 / n * 0.85))
    elements = []
    for p in photos:
        planet = _shaped(p, (d, d), "circle", max(4, d // 40), ((140, 220, 255), (90, 120, 255)))
        halo = Image.new("RGBA", (planet.width + d // 3, planet.height + d // 3), (0, 0, 0, 0))
        ImageDraw.Draw(halo).ellipse([d // 6 - 4, d // 6 - 4, halo.width - d // 6 + 4, halo.height - d // 6 + 4], fill=(120, 200, 255, 140))
        halo = halo.filter(ImageFilter.GaussianBlur(d // 14))
        halo.alpha_composite(planet, (d // 6, d // 6))
        elements.append(halo)
    _place_row(canvas, elements, H * 0.55, rng, 0.82, 0.12, 0)
    _title(canvas, _t(N_("Dans les étoiles")), "DejaVuSans-ExtraLight.ttf", int(H * 0.08), (230, 240, 255), (W * 0.4, H * 0.1), glow=(120, 160, 255))
    _message_note(canvas, message, rng, "fiche", (0.1, 0.85), 0.16)
    return canvas.convert("RGB")


def synthwave(photos, message, W, H, rng):
    horizon = H * 0.58
    canvas = _gradient(W, H, (40, 10, 70), (240, 70, 150)).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    r = H * 0.24  # soleil rayé
    sun = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sun)
    sd.ellipse([W / 2 - r, horizon - r * 1.4, W / 2 + r, horizon + r * 0.6], fill=(255, 210, 90, 255))
    for k in range(6):
        y = horizon - r * 0.1 - k * r * 0.18
        sd.rectangle([0, y, W, y + r * 0.04 * (6 - k) / 2], fill=(0, 0, 0, 0))
    canvas.alpha_composite(sun)
    draw.rectangle([0, horizon, W, H], fill=(18, 6, 34))
    for k in range(1, 18):  # sol quadrillé en perspective
        y = horizon + (H - horizon) * (k / 17) ** 2
        draw.line([(0, y), (W, y)], fill=(255, 60, 200), width=2)
    for k in range(-20, 21):
        draw.line([(W / 2 + k * W * 0.02, horizon), (W / 2 + k * W * 0.25, H)], fill=(255, 60, 200), width=2)
    size = _photo_size(W, H, len(photos), 0.9)
    elements = []
    for p in photos:
        photo = base.framed(base.print_photo(p, size, size * 0.75), max(4, size // 50), (60, 240, 255))
        glow = Image.new("RGBA", (photo.width + size // 5, photo.height + size // 5), (0, 0, 0, 0))
        ImageDraw.Draw(glow).rectangle([size // 10, size // 10, glow.width - size // 10, glow.height - size // 10], fill=(60, 240, 255, 180))
        glow = glow.filter(ImageFilter.GaussianBlur(size // 20))
        glow.alpha_composite(photo, (size // 10, size // 10))
        elements.append(glow)
    _place_row(canvas, elements, H * 0.5, rng, 0.84, 0.03, 0)
    _title(canvas, _t(N_("Années 80")), MARKER, int(H * 0.09), (255, 120, 230), (W / 2, H * 0.11), glow=(255, 40, 200))
    _message_note(canvas, message, rng, "postit", (0.9, 0.85), 0.16)
    return canvas.convert("RGB")


def seventies(photos, message, W, H, rng):
    canvas = Image.new("RGB", (W, H), (245, 225, 180))
    draw = ImageDraw.Draw(canvas)
    colors = [(214, 110, 40), (240, 170, 50), (150, 70, 30), (245, 225, 180)]
    cx, cy = W / 2, H * 1.1
    for k in range(36):  # rayons de soleil
        a0, a1 = math.pi + k * math.pi / 36, math.pi + (k + 1) * math.pi / 36
        R = W * 1.2
        draw.polygon([(cx, cy), (cx + R * math.cos(a0), cy + R * math.sin(a0)), (cx + R * math.cos(a1), cy + R * math.sin(a1))], fill=colors[k % 4])
    canvas = _textured(canvas, rng, 12).convert("RGBA")
    size = _photo_size(W, H, len(photos), 0.95)
    elements = []
    for p in photos:
        photo = base.print_photo(p, size, size).convert("RGBA")
        mask = Image.new("L", photo.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, photo.width - 1, photo.height - 1], radius=size // 7, fill=255)
        photo.putalpha(mask)
        card = Image.new("RGBA", (photo.width + size // 8, photo.height + size // 8), (0, 0, 0, 0))
        ImageDraw.Draw(card).rounded_rectangle([0, 0, card.width - 1, card.height - 1], radius=size // 6, fill=(255, 246, 225, 255))
        card.alpha_composite(photo, (size // 16, size // 16))
        elements.append(card)
    _place_row(canvas, elements, H * 0.48, rng, 0.84, 0.05, 5)
    _title(canvas, _t(N_("Années 70")), SERIF_BI, int(H * 0.09), (110, 50, 20), (W / 2, H * 0.11), glow=(255, 246, 225))
    _message_note(canvas, message, rng, "postit", (0.9, 0.82), 0.16)
    return canvas.convert("RGB")


def _flower(draw, x, y, r, petal, center, petals=8, rot=0.0):
    for k in range(petals):
        a = rot + k * 2 * math.pi / petals
        px, py = x + math.cos(a) * r, y + math.sin(a) * r
        draw.ellipse([px - r * 0.55, py - r * 0.55, px + r * 0.55, py + r * 0.55], fill=petal)
    draw.ellipse([x - r * 0.5, y - r * 0.5, x + r * 0.5, y + r * 0.5], fill=center)


def spring(photos, message, W, H, rng):
    canvas = _textured(_gradient(W, H, (236, 250, 230), (255, 246, 214)), rng, 8).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    for _ in range(46):  # fleurs le long des bords
        side = rng.random()
        x = rng.uniform(0, W)
        y = rng.uniform(0, H * 0.12) if side < 0.5 else rng.uniform(H * 0.86, H)
        if rng.random() < 0.25:
            x, y = (rng.uniform(0, W * 0.06) if rng.random() < 0.5 else rng.uniform(W * 0.94, W)), rng.uniform(0, H)
        petal = rng.choice([(255, 255, 255), (255, 190, 210), (255, 230, 120), (200, 180, 255)])
        _flower(draw, x, y, H * rng.uniform(0.018, 0.035), petal, (250, 190, 40), rng.choice([5, 6, 8]), rng.uniform(0, 1))
    size = _photo_size(W, H, len(photos), 0.92)
    elements = [base.framed(base.print_photo(p, size, size * 0.8), max(8, size // 20), (255, 255, 255)) for p in photos]
    _place_row(canvas, elements, H * 0.52, rng, 0.82, 0.04, 6)
    _title(canvas, _t(N_("Le printemps")), HAND2, int(H * 0.1), (80, 140, 80), (W / 2, H * 0.19), shadow=False)
    _message_note(canvas, message, rng, "postit", (0.88, 0.76), 0.17)
    return canvas.convert("RGB")


def _leaf(draw, x, y, s, angle, color, maple=False):
    """Feuille d'automne : ovale pointu avec nervure, ou feuille d'érable à cinq lobes."""
    ca, sa = math.cos(angle), math.sin(angle)
    rot = lambda px, py: (x + px * ca - py * sa, y + px * sa + py * ca)
    if maple:
        radii = [1.0, 0.5, 0.78, 0.38, 0.62, 0.42, 0.62, 0.38, 0.78, 0.5]
        pts = [rot(s * r * math.cos(-math.pi / 2 + k * math.pi / 5), s * r * math.sin(-math.pi / 2 + k * math.pi / 5)) for k, r in enumerate(radii)]
    else:
        pts = [rot(s * math.cos(t), s * 0.42 * math.sin(t) * (1 - 0.25 * math.cos(t))) for t in [k * 2 * math.pi / 24 for k in range(24)]]
    draw.polygon(pts, fill=color)
    dark = tuple(int(c * 0.7) for c in color)
    draw.line([rot(-s * (0.2 if maple else 1.25), 0) if not maple else rot(0, s * 0.5), rot(s * 0.9, 0) if not maple else rot(0, -s * 0.85)],
              fill=dark, width=max(2, int(s / 9)))


def autumn(photos, message, W, H, rng):
    canvas = _vignette(_textured(_gradient(W, H, (250, 200, 130), (200, 110, 60)), rng, 14), 0.35).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    for _ in range(55):
        _leaf(draw, rng.uniform(0, W), rng.uniform(0, H), H * rng.uniform(0.02, 0.045), rng.uniform(0, 6.3),
              rng.choice([(220, 80, 30), (240, 150, 30), (190, 50, 40), (250, 200, 60), (160, 90, 40)]), maple=rng.random() < 0.5)
    size = _photo_size(W, H, len(photos), 0.92)
    elements = [base.framed(base.print_photo(p, size, size), max(8, size // 20), (252, 248, 240), bottom=max(8, size // 20) * 4) for p in photos]
    _place_row(canvas, elements, H * 0.53, rng, 0.82, 0.05, 9)
    _title(canvas, _t(N_("L'automne")), HAND2, int(H * 0.11), (110, 40, 20), (W / 2, H * 0.12), shadow=False)
    _message_note(canvas, message, rng, "fiche", (0.88, 0.85), 0.16)
    return canvas.convert("RGB")


def winter(photos, message, W, H, rng):
    canvas = _gradient(W, H, (60, 90, 150), (170, 200, 235)).convert("RGBA")
    _mountains(canvas, [(220, 230, 245, 255), (190, 205, 230, 255)], rng, 0.55)
    draw = ImageDraw.Draw(canvas)
    ground = [(0, H)] + [(x, H * 0.85 + math.sin(x / W * 5) * H * 0.02) for x in range(0, W + 40, 40)] + [(W, H)]
    draw.polygon(ground, fill=(250, 252, 255))
    for _ in range(18):  # sapins enneigés
        x, s = rng.choice([rng.uniform(0, W * 0.15), rng.uniform(W * 0.85, W)]), H * rng.uniform(0.12, 0.22)
        y = H * 0.9
        for k in range(3):
            tier = [(x, y - s * (1 - k * 0.28)), (x - s * 0.33 * (1 + k * 0.3), y - s * 0.32 * k), (x + s * 0.33 * (1 + k * 0.3), y - s * 0.32 * k)]
            draw.polygon(tier, fill=(30, 70, 60))
            draw.polygon([tier[0], (tier[0][0] - s * 0.12, tier[0][1] + s * 0.12), (tier[0][0] + s * 0.12, tier[0][1] + s * 0.12)], fill=(250, 252, 255))
    _snow(canvas, int(W * H / 6000), rng, (1.5, 4.5))
    size = _photo_size(W, H, len(photos), 0.88)
    elements = []
    for p in photos:
        frame = base.framed(base.print_photo(p, size, size * 0.8), max(10, size // 14), (130, 85, 50))
        fd = ImageDraw.Draw(frame)
        fd.ellipse([-size * 0.05, -size * 0.06, frame.width + size * 0.05, size * 0.09], fill=(252, 253, 255))  # neige sur le cadre
        elements.append(frame)
    _place_row(canvas, elements, H * 0.5, rng, 0.7, 0.03, 3)
    _title(canvas, _t(N_("L'hiver")), HAND2, int(H * 0.11), (255, 255, 255), (W / 2, H * 0.11), glow=(160, 200, 255))
    _message_note(canvas, message, rng, "fiche", (0.5, 0.88), 0.15)
    return canvas.convert("RGB")


def birthday(photos, message, W, H, rng):
    canvas = _textured(_gradient(W, H, (255, 250, 240), (250, 236, 250)), rng, 6).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    for _ in range(140):  # confettis
        x, y, s = rng.uniform(0, W), rng.uniform(0, H), H * rng.uniform(0.004, 0.01)
        color = rng.choice([(255, 90, 120), (90, 180, 255), (255, 200, 60), (120, 220, 140), (190, 120, 255)])
        draw.rectangle([x, y, x + s * 2, y + s], fill=color)
    for side in (0.07, 0.93):  # ballons
        for k in range(3):
            bx, by = W * side + rng.uniform(-W * 0.04, W * 0.04), H * (0.25 + k * 0.17)
            rw, rh = H * 0.06, H * 0.075
            color = rng.choice([(255, 80, 110), (80, 170, 255), (255, 200, 50), (150, 110, 255)])
            draw.line([(bx, by + rh), (bx + rng.uniform(-20, 20), H)], fill=(150, 150, 150), width=2)
            draw.ellipse([bx - rw, by - rh, bx + rw, by + rh], fill=color)
            draw.polygon([(bx, by + rh), (bx - rw * 0.15, by + rh * 1.15), (bx + rw * 0.15, by + rh * 1.15)], fill=color)
            draw.ellipse([bx - rw * 0.55, by - rh * 0.65, bx - rw * 0.2, by - rh * 0.25], fill=(255, 255, 255, 140))
    size = _photo_size(W, H, len(photos), 0.85)
    elements = [base.framed(base.print_photo(p, size, size), max(8, size // 20), (255, 255, 255), bottom=max(8, size // 20) * 4) for p in photos]
    _place_row(canvas, elements, H * 0.56, rng, 0.7, 0.05, 8)
    _title(canvas, _t(N_("Joyeux anniversaire !")), MARKER, int(H * 0.08), (230, 60, 110), (W / 2, H * 0.12), shadow=False, max_width=W * 0.7)
    _message_note(canvas, message, rng, "postit", (0.5, 0.88), 0.15)
    return canvas.convert("RGB")


def cinema(photos, message, W, H, rng):
    canvas = _gradient(W, H, (30, 6, 10), (10, 2, 4)).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    for side in (0, 1):  # rideaux de velours
        x0 = 0 if side == 0 else W * 0.86
        for k in range(8):
            x = x0 + k * W * 0.0175
            draw.rectangle([x, 0, x + W * 0.0175, H], fill=(150 - (k % 2) * 40, 16, 24))
    draw.rectangle([0, 0, W, H * 0.06], fill=(120, 12, 20))
    canvas = canvas.filter(ImageFilter.GaussianBlur(2)).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    size = int(min(_photo_size(W, H, len(photos), 1.0), W * 0.68 / len(photos) * 0.92))
    elements = []
    for p in photos:  # écrans entourés d'ampoules
        photo = base.framed(base.print_photo(p, size, size * 0.62), max(14, size // 12), (40, 30, 26))
        bulbs = Image.new("RGBA", photo.size, (0, 0, 0, 0))
        bd = ImageDraw.Draw(bulbs)
        step, r, m = max(18, size // 12), max(4, size // 60), max(7, size // 24)
        for x in range(m, photo.width - m + 1, step):
            for y in (m, photo.height - m):
                bd.ellipse([x - r, y - r, x + r, y + r], fill=(255, 230, 140, 255))
        for y in range(m, photo.height - m + 1, step):
            for x in (m, photo.width - m):
                bd.ellipse([x - r, y - r, x + r, y + r], fill=(255, 230, 140, 255))
        photo.alpha_composite(bulbs.filter(ImageFilter.GaussianBlur(r)))
        photo.alpha_composite(bulbs)
        elements.append(photo)
    _place_row(canvas, elements, H * 0.55, rng, 0.66, 0.02, 0)
    _title(canvas, _t(N_("À l'affiche")), MARKER, int(H * 0.08), (255, 225, 140), (W / 2, H * 0.17), glow=(255, 190, 60))
    _message_note(canvas, message, rng, "fiche", (0.5, 0.9), 0.14)
    return canvas.convert("RGB")


def comic(photos, message, W, H, rng):
    canvas = Image.new("RGB", (W, H), (250, 248, 240))
    draw = ImageDraw.Draw(canvas)
    gutter, border = int(H * 0.025), max(5, H // 140)
    n = len(photos)
    panel_widths = base.proportional_widths(photos, W - gutter * (n + 1), H * 0.92) if base.FULL_PHOTOS else \
        [(W - gutter * (n + 1)) * f / sum(fs) for fs in [[rng.uniform(0.8, 1.2) for _ in range(n)]] for f in fs]
    x = gutter
    for i, photo in enumerate(photos):  # cases légèrement inclinées
        w = panel_widths[i]
        top, bottom = gutter + rng.uniform(0, H * 0.04), H - gutter - rng.uniform(0, H * 0.04)
        panel = base.cell_photo(photo, w, bottom - top)
        dots = Image.new("L", panel.size, 0)  # trame de points façon impression BD
        dd = ImageDraw.Draw(dots)
        step = max(8, H // 120)
        for yy in range(0, panel.height, step):
            for xx in range((yy // step % 2) * step // 2, panel.width, step):
                dd.ellipse([xx - 1.5, yy - 1.5, xx + 1.5, yy + 1.5], fill=60)
        panel.paste((0, 0, 0), (0, 0), dots)
        canvas.paste(panel, (int(x), int(top)))
        draw.rectangle([x, top, x + w, bottom], outline=(10, 10, 10), width=border)
        x += w + gutter
    canvas = canvas.convert("RGBA")
    word = _t(N_("WOUAH !"))
    bx, by, br = W * rng.uniform(0.3, 0.7), H * 0.22, H * 0.16
    burst = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(burst)
    bdraw.polygon(_star(bx, by, br * 1.15, br * 0.7, 14), fill=(20, 20, 20, 255))
    bdraw.polygon(_star(bx, by, br, br * 0.62, 14), fill=(255, 220, 40, 255))
    bdraw.polygon(_star(bx, by, br * 0.7, br * 0.45, 14), fill=(240, 60, 40, 255))
    canvas.alpha_composite(burst)
    _title(canvas, word, MARKER, int(br * 0.5), (255, 255, 255), (bx, by), shadow=False, max_width=br * 1.5)
    _message_note(canvas, message, rng, "fiche", (0.85, 0.82), 0.18)
    return canvas.convert("RGB")


def travel_map(photos, message, W, H, rng):
    canvas = _paper(W, H, rng, (236, 220, 180), (214, 190, 140), 24).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    for _ in range(4):  # côtes stylisées
        cx, cy, r = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(H * 0.15, H * 0.3)
        pts = [(cx + r * (0.7 + 0.3 * rng.random()) * math.cos(a), cy + r * (0.7 + 0.3 * rng.random()) * math.sin(a))
               for a in [k * 2 * math.pi / 24 for k in range(24)]]
        draw.polygon(pts, fill=(205, 186, 140), outline=(140, 110, 70))
    # Rose des vents
    rx, ry, rr = W * 0.9, H * 0.82, H * 0.1
    draw.ellipse([rx - rr, ry - rr, rx + rr, ry + rr], outline=(120, 80, 50), width=3)
    draw.polygon(_star(rx, ry, rr * 0.95, rr * 0.18, 4), fill=(120, 60, 40))
    draw.polygon(_star(rx, ry, rr * 0.6, rr * 0.12, 4, -math.pi / 4), fill=(200, 160, 100))
    route = _bezier([(W * 0.05, H * 0.9), (W * 0.3, H * 0.6), (W * 0.6, H * 1.0), (W * 0.82, H * 0.55)], 60)
    for i in range(0, len(route) - 1, 2):
        draw.line([route[i], route[i + 1]], fill=(170, 40, 40), width=max(3, H // 220))
    ex, ey = route[-1]
    s = H * 0.025
    draw.line([(ex - s, ey - s), (ex + s, ey + s)], fill=(170, 40, 40), width=max(4, H // 160))
    draw.line([(ex - s, ey + s), (ex + s, ey - s)], fill=(170, 40, 40), width=max(4, H // 160))
    size = _photo_size(W, H, len(photos), 0.85)
    elements = []
    for p in photos:
        photo = base.framed(base.print_photo(p, size, size * 0.78), max(6, size // 26), (250, 246, 236))
        tape = base.tape_strip(int(size * 0.35), max(10, size // 12), rng)
        photo.alpha_composite(base.rotated(tape, rng.uniform(-8, 8)).resize((int(size * 0.35), max(10, size // 10))), (int(photo.width / 2 - size * 0.17), 0))
        elements.append(photo)
    _place_row(canvas, elements, H * 0.45, rng, 0.78, 0.06, 7)
    _title(canvas, _t(N_("Carnet de voyage")), HAND2, int(H * 0.1), (90, 50, 30), (W * 0.42, H * 0.1), shadow=False)
    _message_note(canvas, message, rng, "fiche", (0.12, 0.2), 0.15)
    return canvas.convert("RGB")


def old_album(photos, message, W, H, rng):
    canvas = _vignette(_textured(_gradient(W, H, (40, 38, 36), (26, 24, 22)), rng, 20), 0.35).convert("RGBA")
    size = _photo_size(W, H, len(photos), 0.92)
    elements = []
    for p in photos:
        photo = base.print_photo(p, size, size * 0.8)
        photo = Image.blend(photo, photo.convert("L").convert("RGB"), 0.5)  # couleurs passées
        card = base.framed(photo, max(10, size // 16), (244, 240, 228))
        cd = ImageDraw.Draw(card)
        c = max(18, size // 9)  # coins photo
        for (x, y, pts) in [(0, 0, [(0, 0), (c, 0), (0, c)]), (card.width, 0, [(card.width, 0), (card.width - c, 0), (card.width, c)]),
                            (0, card.height, [(0, card.height), (c, card.height), (0, card.height - c)]),
                            (card.width, card.height, [(card.width, card.height), (card.width - c, card.height), (card.width, card.height - c)])]:
            cd.polygon(pts, fill=(20, 20, 20))
        elements.append(card)
    _place_row(canvas, elements, H * 0.45, rng, 0.84, 0.05, 3)
    draw = ImageDraw.Draw(canvas)
    font = _font(HAND2, int(H * 0.045))
    for i in range(len(elements)):  # légendes à l'encre blanche
        x = W * (0.08 + 0.84 * (i + 0.5) / len(elements))
        text = _t(N_("Souvenir"))
        draw.text((x - draw.textlength(text, font=font) / 2, H * 0.78), text, font=font, fill=(235, 232, 220))
    _message_note(canvas, message, rng, "fiche", (0.88, 0.88), 0.14)
    return canvas.convert("RGB")


def _firework(canvas, cx, cy, radius, color, rng):
    """Bouquet de feu d'artifice : rayons scintillants et halo."""
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    rays = rng.randint(16, 26)
    for k in range(rays):
        a = k * 2 * math.pi / rays + rng.uniform(-0.08, 0.08)
        r0, r1 = radius * rng.uniform(0.15, 0.3), radius * rng.uniform(0.75, 1.0)
        draw.line([(cx + r0 * math.cos(a), cy + r0 * math.sin(a)), (cx + r1 * math.cos(a), cy + r1 * math.sin(a))],
                  fill=color + (230,), width=max(2, int(radius * 0.025)))
        tip = max(2, radius * 0.035)
        x, y = cx + r1 * math.cos(a), cy + r1 * math.sin(a)
        draw.ellipse([x - tip, y - tip, x + tip, y + tip], fill=(255, 250, 220, 255))
    glow = layer.filter(ImageFilter.GaussianBlur(radius * 0.08))
    canvas.alpha_composite(glow)
    canvas.alpha_composite(layer)


def new_year_label(today=None):
    """« Bonne année 2027 » : à partir de l'été, l'année qui arrive ; en début d'année, l'année en cours."""
    today = today or date.today()
    return f"{_t(N_('Bonne année'))} {today.year + 1 if today.month >= 7 else today.year}"


def new_year(photos, message, W, H, rng):
    canvas = _vignette(_gradient(W, H, (10, 14, 40), (34, 20, 70)), 0.5).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    for _ in range(160):  # étoiles
        x, y, r = rng.uniform(0, W), rng.uniform(0, H * 0.75), rng.uniform(0.6, 2.2)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, rng.randint(90, 220)))
    palette = [(255, 205, 80), (255, 110, 160), (110, 210, 255), (180, 140, 255), (255, 255, 255)]
    for fx, fy, fr in ((0.12, 0.2, 0.17), (0.86, 0.17, 0.2), (0.62, 0.1, 0.11), (0.3, 0.08, 0.09)):
        _firework(canvas, W * fx + rng.uniform(-W * 0.02, W * 0.02), H * fy, H * fr, rng.choice(palette), rng)
    for _ in range(170):  # confettis dorés et serpentins
        x, y, s = rng.uniform(0, W), rng.uniform(H * 0.55, H), H * rng.uniform(0.004, 0.011)
        color = rng.choice([(255, 210, 90), (240, 180, 60), (255, 120, 170), (120, 210, 255), (255, 255, 255)])
        a = rng.uniform(0, math.pi)
        dx, dy, ex, ey = s * math.cos(a), s * math.sin(a), -s * 0.45 * math.sin(a), s * 0.45 * math.cos(a)
        draw.polygon([(x - dx - ex, y - dy - ey), (x + dx - ex, y + dy - ey), (x + dx + ex, y + dy + ey), (x - dx + ex, y - dy + ey)], fill=color)
    size = _photo_size(W, H, len(photos), 0.9)
    elements = [base.framed(base.framed(base.print_photo(p, size, size * 0.78), max(4, size // 45), (230, 190, 90)).convert("RGB"),
                            max(8, size // 20), (250, 246, 236)) for p in photos]
    _place_row(canvas, elements, H * 0.56, rng, 0.78, 0.05, 7)
    _title(canvas, new_year_label(), HAND2, int(H * 0.13), (255, 214, 110), (W / 2, H * 0.14), glow=(255, 170, 40), max_width=W * 0.6)
    _message_note(canvas, message, rng, "fiche", (0.87, 0.82), 0.19)
    return canvas.convert("RGB")


THEMES = {
    "hokusai": (N_("Hokusai – La Grande Vague"), 2, 3, True, hokusai),
    "fuji": (N_("Mont Fuji"), 3, 4, True, fuji),
    "espace": (N_("Espace"), 3, 4, True, space),
    "annees80": (N_("Années 80"), 3, 4, True, synthwave),
    "annees70": (N_("Années 70"), 3, 4, True, seventies),
    "printemps": (N_("Printemps"), 3, 4, True, spring),
    "automne": (N_("Automne"), 3, 4, True, autumn),
    "hiver": (N_("Hiver"), 3, 3, True, winter),
    "anniversaire": (N_("Anniversaire"), 3, 3, True, birthday),
    "cinema": (N_("Cinéma"), 2, 3, True, cinema),
    "bd": (N_("Bande dessinée"), 3, 4, True, comic),
    "carnet": (N_("Carnet de voyage"), 3, 4, True, travel_map),
    "album": (N_("Album ancien"), 3, 4, True, old_album),
    "nouvel_an": (N_("Nouvel An"), 3, 4, True, new_year),
}
