"""
Mode fête (anniversaire, mariage, soirée...) : un QR code reste à l'écran, les invités envoient leurs photos depuis
leur téléphone et elles s'affichent aussitôt sur le cadre, en grand avec le prénom de l'invité, puis dans le
« Mur de la fête » (disposition réservée à la fête). Les photos sont rangées dans leur propre source (l'album de la
fête, gardé ensuite). À la fin (heure choisie ou bouton), les sources et la disposition d'avant reviennent.
"""
import json
import math
import os
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

from utils.message_renderer import N_, _font, _gradient, _paste_with_shadow, _textured, _vignette
from utils.platform_info import tmp_path

LIVE_FILE = tmp_path("pimmich_party_live.json")      # photos arrivées, pas encore montrées (hors carte SD)
AUTHORS_FILE = tmp_path("pimmich_party_authors.json")  # photo préparée -> prénom de l'invité (bandeau à l'écran)
MAX_HOURS = 48
_lock = threading.Lock()


# --- État ---

def state(config):
    party = (config or {}).get("party") or {}
    return party if isinstance(party, dict) else {}


def active(config, now=None):
    party = state(config)
    if not party.get("active"):
        return False
    try:
        return (now or datetime.now()) < datetime.fromisoformat(party["until"])
    except (KeyError, TypeError, ValueError):
        return False


def source_for(started):
    """Source (dossier) de l'album de la fête : « fete_AAAAMMJJ »."""
    return f"fete_{started:%Y%m%d}"


def _clean_name(name):
    name = re.sub(r"\s+", " ", str(name or "")).strip()[:60]
    return name or "La fête"


def start(config, name, hours, only_party=True, auto_approve=True, now=None, wifi_qr=False):
    """Nouvelle configuration avec la fête lancée (les réglages remplacés sont gardés pour la fin)."""
    now = now or datetime.now()
    if not active(config, now):
        from utils import photobooth
        photobooth.reset_counts()  # nouvelle fête : chacun retrouve ses tirages
    hours = max(1, min(MAX_HOURS, int(hours)))
    previous = state(config) if active(config, now) else {}
    source = previous.get("source") or source_for(now)
    party = {"active": True, "name": _clean_name(name), "started": previous.get("started") or now.isoformat(timespec="minutes"),
             "until": (now + timedelta(hours=hours)).isoformat(timespec="minutes"), "source": source,
             "only_party": bool(only_party), "auto_approve": bool(auto_approve), "wifi_qr": bool(wifi_qr),
             "saved": previous.get("saved") or {"display_sources": list(config.get("display_sources") or []),
                                                "layout_override": config.get("layout_override", "auto")}}
    sources = [source, "messages"] if only_party else list(dict.fromkeys(list(party["saved"]["display_sources"]) + [source]))
    # Que les photos de la fête : elles passent en grand à leur arrivée, puis dans le Mur de la fête
    return dict(config, party=party, display_sources=sources, layout_override="fete" if only_party else "auto")


def stop(config):
    """Nouvelle configuration, fête terminée : sources et disposition d'avant ; l'album de la fête reste disponible."""
    party = state(config)
    if not party:
        return dict(config)
    saved = party.get("saved") or {}
    out = dict(config, party=dict(party, active=False, ended=datetime.now().isoformat(timespec="minutes")))
    if "display_sources" in saved:
        out["display_sources"] = saved["display_sources"]
    if "layout_override" in saved:
        out["layout_override"] = saved["layout_override"]
    return out


# --- Arrivées en direct ---

def _read(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def push_live(prepared_path, author=""):
    """Une photo vient d'arriver : le diaporama la montre à la diapositive suivante."""
    with _lock:
        live = _read(LIVE_FILE, [])
        live.append({"path": str(prepared_path), "author": author or "", "at": time.time()})
        _write(LIVE_FILE, live[-30:])
        authors = _read(AUTHORS_FILE, {})
        authors[os.path.realpath(prepared_path)] = author or ""
        _write(AUTHORS_FILE, dict(list(authors.items())[-300:]))


def pop_live():
    with _lock:
        live = _read(LIVE_FILE, [])
        if live:
            LIVE_FILE.unlink(missing_ok=True)
    return [item for item in live if Path(item["path"]).exists()]


def author_of(path):
    if not path:
        return None
    return _read(AUTHORS_FILE, {}).get(os.path.realpath(path))


def inject(playlist, index, paths):
    """Place les photos arrivées à `index` (la plus récente d'abord), sans les répéter plus loin."""
    new = [p for p in reversed(paths)]
    real = {os.path.realpath(p) for p in new}
    rest = [p for p in playlist if os.path.realpath(p) not in real]
    index = min(index, len(rest))
    return rest[:index] + new + rest[index:]


def stats(config):
    party = state(config)
    folder = Path("static") / "photos" / party.get("source", "")
    photos = [f for f in folder.iterdir() if f.is_file() and not f.name.startswith(".")] if party.get("source") and folder.is_dir() else []
    return {"photos": len(photos)}


# --- Mur de la fête (disposition) ---

CONFETTI = [(255, 99, 132), (255, 205, 86), (75, 192, 192), (54, 162, 235), (153, 102, 255), (255, 159, 64), (240, 240, 240)]


def party_wall(photos, message, W, H, rng):
    """Les photos de la fête en polaroïds inclinés sur un fond festif, avec le nom de la fête en titre."""
    from utils import compositions as base
    from utils.themed_compositions import HAND2, _title
    from utils.config_manager import load_config
    canvas = _vignette(_textured(_gradient(W, H, (54, 24, 92), (18, 12, 46)), rng, 12), 0.4).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    for _ in range(int(W * H / 5000)):  # confettis
        x, y, size = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(3, 9) * H / 1080
        color = rng.choice(CONFETTI) + (rng.randint(140, 230),)
        if rng.random() < 0.5:
            draw.ellipse([x, y, x + size, y + size], fill=color)
        else:
            angle = rng.uniform(0, math.pi)
            dx, dy = math.cos(angle) * size * 1.4, math.sin(angle) * size * 1.4
            draw.line([x - dx, y - dy, x + dx, y + dy], fill=color, width=max(2, int(size / 2)))
    name = state(load_config()).get("name") or ""
    top = H * 0.17 if name else H * 0.05
    if name:
        _title(canvas, name, HAND2, int(H * 0.1), (255, 230, 150), (W / 2, H * 0.09), glow=(255, 120, 200), max_width=W * 0.85)
    n = len(photos)
    cols = min(n, 3 if n <= 6 else 4) if W >= H else min(n, 2 if n <= 4 else 3)
    rows = math.ceil(n / cols)
    cell_w, cell_h = W * 0.94 / cols, (H - top - H * 0.04) / rows
    for i, photo in enumerate(photos):
        row, col = divmod(i, cols)
        in_row = min(cols, n - row * cols)
        border = max(8, int(min(cell_w, cell_h) * 0.04))
        size = base.print_photo(photo, cell_w * 0.78, cell_h * 0.72)
        card = base.framed(size, border, (255, 255, 255), bottom=border * 3)
        card = base.rotated(card, rng.uniform(-7, 7))
        cx = W * 0.03 + (col + 0.5 + (cols - in_row) / 2) * cell_w
        cy = top + (row + 0.5) * cell_h
        _paste_with_shadow(canvas, card, base._inside((cx + rng.uniform(-0.04, 0.04) * cell_w, cy), card, W, H, 0.02))
    return canvas.convert("RGB")


THEMES = {"fete": (N_("Mur de la fête"), 2, 9, False, party_wall)}
