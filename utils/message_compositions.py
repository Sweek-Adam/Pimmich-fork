"""
Dispositions construites autour d'un message (texte, ou dessin d'invité) : lettre sur le bureau, porte du frigo,
carte postale, une de journal, conversation sur téléphone, fil à linge, livre ouvert...
Elles n'apparaissent que lorsqu'un message est à afficher (sans message, une autre disposition est choisie).
Les messages vocaux restent affichés seuls, en plein écran (c'est là que le cadre les lit).
"""
import math

from PIL import Image, ImageDraw, ImageOps

from utils import compositions as base
from utils.message_renderer import (N_, STYLES, PAINTERS, render_note, _card, _draw_text, _font, _gradient, _textured,
                                    _vignette, _paste_with_shadow, _has_cjk, _cjk_font, soft_blur,
                                    SANS, SANS_BOLD, SERIF_ITALIC, SERIF_BOLD_ITALIC, HAND, HAND2, MARKER, TYPEWRITER)

def _t(text):
    from utils import themed_compositions
    return themed_compositions._translate(text)


# --- Outils ---

def _style(name, **changes):
    return dict(STYLES[name], **changes)


def write(canvas, message, box, style):
    """Le message dans la boîte (x, y, largeur, hauteur) : son texte mis en page, ou le dessin de l'invité."""
    x, y, w, h = (int(v) for v in box)
    if w < 8 or h < 8:
        return
    if message.get("kind") == "drawing":
        note = render_note(message, w, h)
        if canvas.mode == "RGBA":
            canvas.alpha_composite(note, (x, y))
        else:
            canvas.paste(note, (x, y), note)
        return
    title, body, signature = (message.get(k) or "" for k in ("title", "body", "signature"))
    if _has_cjk(title, body, signature) and _cjk_font():
        style = dict(style, fonts=(_cjk_font(),) * 3, dash="－")
    _draw_text(canvas, style, title.strip(), body.strip(), signature.strip(), (x, y, w, h))


def sheet(message, w, h, style_name):
    """Feuille (RGBA) d'un style de message, ou le dessin sur sa carte blanche."""
    return base.message_tile(message, int(w), int(h), style_name).convert("RGBA")


def paper(w, h, color=(252, 250, 244), radius=0):
    card = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle([0, 0, card.width - 1, card.height - 1], radius=radius, fill=color + (255,))
    return card


def polaroid(photo, side):
    border = max(6, int(side * 0.05))
    return base.framed(base.print_photo(photo, side * 0.86, side * 0.86), border, (250, 250, 246), bottom=border * 4).convert("RGBA")


def printed(photo, w, h, border=None, color=(255, 255, 255)):
    border = border if border is not None else max(5, int(min(w, h) * 0.035))
    return base.framed(base.fit_inside(photo, w, h), border, color).convert("RGBA")


def rounded(photo, w, h, radius):
    tile = base.cell_photo(photo, int(w), int(h)).convert("RGBA")
    mask = Image.new("L", tile.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, tile.width - 1, tile.height - 1], radius=int(radius), fill=255)
    tile.putalpha(mask)
    return tile


def magnet(canvas, x, y, r, color):
    draw = ImageDraw.Draw(canvas)
    draw.ellipse([x - r + 2, y - r + 3, x + r + 2, y + r + 3], fill=(0, 0, 0, 70))
    draw.ellipse([x - r, y - r, x + r, y + r], fill=color + (255,))
    draw.ellipse([x - r * 0.55, y - r * 0.65, x - r * 0.05, y - r * 0.25], fill=(255, 255, 255, 110))


def place(canvas, element, center, tilt=0, rng=None, shadow=True):
    if tilt and rng:
        element = base.rotated(element, rng.uniform(-tilt, tilt))
    W, H = canvas.size
    _paste_with_shadow(canvas, element, base._inside(center, element, W, H, 0.02), shadow)
    return element


def column_centers(n, x0, x1):
    return [x0 + (x1 - x0) * (i + 0.5) / n for i in range(n)]


def _photo_or_none(photos, i):
    return photos[i % len(photos)] if photos else None


# --- Dispositions ---

def desk_letter(photos, message, W, H, rng):
    """Lettre sur le bureau : une lettre manuscrite et des polaroïds posés à côté."""
    canvas = base.texture("wood", W, H).convert("RGBA")
    lh = H * 0.84
    letter = sheet(message, lh * 0.74, lh, "lettre")
    place(canvas, letter, (W * 0.3, H * 0.5), 4, rng)
    side = min(W * 0.3, H * 0.44)
    for i, (cx, cy) in enumerate([(0.72, 0.3), (0.82, 0.68), (0.62, 0.72)][:len(photos)]):
        place(canvas, polaroid(photos[i], side), (W * cx, H * cy), 10, rng)
    return canvas.convert("RGB")


def kitchen_chalkboard(photos, message, W, H, rng):
    """Ardoise de cuisine : le message à la craie, les photos aimantées à côté."""
    canvas = base.texture("kraft", W, H).convert("RGBA")
    bw, bh = W * 0.56, H * 0.8
    board = base.framed(base.message_tile(message, int(bw), int(bh), "ardoise"), max(10, int(H * 0.025)), (120, 80, 46)).convert("RGBA")
    place(canvas, board, (W * 0.32, H * 0.5))
    n = len(photos)
    for i, cy in enumerate(column_centers(n, H * 0.08, H * 0.92)):
        tile = printed(photos[i], W * 0.3, H * 0.84 / n * 0.9)
        place(canvas, tile, (W * 0.8, cy), 5, rng)
        magnet(canvas, W * 0.8, cy - tile.height * 0.45, max(8, int(H * 0.018)), rng.choice([(220, 60, 60), (60, 140, 220), (250, 190, 40), (90, 180, 90)]))
    return canvas.convert("RGB")


def fridge(photos, message, W, H, rng):
    """Porte du frigo : photos et post-it tenus par des aimants de couleur."""
    canvas = _gradient(W, H, (236, 238, 240), (210, 214, 218)).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle([W * 0.95, H * 0.3, W * 0.975, H * 0.7], radius=int(W * 0.01), fill=(180, 184, 190, 255))  # poignée
    items = photos + [message]
    positions, cols, rows = base._scatter_positions(len(items), W * 0.84, H * 0.8, rng, 0.2)
    cell = min(W * 0.84 / cols, H * 0.8 / rows)
    colors = [(230, 70, 70), (70, 150, 230), (250, 200, 50), (110, 190, 100), (190, 110, 210)]
    for (cx, cy), item in zip(positions, items):
        cx, cy = cx + W * 0.05, cy + H * 0.1
        if isinstance(item, dict):
            element = render_note(item, int(cell * 0.95), int(cell * 0.95), "postit", seed=rng.random())
        else:
            element = printed(item, cell * 1.1, cell * 0.95)
        element = place(canvas, element, (cx, cy), 5, rng)
        magnet(canvas, cx, cy - element.height * 0.42, max(9, int(cell * 0.06)), rng.choice(colors))
    return canvas.convert("RGB")


