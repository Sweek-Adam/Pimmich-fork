"""
Livre photo de l'année : un PDF prêt à imprimer (A4 à l'italienne, 200 points par pouce) avec les plus belles photos
de l'année, mois par mois.

- Choix des photos : prises cette année-là (index des photos), sans les photos écartées par le tri automatique
  (floues, sombres, captures d'écran, rafales) ; les plus aimées (❤️), les favorites et les plus nettes d'abord, et
  réparties sur les mois (chaque mois photographié a sa page).
- Mise en page : une couverture, puis pour chaque mois une ou plusieurs pages de 1 à 4 photos (recadrées autour des
  visages), avec la date et le lieu ; une dernière page « L'année en chiffres ».
- Photos d'origine quand elles existent (meilleure qualité d'impression), sinon la version préparée.
- Le PDF est écrit page par page (photos en JPEG) : peu de mémoire, même sur un Raspberry Pi 3.
"""
import io
import json
import warnings
import zlib
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from utils.boot_screen import font
from utils.message_renderer import N_

DPI = 200
PAGE_W, PAGE_H = 2339, 1654          # A4 à l'italienne (297 × 210 mm) à 200 points par pouce
POINTS = (842, 595)                  # même page en points PDF
MAX_PHOTOS = 80
MAX_SOURCE_PIXELS = 40_000_000
PER_PAGE = 4
PAPER, INK, SOFT = (250, 247, 242), (34, 32, 40), (128, 122, 116)
ACCENT = (196, 92, 74)
MONTHS = [N_("janvier"), N_("février"), N_("mars"), N_("avril"), N_("mai"), N_("juin"), N_("juillet"), N_("août"),
          N_("septembre"), N_("octobre"), N_("novembre"), N_("décembre")]
_tr = [lambda text: text]  # traduction (langue du cadre), fixée par build()


def tr(text):
    return _tr[0](text)
SKIP_SOURCES = {"messages"}
HAND = Path(__file__).resolve().parent.parent / "static" / "fonts" / "Caveat-Regular.ttf"


