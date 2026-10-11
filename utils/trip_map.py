"""
Cartes dessinées pour le cadre (Pillow, hors ligne) : carte d'un voyage avec son trajet et quelques photos,
souvenir « il y a un an », récapitulatif des voyages d'une année (pays visités en couleur).
Projection de Mercator, fond Natural Earth (utils/world.py) ; rendu en double résolution puis réduit (bords lisses).
"""
import math
from functools import lru_cache

import numpy as np

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from utils import world
from utils.message_renderer import _cjk_font, _font, _has_cjk, SANS, SANS_BOLD

OCEAN = (205, 225, 236)
LAND = (246, 242, 233)
VISITED = (247, 205, 160)
BORDER = (196, 186, 170)
ROUTE = (214, 76, 52)
PIN = (214, 76, 52)
HOME = (52, 120, 190)
INK = (38, 40, 48)
MAX_LAT = 82.0
SCALE = 2  # rendu en double résolution


def _project(lat, lon):
    """Coordonnées de Mercator normalisées (0..1, y vers le bas)."""
    lat = max(-MAX_LAT, min(MAX_LAT, lat))
    y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    return (lon + 180) / 360, 0.5 - y / (2 * math.pi)


def view_for(points, width, height, padding=0.35, min_span_deg=7.0, region=(0.0, 0.0, 1.0, 1.0)):
    """Fenêtre (x0, y0, x1, y1) en coordonnées projetées pour une image width×height, telle que ces points (lat, lon)
    tiennent dans `region` (fractions de l'image : gauche, haut, droite, bas) ; le reste de l'image montre la suite de la
    carte (place pour les photos et le titre)."""
    if not points:
        x0, y0 = _project(72, -170)
        x1, y1 = _project(-56, 190)
    else:
        xs, ys = zip(*(_project(lat, lon) for lat, lon in points))
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    span = max(x1 - x0, y1 - y0, min_span_deg / 360)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w = max(x1 - x0, span) * (1 + 2 * padding)
    h = max(y1 - y0, span * 0.6) * (1 + 2 * padding)
    rx0, ry0, rx1, ry1 = region
    target = (width * (rx1 - rx0)) / (height * (ry1 - ry0))
    if w / h < target:
        w = h * target
    else:
        h = w / target
    total_w, total_h = w / (rx1 - rx0), h / (ry1 - ry0)
    left, top = cx - w / 2 - rx0 * total_w, cy - h / 2 - ry0 * total_h
    return left, top, left + total_w, top + total_h


@lru_cache(maxsize=1)
def _projected():
    """Contours des pays en coordonnées de Mercator, calculés une fois : [(iso, [(x0, y0, x1, y1, [anneaux numpy])])]."""
    found = []
    for country in world.countries():
        polygons = []
        for polygon in country["polygons"]:
            rings = []
            for ring in polygon:
                arr = np.asarray(ring, dtype=np.float64)
                lat = np.radians(np.clip(arr[:, 1], -MAX_LAT, MAX_LAT))
                rings.append(np.column_stack(((arr[:, 0] + 180) / 360, 0.5 - np.log(np.tan(np.pi / 4 + lat / 2)) / (2 * np.pi))))
            outer = rings[0]
            polygons.append((outer[:, 0].min(), outer[:, 1].min(), outer[:, 0].max(), outer[:, 1].max(), rings))
        found.append((country["iso"], polygons))
    return found


def draw_base(width, height, view, highlight=()):
    """Fond de carte : mers, terres, pays mis en valeur (codes ISO), frontières."""
    W, H = width * SCALE, height * SCALE
    x0, y0, x1, y1 = view
    sx, sy = W / (x1 - x0), H / (y1 - y0)
    image = Image.new("RGB", (W, H), OCEAN)
    draw = ImageDraw.Draw(image)
    border = max(1, int(SCALE * width / 1400))
    min_size = 1.5 / sx  # plus petit qu'un pixel et demi : invisible
    for offset in (-1, 0, 1):  # la carte peut déborder de l'antiméridien
        for iso, polygons in _projected():
            fill = VISITED if iso in highlight else LAND
            for px0, py0, px1, py1, rings in polygons:
                if px1 + offset < x0 or px0 + offset > x1 or py1 < y0 or py0 > y1:
                    continue
                if px1 - px0 < min_size and py1 - py0 < min_size:
                    continue
                for i, ring in enumerate(rings):
                    pts = ((ring + (offset - x0, -y0)) * (sx, sy)).ravel().tolist()
                    if len(pts) >= 6:
                        draw.polygon(pts, fill=OCEAN if i else fill, outline=BORDER, width=border)
    return image


