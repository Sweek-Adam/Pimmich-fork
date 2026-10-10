"""
Compositions de plusieurs photos sur un même écran (tableau en liège, polaroïds, mosaïque, pellicule,
mur de cadres, duo/triptyque, magazine, scrapbook, photomaton). Les messages peuvent y apparaître
sous forme de note (post-it, fiche) ou de case de texte.
"""
import math
import random
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageChops

from utils.message_renderer import N_, render_message, render_note, _textured, _gradient, _paste_with_shadow, _vignette

logger = logging.getLogger("pimmich.compositions")

PROJECT_DIR = Path(__file__).resolve().parent.parent
PHOTOS_DIR = PROJECT_DIR / "static" / "photos"
OUTPUT_DIR = PROJECT_DIR / "static" / "compositions"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")
VARIANT_SUFFIXES = ("_polaroid", "_postcard")

# --- Chargement des photos ---

def original_for(display_path):
    """Photo d'origine (pleine qualité, sans bandes floues) correspondant à un média préparé, si elle existe."""
    path = Path(display_path)
    stem = path.stem
    for suffix in VARIANT_SUFFIXES:
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    source = path.parent.name
    folder = PHOTOS_DIR / source
    if folder.is_dir():
        for ext in IMAGE_EXTENSIONS + (".JPG", ".JPEG", ".PNG"):
            candidate = folder / f"{stem}{ext}"
            if candidate.exists():
                return candidate
    return path.with_name(f"{stem}{path.suffix}") if path.with_name(f"{stem}{path.suffix}").exists() else path


def load_photo(display_path, max_side=1400):
    """Charge une photo réduite (décodage JPEG accéléré), orientée selon ses données EXIF."""
    for candidate in (original_for(display_path), Path(display_path)):
        try:
            with Image.open(candidate) as image:
                image.draft("RGB", (max_side, max_side))
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail((max_side, max_side), Image.LANCZOS)
                return image
        except Exception as e:
            logger.debug(f"Photo illisible pour une composition ({candidate}) : {e}")
    return None


def cover(image, width, height, focus_y=0.42):
    """Recadre pour remplir exactement width × height (centre légèrement remonté, souvent les visages)."""
    width, height = max(1, int(width)), max(1, int(height))
    scale = max(width / image.width, height / image.height)
    resized = image.resize((max(width, round(image.width * scale)), max(height, round(image.height * scale))), Image.LANCZOS)
    left = (resized.width - width) // 2
    top = int((resized.height - height) * focus_y)
    return resized.crop((left, top, left + width, top + height))


def fit_inside(image, max_w, max_h):
    scale = min(max_w / image.width, max_h / image.height)
    return image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.LANCZOS)


# --- Éléments graphiques ---

def framed(image, border, color=(255, 255, 255), bottom=None):
    """Tirage photo avec bordure (bottom plus large pour un polaroïd)."""
    bottom = border if bottom is None else bottom
    out = Image.new("RGBA", (image.width + 2 * border, image.height + border + bottom), color + (255,))
    out.paste(image, (border, border))
    return out


def rotated(element, angle):
    return element.rotate(angle, resample=Image.BICUBIC, expand=True)


def draw_pin(canvas, x, y, radius, rng):
    color = rng.choice([(214, 40, 40), (30, 110, 210), (40, 160, 70), (240, 180, 20), (150, 60, 190)])
    draw = ImageDraw.Draw(canvas)
    draw.ellipse([x - radius * 0.6 + radius * 0.5, y - radius * 0.6 + radius * 0.9, x + radius * 0.6 + radius * 0.5, y + radius * 0.6 + radius * 0.9],
                 fill=(0, 0, 0, 90))
    draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=color + (255,))
    shade = tuple(int(c * 0.7) for c in color)
    draw.ellipse([x - radius * 0.55, y - radius * 0.35, x + radius * 0.75, y + radius * 0.9], fill=shade + (255,))
    draw.ellipse([x - radius * 0.55, y - radius * 0.6, x - radius * 0.05, y - radius * 0.1], fill=(255, 255, 255, 170))


