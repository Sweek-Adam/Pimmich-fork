"""
Écran de démarrage du cadre photo (thème Plymouth, à la place de celui de Raspberry Pi OS, sans messages du système) :
un fond sombre aux reflets colorés, « Votre cadre photo s'allume », les fonctions du cadre en cartes (mises en valeur
tour à tour pendant le démarrage) et le QR code pour envoyer une photo depuis un téléphone.

Quatre styles (aurore, lumière, mosaïque, néon) : le thème en tire un au hasard à chaque démarrage.
Les images sont dessinées ici (Pillow, `python3 -m utils.boot_screen <dossier>`) ; utils/install_boot_screen.sh les
installe comme thème Plymouth.
"""
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

FONT_PATHS = ["/usr/share/fonts/truetype/nunito-sans/NunitoSans-VariableFont_YTLC,opsz,wdth,wght.ttf",
              str(Path(__file__).resolve().parent.parent / "static" / "fonts" / "NunitoSans.ttf")]
INK, SOFT, MUTED = (255, 255, 255), (214, 216, 240), (150, 154, 190)
ACCENTS = [(255, 122, 155), (130, 140, 255), (64, 210, 200), (255, 190, 90), (190, 120, 255), (90, 190, 255)]
FEATURES = [  # (icône, titre, détail)
    ("photo", "Photos de famille", "Envoyées depuis vos téléphones"),
    ("message", "Messages & dessins", "Un mot doux s'affiche en grand"),
    ("dice", "Jeux en famille", "Où et quand ? Qui est-ce ?"),
    ("party", "Mode fête", "Vos invités partagent en direct"),
    ("music", "Musique & radio", "Spotify, AirPlay, Bluetooth"),
    ("weather", "Météo & agenda", "La journée d'un coup d'œil"),
]


def font(size, weight=400, path=None):
    from PIL import ImageFont
    for candidate in ([path] if path else []) + FONT_PATHS:
        if candidate and Path(candidate).exists():
            f = ImageFont.truetype(candidate, int(size))
            try:
                f.set_variation_by_axes([weight, 100, 12, 500])
            except Exception:
                pass
            return f
    return ImageFont.load_default(size=int(size))