def postcard_back(photos, message, W, H, rng):
    """Carte postale : le dos écrit à la main, avec timbre et cachet, sur la photo de la carte."""
    canvas = base.blurred_fill(photos[0], W, H).convert("RGBA")
    cw, ch = min(W * 0.78, H * 1.25), min(H * 0.78, W * 0.52)
    if len(photos) > 1:
        front = printed(photos[1], cw * 0.8, ch * 0.8, color=(250, 250, 246))
        place(canvas, front, (W * 0.38, H * 0.42), 0, None)
    card = paper(cw, ch, (246, 238, 220), radius=int(ch * 0.02))
    draw = ImageDraw.Draw(card)
    draw.line([(cw * 0.56, ch * 0.1), (cw * 0.56, ch * 0.9)], fill=(150, 130, 110, 255), width=2)
    for k in range(4):
        y = ch * (0.5 + k * 0.1)
        draw.line([(cw * 0.6, y), (cw * 0.94, y)], fill=(170, 150, 130, 255), width=2)
    stamp = base.cell_photo(photos[0], int(cw * 0.14), int(cw * 0.17)).convert("RGBA")
    stamp = base.framed(stamp.convert("RGB"), max(4, int(cw * 0.012)), (255, 255, 255)).convert("RGBA")
    card.alpha_composite(stamp, (int(cw * 0.94 - stamp.width), int(ch * 0.08)))
    cx, cy, r = cw * 0.72, ch * 0.24, cw * 0.07
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(60, 60, 110, 170), width=3)
    for k in range(3):
        draw.arc([cx + r * 0.6, cy - r * 0.6 + k * r * 0.4, cx + r * 3.4, cy + r * 0.2 + k * r * 0.4], 200, 340, fill=(60, 60, 110, 150), width=3)
    write(card, message, (cw * 0.05, ch * 0.08, cw * 0.47, ch * 0.84), _style("carte", fonts=(HAND2, HAND2, HAND2), frame=False))
    place(canvas, card, (W * 0.54, H * 0.56), 4, rng)
    return canvas.convert("RGB")


def envelope(photos, message, W, H, rng):
    """Lettre dans l'enveloppe : la lettre dépasse, des photos glissées autour."""
    canvas = base.texture("kraft", W, H).convert("RGBA")
    ew, eh = W * 0.5, H * 0.42
    letter = sheet(message, ew * 0.88, H * 0.66, "lettre")
    canvas.alpha_composite(letter, (int(W / 2 - letter.width / 2), int(H * 0.06)))
    env = paper(ew, eh, (236, 226, 204), radius=6)
    draw = ImageDraw.Draw(env)
    draw.line([(0, 0), (ew / 2, eh * 0.55), (ew, 0)], fill=(196, 182, 156, 255), width=3)
    draw.line([(0, eh), (ew * 0.42, eh * 0.48)], fill=(210, 198, 174, 255), width=2)
    draw.line([(ew, eh), (ew * 0.58, eh * 0.48)], fill=(210, 198, 174, 255), width=2)
    _paste_with_shadow(canvas, env, (W / 2, H * 0.98 - eh / 2))
    side = min(W * 0.24, H * 0.4)
    for i, (cx, cy) in enumerate([(0.13, 0.32), (0.87, 0.32), (0.13, 0.76)][:len(photos)]):
        place(canvas, polaroid(photos[i], side), (W * cx, H * cy), 12, rng)
    return canvas.convert("RGB")


def newspaper(photos, message, W, H, rng):
    """À la une : le message en gros titre du journal de la famille, les photos en noir et blanc."""
    canvas = _textured(_gradient(W, H, (244, 240, 230), (232, 226, 212)), rng, 10).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    m = int(min(W, H) * 0.04)
    ink = (30, 28, 26)
    masthead = _t(N_("La Gazette de la famille"))
    size = int(H * 0.09)
    font = _font(SERIF_BOLD_ITALIC, size)
    while draw.textlength(masthead, font=font) > W - 2 * m and size > 14:
        size = int(size * 0.9)
        font = _font(SERIF_BOLD_ITALIC, size)
    draw.text((W / 2, m + size * 0.6), masthead, font=font, fill=ink, anchor="mm")
    top = m + size * 1.3
    draw.line([(m, top), (W - m, top)], fill=ink, width=3)
    draw.line([(m, top + 6), (W - m, top + 6)], fill=ink, width=1)
    top += m * 0.6
    n = len(photos)
    article_w = W * (0.48 if n else 0.92)
    write(canvas, message, (m, top, article_w - m, H - top - m), _style("clair", text=ink, accent=ink, fonts=(SERIF_BOLD_ITALIC, SERIF_ITALIC, SERIF_ITALIC), align="left"))
    if n:
        x0 = article_w + m * 0.5
        draw.line([(x0 - m * 0.25, top), (x0 - m * 0.25, H - m)], fill=ink, width=1)
        ph = (H - top - m - (n - 1) * m * 0.5) / n
        for i, photo in enumerate(photos):
            tile = ImageOps.grayscale(base.cell_photo(photo, int(W - x0 - m), int(ph))).convert("RGB")
            canvas.paste(tile, (int(x0), int(top + i * (ph + m * 0.5))))
    return canvas.convert("RGB")


def telegram(photos, message, W, H, rng):
    """Télégramme : le message tapé à la machine sur un formulaire, avec des photos sépia."""
    canvas = base.texture("dark", W, H).convert("RGBA")
    tw, th = W * 0.5, H * 0.74
    form = sheet(message, tw, th, "machine") if message.get("kind") == "drawing" else None
    if form is None:
        form = PAINTERS["old_paper"](int(tw), int(th), rng).convert("RGBA")
        draw = ImageDraw.Draw(form)
        band = th * 0.14
        draw.rectangle([0, 0, tw, band], fill=(170, 40, 36, 255))
        f = _font(TYPEWRITER, int(band * 0.5))
        draw.text((tw / 2, band / 2), _t(N_("TÉLÉGRAMME")), font=f, fill=(250, 244, 230, 255), anchor="mm")
        write(form, message, (tw * 0.08, band + th * 0.06, tw * 0.84, th - band - th * 0.12), STYLES["machine"])
    place(canvas, form, (W * 0.32, H * 0.5), 3, rng)
    side = min(W * 0.3, H * 0.42)
    for i, (cx, cy) in enumerate([(0.79, 0.28), (0.79, 0.72)][:len(photos)]):
        p = ImageOps.colorize(ImageOps.grayscale(base.print_photo(photos[i], side, side * 0.8)), (50, 32, 18), (250, 232, 200))
        place(canvas, base.framed(p, max(6, int(side * 0.04)), (244, 236, 220)).convert("RGBA"), (W * cx, H * cy), 8, rng)
    return canvas.convert("RGB")