def tape_strip(length, thickness, rng):
    color = rng.choice([(245, 200, 210), (190, 225, 245), (250, 235, 160), (200, 235, 200), (230, 210, 250)])
    strip = Image.new("RGBA", (length, thickness), color + (190,))
    draw = ImageDraw.Draw(strip)
    for x in range(0, length, max(6, thickness // 2)):  # motif rayé du masking tape
        draw.line([(x, 0), (x + thickness // 2, thickness)], fill=(255, 255, 255, 60), width=max(2, thickness // 8))
    mask = strip.getchannel("A")
    mask_draw = ImageDraw.Draw(mask)
    step = max(3, thickness // 6)
    for y in range(0, thickness, step):  # bords déchirés
        mask_draw.polygon([(0, y), (rng.randrange(2, step + 3), y + step // 2), (0, y + step)], fill=0)
        mask_draw.polygon([(length, y), (length - rng.randrange(2, step + 3), y + step // 2), (length, y + step)], fill=0)
    strip.putalpha(mask)
    return strip


_texture_cache = {}


def texture(kind, width, height):
    """Textures de fond générées une fois par taille d'écran (le processus du diaporama les garde en mémoire)."""
    key = (kind, width, height)
    if key in _texture_cache:
        return _texture_cache[key].copy()
    rng = random.Random(kind)
    if kind == "cork":
        base = _gradient(width, height, (196, 150, 98), (176, 128, 80))
        layer = Image.new("RGB", (width, height))
        speck = Image.effect_noise((width // 3, height // 3), 120).resize((width, height)).convert("RGB")
        base = ImageChops.multiply(base, ImageChops.lighter(speck, Image.new("RGB", (width, height), (150, 150, 150))))
        result = _vignette(_textured(base, rng, 35), 0.35)
        frame = max(12, min(width, height) // 28)
        ImageDraw.Draw(result).rectangle([0, 0, width - 1, height - 1], outline=(110, 74, 40), width=frame)
    elif kind == "wood":
        result = Image.new("RGB", (width, height), (120, 78, 44))
        draw = ImageDraw.Draw(result)
        plank = max(60, height // 6)
        for y in range(0, height, plank):
            shade = rng.randrange(-14, 14)
            draw.rectangle([0, y, width, y + plank - 3], fill=(124 + shade, 80 + shade, 46 + shade // 2))
            for _ in range(30):  # veines
                yy = y + rng.randrange(plank)
                draw.line([(0, yy), (width, yy + rng.randrange(-8, 8))], fill=(104 + shade, 64 + shade, 34), width=rng.randrange(1, 3))
        result = _vignette(_textured(result.filter(ImageFilter.GaussianBlur(1.2)), rng, 18), 0.45)
    elif kind == "kraft":
        result = _vignette(_textured(_gradient(width, height, (206, 172, 128), (190, 154, 110)), rng, 28), 0.25)
    elif kind == "wall":
        result = _vignette(_textured(_gradient(width, height, (240, 236, 228), (226, 220, 210)), rng, 8), 0.2)
    elif kind == "dark":
        result = _vignette(_gradient(width, height, (36, 36, 40), (16, 16, 18)), 0.4)
    elif kind == "curtain":
        result = Image.new("RGB", (width, height), (120, 18, 28))
        draw = ImageDraw.Draw(result)
        fold = max(30, width // 28)
        for x in range(0, width, fold):
            draw.rectangle([x, 0, x + fold // 2, height], fill=(96, 12, 22))
        result = _vignette(result.filter(ImageFilter.GaussianBlur(fold // 3)), 0.5)
    else:
        result = Image.new("RGB", (width, height), (255, 255, 255))
    _texture_cache[key] = result
    return result.copy()


def _scatter_positions(count, width, height, rng, margin=0.2):
    """Positions réparties en rangées (la dernière, incomplète, est centrée), légèrement décalées au hasard."""
    cols = max(1, round(math.sqrt(count * width / height)))
    rows = math.ceil(count / cols)
    positions = []
    for r in range(rows):
        in_row = min(cols, count - r * cols)
        for i in range(in_row):
            cx = (i + 0.5) / in_row * width + rng.uniform(-1, 1) * width / cols * margin
            cy = (r + 0.5) / rows * height + rng.uniform(-1, 1) * height / rows * margin
            positions.append((cx, cy))
    rng.shuffle(positions)
    return positions, cols, rows


def _inside(center, element, W, H, pad=0.02):
    """Recentre un élément pour qu'il reste entièrement à l'écran."""
    px, py = W * pad, H * pad
    cx = min(max(center[0], element.width / 2 + px), W - element.width / 2 - px)
    cy = min(max(center[1], element.height / 2 + py), H - element.height / 2 - py)
    return cx, cy


def _note_or_tile(message, w, h, rng, kind="postit"):
    return render_note(message, int(w), int(h), kind, seed=rng.random())


# --- Formats ---

def corkboard(photos, message, W, H, rng):
    canvas = texture("cork", W, H).convert("RGBA")
    items = photos + ([message] if message else [])
    positions, cols, rows = _scatter_positions(len(items), W * 0.9, H * 0.84, rng, 0.18)
    cell = min(W * 0.9 / cols, H * 0.84 / rows)
    for (cx, cy), item in zip(positions, items):
        cx, cy = cx + W * 0.05, cy + H * 0.08
        if isinstance(item, dict):
            side = cell * 0.9
            element = _note_or_tile(item, side, side, rng, "postit")
        else:
            photo = fit_inside(item, cell * 1.2, cell * 1.0)
            element = framed(photo, max(6, int(cell * 0.035)))
        element = rotated(element, rng.uniform(-6, 6))
        cx, cy = _inside((cx, cy), element, W, H, 0.04)
        _paste_with_shadow(canvas, element, (cx, cy))
        draw_pin(canvas, cx, cy - element.height / 2 + cell * 0.06, max(7, int(cell * 0.035)), rng)
    return canvas.convert("RGB")


def polaroids(photos, message, W, H, rng):
    canvas = texture("wood", W, H).convert("RGBA")
    items = photos + ([message] if message else [])
    positions, cols, rows = _scatter_positions(len(items), W * 0.84, H * 0.78, rng, 0.32)
    side = min(W * 0.84 / cols, H * 0.78 / rows) * 1.02
    for (cx, cy), item in zip(positions, items):
        cx, cy = cx + W * 0.08, cy + H * 0.1
        if isinstance(item, dict):
            element = _note_or_tile(item, side * 0.95, side * 0.95, rng, "fiche")
        else:
            border = max(8, int(side * 0.05))
            element = framed(cover(item, side * 0.86, side * 0.86), border, (250, 250, 246), bottom=border * 4)
        element = rotated(element, rng.uniform(-14, 14))
        _paste_with_shadow(canvas, element, _inside((cx, cy), element, W, H))
    return canvas.convert("RGB")


MOSAIC_LAYOUTS = {  # cases (x, y, largeur, hauteur) en fraction de l'écran
    3: [[(0, 0, .62, 1), (.62, 0, .38, .5), (.62, .5, .38, .5)], [(0, 0, 1 / 3, 1), (1 / 3, 0, 1 / 3, 1), (2 / 3, 0, 1 / 3, 1)]],
    4: [[(0, 0, .5, .5), (.5, 0, .5, .5), (0, .5, .5, .5), (.5, .5, .5, .5)], [(0, 0, .5, 1), (.5, 0, .5, 1 / 3), (.5, 1 / 3, .5, 1 / 3), (.5, 2 / 3, .5, 1 / 3)]],
    5: [[(0, 0, .5, .6), (.5, 0, .5, .6), (0, .6, 1 / 3, .4), (1 / 3, .6, 1 / 3, .4), (2 / 3, .6, 1 / 3, .4)],
        [(0, 0, .4, 1), (.4, 0, .3, .5), (.7, 0, .3, .5), (.4, .5, .3, .5), (.7, .5, .3, .5)]],
    6: [[(i % 3 / 3, i // 3 / 2, 1 / 3, .5) for i in range(6)]],
}


def mosaic(photos, message, W, H, rng):
    items = photos + ([message] if message else [])
    layout = rng.choice(MOSAIC_LAYOUTS[len(items)])
    gutter = max(4, int(min(W, H) * 0.008))
    canvas = Image.new("RGB", (W, H), (250, 250, 250))
    rng.shuffle(items)
    for (x, y, w, h), item in zip(layout, items):
        bx, by = int(x * W) + gutter, int(y * H) + gutter
        bw, bh = int(w * W) - 2 * gutter, int(h * H) - 2 * gutter
        if isinstance(item, dict):
            tile = render_message(item.get("title"), item.get("body"), item.get("signature"), item.get("style", "nuit"), bw, bh)
        else:
            tile = cover(item, bw, bh)
        canvas.paste(tile, (bx, by))
    return canvas


def filmstrip(photos, message, W, H, rng):
    canvas = texture("dark", W, H).convert("RGBA")
    count = len(photos)
    strip_h = int(H * 0.5)
    hole = strip_h // 14
    frame_h = strip_h - 6 * hole
    frame_w = int(frame_h * 1.5)
    gap = hole * 2
    strip_w = count * (frame_w + gap) + gap
    strip = Image.new("RGBA", (strip_w, strip_h), (18, 16, 14, 255))
    draw = ImageDraw.Draw(strip)
    for x in range(hole, strip_w - hole, hole * 2):  # perforations
        for y in (hole, strip_h - 2 * hole):
            draw.rounded_rectangle([x, y, x + hole, y + hole], radius=hole // 4, fill=(230, 226, 214, 255))
    for i, photo in enumerate(photos):
        tile = cover(photo, frame_w, frame_h)
        tile = Image.blend(tile, ImageOps.colorize(ImageOps.grayscale(tile), (30, 20, 10), (255, 240, 210)), 0.15)  # teinte argentique
        strip.paste(tile, (gap + i * (frame_w + gap), 3 * hole))
    scale = min(1.0, W * 0.96 / strip_w)
    strip = strip.resize((int(strip_w * scale), int(strip_h * scale)), Image.LANCZOS)
    _paste_with_shadow(canvas, rotated(strip, rng.uniform(-3, 3)), (W / 2, H / 2))
    return canvas.convert("RGB")


GALLERY_LAYOUTS = {  # centres et tailles (fraction de la hauteur) des cadres
    3: [[(.28, .5, .5), (.62, .32, .3), (.62, .7, .3)], [(.2, .5, .38), (.5, .5, .55), (.8, .5, .38)]],
    4: [[(.24, .34, .36), (.24, .72, .3), (.56, .5, .55), (.84, .42, .32)], [(.2, .3, .3), (.2, .7, .34), (.55, .5, .62), (.85, .5, .36)]],
    5: [[(.16, .5, .34), (.4, .3, .32), (.4, .72, .3), (.66, .5, .52), (.88, .42, .3)]],
}


def gallery_wall(photos, message, W, H, rng):
    canvas = texture("wall", W, H).convert("RGBA")
    items = photos + ([message] if message else [])
    layout = rng.choice(GALLERY_LAYOUTS[len(items)])
    rng.shuffle(items)
    frame_color = rng.choice([(28, 28, 30), (120, 82, 50), (200, 170, 110), (245, 245, 245)])
    for (fx, fy, size), item in zip(layout, items):
        side = size * H
        if isinstance(item, dict):
            inner = render_message(item.get("title"), item.get("body"), item.get("signature"), item.get("style", "minimal"),
                                   int(side * 0.75), int(side * 0.95)).convert("RGB")
        else:
            portrait = item.height > item.width
            inner = cover(item, side * (0.72 if portrait else 1.0), side * (0.95 if portrait else 0.72))
        mat = framed(inner, max(10, int(side * 0.08)), (250, 248, 242))
        frame = framed(mat.convert("RGB"), max(6, int(side * 0.035)), frame_color)
        _paste_with_shadow(canvas, frame, (fx * W, fy * H))
    return canvas.convert("RGB")


def duo(photos, message, W, H, rng):
    count = len(photos)
    gap = max(6, int(W * 0.008))
    canvas = Image.new("RGB", (W, H), (12, 12, 12))
    width = (W - (count + 1) * gap) // count
    for i, photo in enumerate(photos):
        canvas.paste(cover(photo, width, H - 2 * gap), (gap + i * (width + gap), gap))
    return canvas


def magazine(photos, message, W, H, rng):
    canvas = Image.new("RGB", (W, H), (252, 251, 248))
    margin = int(min(W, H) * 0.05)
    big_w = int(W * 0.6)
    canvas.paste(cover(photos[0], big_w - margin, H - 2 * margin), (margin, margin))
    col_x = big_w + margin // 2
    col_w = W - col_x - margin
    col_h = (H - 3 * margin) // 2
    second = message if message else (photos[1] if len(photos) > 1 else photos[0])
    third = photos[2] if len(photos) > 2 else photos[-1]
    for i, item in enumerate([third, second]):
        y = margin + i * (col_h + margin)
        if isinstance(item, dict):
            tile = render_message(item.get("title"), item.get("body"), item.get("signature"), "minimal", col_w, col_h)
            ImageDraw.Draw(tile).rectangle([0, 0, col_w - 1, col_h - 1], outline=(30, 30, 30), width=2)
        else:
            tile = cover(item, col_w, col_h)
        canvas.paste(tile, (col_x, y))
    draw = ImageDraw.Draw(canvas)
    draw.line([(col_x - margin // 4, margin), (col_x - margin // 4, H - margin)], fill=(40, 40, 40), width=2)
    return canvas


def scrapbook(photos, message, W, H, rng):
    canvas = texture("kraft", W, H).convert("RGBA")
    items = photos + ([message] if message else [])
    positions, cols, rows = _scatter_positions(len(items), W * 0.86, H * 0.8, rng, 0.2)
    cell = min(W * 0.86 / cols, H * 0.8 / rows)
    for (cx, cy), item in zip(positions, items):
        cx, cy = cx + W * 0.07, cy + H * 0.1
        if isinstance(item, dict):
            element = _note_or_tile(item, cell * 0.9, cell * 0.9, rng, "postit")
        else:
            element = framed(fit_inside(item, cell * 1.15, cell * 0.98), max(6, int(cell * 0.03)))
        element = rotated(element, rng.uniform(-5, 5))
        cx, cy = _inside((cx, cy), element, W, H, 0.05)
        _paste_with_shadow(canvas, element, (cx, cy))
        tape_len, tape_thick = int(cell * 0.32), max(10, int(cell * 0.08))
        for corner in (-1, 1):  # deux bandes de masking tape aux coins supérieurs
            strip = rotated(tape_strip(tape_len, tape_thick, rng), corner * -35 + rng.uniform(-6, 6))
            sx = cx + corner * element.width * 0.42 - strip.width / 2
            sy = cy - element.height * 0.45 - strip.height / 2
            canvas.alpha_composite(strip, (int(sx), int(sy)))
    return canvas.convert("RGB")


def photobooth(photos, message, W, H, rng):
    canvas = texture("curtain", W, H).convert("RGBA")
    per_strip = 4
    strips = max(1, len(photos) // per_strip)
    strip_h = int(H * 0.9)
    pad = max(6, strip_h // 50)
    shot = (strip_h - (per_strip + 1) * pad - pad * 3) // per_strip
    strip_w = int(shot * 1.25) + 2 * pad
    for s in range(strips):
        strip = Image.new("RGBA", (strip_w, strip_h), (250, 250, 248, 255))
        for i in range(per_strip):
            photo = ImageOps.grayscale(cover(photos[s * per_strip + i], strip_w - 2 * pad, shot)).convert("RGB")
            strip.paste(photo, (pad, pad + i * (shot + pad)))
        cx = W * (s + 1) / (strips + 1)
        _paste_with_shadow(canvas, rotated(strip, rng.uniform(-4, 4)), (cx, H / 2))
    return canvas.convert("RGB")


# clé : (libellé, nombre de photos min, max, accepte un message, fonction)
FORMATS = {
    "liege": (N_("Tableau en liège"), 3, 5, True, corkboard),
    "polaroids": (N_("Polaroïds éparpillés"), 4, 6, True, polaroids),
    "mosaique": (N_("Mosaïque"), 3, 6, True, mosaic),
    "pellicule": (N_("Pellicule"), 3, 4, False, filmstrip),
    "mur": (N_("Mur de cadres"), 3, 5, True, gallery_wall),
    "duo": (N_("Duo / Triptyque"), 2, 3, False, duo),
    "magazine": (N_("Magazine"), 3, 3, True, magazine),
    "scrapbook": (N_("Scrapbook"), 3, 4, True, scrapbook),
    "photomaton": (N_("Photomaton"), 8, 12, False, photobooth),
}
LIMITS = {"mosaique": {3, 4, 5, 6}, "mur": {3, 4, 5}}


def compose(style, photo_paths, messages, width, height, rng=None, include_message=True):
    """
    Crée une composition. `photo_paths` : médias disponibles, `messages` : messages utilisables.
    Retourne l'image, ou None si le format n'a pas assez de photos lisibles.
    """
    rng = rng or random.Random()
    label, min_n, max_n, accepts_message, render = FORMATS[style]
    message = rng.choice(messages) if (accepts_message and include_message and messages and rng.random() < 0.6) else None
    takes_slot = message is not None and style in LIMITS  # le message occupe une case de la mise en page
    if style == "photomaton":
        wanted = 12 if len(photo_paths) >= 12 and width > height else 8
    elif style in LIMITS:
        wanted = rng.choice(sorted(LIMITS[style])) - (1 if takes_slot else 0)
    else:
        wanted = rng.randint(min_n, max_n)
    minimum = min_n - (1 if takes_slot else 0)

    candidates = list(photo_paths)
    rng.shuffle(candidates)
    photos, skipped = [], []
    for path in candidates:
        photo = load_photo(path, max_side=max(width, height) // (1 if wanted <= 3 else 2))
        if photo is None:
            continue
        if style == "duo" and photo.width > photo.height and len(skipped) < 6:
            skipped.append(photo)  # le duo met en valeur les photos en hauteur ; paysages en dernier recours
            continue
        photos.append(photo)
        if len(photos) == wanted:
            break
    if style == "duo":
        photos = (photos + skipped)[:wanted]
    if style in LIMITS:  # garder un nombre d'éléments qui correspond à une mise en page
        while photos and len(photos) + (1 if takes_slot else 0) not in LIMITS[style]:
            photos.pop()
    if style == "photomaton":
        photos = photos[: (len(photos) // 4) * 4]
    if len(photos) < max(minimum, 1):
        return None
    return render(photos, message, width, height, rng)


def enabled_formats(config):
    """Formats activés : tous sauf ceux décochés (un nouveau format est donc actif par défaut)."""
    disabled = config.get("compositions_disabled")
    if disabled is None and "compositions_styles" in config:  # ancien réglage (liste des formats cochés)
        disabled = [k for k in BASIC_FORMATS if k not in config["compositions_styles"]]
    return [k for k in FORMATS if k not in set(disabled or [])]


def compose_random(enabled_styles, photo_paths, messages, width, height, include_messages=True, rng=None, seasonal=True, today=None):
    """
    Choisit un format au hasard parmi ceux activés et crée la composition (None si impossible).
    Avec `seasonal`, les thèmes de saison ne sont proposés que pendant leur période, et y sont trois fois plus fréquents.
    """
    rng = rng or random.Random()
    weighted = []
    for style in enabled_styles:
        if style not in FORMATS:
            continue
        if seasonal and style in SEASONAL:
            if not in_season(style, today):
                continue
            weighted += [style] * 3
        else:
            weighted.append(style)
    tried = set()
    while weighted:
        style = rng.choice(weighted)
        weighted = [s for s in weighted if s != style]
        if style in tried:
            continue
        tried.add(style)
        try:
            image = compose(style, photo_paths, messages, width, height, rng, include_messages)
        except Exception as e:
            logger.warning(f"[Compositions] Échec du format {style} : {e}", exc_info=True)
            image = None
        if image is not None:
            return style, image
    return None, None


# Formats à thème (enregistrés ici : ces modules réutilisent les outils ci-dessus)
BASIC_FORMATS = list(FORMATS)
from utils.themed_compositions import THEMES as _THEMES, in_season, SEASONAL  # noqa: E402
from utils.themed_compositions_extra import THEMES as _THEMES_EXTRA  # noqa: E402
FORMATS.update(_THEMES)
FORMATS.update(_THEMES_EXTRA)
THEME_KEYS = list(_THEMES) + list(_THEMES_EXTRA)