class PdfWriter:
    """PDF minimal : une image JPEG pleine page par page, écrite au fur et à mesure."""

    def __init__(self, path, page_points=POINTS):
        self.file = open(path, "wb")
        self.page_points = page_points
        self.offsets = {}
        self.pages = []
        self.next_id = 3  # 1 : catalogue, 2 : arbre des pages (écrits à la fin)
        self.file.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    def _object(self, number, body, stream=None):
        self.offsets[number] = self.file.tell()
        self.file.write(f"{number} 0 obj\n".encode())
        self.file.write(body)
        if stream is not None:
            self.file.write(b"\nstream\n" + stream + b"\nendstream")
        self.file.write(b"\nendobj\n")

    def add_page(self, image, quality=90):
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, "JPEG", quality=quality, optimize=True, dpi=(DPI, DPI))
        data = buffer.getvalue()
        image_id, content_id, page_id = self.next_id, self.next_id + 1, self.next_id + 2
        self.next_id += 3
        w, h = self.page_points
        self._object(image_id, (f"<< /Type /XObject /Subtype /Image /Width {image.width} /Height {image.height} "
                                f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length {len(data)} >>").encode(), data)
        content = zlib.compress(f"q {w} 0 0 {h} 0 0 cm /Im0 Do Q".encode())
        self._object(content_id, f"<< /Length {len(content)} /Filter /FlateDecode >>".encode(), content)
        self._object(page_id, (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w} {h}] /Contents {content_id} 0 R "
                               f"/Resources << /XObject << /Im0 {image_id} 0 R >> >> >>").encode())
        self.pages.append(page_id)

    def close(self):
        kids = " ".join(f"{p} 0 R" for p in self.pages)
        self._object(2, f"<< /Type /Pages /Kids [{kids}] /Count {len(self.pages)} >>".encode())
        self._object(1, b"<< /Type /Catalog /Pages 2 0 R >>")
        xref = self.file.tell()
        count = self.next_id
        self.file.write(f"xref\n0 {count}\n0000000000 65535 f \n".encode())
        for number in range(1, count):
            self.file.write(f"{self.offsets.get(number, 0):010d} 00000 n \n".encode())
        self.file.write(f"trailer\n<< /Size {count} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
        self.file.close()


def _date(entry):
    try:
        return datetime.fromisoformat(entry["date"]) if entry.get("date") else None
    except ValueError:
        return None


def years(index):
    """Années présentes dans l'index : {année: nombre de photos}, les plus récentes d'abord."""
    counts = defaultdict(int)
    for key, entry in index.items():
        when = _date(entry)
        if when and key.split("/", 1)[0] not in SKIP_SOURCES:
            counts[when.year] += 1
    return dict(sorted(counts.items(), reverse=True))


def select(index, year, excluded=(), loved=None, favorites=(), limit=MAX_PHOTOS):
    """Photos du livre : [(clé, date)], dans l'ordre chronologique, réparties sur les mois de l'année."""
    loved, favorites, excluded = loved or {}, set(favorites), set(excluded)
    by_month = defaultdict(list)
    for key, entry in index.items():
        when = _date(entry)
        if not when or when.year != year or key in excluded or key.split("/", 1)[0] in SKIP_SOURCES:
            continue
        if (entry.get("q") or {}).get("shot"):
            continue
        sharp = min(1.0, float((entry.get("q") or {}).get("s") or 0) / 600)
        score = 3 * loved.get(key, 0) + (5 if key in favorites else 0) + sharp
        by_month[when.month].append((score, when, key))
    total = sum(len(v) for v in by_month.values())
    if not total:
        return []
    chosen = []
    for month, items in by_month.items():
        share = max(1, round(limit * len(items) / total))
        items.sort(key=lambda i: -i[0])
        picked = items[:share]
        # Pas deux photos prises à moins d'une minute d'écart (souvent la même scène)
        kept = []
        for score, when, key in picked + items[share:]:
            if len(kept) >= share:
                break
            if all(abs((when - other).total_seconds()) > 60 for _s, other, _k in kept):
                kept.append((score, when, key))
        chosen += kept
    if len(chosen) > limit:
        chosen = sorted(chosen, key=lambda i: -i[0])[:limit]
    return [(key, when) for _score, when, key in sorted(chosen, key=lambda i: i[1])]


def _open(key, base_dir):
    """Photo d'origine (sinon préparée), orientée, réduite à la taille utile pour l'impression."""
    source, name = key.split("/", 1)
    stem = Path(name).stem
    candidates = sorted((base_dir / "static" / "photos" / source).glob(f"{_glob_escape(stem)}.*")) + [base_dir / "static" / "prepared" / key]
    for path in candidates:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", Image.DecompressionBombWarning)
                image = Image.open(path)
            if image.format != "JPEG" and image.width * image.height > MAX_SOURCE_PIXELS:
                continue  # immense image non JPEG : trop de mémoire sur un Raspberry Pi, la version préparée suffit
            image.draft("RGB", (PAGE_W, PAGE_W))  # JPEG : lecture directement réduite (mémoire)
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((PAGE_W, PAGE_W))
            return image, path
        except (OSError, ValueError, Image.DecompressionBombError):
            continue
    return None, None


def _glob_escape(text):
    import glob
    return glob.escape(text)


def _fit(image, path, width, height):
    """Photo recadrée à width × height, en gardant les visages."""
    ratio = max(width / image.width, height / image.height)
    resized = image.resize((max(width, round(image.width * ratio)), max(height, round(image.height * ratio))), Image.LANCZOS)
    try:
        from utils import faces
        found = faces.for_file(path, image)
    except Exception:
        found = []
    left, top = _window(resized.width, resized.height, width, height, found)
    return resized.crop((left, top, left + width, top + height))


def _window(img_w, img_h, crop_w, crop_h, found):
    try:
        from utils import faces
        return faces.window(img_w, img_h, crop_w, crop_h, found)
    except Exception:
        return (img_w - crop_w) // 2, int((img_h - crop_h) * 0.42)


def _shadowed(page, photo, x, y):
    shadow = Image.new("RGBA", (photo.width + 40, photo.height + 40), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle([20, 26, photo.width + 20, photo.height + 26], fill=(60, 40, 20, 50))
    from PIL import ImageFilter
    page.paste(shadow.filter(ImageFilter.GaussianBlur(12)), (x - 20, y - 20), shadow.filter(ImageFilter.GaussianBlur(12)))
    page.paste(photo, (x, y))


def _caption(when, place):
    text = f"{when.day} {tr(MONTHS[when.month - 1])}"
    return f"{text} · {place}" if place else text


def _place(entry):
    try:
        from utils import geocode
        found = geocode.cached(entry.get("lat"), entry.get("lon"))
        return (found or {}).get("city") or ""
    except Exception:
        return ""


SLOTS = {  # cases (x, y, largeur, hauteur) en fraction de la zone photo
    1: [(0, 0, 1, 1)],
    2: [(0, 0, 0.495, 1), (0.505, 0, 0.495, 1)],
    3: [(0, 0, 0.62, 1), (0.63, 0, 0.37, 0.495), (0.63, 0.505, 0.37, 0.495)],
    4: [(0, 0, 0.495, 0.495), (0.505, 0, 0.495, 0.495), (0, 0.505, 0.495, 0.495), (0.505, 0.505, 0.495, 0.495)],
}


def _month_page(items, month, year, base_dir, index, first):
    page = Image.new("RGB", (PAGE_W, PAGE_H), PAPER)
    draw = ImageDraw.Draw(page)
    margin = 130
    title_font = font(150, 400, str(HAND)) if HAND.exists() else font(110, 800)
    title = tr(MONTHS[month - 1]).capitalize() + ("" if first else " " + tr(N_("(suite)")))
    draw.text((margin, 70), title, font=title_font, fill=ACCENT)
    draw.text((PAGE_W - margin - draw.textlength(str(year), font=font(40, 700)), 120), str(year), font=font(40, 700), fill=SOFT)
    area = (margin, 290, PAGE_W - 2 * margin, PAGE_H - 290 - 150)
    small = font(34, 500)
    for (key, when), (fx, fy, fw, fh) in zip(items, SLOTS[len(items)]):
        image, path = _open(key, base_dir)
        if image is None:
            continue
        x, y = area[0] + int(fx * area[2]), area[1] + int(fy * area[3])
        w, h = int(fw * area[2]), int(fh * area[3]) - 54
        photo = _fit(image, path, w, h)
        _shadowed(page, photo, x, y)
        draw.text((x, y + h + 12), _caption(when, _place(index.get(key) or {})), font=small, fill=SOFT)
    return page


def _cover(items, year, title, base_dir):
    page = Image.new("RGB", (PAGE_W, PAGE_H), PAPER)
    draw = ImageDraw.Draw(page)
    hero_w = int(PAGE_W * 0.56)
    photos = [_open(key, base_dir) for key, _when in items[:5]]
    photos = [(img, path) for img, path in photos if img is not None]
    if photos:
        page.paste(_fit(photos[0][0], photos[0][1], hero_w, PAGE_H), (PAGE_W - hero_w, 0))
        thumbs, gap = photos[1:5], 36
        size = (PAGE_W - hero_w - 2 * 130 - gap * (len(thumbs) - 1)) // max(1, len(thumbs))
        for i, (img, path) in enumerate(thumbs):
            _shadowed(page, _fit(img, path, size, size), 130 + i * (size + gap), PAGE_H - size - 160)
    left = 130
    draw.text((left, 230), title, font=font(130, 850), fill=INK)
    hand = font(150, 400, str(HAND)) if HAND.exists() else font(120, 300)
    draw.text((left, 400), str(year), font=hand, fill=ACCENT)
    draw.text((left, 620), tr(N_("Les souvenirs de la famille, mois par mois")), font=font(46, 500), fill=SOFT)
    return page


def _summary(items, year, index, loved):
    page = Image.new("RGB", (PAGE_W, PAGE_H), PAPER)
    draw = ImageDraw.Draw(page)
    draw.text((130, 130), tr(N_("%(year)s en chiffres")) % {"year": year}, font=font(110, 850), fill=INK)
    months = defaultdict(int)
    for _key, when in items:
        months[when.month] += 1
    year_photos = sum(1 for e in index.values() if (_date(e) or datetime.min).year == year)
    places = {p for p in (_place(index.get(k) or {}) for k, _w in items) if p}
    best = max(months, key=months.get) if months else None
    lines = [
        (str(year_photos), tr(N_("photos prises cette année"))),
        (str(len(items)), tr(N_("photos choisies pour ce livre"))),
        (str(sum(loved.get(k, 0) for k, _w in items)), tr(N_("cœurs reçus sur le cadre par ces photos"))),
        (str(len(places)) if places else "—", tr(N_("lieux différents"))),
        (tr(MONTHS[best - 1]) if best else "—", tr(N_("le mois le plus photographié"))),
    ]
    y = 400
    for number, label in [line for line in lines if line[0] not in ("0", "—")]:
        draw.text((130, y), number, font=font(96, 850), fill=ACCENT)
        draw.text((560, y + 30), label, font=font(50, 500), fill=INK)
        y += 190
    return page


def build(index, year, out_path, base_dir, excluded=(), loved=None, favorites=(), title=None, progress=None, translate=None):
    """Écrit le livre photo de l'année ; retourne le nombre de pages (0 si aucune photo cette année-là)."""
    _tr[0] = translate or (lambda text: text)
    title = title or tr(N_("Notre année"))
    loved = loved or {}
    items = select(index, year, excluded, loved, favorites)
    if not items:
        return 0
    groups = []
    for month in sorted({when.month for _k, when in items}):
        month_items = [i for i in items if i[1].month == month]
        for start in range(0, len(month_items), PER_PAGE):
            groups.append((month, month_items[start:start + PER_PAGE], start == 0))
    total = len(groups) + 2
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp")
    writer = PdfWriter(tmp)
    try:
        cover_pick = sorted(items, key=lambda i: -(3 * loved.get(i[0], 0) + (5 if i[0] in set(favorites) else 0)))
        writer.add_page(_cover(cover_pick, year, title, base_dir))
        if progress:
            progress(1, total)
        for n, (month, group, first) in enumerate(groups, start=2):
            writer.add_page(_month_page(group, month, year, base_dir, index, first))
            if progress:
                progress(n, total)
        writer.add_page(_summary(items, year, index, loved))
    finally:
        writer.close()
    tmp.replace(out_path)
    if progress:
        progress(total, total)
    return total


def loved_by_key(reactions_data):
    """Réactions {"prepared/source/x.jpg": {...}} -> {"source/x.jpg": total}."""
    out = {}
    for photo, counts in (reactions_data.get("photos") or {}).items():
        key = photo.split("prepared/", 1)[-1]
        out[key] = out.get(key, 0) + sum(counts.values())
    return out


def favorites_keys(favorites):
    return {str(f).split("prepared/", 1)[-1] for f in favorites or []}


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