def neon_wall(photos, message, W, H, rng):
    """Néon : le message en lettres lumineuses sur un mur de briques, les photos accrochées dessous."""
    canvas = PAINTERS["bricks"](W, H, rng).convert("RGBA")
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 90))
    canvas.alpha_composite(shade)
    write(canvas, message, (W * 0.08, H * 0.06, W * 0.84, H * 0.48), STYLES["neon"])
    n = len(photos)
    side = min(W * 0.84 / n, H * 0.36)
    for i, cx in enumerate(column_centers(n, W * 0.08, W * 0.92)):
        tile = base.framed(base.print_photo(photos[i], side * 0.9, side * 0.8), max(5, int(side * 0.04)), (20, 20, 22)).convert("RGBA")
        place(canvas, tile, (cx, H * 0.76), 3, rng)
    return canvas.convert("RGB")


def travel_journal(photos, message, W, H, rng):
    """Carnet de voyage : à gauche le mot écrit à la main, à droite les photos scotchées."""
    canvas = base.texture("kraft", W, H).convert("RGBA")
    m = min(W, H) * 0.06
    pw, ph = (W - 2 * m) / 2, H - 2 * m
    for k in range(2):
        page = paper(pw, ph, (250, 246, 236))
        if k == 0:
            lines = PAINTERS["lined_paper"](int(pw), int(ph), rng).convert("RGBA")
            page.alpha_composite(lines)
            write(page, message, (pw * 0.1, ph * 0.1, pw * 0.8, ph * 0.8), _style("lettre", align="center"))
        canvas.alpha_composite(page, (int(m + k * pw), int(m)))
    shade = Image.new("RGBA", (int(m * 0.8), int(ph)), (0, 0, 0, 50))
    canvas.alpha_composite(soft_blur(shade, m * 0.2), (int(W / 2 - m * 0.4), int(m)))
    n = len(photos)
    for i, cy in enumerate(column_centers(n, m * 1.4, H - m * 1.4)):
        tile = printed(photos[i], pw * 0.78, (ph * 0.86) / n * 0.92)
        element = place(canvas, tile, (W * 0.75, cy), 5, rng)
        strip = base.rotated(base.tape_strip(int(pw * 0.2), max(10, int(H * 0.025)), rng), rng.uniform(-8, 8))
        canvas.alpha_composite(strip, (int(W * 0.75 - strip.width / 2), int(cy - element.height / 2 - strip.height / 2)))
    return canvas.convert("RGB")


def golden_frame(photos, message, W, H, rng):
    """Le message encadré d'or au centre, les photos dans des cadres autour."""
    canvas = base.texture("wall", W, H).convert("RGBA")
    mw, mh = W * 0.4, H * 0.5
    inner = base.message_tile(message, int(mw), int(mh), "clair")
    mat = base.framed(inner, max(10, int(mh * 0.06)), (250, 246, 236))
    frame = base.framed(mat, max(8, int(mh * 0.05)), (196, 158, 70)).convert("RGBA")
    place(canvas, frame, (W / 2, H / 2))
    spots = [(0.15, 0.27), (0.85, 0.73), (0.85, 0.27), (0.15, 0.73)]
    side = min(W * 0.24, H * 0.36)
    for i, (cx, cy) in enumerate(spots[:len(photos)]):
        p = base.framed(base.print_photo(photos[i], side, side * 0.78), max(6, int(side * 0.05)), (250, 248, 242))
        place(canvas, base.framed(p, max(4, int(side * 0.03)), (40, 34, 30)).convert("RGBA"), (W * cx, H * cy))
    return canvas.convert("RGB")


def speech_bubbles(photos, message, W, H, rng):
    """Bulles : les photos en médaillons, le message dans une bulle de bande dessinée."""
    canvas = PAINTERS["halftone"](W, H, rng).convert("RGBA")
    n = len(photos)
    d = int(min(W / (n + 1.6), H * 0.42))
    for i, cx in enumerate(column_centers(n, W * 0.06, W * 0.94)):
        medal = base_shape(photos[i], d)
        place(canvas, medal, (cx, H * 0.74 + (i % 2) * H * 0.04))
    bw, bh = int(W * 0.62), int(H * 0.56)
    if message.get("kind") == "drawing":
        bubble = render_note(message, int(bh * 1.2), bh)
    else:
        bubble = _card(STYLES["bulle"], bw, bh, *(message.get(k) or "" for k in ("title", "body", "signature")))
    place(canvas, bubble, (W * 0.52, H * 0.3), 2, rng)
    return canvas.convert("RGB")