def _to_px(view, width, height, lat, lon):
    x0, y0, x1, y1 = view
    px, py = _project(lat, lon)
    return (px - x0) / (x1 - x0) * width * SCALE, (py - y0) / (y1 - y0) * height * SCALE


def draw_route(image, view, width, height, route, home=None, lines=True):
    """Trajet (pointillés entre les étapes, dans l'ordre) et épingles ; la maison en bleu si elle est visible."""
    draw = ImageDraw.Draw(image)
    s = SCALE * width / 1920
    points = [_to_px(view, width, height, lat, lon) for lat, lon in route]
    for (ax, ay), (bx, by) in zip(points, points[1:]) if lines else ():
        length = math.hypot(bx - ax, by - ay)
        steps = max(1, int(length / (22 * s)))
        for k in range(steps):
            if k % 2 == 0:
                t0, t1 = k / steps, min(1, (k + 1) / steps)
                draw.line([(ax + (bx - ax) * t0, ay + (by - ay) * t0), (ax + (bx - ax) * t1, ay + (by - ay) * t1)],
                          fill=ROUTE, width=max(2, int(5 * s)))
    if home:
        hx, hy = _to_px(view, width, height, *home)
        if 0 <= hx <= image.width and 0 <= hy <= image.height:
            r = 11 * s
            draw.ellipse([hx - r, hy - r, hx + r, hy + r], fill=HOME, outline=(255, 255, 255), width=max(2, int(4 * s)))
    # Épingles : ombre douce (floutée autour de chaque épingle seulement), cercle blanc, centre coloré ;
    # la première et la dernière un peu plus grandes
    for i, (x, y) in enumerate(points):
        r = (22 if lines and i in (0, len(points) - 1) else 18 if not lines else 15) * s
        blur = 8 * s
        pad = int(r + blur * 3)
        shadow = Image.new("L", (pad * 2, pad * 2), 0)
        ImageDraw.Draw(shadow).ellipse([pad - r, pad - r + 5 * s, pad + r, pad + r + 5 * s], fill=110)
        image.paste((0, 0, 0), (int(x) - pad, int(y) - pad), shadow.filter(ImageFilter.GaussianBlur(blur)))
    draw = ImageDraw.Draw(image)
    for i, (x, y) in enumerate(points):
        r = (22 if lines and i in (0, len(points) - 1) else 18 if not lines else 15) * s
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255))
        draw.ellipse([x - r * 0.62, y - r * 0.62, x + r * 0.62, y + r * 0.62], fill=PIN)
    return image


def _font_for(text, name, size):
    cjk = _cjk_font() if _has_cjk(text) else None
    return _font(cjk or name, size)


def _fit(draw, text, name, size, max_width, min_size=18):
    font = _font_for(text, name, size)
    while size > min_size and draw.textlength(text, font=font) > max_width:
        size = int(size * 0.92)
        font = _font_for(text, name, size)
    return font


