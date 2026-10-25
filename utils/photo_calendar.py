"""
Calendrier photo à imprimer : un PDF A4 en portrait, une couverture puis un mois par page — en haut une belle photo
prise ce mois-là une année précédente, en bas la grille des jours avec les anniversaires et fêtes de la famille
(dates saisies dans Occasions) et la fête des mères et des pères.

Même choix des photos que le livre photo (les plus aimées, les favorites, les plus nettes ; ni floues ni captures
d'écran) et même écriture du PDF page par page (utils/photo_book.py).
"""
import calendar
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw

from utils import occasions
from utils import photo_book as book
from utils.boot_screen import font
from utils.message_renderer import N_

PAGE_W, PAGE_H = book.PAGE_H, book.PAGE_W          # A4 en portrait (1654 × 2339 à 200 points par pouce)
POINTS = (book.POINTS[1], book.POINTS[0])
DAYS = [N_("lun."), N_("mar."), N_("mer."), N_("jeu."), N_("ven."), N_("sam."), N_("dim.")]


def month_photos(index, year, excluded=(), loved=None, favorites=()):
    """Une photo par mois (1 à 12) : prise ce mois-là avant l'année du calendrier, la mieux notée, jamais deux fois."""
    loved, favorites, excluded = loved or {}, set(favorites), set(excluded)
    candidates = {m: [] for m in range(1, 13)}
    for key, entry in index.items():
        when = book._date(entry)
        if not when or when.year >= year or key in excluded or key.split("/", 1)[0] in book.SKIP_SOURCES:
            continue
        quality = entry.get("q") or {}
        if quality.get("shot"):
            continue
        score = 3 * loved.get(key, 0) + (5 if key in favorites else 0) + min(1.0, float(quality.get("s") or 0) / 600)
        candidates[when.month].append((score, key))
    used, chosen = set(), {}
    for month in range(1, 13):
        for _score, key in sorted(candidates[month], reverse=True):
            if key not in used:
                chosen[month] = key
                used.add(key)
                break
    spare = [k for _s, k in sorted((c for items in candidates.values() for c in items), reverse=True) if k not in used]
    for month in range(1, 13):  # mois sans photo : une des meilleures photos restantes
        if month not in chosen and spare:
            chosen[month] = spare.pop(0)
    return chosen


def events(config, year):
    """Jours à marquer : {date: [texte]} (anniversaires avec l'âge, mariages, fête des mères et des pères)."""
    tr = book.tr
    found = {}
    for item in occasions.family_dates(config):
        day = item["date"]
        try:
            when = day.replace(year=year)
        except ValueError:  # 29 février
            when = date(year, 3, 1)
        years = year - day.year
        if item["kind"] == "birthday":
            text = tr(N_("%(name)s (%(age)s ans)")) % {"name": item["name"], "age": years} if years > 0 else item["name"]
        elif item["kind"] == "wedding":
            text = tr(N_("Mariage %(name)s")) % {"name": item["name"]}
        else:
            text = tr(N_("Naissance %(name)s")) % {"name": item["name"]}
        found.setdefault(when, []).append(text)
    where = occasions.country(config)
    for when, label in ((occasions.mothers_day(year, where), N_("Fête des mères")), (occasions.fathers_day(year, where), N_("Fête des pères"))):
        if when:
            found.setdefault(when, []).append(tr(label))
    return found


def _month_page(year, month, key, base_dir, marks):
    page = Image.new("RGB", (PAGE_W, PAGE_H), book.PAPER)
    draw = ImageDraw.Draw(page)
    margin = 110
    photo_h = int(PAGE_H * 0.5)
    if key:
        image, path = book._open(key, base_dir)
        if image is not None:
            page.paste(book._fit(image, path, PAGE_W, photo_h), (0, 0))
    hand = font(150, 400, str(book.HAND)) if book.HAND.exists() else font(110, 800)
    title_y = photo_h + 50
    draw.text((margin, title_y), book.tr(book.MONTHS[month - 1]).capitalize(), font=hand, fill=book.ACCENT)
    year_font = font(54, 700)
    draw.text((PAGE_W - margin - draw.textlength(str(year), font=year_font), title_y + 70), str(year), font=year_font, fill=book.SOFT)
    grid_top = title_y + 230
    weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
    cell_w = (PAGE_W - 2 * margin) / 7
    cell_h = (PAGE_H - grid_top - 90) / max(5, len(weeks)) - 6
    head = font(34, 700)
    for i, name in enumerate(DAYS):
        label = book.tr(name)
        draw.text((margin + i * cell_w + 12, grid_top - 52), label, font=head, fill=book.ACCENT if i >= 5 else book.SOFT)
    number, note = font(46, 700), font(25, 600)
    for row, week in enumerate(weeks):
        for col, day in enumerate(week):
            if not day:
                continue
            x, y = margin + col * cell_w, grid_top + row * (cell_h + 6)
            draw.rectangle([x + 3, y, x + cell_w - 3, y + cell_h], outline=(226, 218, 206), width=2,
                           fill=(255, 251, 245) if col < 5 else (250, 238, 230))
            draw.text((x + 14, y + 8), str(day), font=number, fill=book.INK if col < 5 else book.ACCENT)
            for n, text in enumerate(marks.get(date(year, month, day), [])[:2]):
                text = _fit(draw, text, note, cell_w - 22)
                draw.text((x + 12, y + cell_h - 36 - 32 * n), text, font=note, fill=book.ACCENT)
    return page


def _fit(draw, text, fnt, width):
    if draw.textlength(text, font=fnt) <= width:
        return text
    while text and draw.textlength(text + "…", font=fnt) > width:
        text = text[:-1]
    return text + "…"


def _cover(year, keys, base_dir, title):
    page = Image.new("RGB", (PAGE_W, PAGE_H), book.PAPER)
    draw = ImageDraw.Draw(page)
    margin, gap = 110, 30
    size = (PAGE_W - 2 * margin - gap) // 2
    for i, key in enumerate(keys[:4]):
        image, path = book._open(key, base_dir)
        if image is not None:
            book._shadowed(page, book._fit(image, path, size, size), margin + (i % 2) * (size + gap), 240 + (i // 2) * (size + gap))
    hand = font(260, 400, str(book.HAND)) if book.HAND.exists() else font(200, 800)
    y = 240 + 2 * (size + gap) + 60
    draw.text((margin, y), str(year), font=hand, fill=book.ACCENT)
    draw.text((margin, y + 300), title, font=font(70, 850), fill=book.INK)
    return page


def build(index, config, year, out_path, base_dir, excluded=(), loved=None, favorites=(), progress=None, translate=None):
    """Écrit le calendrier de l'année ; retourne le nombre de pages (0 si aucune photo datée)."""
    book._tr[0] = translate or (lambda text: text)
    chosen = month_photos(index, year, excluded, loved, favorites)
    if not chosen:
        return 0
    marks = events(config, year)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp")
    writer = book.PdfWriter(tmp, POINTS)
    try:
        writer.add_page(_cover(year, [chosen[m] for m in sorted(chosen)][::3], base_dir, book.tr(N_("Calendrier de la famille"))))
        for month in range(1, 13):
            writer.add_page(_month_page(year, month, chosen.get(month), base_dir, marks))
            if progress:
                progress(month + 1, 13)
    finally:
        writer.close()
    tmp.replace(out_path)
    return 13