def base_shape(photo, d, shape="circle", ring_colors=((255, 255, 255), (235, 235, 235))):
    from utils.themed_compositions import _shaped
    return _shaped(photo, (d, d), shape, ring=max(4, d // 30), ring_colors=ring_colors)


def clothesline(photos, message, W, H, rng):
    """Fil à linge : photos et carte du message suspendues par des pinces à linge."""
    canvas = _gradient(W, H, (178, 214, 240), (232, 244, 250)).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    sag = H * 0.06
    y_line = lambda x: H * 0.26 + sag * math.sin(math.pi * x / W)
    draw.line([(x, y_line(x)) for x in range(0, W + 1, max(1, W // 60))], fill=(90, 70, 50, 255), width=max(2, H // 300))
    items = photos[:]
    items.insert(len(items) // 2, message)
    weights = [1.7 if isinstance(item, dict) else 1 for item in items]
    cell = min(W * 0.92 / sum(weights), H * 0.6)
    centers, x = [], W * 0.04
    for weight in weights:
        centers.append(x + cell * weight / 2)
        x += cell * weight
    shift = (W - x - W * 0.04) / 2
    for i, (item, cx) in enumerate(zip(items, [c + shift for c in centers])):
        if isinstance(item, dict):
            element = render_note(item, int(cell * 1.6), int(cell * 1.15), "fiche", seed=rng.random())
        else:
            element = polaroid(item, cell * 0.98)
        element = base.rotated(element, rng.uniform(-6, 6))
        top = y_line(cx)
        _paste_with_shadow(canvas, element, (cx, top + element.height / 2 - cell * 0.02))
        pw, ph = max(6, int(cell * 0.05)), max(14, int(cell * 0.16))
        ImageDraw.Draw(canvas).rounded_rectangle([cx - pw, top - ph * 0.4, cx + pw, top + ph * 0.6], radius=pw // 2, fill=(196, 150, 96, 255))
    return canvas.convert("RGB")


def hearts(photos, message, W, H, rng):
    """Cœurs : les photos en forme de cœur autour du message."""
    canvas = _gradient(W, H, (255, 228, 236), (250, 200, 214)).convert("RGBA")
    mw, mh = W * 0.42, H * 0.56
    write(canvas, message, (W / 2 - mw / 2, H / 2 - mh / 2, mw, mh), _style("pastel", text=(110, 40, 70), accent=(200, 50, 100)))
    side = int(min(W * 0.26, H * 0.42))
    spots = [(0.16, 0.36), (0.84, 0.64), (0.84, 0.3), (0.16, 0.72)]
    for i, (cx, cy) in enumerate(spots[:len(photos)]):
        heart = base_shape(photos[i], side, "heart", ((255, 120, 160), (220, 60, 110)))
        place(canvas, heart, (W * cx, H * cy), 8, rng, shadow=True)
    return canvas.convert("RGB")


def postit_wall(photos, message, W, H, rng):
    """Mur de post-it : un grand post-it pour le message, au milieu des photos et de petits post-it de couleur."""
    canvas = base.texture("wall", W, H).convert("RGBA")
    colors = [(255, 236, 120), (255, 190, 210), (180, 230, 255), (200, 245, 180)]
    small = int(min(W, H) * 0.09)
    for _ in range(14):
        note = paper(small, small, rng.choice(colors))
        place(canvas, note, (rng.uniform(0.05, 0.95) * W, rng.uniform(0.05, 0.95) * H), 12, rng, shadow=False)
    side = min(W, H) * 0.52
    note = render_note(message, int(side), int(side), "postit", seed=rng.random())
    place(canvas, note, (W * 0.5, H * 0.5), 4, rng)
    spots = [(0.16, 0.3), (0.84, 0.7), (0.84, 0.28), (0.16, 0.74)]
    ps = min(W * 0.26, H * 0.4)
    for i, (cx, cy) in enumerate(spots[:len(photos)]):
        place(canvas, printed(photos[i], ps, ps), (W * cx, H * cy), 6, rng)
    return canvas.convert("RGB")


def chat(photos, message, W, H, rng):
    """Conversation : un téléphone où le message et les photos arrivent comme des bulles de discussion."""
    canvas = base.blurred_fill(photos[0], W, H).convert("RGBA")
    canvas.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 70)))
    ph = H * 0.92
    pw = min(ph * 0.5, W * 0.9)
    phone = paper(pw, ph, (24, 24, 28), radius=int(pw * 0.12))
    sm = pw * 0.04
    screen = paper(pw - 2 * sm, ph - 2 * sm, (236, 229, 221), radius=int(pw * 0.09))
    sw, sh = screen.size
    draw = ImageDraw.Draw(screen)
    header = sh * 0.09
    draw.rounded_rectangle([0, 0, sw, header], radius=int(pw * 0.09), fill=(7, 94, 84, 255))
    who = (message.get("signature") or "").strip() or _t(N_("Message"))
    draw.text((sw * 0.08, header * 0.55), who[:24], font=_font(SANS_BOLD, int(header * 0.32)), fill=(255, 255, 255, 255), anchor="lm")
    y = header + sh * 0.03
    for photo in photos[:1]:
        bubble = rounded(photo, sw * 0.7, sh * 0.3, sw * 0.04)
        screen.alpha_composite(bubble, (int(sw * 0.05), int(y)))
        y += bubble.height + sh * 0.025
    bh = sh - y - sh * 0.04
    if bh > sh * 0.15:
        bubble = paper(sw * 0.84, bh, (220, 248, 198), radius=int(sw * 0.05))
        write(bubble, message, (sw * 0.05, bh * 0.06, sw * 0.74, bh * 0.88), _style("clair", fonts=(SANS_BOLD, SANS, SERIF_ITALIC), text=(30, 30, 30), accent=(7, 94, 84)))
        screen.alpha_composite(bubble, (int(sw * 0.11), int(y)))
    phone.alpha_composite(screen, (int(sm), int(sm)))
    place(canvas, phone, (W / 2, H / 2))
    return canvas.convert("RGB")


def folded_card(photos, message, W, H, rng):
    """Carte pliée : la photo à gauche, le message à l'intérieur à droite."""
    canvas = _gradient(W, H, (60, 66, 90), (30, 32, 44)).convert("RGBA")
    ch = H * 0.82
    cw = min(ch * 0.72, W * 0.42)
    left = base.cell_photo(photos[0], int(cw), int(ch)).convert("RGBA")
    shade = Image.linear_gradient("L").rotate(90).resize(left.size)
    left.alpha_composite(Image.merge("RGBA", (*Image.new("RGB", left.size, (0, 0, 0)).split(), shade.point(lambda v: v * 0.25))))
    right = paper(cw, ch, (252, 249, 242))
    write(right, message, (cw * 0.1, ch * 0.1, cw * 0.8, ch * 0.8), _style("carte", frame=False))
    card = Image.new("RGBA", (int(cw * 2), int(ch)), (0, 0, 0, 0))
    card.alpha_composite(left, (0, 0))
    card.alpha_composite(right, (int(cw), 0))
    ImageDraw.Draw(card).line([(cw, 0), (cw, ch)], fill=(200, 196, 188, 255), width=2)
    place(canvas, card, (W / 2, H / 2))
    return canvas.convert("RGB")


def giant_polaroid(photos, message, W, H, rng):
    """Polaroïd géant : le message écrit dans la marge blanche, d'autres polaroïds à côté."""
    canvas = base.texture("wood", W, H).convert("RGBA")
    side = min(H * 0.56, W * 0.42)
    border = max(10, int(side * 0.05))
    margin = int(side * 0.62)
    pic = base.print_photo(photos[0], side, side)
    card = Image.new("RGBA", (pic.width + 2 * border, pic.height + border + margin), (250, 250, 246, 255))
    card.paste(pic, (border, border))
    write(card, message, (border * 2, pic.height + border * 1.4, card.width - border * 4, margin - border * 1.2),
          _style("lettre", text=(30, 30, 60), accent=(30, 30, 60), align="center"))
    place(canvas, card, (W * (0.38 if len(photos) > 1 else 0.5), H * 0.5), 4, rng)
    small = min(W * 0.26, H * 0.4)
    for i, (cx, cy) in enumerate([(0.8, 0.32), (0.8, 0.72)][:len(photos) - 1]):
        place(canvas, polaroid(photos[i + 1], small), (W * cx, H * cy), 10, rng)
    return canvas.convert("RGB")


def open_book(photos, message, W, H, rng):
    """Livre ouvert : la photo sur la page de gauche, le message sur celle de droite."""
    canvas = base.texture("dark", W, H).convert("RGBA")
    bh = H * 0.84
    pw = min(bh * 0.72, W * 0.45)
    cover = paper(pw * 2 + 24, bh + 24, (90, 30, 34), radius=10)
    _paste_with_shadow(canvas, cover, (W / 2, H / 2))
    for k in range(2):
        page = paper(pw, bh, (250, 244, 228))
        if k == 0:
            pic = base.framed(base.print_photo(photos[0], pw * 0.8, bh * 0.78), max(4, int(pw * 0.015)), (255, 255, 255)).convert("RGBA")
            page.alpha_composite(pic, (int((pw - pic.width) / 2), int((bh - pic.height) / 2)))
        else:
            write(page, message, (pw * 0.12, bh * 0.1, pw * 0.76, bh * 0.8), _style("carte", frame=False, text=(60, 44, 30)))
        gutter = Image.linear_gradient("L").rotate(90 if k == 0 else -90).resize((int(pw * 0.12), int(bh))).point(lambda v: v * 0.35)
        page.alpha_composite(Image.merge("RGBA", (*Image.new("RGB", gutter.size, (0, 0, 0)).split(), gutter)), (int(pw - pw * 0.12) if k == 0 else 0, 0))
        canvas.alpha_composite(page, (int(W / 2 - pw + k * pw), int(H / 2 - bh / 2)))
    return canvas.convert("RGB")


def poster(photos, message, W, H, rng):
    """Affiche : une grande photo et le message en titre lumineux, entouré d'ampoules."""
    canvas = Image.new("RGBA", (W, H), (14, 12, 16, 255))
    m = int(min(W, H) * 0.05)
    pic = base.cell_photo(photos[0], W - 2 * m, int(H * 0.6)).convert("RGBA")
    canvas.alpha_composite(pic, (m, m))
    fade = Image.linear_gradient("L").resize((W - 2 * m, int(H * 0.2)))
    canvas.alpha_composite(Image.merge("RGBA", (*Image.new("RGB", fade.size, (14, 12, 16)).split(), fade)), (m, int(m + H * 0.4)))
    write(canvas, message, (m * 2, H * 0.62, W - 4 * m, H * 0.33), _style("festif", text=(255, 236, 190), accent=(255, 200, 80), shadow=False, glow=True))
    draw = ImageDraw.Draw(canvas)
    r = max(3, m // 6)
    step = m * 0.9
    for x in range(int(m / 2), W, int(step)):
        for y in (m / 3, H - m / 3):
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 220, 140, 255))
    for y in range(int(m / 2), H, int(step)):
        for x in (m / 3, W - m / 3):
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 220, 140, 255))
    return canvas.convert("RGB")


def stamp(photo, w, h):
    """Photo en timbre-poste (bord dentelé)."""
    border = max(8, int(min(w, h) * 0.08))
    inner = base.cell_photo(photo, int(w - 2 * border), int(h - 2 * border))
    tile = Image.new("RGBA", (int(w), int(h)), (255, 255, 255, 255))
    tile.paste(inner, (border, border))
    mask = Image.new("L", tile.size, 255)
    draw = ImageDraw.Draw(mask)
    r = border * 0.42
    for x in range(0, tile.width + 1, int(r * 2.6)):
        for y in (0, tile.height):
            draw.ellipse([x - r, y - r, x + r, y + r], fill=0)
    for y in range(0, tile.height + 1, int(r * 2.6)):
        for x in (0, tile.width):
            draw.ellipse([x - r, y - r, x + r, y + r], fill=0)
    tile.putalpha(mask)
    return tile


def airmail(photos, message, W, H, rng):
    """Par avion : le message sur une enveloppe à bord rayé, les photos en timbres."""
    canvas = base.texture("wall", W, H).convert("RGBA")
    ew, eh = W * 0.6, H * 0.6
    env = paper(ew, eh, (252, 250, 245))
    draw = ImageDraw.Draw(env)
    band = max(10, int(eh * 0.05))
    k = 0
    for x in range(-int(eh), int(ew + eh), band * 2):
        color = (200, 40, 50, 255) if k % 2 == 0 else (30, 60, 150, 255)
        k += 1
        for edge in (0, eh - band):
            draw.polygon([(x, edge), (x + band, edge), (x + band + band, edge + band), (x + band, edge + band)], fill=color)
    write(env, message, (ew * 0.1, band * 2.2, ew * 0.8, eh - band * 4.4), _style("clair", fonts=(HAND2, HAND2, HAND2), text=(30, 40, 90), accent=(180, 40, 50)))
    place(canvas, env, (W / 2, H / 2), 3, rng)
    spots = [(0.12, 0.2), (0.88, 0.8), (0.88, 0.22), (0.12, 0.78), (0.5, 0.1)]
    s = min(W, H) * 0.24
    for i, (cx, cy) in enumerate(spots[:len(photos)]):
        place(canvas, stamp(photos[i], s * 0.84, s), (W * cx, H * cy), 10, rng)
    return canvas.convert("RGB")


def minimal_half(photos, message, W, H, rng):
    """Épuré : la photo d'un côté, le message de l'autre, en lettres fines."""
    canvas = Image.new("RGBA", (W, H), (252, 252, 250, 255))
    portrait = H > W
    if portrait:
        canvas.alpha_composite(base.cell_photo(photos[0], W, int(H * 0.55)).convert("RGBA"), (0, 0))
        box = (W * 0.1, H * 0.6, W * 0.8, H * 0.34)
    else:
        canvas.alpha_composite(base.cell_photo(photos[0], int(W * 0.55), H).convert("RGBA"), (0, 0))
        box = (W * 0.6, H * 0.14, W * 0.34, H * 0.72)
    write(canvas, message, box, STYLES["minimal"])
    return canvas.convert("RGB")


def triptych(photos, message, W, H, rng):
    """Triptyque : une photo, le message, une photo."""
    canvas = Image.new("RGBA", (W, H), (14, 14, 16, 255))
    gap = max(6, int(W * 0.008))
    pw = (W - 4 * gap) / 3
    for i in range(3):
        x = int(gap + i * (pw + gap))
        if i == 1:
            tile = base.message_tile(message, int(pw), H - 2 * gap, message.get("style") or "nuit")
        else:
            tile = base.cell_photo(photos[0 if i == 0 else -1], int(pw), H - 2 * gap)
        canvas.paste(tile, (x, gap))
    return canvas.convert("RGB")


def starry_night(photos, message, W, H, rng):
    """Nuit étoilée : les photos en lunes lumineuses, le message au milieu des étoiles."""
    from utils.themed_compositions import _star
    canvas = _gradient(W, H, (10, 14, 40), (40, 26, 76)).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    for _ in range(140):
        x, y, r = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0.6, 2.4)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 240, int(rng.uniform(90, 255))))
    for _ in range(6):
        x, y, r = rng.uniform(0, W), rng.uniform(0, H * 0.16), rng.uniform(H * 0.01, H * 0.02)
        draw.polygon(_star(x, y, r, r * 0.45), fill=(255, 230, 150, 230))
    write(canvas, message, (W * 0.26, H * 0.2, W * 0.48, H * 0.6), STYLES["nuit"])
    d = int(min(W * 0.22, H * 0.36))
    spots = [(0.13, 0.32), (0.87, 0.68), (0.87, 0.3), (0.13, 0.72)]
    for i, (cx, cy) in enumerate(spots[:len(photos)]):
        medal = base_shape(photos[i], d, "circle", ((255, 236, 170), (240, 200, 110)))
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([W * cx - d * 0.62, H * cy - d * 0.62, W * cx + d * 0.62, H * cy + d * 0.62], fill=(255, 220, 140, 90))
        canvas.alpha_composite(soft_blur(glow, d * 0.12))
        place(canvas, medal, (W * cx, H * cy), shadow=False)
    return canvas.convert("RGB")