def _aurora(width, height, seed=7):
    """Fond : dégradé nuit profonde et taches de lumière floues."""
    base = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(base)
    for y in range(height):
        t = y / height
        draw.line([(0, y), (width, y)], fill=(int(12 + 16 * t), int(13 + 6 * t), int(34 + 30 * t)))
    glow = Image.new("RGB", (width // 4, height // 4))
    gd = ImageDraw.Draw(glow)
    rng = random.Random(seed)
    for (cx, cy, r, color) in [(0.15, 0.2, 0.32, (120, 70, 220)), (0.85, 0.15, 0.28, (230, 80, 140)),
                               (0.75, 0.9, 0.35, (40, 160, 180)), (0.3, 0.95, 0.25, (90, 60, 200))]:
        w, h = glow.size
        rr = r * w
        gd.ellipse([cx * w - rr, cy * h - rr * 0.8, cx * w + rr, cy * h + rr * 0.8], fill=color)
    glow = glow.filter(ImageFilter.GaussianBlur(glow.size[0] / 14)).resize((width, height), Image.BICUBIC)
    image = Image.blend(base, glow, 0.38)
    noise = Image.effect_noise((width // 2, height // 2), 10).resize((width, height)).convert("RGB")
    return Image.blend(image, noise, 0.025)


def _icon(kind, size, color):
    """Icônes au trait (dessinées en grand puis réduites : bords nets)."""
    k = 4
    s = size * k
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = max(2, int(s * 0.07))
    c = color + (255,)
    if kind == "photo":
        d.rounded_rectangle([s * .1, s * .2, s * .9, s * .8], radius=s * .1, outline=c, width=w)
        d.polygon([(s * .18, s * .72), (s * .42, s * .45), (s * .58, s * .62), (s * .68, s * .52), (s * .82, s * .72)], fill=c)
        d.ellipse([s * .62, s * .28, s * .74, s * .4], fill=c)
    elif kind == "message":
        d.rounded_rectangle([s * .1, s * .15, s * .9, s * .68], radius=s * .14, outline=c, width=w)
        d.polygon([(s * .3, s * .66), (s * .22, s * .86), (s * .46, s * .67)], fill=c)
        for i, y in enumerate((.33, .5)):
            d.line([s * .26, s * y, s * (.74 if i == 0 else .58), s * y], fill=c, width=w)
    elif kind == "dice":
        d.rounded_rectangle([s * .15, s * .15, s * .85, s * .85], radius=s * .16, outline=c, width=w)
        for px, py in ((.33, .33), (.67, .33), (.5, .5), (.33, .67), (.67, .67)):
            r = s * .06
            d.ellipse([s * px - r, s * py - r, s * px + r, s * py + r], fill=c)
    elif kind == "party":
        cx, cy = s * .5, s * .5
        pts = []
        for i in range(8):
            r = s * (.42 if i % 2 == 0 else .13)
            a = math.pi / 4 * i - math.pi / 2
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        d.polygon(pts, fill=c)
        for (x, y, r) in ((.18, .2, .05), (.84, .78, .06), (.82, .22, .035)):
            d.ellipse([s * x - s * r, s * y - s * r, s * x + s * r, s * y + s * r], fill=c)
    elif kind == "music":
        d.line([s * .38, s * .25, s * .38, s * .72], fill=c, width=w)
        d.line([s * .78, s * .15, s * .78, s * .62], fill=c, width=w)
        d.polygon([(s * .38, s * .25), (s * .78, s * .15), (s * .78, s * .29), (s * .38, s * .39)], fill=c)
        for x, y in ((.28, .72), (.68, .62)):
            d.ellipse([s * x - s * .12, s * y - s * .09, s * x + s * .12, s * y + s * .09], fill=c)
    elif kind == "weather":
        d.ellipse([s * .42, s * .12, s * .82, s * .52], outline=c, width=w)
        cloud = [(.14, .58, .2), (.34, .5, .2), (.52, .6, .16)]
        mask = Image.new("L", (s, s), 0)
        md = ImageDraw.Draw(mask)
        for x, y, r in cloud:
            md.ellipse([s * (x - r), s * (y - r), s * (x + r), s * (y + r)], fill=255)
        md.rounded_rectangle([s * .02, s * .58, s * .7, s * .8], radius=s * .1, fill=255)
        shape = Image.new("RGBA", (s, s), c)
        img.paste((0, 0, 0, 0), (0, 0), mask)  # le nuage passe devant le soleil
        img.paste(shape, (0, 0), mask)
    return img.resize((size, size), Image.LANCZOS)


def _qr(url, size):
    import qrcode
    qr = qrcode.QRCode(border=1, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill_color=(18, 20, 44), back_color="white").convert("RGB").resize((size, size), Image.NEAREST)


def _card(width, height, radius, fill=(255, 255, 255, 22), outline=(255, 255, 255, 40)):
    card = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle([0, 0, width - 1, height - 1], radius=radius, fill=fill, outline=outline, width=2)
    return card


def layout(width, height):
    """Positions : cartes des fonctions (x, y, w, h), carte du QR code."""
    margin = width * 0.065
    grid_w = width * 0.56
    card_w, card_h = (grid_w - width * 0.02) / 2, height * 0.115
    top = height * 0.42
    cards = []
    for i in range(len(FEATURES)):
        col, row = i % 2, i // 2
        cards.append((int(margin + col * (card_w + width * 0.02)), int(top + row * (card_h + height * 0.022)), int(card_w), int(card_h)))
    qr_w = int(width * 0.24)
    qr_box = (int(width - margin - qr_w), int(height * 0.28), qr_w, int(height * 0.52))
    return cards, qr_box


def _features_cards(canvas, cards, font_path, height, dark=False, tile=True):
    """Cartes des fonctions : pastille de couleur (icône blanche), titre et détail."""
    draw = ImageDraw.Draw(canvas)
    name_font, detail_font = font(height * 0.027, 750, font_path), font(height * 0.021, 450, font_path)
    for i, ((kind, name, detail), (cx, cy, cw, ch)) in enumerate(zip(FEATURES, cards)):
        if tile:
            canvas.alpha_composite(_card(cw, ch, int(ch * 0.22), fill=(255, 255, 255, 190) if dark else (255, 255, 255, 22),
                                         outline=(255, 255, 255, 230) if dark else (255, 255, 255, 40)), (cx, cy))
        bubble = int(ch * 0.66)
        bx, by = cx + int(ch * 0.17), cy + (ch - bubble) // 2
        canvas.alpha_composite(_pastille(bubble, ACCENTS[i % len(ACCENTS)]), (bx, by))
        icon_size = int(ch * 0.46)
        canvas.alpha_composite(_icon(kind, icon_size, (255, 255, 255)), (bx + (bubble - icon_size) // 2, by + (bubble - icon_size) // 2))
        tx = bx + bubble + int(ch * 0.2)
        draw.text((tx, cy + ch * 0.2), name, font=name_font, fill=(28, 30, 52) if dark else INK)
        draw.text((tx, cy + ch * 0.55), detail, font=detail_font, fill=(110, 112, 140) if dark else MUTED)


def _pastille(size, accent):
    pastille = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pastille)
    for yy in range(size):  # léger dégradé vertical
        t = yy / size
        pd.line([(0, yy), (size, yy)], fill=tuple(min(255, int(c * (1.08 - 0.22 * t))) for c in accent) + (255,))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.3), fill=255)
    pastille.putalpha(mask)
    return pastille


def _qr_card(canvas, box, url, address, font_path, height, style="white"):
    qx, qy, qw, qh = box
    draw = ImageDraw.Draw(canvas)
    if style == "neon":
        card = _card(qw, qh, int(qw * 0.08), fill=(10, 10, 20, 230), outline=(0, 0, 0, 0))
        canvas.alpha_composite(_neon_outline(qw, qh, int(qw * 0.08)), (qx - 30, qy - 30))
        canvas.alpha_composite(card, (qx, qy))
        dark, sub = INK, (170, 175, 210)
    else:
        canvas.alpha_composite(_card(qw, qh, int(qw * 0.08), fill=(255, 255, 255, 238), outline=(255, 255, 255, 255)), (qx, qy))
        dark, sub = (24, 26, 56), (110, 112, 150)
    qr_size = int(qw * 0.7)
    qr = _qr(url, qr_size)
    if style == "neon":  # QR sur fond blanc arrondi, au centre de la carte sombre
        plate = _card(qr_size + 24, qr_size + 24, 18, fill=(255, 255, 255, 255), outline=(255, 255, 255, 255))
        canvas.alpha_composite(plate, (qx + (qw - qr_size) // 2 - 12, qy + int(qw * 0.12) - 12))
    canvas.paste(qr, (qx + (qw - qr_size) // 2, qy + int(qw * 0.12)))
    head = font(height * 0.028, 800, font_path)
    for j, text in enumerate(("Scannez pour envoyer", "une photo au cadre")):
        w = draw.textlength(text, font=head)
        draw.text((qx + (qw - w) / 2, qy + qw * 0.12 + qr_size + height * 0.022 + j * height * 0.036), text, font=head, fill=dark)
    addr_font = font(height * 0.021, 500, font_path)
    w = draw.textlength(address, font=addr_font)
    draw.text((qx + (qw - w) / 2, qy + qh - height * 0.05), address, font=addr_font, fill=sub)


def _neon_outline(width, height, radius, colors=((170, 90, 255), (40, 220, 255)), thickness=4):
    """Contour lumineux en dégradé (violet vers cyan) avec halo, de la taille donnée (+30 px de halo)."""
    pad = 30
    w, h = width + 2 * pad, height + 2 * pad
    grad = Image.new("RGBA", (w, h))
    gd = ImageDraw.Draw(grad)
    for x in range(w):
        t = x / w
        gd.line([(x, 0), (x, h)], fill=tuple(int(a + (b - a) * t) for a, b in zip(*colors)) + (255,))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([pad, pad, pad + width - 1, pad + height - 1], radius=radius, outline=255, width=thickness)
    halo = mask.filter(ImageFilter.GaussianBlur(12)).point(lambda v: min(255, v * 3))
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(grad, (0, 0), halo.point(lambda v: v // 2))
    out.paste(grad, (0, 0), mask)
    return out


def _spaced(draw, xy, text, fnt, fill, spacing):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + spacing
    return x


def _glow_frame(w, h, radius):
    highlight = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    ImageDraw.Draw(highlight).rounded_rectangle([20, 20, w + 19, h + 19], radius=radius, outline=(255, 255, 255, 170), width=3)
    return Image.alpha_composite(highlight.filter(ImageFilter.GaussianBlur(9)), highlight)


def _dot(color=(255, 255, 255)):
    dot = Image.new("RGBA", (28, 28), (0, 0, 0, 0))
    ImageDraw.Draw(dot).ellipse([4, 4, 24, 24], fill=color + (230,))
    return dot


def render_aurore(width, height, url, address, font_path):
    """Nuit aux reflets colorés, très grand titre, fonctions en cartes de verre, QR code sur carte blanche."""
    canvas = _aurora(width, height).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    margin = width * 0.065
    big = font(height * 0.088, 850, font_path)
    draw.text((margin, height * 0.075), "Votre cadre photo", font=big, fill=INK)
    # « s'allume » en dégradé rose vers violet
    word = "s'allume"
    tw = int(draw.textlength(word, font=big)) + 10
    grad = Image.new("RGBA", (tw, int(height * 0.13)))
    gd = ImageDraw.Draw(grad)
    for x in range(tw):
        t = x / tw
        gd.line([(x, 0), (x, grad.height)], fill=(int(255 - 90 * t), int(122 + 20 * t), int(155 + 100 * t), 255))
    mask = Image.new("L", grad.size, 0)
    ImageDraw.Draw(mask).text((0, 0), word, font=big, fill=255)
    canvas.paste(grad, (int(margin), int(height * 0.175)), mask)
    draw.text((margin, height * 0.3), "Les souvenirs de la famille arrivent dans un instant.", font=font(height * 0.03, 400, font_path), fill=SOFT)
    cards, qr_box = layout(width, height)
    cards = [(x, y + int(height * 0.03), w, h) for x, y, w, h in cards]
    _features_cards(canvas, cards, font_path, height)
    _qr_card(canvas, (qr_box[0], qr_box[1] + int(height * 0.02), qr_box[2], qr_box[3]), url, address, font_path, height)
    return {"background": canvas.convert("RGB"), "highlight": _glow_frame(cards[0][2], cards[0][3], int(cards[0][3] * 0.22)),
            "dot": _dot(), "cards": cards, "dots_at": (int(margin), int(height * 0.385))}


def render_lumiere(width, height, url, address, font_path):
    """Clair et épuré : fond crème, titre centré, anneau de progression, fonctions en rangée d'icônes."""
    canvas = Image.new("RGBA", (width, height), (250, 247, 242, 255))
    soft = Image.new("RGBA", (width // 4, height // 4), (0, 0, 0, 0))
    sd = ImageDraw.Draw(soft)
    for cx, cy, r, color in ((0.1, 0.1, 0.3, (255, 214, 196)), (0.95, 0.2, 0.25, (214, 222, 255)), (0.5, 1.05, 0.35, (255, 236, 200))):
        w, h = soft.size
        sd.ellipse([cx * w - r * w, cy * h - r * w, cx * w + r * w, cy * h + r * w], fill=color + (255,))
    canvas.alpha_composite(soft.filter(ImageFilter.GaussianBlur(soft.size[0] / 12)).resize((width, height), Image.BICUBIC))
    draw = ImageDraw.Draw(canvas)
    ink = (30, 32, 48)
    big = font(height * 0.1, 300, font_path)
    for j, text in enumerate(("Votre cadre photo", "s'allume")):
        f = big if j == 0 else font(height * 0.1, 800, font_path)
        w = draw.textlength(text, font=f)
        draw.text(((width - w) / 2, height * (0.12 + 0.11 * j)), text, font=f, fill=ink)
    sub = font(height * 0.028, 400, font_path)
    text = "Les souvenirs de la famille arrivent dans un instant."
    draw.text(((width - draw.textlength(text, font=sub)) / 2, height * 0.37), text, font=sub, fill=(120, 118, 130))
    # Rangée de fonctions : pastille ronde, nom dessous
    n = len(FEATURES)
    step = width * 0.1
    x0 = (width - step * (n - 1)) / 2 - width * 0.12
    bubble = int(height * 0.085)
    name_font = font(height * 0.02, 700, font_path)
    spots = []
    for i, (kind, name, _detail) in enumerate(FEATURES):
        cx = int(x0 + i * step)
        cy = int(height * 0.56)
        canvas.alpha_composite(_pastille(bubble, ACCENTS[i % len(ACCENTS)]), (cx - bubble // 2, cy - bubble // 2))
        icon = int(bubble * 0.56)
        canvas.alpha_composite(_icon(kind, icon, (255, 255, 255)), (cx - icon // 2, cy - icon // 2))
        for k, part in enumerate(name.split(" & ") if " & " in name else [name]):
            label = part + (" &" if k == 0 and " & " in name else "")
            w = draw.textlength(label, font=name_font)
            draw.text((cx - w / 2, cy + bubble * 0.68 + k * height * 0.026), label, font=name_font, fill=ink)
        spots.append((cx - bubble // 2 - 10, cy - bubble // 2 - 10, bubble + 20, bubble + 20))
    # QR code à droite, sur carte blanche ombrée
    qw = int(width * 0.19)
    box = (int(width * 0.765), int(height * 0.43), qw, int(height * 0.44))
    shadow = Image.new("RGBA", (qw + 80, box[3] + 80), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([40, 48, qw + 40, box[3] + 40], radius=30, fill=(80, 60, 40, 60))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)), (box[0] - 40, box[1] - 40))
    _qr_card(canvas, box, url, address, font_path, height)
    # Anneau de progression (tourne pendant le démarrage) : un arc
    ring = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(ring).arc([6, 6, 58, 58], 0, 270, fill=(30, 32, 48, 220), width=6)
    halo = Image.new("RGBA", (bubble + 40, bubble + 40), (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse([6, 6, bubble + 33, bubble + 33], outline=(30, 32, 48, 160), width=3)
    return {"background": canvas.convert("RGB"), "highlight": halo, "dot": _dot((30, 32, 48)), "cards": spots,
            "dots_at": (int(width / 2 - 40), int(height * 0.83)), "spinner": ring}


def render_mosaique(width, height, url, address, font_path, seed=3):
    """Mur de photos (formes colorées floutées) derrière un grand panneau de verre dépoli."""
    rng = random.Random(seed)
    wall = Image.new("RGB", (width, height), (20, 18, 30))
    wd = ImageDraw.Draw(wall)
    palette = [(240, 150, 120), (110, 170, 230), (250, 210, 120), (150, 210, 160), (200, 140, 220), (240, 120, 150), (120, 200, 210)]
    tile = width // 7
    for row in range(-1, height // tile + 2):
        for col in range(-1, 8):
            x = col * tile + (tile // 2 if row % 2 else 0) + rng.randint(-20, 20)
            y = row * tile * 0.78 + rng.randint(-20, 20)
            c1, c2 = rng.sample(palette, 2)
            for k in range(int(tile * 0.9)):
                t = k / (tile * 0.9)
                wd.line([(x, y + k), (x + tile * 0.9, y + k)], fill=tuple(int(a + (b - a) * t) for a, b in zip(c1, c2)))
    wall = wall.filter(ImageFilter.GaussianBlur(28))
    wall = Image.blend(wall, Image.new("RGB", (width, height), (16, 14, 28)), 0.45)
    canvas = wall.convert("RGBA")
    panel_box = (int(width * 0.06), int(height * 0.09), int(width * 0.88), int(height * 0.82))
    px, py, pw, ph = panel_box
    glass = canvas.crop((px, py, px + pw, py + ph)).filter(ImageFilter.GaussianBlur(30))
    glass = Image.blend(glass.convert("RGB"), Image.new("RGB", glass.size, (255, 255, 255)), 0.12).convert("RGBA")
    mask = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, pw - 1, ph - 1], radius=48, fill=255)
    canvas.paste(glass, (px, py), mask)
    canvas.alpha_composite(_card(pw, ph, 48, fill=(255, 255, 255, 18), outline=(255, 255, 255, 90)), (px, py))
    draw = ImageDraw.Draw(canvas)
    big = font(height * 0.09, 850, font_path)
    draw.text((px + pw * 0.05, py + ph * 0.08), "Votre cadre photo", font=big, fill=INK)
    draw.text((px + pw * 0.05, py + ph * 0.2), "s'allume", font=font(height * 0.09, 300, font_path), fill=(255, 236, 214))
    draw.text((px + pw * 0.05, py + ph * 0.36), "Les souvenirs de la famille arrivent dans un instant.", font=font(height * 0.028, 450, font_path), fill=SOFT)
    # Fonctions en « pilules »
    pill_font = font(height * 0.023, 700, font_path)
    x, y = px + pw * 0.05, py + ph * 0.52
    spots = []
    for i, (kind, name, _detail) in enumerate(FEATURES):
        w = int(draw.textlength(name, font=pill_font) + height * 0.09)
        h = int(height * 0.062)
        if x + w > px + pw * 0.66:
            x, y = px + pw * 0.05, y + h + height * 0.022
        canvas.alpha_composite(_card(w, h, h // 2, fill=(255, 255, 255, 40), outline=(255, 255, 255, 80)), (int(x), int(y)))
        b = int(h * 0.7)
        canvas.alpha_composite(_pastille(b, ACCENTS[i % len(ACCENTS)]).resize((b, b)), (int(x + h * 0.15), int(y + (h - b) / 2)))
        ic = int(b * 0.6)
        canvas.alpha_composite(_icon(kind, ic, (255, 255, 255)), (int(x + h * 0.15 + (b - ic) / 2), int(y + (h - ic) / 2)))
        draw.text((x + h * 0.15 + b + h * 0.2, y + h * 0.2), name, font=pill_font, fill=INK)
        spots.append((int(x), int(y), w, h))
        x += w + height * 0.02
    qw = int(pw * 0.27)
    _qr_card(canvas, (px + pw - qw - int(pw * 0.05), py + int(ph * 0.12), qw, int(ph * 0.76)), url, address, font_path, height)
    hl = _glow_frame(spots[0][2], spots[0][3], spots[0][3] // 2)
    return {"background": canvas.convert("RGB"), "highlight": hl, "dot": _dot(), "cards": spots,
            "dots_at": (int(px + pw * 0.05), int(py + ph * 0.88)), "per_card_highlight": True}


def render_neon(width, height, url, address, font_path):
    """Nuit noire, grand cadre photo lumineux (dégradé violet vers cyan), fonctions numérotées."""
    canvas = Image.new("RGBA", (width, height), (6, 6, 14, 255))
    glow = Image.new("RGBA", (width // 4, height // 4), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-60, height // 4 - 140, width // 8 + 60, height // 4 + 40], fill=(120, 40, 220, 120))
    gd.ellipse([width // 4 - 160, -80, width // 4 + 60, 120], fill=(0, 170, 220, 90))
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(40)).resize((width, height), Image.BICUBIC))
    draw = ImageDraw.Draw(canvas)
    # Grand cadre photo au néon, à gauche, légèrement incliné
    fw, fh = int(width * 0.26), int(height * 0.58)
    frame = _neon_outline(fw, fh, 26, thickness=6)
    inner = _neon_outline(int(fw * 0.82), int(fh * 0.62), 14, colors=((255, 90, 170), (170, 90, 255)), thickness=3)
    frame.alpha_composite(inner, (int(fw * 0.09), int(fh * 0.08)))
    frame = frame.rotate(-6, resample=Image.BICUBIC, expand=True)
    canvas.alpha_composite(frame, (int(width * 0.05), int(height * 0.18)))
    margin = int(width * 0.36)
    _spaced(draw, (margin, height * 0.12), "VOTRE CADRE PHOTO", font(height * 0.082, 900, font_path), INK, height * 0.006)
    draw.text((margin, height * 0.215), "s'allume", font=font(height * 0.082, 300, font_path), fill=(140, 220, 255))
    num_font, name_font = font(height * 0.024, 800, font_path), font(height * 0.03, 650, font_path)
    spots = []
    for i, (kind, name, detail) in enumerate(FEATURES):
        col, row = i % 2, i // 2
        x = margin + col * int(width * 0.2)
        y = int(height * 0.42 + row * height * 0.11)
        draw.text((x, y + 4), f"0{i + 1}", font=num_font, fill=ACCENTS[i % len(ACCENTS)])
        draw.text((x + height * 0.05, y), name, font=name_font, fill=INK)
        draw.text((x + height * 0.05, y + height * 0.04), detail, font=font(height * 0.02, 400, font_path), fill=(140, 144, 180))
        spots.append((x - 16, y - 12, int(width * 0.19), int(height * 0.09)))
    _qr_card(canvas, (int(width * 0.765), int(height * 0.3), int(width * 0.19), int(height * 0.5)), url, address, font_path, height, style="neon")
    return {"background": canvas.convert("RGB"), "highlight": _glow_frame(spots[0][2], spots[0][3], 16), "dot": _dot((140, 220, 255)),
            "cards": spots, "dots_at": (margin, int(height * 0.36))}


STYLES = {"aurore": render_aurore, "lumiere": render_lumiere, "mosaique": render_mosaique, "neon": render_neon}


def render(width=1920, height=1080, url="http://cadre-photo.local/upload", address="cadre-photo.local", font_path=None, style="aurore"):
    """Images du thème : {background, highlight, dot, cards (positions mises en valeur tour à tour), dots_at}."""
    return STYLES.get(style, render_aurore)(width, height, url, address, font_path)


def preview(width=1920, height=1080, step=0, **kwargs):
    """Image telle qu'affichée pendant le démarrage (une carte mise en valeur, points d'attente)."""
    parts = render(width, height, **kwargs)
    image = parts["background"].convert("RGBA")
    cx, cy, cw, ch = parts["cards"][step % len(parts["cards"])]
    highlight = parts["highlight"]
    if parts.get("per_card_highlight"):  # cartes de tailles différentes : un contour à la bonne taille
        highlight = _glow_frame(cw, ch, ch // 2)
    image.alpha_composite(highlight, (cx - (highlight.width - cw) // 2, cy - (highlight.height - ch) // 2))
    x, y = parts["dots_at"]
    for i in range(3):
        dot = parts["dot"].copy()
        if i != step % 3:
            dot.putalpha(dot.getchannel("A").point(lambda v: v // 3))
        image.alpha_composite(dot, (x + i * 40, y))
    return image.convert("RGB")


THEME_NAME = "cadre-photo"
CYCLE_FRAMES, DOT_FRAMES = 90, 25  # Plymouth rafraîchit 50 fois par seconde : une fonction toutes les 1,8 s


def export_theme(out_dir, width=1920, height=1080, url=None, address=None, font_path=None):
    """Écrit le thème Plymouth complet (images des 4 styles + script qui en choisit un au hasard) dans out_dir."""
    import socket
    host = socket.gethostname().lower().split(".")[0] or "cadre-photo"
    address = address or f"{host}.local"
    url = url or f"http://{address}/upload"
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    lines = []
    for s, style in enumerate(STYLES):
        parts = render(width, height, url=url, address=address, font_path=font_path, style=style)
        parts["background"].save(out / f"bg{s}.png", optimize=True)
        dot = parts["dot"]
        dot.save(out / f"dot{s}.png")
        faint = dot.copy()
        faint.putalpha(dot.getchannel("A").point(lambda v: v // 3))
        faint.save(out / f"dotf{s}.png")
        lines.append(f'bgfile[{s}] = "bg{s}.png"; dotfile[{s}] = "dot{s}.png"; dotffile[{s}] = "dotf{s}.png";')
        lines.append(f"ncards[{s}] = {len(parts['cards'])}; dotx[{s}] = {parts['dots_at'][0]}; doty[{s}] = {parts['dots_at'][1]};")
        for i, (cx, cy, cw, ch) in enumerate(parts["cards"]):
            highlight = _glow_frame(cw, ch, ch // 2) if parts.get("per_card_highlight") else parts["highlight"]
            highlight.save(out / f"hl{s}_{i}.png")
            k = s * 10 + i
            lines.append(f'hlfile[{k}] = "hl{s}_{i}.png"; hlx[{k}] = {cx - (highlight.width - cw) // 2}; '
                         f"hly[{k}] = {cy - (highlight.height - ch) // 2};")
        if parts.get("spinner"):
            parts["spinner"].save(out / f"spin{s}.png")
            lines.append(f'spinfile[{s}] = "spin{s}.png";')
        else:
            lines.append(f'spinfile[{s}] = "";')
    (out / f"{THEME_NAME}.script").write_text(PLYMOUTH_SCRIPT.format(
        nstyles=len(STYLES), width=width, height=height, cycle=CYCLE_FRAMES, dot=DOT_FRAMES, data="\n".join(lines)))
    (out / f"{THEME_NAME}.plymouth").write_text(
        "[Plymouth Theme]\nName=Cadre photo\nDescription=Votre cadre photo s'allume\nModuleName=script\n\n"
        f"[script]\nImageDir=/usr/share/plymouth/themes/{THEME_NAME}\n"
        f"ScriptFile=/usr/share/plymouth/themes/{THEME_NAME}/{THEME_NAME}.script\n")
    return out


# Script Plymouth : un style au hasard, fond mis à l'échelle de l'écran, fonction mise en valeur tour à tour,
# trois points d'attente (et l'anneau qui tourne pour le style lumière). Aucun message du système n'est affiché.
PLYMOUTH_SCRIPT = """# Thème « Cadre photo » (généré par utils/boot_screen.py : ne pas modifier à la main)
{data}

Window.SetBackgroundTopColor(0, 0, 0);
Window.SetBackgroundBottomColor(0, 0, 0);
style = Math.Int(Math.Random() * {nstyles});
if (style >= {nstyles}) style = {nstyles} - 1;
sw = Window.GetWidth();
sh = Window.GetHeight();
kx = sw / {width};
ky = sh / {height};

background.image = Image(bgfile[style]).Scale(sw, sh);
background.sprite = Sprite(background.image);
background.sprite.SetZ(-10);

for (i = 0; i < ncards[style]; i++) {{
    hl[i].image = Image(hlfile[style * 10 + i]);
    hl[i].image = hl[i].image.Scale(hl[i].image.GetWidth() * kx, hl[i].image.GetHeight() * ky);
    hl[i].sprite = Sprite(hl[i].image);
    hl[i].sprite.SetPosition(hlx[style * 10 + i] * kx, hly[style * 10 + i] * ky, 5);
    hl[i].sprite.SetOpacity(0);
}}

dot_on = Image(dotfile[style]);
dot_off = Image(dotffile[style]);
for (i = 0; i < 3; i++) {{
    dots[i] = Sprite(dot_off);
    dots[i].SetPosition((dotx[style] + i * 40) * kx, doty[style] * ky, 6);
}}

if (spinfile[style] != "") {{
    spin.image = Image(spinfile[style]);
    spin.sprite = Sprite(spin.image);
    spin.x = dotx[style] * kx + 140;
    spin.y = doty[style] * ky - 18;
}}

frame = 0;
fun refresh() {{
    frame++;
    step = Math.Int(frame / {cycle});
    card = step - Math.Int(step / ncards[style]) * ncards[style];
    phase = (frame - step * {cycle}) / {cycle};
    for (i = 0; i < ncards[style]; i++) {{
        if (i == card) {{
            opacity = 1;
            if (phase < 0.2) opacity = phase / 0.2;
            if (phase > 0.85) opacity = (1 - phase) / 0.15;
            hl[i].sprite.SetOpacity(opacity);
        }}
        else hl[i].sprite.SetOpacity(0);
    }}
    d = Math.Int(frame / {dot});
    d = d - Math.Int(d / 3) * 3;
    for (i = 0; i < 3; i++) {{
        if (i == d) dots[i].SetImage(dot_on);
        else dots[i].SetImage(dot_off);
    }}
    if (spinfile[style] != "") {{
        spin.sprite.SetImage(spin.image.Rotate(frame * 0.12));
        spin.sprite.SetPosition(spin.x, spin.y, 6);
    }}
}}
Plymouth.SetRefreshFunction(refresh);

# Pas de messages du système, pas de barre de progression : seulement l'écran du cadre.
fun no_message(text) {{ }}
Plymouth.SetMessageFunction(no_message);
"""


if __name__ == "__main__":
    import sys
    size = (sys.argv[2] if len(sys.argv) > 2 else "1920x1080").lower().split("x")
    print(export_theme(sys.argv[1] if len(sys.argv) > 1 else THEME_NAME, int(size[0]), int(size[1])))