def _photo_frame(path, size, angle):
    """Photo façon tirage : bord blanc, légère rotation, ombre."""
    try:
        with Image.open(path) as photo:
            photo = ImageOps.fit(photo.convert("RGB"), size)
    except (OSError, ValueError):
        return None
    border = max(6, size[0] // 22)
    framed = ImageOps.expand(photo, border=border, fill=(255, 255, 255)).convert("RGBA")
    framed = framed.rotate(angle, resample=Image.BICUBIC, expand=True)
    pad = border * 3
    shadow = Image.new("RGBA", (framed.width + pad * 2, framed.height + pad * 2), (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 110), (pad, pad + border), framed.split()[3])
    shadow = shadow.filter(ImageFilter.GaussianBlur(border))
    shadow.alpha_composite(framed, (pad, pad))
    return shadow


def card(width, height, trip, photos=(), title="", lines=(), banner="", home=None, highlight=None):
    """Carte d'un voyage : le trajet sur la carte (à gauche), quelques photos (à droite), le titre en bas à gauche."""
    route = list(trip.get("route") or [])
    if not route and trip.get("lat") is not None:
        route = [(trip["lat"], trip["lon"])]
    region = (0.04, 0.06, 0.56, 0.66) if photos else (0.06, 0.06, 0.94, 0.66)  # au-dessus du titre, à côté des photos
    view = view_for(route, width, height, region=region)
    isos = highlight if highlight is not None else {c["iso"] for c in trip.get("countries") or []}
    image = draw_base(width, height, view, isos)
    image = draw_route(image, view, width, height, route, home)
    image = image.resize((width, height), Image.LANCZOS).convert("RGBA")
    _photos(image, photos, width, height)
    _caption(image, title, lines, banner, width, height)
    return image.convert("RGB")


def year_card(width, height, trips, title="", lines=(), home=None):
    """Récapitulatif d'une année : tous les voyages (épingles), pays visités en couleur."""
    spots = [(t["lat"], t["lon"]) for t in trips if t.get("lat") is not None]
    view = view_for(spots + ([home] if home else []), width, height, padding=0.15, min_span_deg=40,
                    region=(0.03, 0.04, 0.97, 0.72))
    isos = {c["iso"] for t in trips for c in t.get("countries") or []}
    image = draw_base(width, height, view, isos)
    spots = [(t["lat"], t["lon"]) for t in sorted(trips, key=lambda t: t["start"]) if t.get("lat") is not None]
    image = draw_route(image, view, width, height, spots, home, lines=False)  # une épingle par voyage, sans trajet
    image = image.resize((width, height), Image.LANCZOS).convert("RGBA")
    _caption(image, title, lines, "", width, height)
    return image.convert("RGB")


def _photos(image, photos, width, height):
    photos = [p for p in photos if p][:3]
    if not photos:
        return
    size = int(height * 0.36)
    spots = [(0.80, 0.27, -4), (0.72, 0.57, 3), (0.86, 0.66, -2)][:len(photos)]
    for path, (fx, fy, angle) in zip(photos, spots):
        framed = _photo_frame(path, (int(size * 1.25), size), angle)
        if framed is not None:
            image.alpha_composite(framed, (int(width * fx - framed.width / 2), int(height * fy - framed.height / 2)))


def _caption(image, title, lines, banner, width, height):
    """Titre, lignes d'informations et bandeau (« Il y a un an ») en bas à gauche, sur un cartouche clair."""
    if not title:
        return
    margin = int(height * 0.05)
    draw = ImageDraw.Draw(image)
    max_width = int(width * 0.52)
    title_font = _fit(draw, title, SANS_BOLD, int(height * 0.075), max_width)
    small = int(height * 0.034)
    banner_font = _font_for(banner, SANS_BOLD, int(height * 0.03)) if banner else None
    line_fonts = [_fit(draw, line, SANS, small, max_width) for line in lines]
    inner = int(height * 0.03)
    heights = ([int(height * 0.03) + inner // 2] if banner else []) + [int(title_font.size * 1.15)] + [int(small * 1.35)] * len(lines)
    box_h = sum(heights) + inner * 2
    box_w = max([draw.textlength(title, font=title_font)] + [draw.textlength(l, font=f) for l, f in zip(lines, line_fonts)]
                + ([draw.textlength(banner, font=banner_font)] if banner else [])) + inner * 2
    x, y = margin, height - margin - box_h
    panel = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(panel).rounded_rectangle([x, y, x + box_w, y + box_h], radius=inner, fill=(255, 255, 255, 225))
    image.alpha_composite(panel)
    draw = ImageDraw.Draw(image)
    ty = y + inner
    if banner:
        draw.text((x + inner, ty), banner.upper(), font=banner_font, fill=ROUTE)
        ty += heights[0]
    draw.text((x + inner, ty), title, font=title_font, fill=INK)
    ty += int(title_font.size * 1.15)
    for line, font in zip(lines, line_fonts):
        draw.text((x + inner, ty + small * 0.15), line, font=font, fill=(90, 92, 100))
        ty += int(small * 1.35)