def watercolor(photos, message, W, H, rng):
    """Aquarelle : fond peint, photos à bord blanc et le message écrit au pinceau."""
    canvas = PAINTERS["watercolor"](W, H, rng).convert("RGBA")
    write(canvas, message, (W * 0.3, H * 0.18, W * 0.4, H * 0.64), STYLES["pastel"])
    spots = [(0.15, 0.3), (0.85, 0.7), (0.85, 0.3), (0.15, 0.72)]
    side = min(W * 0.26, H * 0.4)
    for i, (cx, cy) in enumerate(spots[:len(photos)]):
        place(canvas, printed(photos[i], side, side, border=max(8, int(side * 0.06))), (W * cx, H * cy), 7, rng)
    return canvas.convert("RGB")


def playing_cards(photos, message, W, H, rng):
    """Jeu de cartes : les photos en cartes à jouer en éventail, le message sur la carte du dessus."""
    canvas = _vignette(_textured(_gradient(W, H, (30, 110, 60), (16, 80, 42)), rng, 14), 0.45).convert("RGBA")
    ch = H * 0.62
    cw = ch * 0.68
    suits = ["♥", "♦", "♣", "♠"]
    n = len(photos)
    for i, photo in enumerate(photos):
        card = paper(cw, ch, (255, 255, 255), radius=int(cw * 0.06))
        pic = base.cell_photo(photo, int(cw * 0.82), int(ch * 0.74)).convert("RGBA")
        card.alpha_composite(pic, (int(cw * 0.09), int(ch * 0.13)))
        suit = suits[i % 4]
        ImageDraw.Draw(card).text((cw * 0.1, ch * 0.065), suit, font=_font(SANS_BOLD, int(ch * 0.06)),
                                  fill=(200, 30, 40, 255) if suit in "♥♦" else (20, 20, 20, 255), anchor="mm")
        angle = (i - (n - 1) / 2) * 12
        element = base.rotated(card, -angle)
        _paste_with_shadow(canvas, element, (W * 0.38 + (i - (n - 1) / 2) * cw * 0.42, H * 0.54 + abs(i - (n - 1) / 2) * H * 0.03))
    top = paper(cw * 1.1, ch * 1.1, (255, 252, 244), radius=int(cw * 0.06))
    write(top, message, (cw * 0.1, ch * 0.1, cw * 0.9, ch * 0.9), _style("clair", accent=(200, 30, 40)))
    place(canvas, top, (W * 0.78, H * 0.5), 6, rng)
    return canvas.convert("RGB")


