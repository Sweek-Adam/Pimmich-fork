"""
Mur de cadres : plusieurs cadres posés côte à côte affichent ensemble une même grande photo (pour une fête, un salon).

- Le cadre qui pilote choisit une photo (de préférence en largeur), la découpe en autant de morceaux qu'il y a
  d'écrans, en tenant compte de l'espace entre deux écrans (bordures), et envoie à chaque cadre son morceau avec
  l'heure exacte d'affichage et de fin (horloges réglées par Internet : moins d'un dixième de seconde d'écart).
- Chaque cadre range les morceaux reçus dans le dossier temporaire ; le diaporama affiche le prochain à l'heure dite,
  sans transition, puis reprend ses photos quand le mur s'arrête.
"""
import json
import random
import time
from pathlib import Path

from PIL import Image, ImageOps

from utils.platform_info import tmp_path

WALL_DIR = Path(str(tmp_path("pimmich_wall")))
LEAD = 4.0          # secondes entre l'envoi et l'affichage (le temps que chaque cadre reçoive son morceau)
KEEP = 3            # morceaux en attente au plus


def receive(data, show_at, until):
    """Morceau reçu (octets JPEG) à afficher de show_at à until (horodatages)."""
    WALL_DIR.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for old in WALL_DIR.glob("*.json"):
        try:
            if json.loads(old.read_text())["until"] < now:
                old.unlink(missing_ok=True)
                old.with_suffix(".jpg").unlink(missing_ok=True)
        except (OSError, ValueError, KeyError):
            old.unlink(missing_ok=True)
    name = f"{int(show_at * 1000)}"
    (WALL_DIR / f"{name}.jpg").write_bytes(data)
    (WALL_DIR / f"{name}.json").write_text(json.dumps({"show_at": show_at, "until": until}))
    for extra in sorted(WALL_DIR.glob("*.json"))[:-KEEP]:
        extra.unlink(missing_ok=True)
        extra.with_suffix(".jpg").unlink(missing_ok=True)


def pending(now=None):
    """Prochain morceau à afficher : (chemin, show_at, until), ou None."""
    now = now or time.time()
    for meta in sorted(WALL_DIR.glob("*.json")) if WALL_DIR.is_dir() else []:
        try:
            info = json.loads(meta.read_text())
        except (OSError, ValueError):
            continue
        if info["until"] <= now + 0.5:
            meta.unlink(missing_ok=True)
            meta.with_suffix(".jpg").unlink(missing_ok=True)
            continue
        image = meta.with_suffix(".jpg")
        if image.exists():
            return image, info["show_at"], info["until"]
    return None


def done(path):
    Path(path).unlink(missing_ok=True)
    Path(path).with_suffix(".json").unlink(missing_ok=True)


def split(image, count, screen=(1920, 1080), gap=0.04):
    """Découpe la photo pour `count` écrans en rangée ; `gap` : espace entre deux écrans (part de la largeur d'un écran)."""
    w, h = screen
    gap_px = int(w * gap)
    canvas_w = count * w + (count - 1) * gap_px
    whole = ImageOps.fit(image.convert("RGB"), (canvas_w, h), Image.LANCZOS, centering=(0.5, 0.42))
    return [whole.crop((i * (w + gap_px), 0, i * (w + gap_px) + w, h)) for i in range(count)]


def original(key, base_dir):
    """Photo d'origine (meilleure qualité), sinon la version préparée."""
    source, name = key.split("/", 1)
    folder = Path(base_dir) / "static" / "photos" / source
    import glob
    for path in sorted(folder.glob(glob.escape(Path(name).stem) + ".*")) if folder.is_dir() else []:
        if path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".heic"):
            return path
    prepared = Path(base_dir) / "static" / "prepared" / key
    return prepared if prepared.exists() else None


def choose(index, base_dir, rng=None, recent=(), tries=25):
    """Photo du mur : une photo en largeur de préférence (elle se prête mieux à plusieurs écrans) ; (clé, chemin)."""
    rng = rng or random.Random()
    keys = [k for k, e in index.items() if k.split("/", 1)[0] != "messages" and not (e.get("q") or {}).get("shot") and k not in recent]
    rng.shuffle(keys)
    fallback = None
    for key in keys[:tries]:
        path = original(key, base_dir)
        if not path:
            continue
        try:
            with Image.open(path) as image:  # seul l'en-tête est lu
                width, height = image.size
                if image.getexif().get(274) in (5, 6, 7, 8):  # photo tournée d'un quart de tour (orientation EXIF)
                    width, height = height, width
        except (OSError, ValueError):
            continue
        if width / max(1, height) >= 1.3:
            return key, path
        fallback = fallback or (key, path)
    return fallback


def tile_bytes(image):
    import io
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=90)
    return buffer.getvalue()