def museum(photos, message, W, H, rng):
    """Musée : les photos encadrées d'or, le message sur le cartel de l'exposition."""
    canvas = _vignette(_textured(_gradient(W, H, (96, 30, 36), (70, 20, 26)), rng, 8), 0.35).convert("RGBA")
    n = len(photos)
    side = min(W * 0.62 / n, H * 0.56)
    for i, cx in enumerate(column_centers(n, W * 0.04, W * 0.66)):
        p = base.framed(base.print_photo(photos[i], side, side * 0.85), max(6, int(side * 0.05)), (244, 240, 230))
        frame = base.framed(p, max(8, int(side * 0.06)), (186, 146, 60)).convert("RGBA")
        place(canvas, frame, (cx, H * 0.42))
        label = paper(side * 0.5, side * 0.12, (244, 240, 230))
        place(canvas, label, (cx, H * 0.42 + frame.height / 2 + side * 0.12), shadow=False)
    cw, ch = W * 0.28, H * 0.58
    placard = paper(cw, ch, (248, 245, 238))
    write(placard, message, (cw * 0.1, ch * 0.08, cw * 0.8, ch * 0.84), _style("clair", fonts=(SERIF_BOLD_ITALIC, SERIF_ITALIC, SERIF_ITALIC), align="left"))
    place(canvas, placard, (W * 0.83, H * 0.5))
    return canvas.convert("RGB")


def stories(photos, message, W, H, rng):
    """Stories : trois écrans verticaux, le message au milieu, avec leurs barres de progression."""
    canvas = _gradient(W, H, (36, 30, 60), (12, 10, 20)).convert("RGBA")
    ph = H * 0.88
    pw = min(ph * 9 / 16, W * 0.3)
    xs = column_centers(3, W / 2 - pw * 1.65, W / 2 + pw * 1.65)
    for i, cx in enumerate(xs):
        if i == 1:
            panel = _gradient(int(pw), int(ph), (214, 51, 108), (255, 145, 77)).convert("RGBA")
            mask = Image.new("L", panel.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, panel.width - 1, panel.height - 1], radius=int(pw * 0.06), fill=255)
            panel.putalpha(mask)
            write(panel, message, (pw * 0.1, ph * 0.12, pw * 0.8, ph * 0.76), STYLES["festif"])
        else:
            panel = rounded(photos[0 if i == 0 else -1], pw, ph, pw * 0.06)
        draw = ImageDraw.Draw(panel)
        for k in range(3):
            x0 = pw * 0.05 + k * pw * 0.3
            draw.rounded_rectangle([x0, ph * 0.02, x0 + pw * 0.28, ph * 0.02 + 4], radius=2,
                                   fill=(255, 255, 255, 240 if k <= i else 110))
        place(canvas, panel, (cx, H / 2 + (0 if i == 1 else H * 0.02)))
    return canvas.convert("RGB")


def typewriter(photos, message, W, H, rng):
    """Machine à écrire : le message tapé sur la feuille, les photos attachées par des trombones."""
    canvas = base.texture("wood", W, H).convert("RGBA")
    sw, sh = W * 0.44, H * 0.66
    page = sheet(message, sw, sh, "machine")
    canvas.alpha_composite(page, (int(W * 0.34 - sw / 2), int(H * 0.04)))
    draw = ImageDraw.Draw(canvas)
    bx0, by0, bx1, by1 = W * 0.34 - sw * 0.68, H * 0.62, W * 0.34 + sw * 0.68, H * 0.98
    draw.rounded_rectangle([bx0, by0, bx1, by1], radius=int(H * 0.04), fill=(34, 36, 40, 255))
    draw.rectangle([bx0 - W * 0.02, by0 - H * 0.03, bx1 + W * 0.02, by0 + H * 0.02], fill=(20, 20, 22, 255))
    kr = max(6, int(H * 0.018))
    for row in range(3):
        for col in range(10):
            x = bx0 + (bx1 - bx0) * (col + 1.2 + row * 0.3) / 12.2
            y = by0 + (by1 - by0) * (0.3 + row * 0.22)
            draw.ellipse([x - kr, y - kr, x + kr, y + kr], fill=(230, 226, 214, 255), outline=(80, 80, 84, 255), width=2)
    side = min(W * 0.28, H * 0.4)
    for i, (cx, cy) in enumerate([(0.8, 0.28), (0.8, 0.72)][:len(photos)]):
        element = place(canvas, printed(photos[i], side, side), (W * cx, H * cy), 6, rng)
        x, y = W * cx - element.width * 0.3, H * cy - element.height / 2
        clip_w, clip_h = max(10, int(side * 0.06)), max(30, int(side * 0.2))
        draw.rounded_rectangle([x, y - clip_h * 0.3, x + clip_w, y + clip_h * 0.7], radius=clip_w // 2, outline=(170, 174, 180, 255), width=max(2, clip_w // 4))
    return canvas.convert("RGB")


def ribbon(photos, message, W, H, rng):
    """Ruban : les photos alignées, le message sur un ruban qui les traverse."""
    canvas = base.texture("wall", W, H).convert("RGBA")
    n = len(photos)
    side = min(W * 0.9 / n, H * 0.52)
    for i, cx in enumerate(column_centers(n, W * 0.05, W * 0.95)):
        place(canvas, polaroid(photos[i], side), (cx, H * 0.36), 7, rng)
    rh = H * 0.3
    band = Image.new("RGBA", (W, int(rh)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(band)
    notch = rh * 0.5
    color = (196, 40, 60, 255)
    draw.polygon([(0, 0), (W * 0.1, 0), (W * 0.1, rh), (0, rh), (notch * 0.6, rh / 2)], fill=(150, 26, 44, 255))
    draw.polygon([(W, 0), (W * 0.9, 0), (W * 0.9, rh), (W, rh), (W - notch * 0.6, rh / 2)], fill=(150, 26, 44, 255))
    draw.rectangle([W * 0.07, rh * 0.08, W * 0.93, rh * 0.92], fill=color)
    write(band, message, (W * 0.12, rh * 0.14, W * 0.76, rh * 0.72), _style("festif", shadow=False))
    _paste_with_shadow(canvas, band, (W / 2, H * 0.78))
    return canvas.convert("RGB")


def tickets(photos, message, W, H, rng):
    """Billets souvenirs : le message sur un grand billet, les photos sur des billets plus petits."""
    canvas = _gradient(W, H, (24, 34, 66), (12, 18, 38)).convert("RGBA")

    def ticket(w, h, color):
        card = paper(w, h, color, radius=int(h * 0.06))
        mask = card.getchannel("A")
        draw = ImageDraw.Draw(mask)
        r = h * 0.09
        for x in (w * 0.78,):
            draw.ellipse([x - r, -r, x + r, r], fill=0)
            draw.ellipse([x - r, h - r, x + r, h + r], fill=0)
        card.putalpha(mask)
        d = ImageDraw.Draw(card)
        for y in range(int(h * 0.12), int(h * 0.9), max(8, int(h * 0.06))):
            d.line([(w * 0.78, y), (w * 0.78, y + h * 0.03)], fill=(120, 110, 100, 255), width=2)
        return card

    tw, th = W * 0.56, H * 0.42
    big = ticket(tw, th, (250, 236, 200))
    write(big, message, (tw * 0.06, th * 0.1, tw * 0.66, th * 0.8), _style("clair", fonts=(MARKER, HAND, HAND), accent=(170, 40, 40)))
    ImageDraw.Draw(big).text((tw * 0.89, th / 2), "★", font=_font(SANS_BOLD, int(th * 0.3)), fill=(170, 40, 40, 255), anchor="mm")
    place(canvas, big, (W * 0.5, H * 0.3), 3, rng)
    n = len(photos)
    sw, sh = min(W * 0.9 / n, W * 0.32), min(H * 0.34, W * 0.9 / n * 0.62)
    for i, cx in enumerate(column_centers(n, W * 0.05, W * 0.95)):
        small = ticket(sw, sh, (255, 255, 255))
        pic = base.cell_photo(photos[i], int(sw * 0.7), int(sh * 0.8)).convert("RGBA")
        small.alpha_composite(pic, (int(sw * 0.04), int(sh * 0.1)))
        place(canvas, small, (cx, H * 0.76), 6, rng)
    return canvas.convert("RGB")


def dedication(photos, message, W, H, rng):
    """Photo dédicacée : la photo en grand, le message écrit au feutre par-dessus."""
    canvas = base.cell_photo(photos[0], W, H).convert("RGBA")
    fade = Image.linear_gradient("L").resize((W, int(H * 0.55)))
    canvas.alpha_composite(Image.merge("RGBA", (*Image.new("RGB", fade.size, (0, 0, 0)).split(), fade.point(lambda v: v * 0.7))), (0, int(H * 0.45)))
    if message.get("kind") == "drawing":
        side = int(min(W, H) * 0.42)
        place(canvas, render_note(message, side, side), (W * 0.8, H * 0.72), 6, rng)
    else:
        write(canvas, message, (W * 0.08, H * 0.56, W * 0.84, H * 0.38),
              _style("festif", fonts=(MARKER, MARKER, MARKER), text=(255, 255, 255), accent=(255, 230, 150)))
    return canvas.convert("RGB")


def diagonal(photos, message, W, H, rng):
    """Diagonale : la photo et le message séparés par une diagonale de couleur."""
    canvas = base.cell_photo(photos[0], W, H).convert("RGBA")
    color = rng.choice([(28, 40, 70), (120, 30, 60), (20, 80, 70), (240, 236, 226)])
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon([(W * 0.62, 0), (W, 0), (W, H), (W * 0.36, H)], fill=255)
    panel = Image.new("RGBA", (W, H), color + (240,))
    canvas.paste(panel, (0, 0), mask)
    light = sum(color) > 600
    style = _style("clair" if light else "nuit", shadow=False)
    write(canvas, message, (W * 0.6, H * 0.14, W * 0.34, H * 0.72), style)
    if len(photos) > 1:
        small = printed(photos[1], W * 0.22, H * 0.3)
        place(canvas, small, (W * 0.2, H * 0.8), 6, rng)
    return canvas.convert("RGB")


def tape_board(photos, message, W, H, rng):
    """Planche de croquis : le message et les photos scotchés sur du papier quadrillé."""
    canvas = _gradient(W, H, (250, 250, 246), (240, 240, 234)).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    step = max(20, int(min(W, H) * 0.04))
    for x in range(0, W, step):
        draw.line([(x, 0), (x, H)], fill=(200, 220, 236, 255), width=1)
    for y in range(0, H, step):
        draw.line([(0, y), (W, y)], fill=(200, 220, 236, 255), width=1)
    items = photos + [message]
    positions, cols, rows = base._scatter_positions(len(items), W * 0.86, H * 0.8, rng, 0.2)
    cell = min(W * 0.86 / cols, H * 0.8 / rows)
    for (cx, cy), item in zip(positions, items):
        cx, cy = cx + W * 0.07, cy + H * 0.1
        if isinstance(item, dict):
            element = paper(cell * 1.05, cell * 0.9, (255, 255, 255))
            write(element, item, (cell * 0.08, cell * 0.08, cell * 0.89, cell * 0.74), _style("lettre", align="center"))
        else:
            element = printed(item, cell * 1.1, cell * 0.95)
        element = place(canvas, element, (cx, cy), 5, rng)
        strip = base.rotated(base.tape_strip(int(cell * 0.34), max(10, int(cell * 0.08)), rng), rng.uniform(-10, 10))
        canvas.alpha_composite(strip, (int(cx - strip.width / 2), int(cy - element.height / 2 - strip.height / 2)))
    return canvas.convert("RGB")


def window_view(photos, message, W, H, rng):
    """Fenêtre : la photo vue à travers une fenêtre, le message sur la buée de la vitre."""
    canvas = base.cell_photo(photos[0], W, H).convert("RGBA")
    fog = soft_blur(canvas, min(W, H) * 0.02)
    fog.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 80)))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rectangle([W * 0.52, H * 0.08, W * 0.94, H * 0.92], fill=255)
    canvas.paste(fog, (0, 0), mask)
    write(canvas, message, (W * 0.56, H * 0.14, W * 0.34, H * 0.72), _style("clair", fonts=(HAND2, HAND2, HAND2), text=(255, 255, 255), accent=(255, 255, 255), shadow=True))
    draw = ImageDraw.Draw(canvas)
    t = max(10, int(min(W, H) * 0.03))
    wood = (240, 238, 232, 255)
    for x in (W * 0.06, W * 0.5, W * 0.94):
        draw.rectangle([x - t / 2, H * 0.06, x + t / 2, H * 0.94], fill=wood)
    for y in (H * 0.06, H * 0.94):
        draw.rectangle([W * 0.06, y - t / 2, W * 0.94, y + t / 2], fill=wood)
    draw.rectangle([W * 0.06, H * 0.5 - t / 2, W * 0.5, H * 0.5 + t / 2], fill=wood)
    return canvas.convert("RGB")


# clé : (libellé, nombre de photos min, max, accepte un message, fonction) — un message est obligatoire
FORMATS = {
    "msg_bureau": (N_("Lettre sur le bureau"), 2, 3, True, desk_letter),
    "msg_ardoise": (N_("Ardoise de cuisine"), 2, 3, True, kitchen_chalkboard),
    "msg_frigo": (N_("Porte du frigo"), 3, 5, True, fridge),
    "msg_carte_postale": (N_("Dos de carte postale"), 1, 2, True, postcard_back),
    "msg_enveloppe": (N_("Lettre dans l'enveloppe"), 2, 3, True, envelope),
    "msg_journal": (N_("À la une du journal"), 2, 3, True, newspaper),
    "msg_telegramme": (N_("Télégramme"), 2, 2, True, telegram),
    "msg_neon": (N_("Néon sur briques"), 2, 4, True, neon_wall),
    "msg_carnet": (N_("Carnet de voyage"), 2, 3, True, travel_journal),
    "msg_cadre_dore": (N_("Message encadré d'or"), 2, 4, True, golden_frame),
    "msg_bulles": (N_("Bulle de bande dessinée"), 2, 4, True, speech_bubbles),
    "msg_fil": (N_("Fil à linge"), 3, 4, True, clothesline),
    "msg_coeurs": (N_("Cœurs"), 2, 4, True, hearts),
    "msg_postits": (N_("Mur de post-it"), 2, 4, True, postit_wall),
    "msg_conversation": (N_("Conversation sur téléphone"), 1, 1, True, chat),
    "msg_carte_pliee": (N_("Carte pliée"), 1, 1, True, folded_card),
    "msg_polaroid": (N_("Polaroïd géant"), 1, 3, True, giant_polaroid),
    "msg_livre": (N_("Livre ouvert"), 1, 1, True, open_book),
    "msg_affiche": (N_("Affiche de cinéma"), 1, 1, True, poster),
    "msg_par_avion": (N_("Par avion"), 2, 5, True, airmail),
    "msg_epure": (N_("Épuré"), 1, 1, True, minimal_half),
    "msg_triptyque": (N_("Triptyque avec message"), 2, 2, True, triptych),
    "msg_nuit": (N_("Nuit étoilée"), 2, 4, True, starry_night),
    "msg_aquarelle": (N_("Aquarelle"), 2, 4, True, watercolor),
    "msg_cartes": (N_("Jeu de cartes"), 3, 4, True, playing_cards),
    "msg_musee": (N_("Musée"), 2, 3, True, museum),
    "msg_stories": (N_("Stories"), 2, 2, True, stories),
    "msg_machine": (N_("Machine à écrire"), 1, 2, True, typewriter),
    "msg_ruban": (N_("Ruban"), 3, 4, True, ribbon),
    "msg_billets": (N_("Billets souvenirs"), 2, 4, True, tickets),
    "msg_dedicace": (N_("Photo dédicacée"), 1, 1, True, dedication),
    "msg_diagonale": (N_("Diagonale"), 1, 2, True, diagonal),
    "msg_croquis": (N_("Papier quadrillé"), 2, 4, True, tape_board),
    "msg_fenetre": (N_("Buée sur la fenêtre"), 1, 1, True, window_view),
}
