"""
GIF animés : la première image sert de photo partout (préparation, compositions, vignettes) et l'animation est
rejouée par-dessus pendant l'affichage, en photo seule comme dans les dispositions.

À côté de l'image affichée, « <nom>_animation.json » décrit où rejouer chaque GIF :
  {"items": [{"gif": "static/photos/x/a.gif", "box": [x, y, w, h], "affine": [a, b, c, d, e, f] | null, "mask": "...png" | null}]}
  - box : rectangle de l'écran où le GIF apparaît ;
  - affine : pour un point (px, py) de la boîte, le pixel (a·px + b·py + c, d·px + e·py + f) du GIF (null : le GIF remplit la boîte) ;
  - mask : parties visibles de la boîte (photo inclinée, recouverte par une autre ou par une punaise...).

Dans une composition, l'emplacement d'un GIF est retrouvé sans toucher aux dispositions : on la redessine deux fois
avec le même tirage au sort, le GIF remplacé par deux dégradés inverses. La différence des deux dessins donne les pixels
où il apparaît (et leur opacité), les couleurs donnent le point du GIF montré à cet endroit. Rotation, recadrage et
ombres sont ainsi suivis quelle que soit la disposition. Si la disposition transforme les couleurs (sépia, peinture),
le GIF reste immobile.
"""
import json
import logging
import os
from pathlib import Path

from PIL import Image, ImageChops, ImageSequence

logger = logging.getLogger("pimmich.animated")

PROJECT_DIR = Path(__file__).resolve().parent.parent
SUFFIX = "_animation"
EXTENSIONS = (".gif",)
MAX_FRAMES = 150           # au-delà, une image sur deux (même durée totale)
MAX_ITEMS = 3              # GIF animés au plus par composition (les autres restent immobiles)
MIN_PIXELS = 400           # GIF presque caché dans la composition : laissé immobile
MIN_COVERAGE = 0.85        # part de l'emplacement calculé qui doit suivre le GIF
MAX_COLOR_GAP = 45         # écart moyen de couleur toléré (disposition qui transforme les couleurs : immobile)


def is_animated(path):
    if Path(path).suffix.lower() not in EXTENSIONS:
        return False
    try:
        with Image.open(path) as image:
            return getattr(image, "is_animated", False) and getattr(image, "n_frames", 1) > 1
    except Exception:
        return False


def sidecar(display_path):
    path = Path(display_path)
    return path.with_name(f"{path.stem}{SUFFIX}.json")


def _relative(path):
    path = Path(path).resolve()
    try:
        return str(path.relative_to(PROJECT_DIR))
    except ValueError:
        return str(path)


def _absolute(path):
    path = Path(path)
    return path if path.is_absolute() else PROJECT_DIR / path


def write(display_path, items):
    """Enregistre les animations d'une image affichée (aucune : le fichier est retiré)."""
    target = sidecar(display_path)
    if not items:
        target.unlink(missing_ok=True)
        return
    stored = []
    for index, item in enumerate(items):
        mask = item.get("mask")
        if isinstance(mask, Image.Image):  # masque calculé (composition) : enregistré à côté
            mask_path = target.with_name(f"{Path(display_path).stem}{SUFFIX}_{index}.png")
            mask.save(mask_path)
            mask = mask_path
        stored.append(dict(item, gif=_relative(item["gif"]), mask=_relative(mask) if mask else None))
    data = {"items": stored}
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, target)


def read(display_path):
    """Animations à rejouer sur cette image (liste vide s'il n'y en a pas)."""
    try:
        data = json.loads(sidecar(display_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    items = []
    for item in data.get("items") or []:
        try:
            gif = _absolute(item["gif"])
            box = [int(v) for v in item["box"]]
        except (KeyError, TypeError, ValueError):
            continue
        if gif.is_file() and len(box) == 4 and box[2] > 0 and box[3] > 0:
            mask = _absolute(item["mask"]) if item.get("mask") else None
            items.append({"gif": gif, "box": box, "affine": item.get("affine"), "mask": mask if mask and mask.is_file() else None})
    return items


def single_item(gif_path, x, y, width, height):
    """GIF affiché seul : il remplit le rectangle où la préparation a posé sa première image."""
    return {"gif": str(gif_path), "box": [int(x), int(y), int(width), int(height)], "affine": None, "mask": None}


def video_to_gif(source, target, seconds=20, width=480):
    """Petite vidéo muette (GIF de Telegram ou de WhatsApp) -> vrai GIF animé (palette optimisée)."""
    import subprocess
    graph = (f"fps=12,scale='min({width},iw)':-2:flags=lanczos,split[a][b];"
             "[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-t", str(seconds), "-i", str(source), "-vf", graph, "-loop", "0", str(target)],
                   check=True, capture_output=True, timeout=300)
    return target


def frame_count(path):
    try:
        with Image.open(path) as image:
            return getattr(image, "n_frames", 1)
    except Exception:
        return 0


def frames(item, scale=1.0, limit=None):
    """Images de l'animation (RGB, ou RGBA avec un masque), à `scale` × la taille de la boîte : [(image, durée en s)]."""
    _x, _y, w, h = item["box"]
    out_w, out_h = max(1, round(w * scale)), max(1, round(h * scale))
    mask = None
    if isinstance(item.get("mask"), Image.Image):  # masque encore en mémoire (composition qui vient d'être repérée)
        mask = item["mask"].convert("L").resize((out_w, out_h), Image.BILINEAR)
    elif item.get("mask"):
        with Image.open(item["mask"]) as m:
            mask = m.convert("L").resize((out_w, out_h), Image.BILINEAR)
    result = []
    with Image.open(item["gif"]) as gif:
        total = getattr(gif, "n_frames", 1)
        step = 2 if total > MAX_FRAMES else 1
        coeffs = None
        if item.get("affine"):
            a, b, c, d, e, f = item["affine"]
            coeffs = (a / scale, b / scale, c, d / scale, e / scale, f)
        pending = 0.0
        for index, frame in enumerate(ImageSequence.Iterator(gif)):
            duration = frame.info.get("duration") or 100
            pending += (duration if duration >= 20 else 100) / 1000  # comme les navigateurs : 0 ou 10 ms = 0,1 s
            if index % step:
                continue
            rgb = frame.convert("RGB")
            if coeffs:
                image = rgb.transform((out_w, out_h), Image.AFFINE, coeffs, resample=Image.BILINEAR)
            else:
                image = rgb.resize((out_w, out_h), Image.BILINEAR)
            if mask is not None:
                image.putalpha(mask)
            result.append([image, pending])
            pending = 0.0
            if len(result) >= (limit or MAX_FRAMES):
                break
        if result and pending:
            result[-1][1] += pending
    return [(image, duration) for image, duration in result]


def matches(item, displayed):
    """La première image du GIF ressemble-t-elle à ce qui est affiché dans la boîte ? (photo filtrée ou tournée : non)"""
    import numpy as np
    x, y, w, h = item["box"]
    first = frames(dict(item, mask=None), scale=min(1.0, 160 / max(w, h)), limit=1)
    if not first:
        return False
    first = first[0][0]
    shown = displayed.convert("RGB").crop((x, y, x + w, y + h)).resize(first.size, Image.BILINEAR)
    gap = np.abs(np.asarray(first, dtype=np.float32) - np.asarray(shown, dtype=np.float32)).mean(axis=2)
    if item.get("mask"):
        with Image.open(item["mask"]) as m:
            weight = np.asarray(m.convert("L").resize(first.size, Image.BILINEAR), dtype=np.float32) / 255
    else:
        weight = np.ones(gap.shape, np.float32)
        inside = (max(0, -x), max(0, -y), min(w, displayed.width - x), min(h, displayed.height - y))  # hors écran : ignoré
        mask = np.zeros(gap.shape, bool)
        sx, sy = first.width / w, first.height / h
        mask[int(inside[1] * sy):int(inside[3] * sy), int(inside[0] * sx):int(inside[2] * sx)] = True
        weight = weight * mask
    return float((gap * weight).sum() / max(1.0, weight.sum())) <= MAX_COLOR_GAP


# --- Repérage dans les compositions ---

def _consensus(points, target, candidates, rng, tolerance, rounds=60):
    """Transformation affine suivie par le plus de pixels parmi `candidates` : (coefficients, pixels qui la suivent)."""
    import numpy as np
    if len(candidates) < 3:
        return None
    best, best_count = None, 0
    for _round in range(rounds):
        trio = rng.choice(candidates, 3, replace=False)
        try:
            coeffs = np.linalg.solve(points[trio], target[trio])
        except np.linalg.LinAlgError:
            continue
        count = int((np.linalg.norm(points[candidates] @ coeffs - target[candidates], axis=1) < tolerance).sum())
        if count > best_count:
            best, best_count = coeffs, count
    if best is None:
        return None
    for _round in range(2):  # affinage sur les pixels qui suivent ce modèle
        inliers = np.linalg.norm(points[candidates] @ best - target[candidates], axis=1) < tolerance
        best, *_rest = np.linalg.lstsq(points[candidates][inliers], target[candidates][inliers], rcond=None)
    return best, np.linalg.norm(points[candidates] @ best - target[candidates], axis=1) < tolerance

def gradient(size, inverted):
    """Dégradé de repérage : rouge selon x, vert selon y ; bleu à 0 (ou tout inversé, bleu à 255)."""
    import numpy as np
    w, h = size
    u = np.linspace(0, 255, w).round().astype(np.uint8)
    v = np.linspace(0, 255, h).round().astype(np.uint8)
    if inverted:
        u, v = 255 - u, 255 - v
    rgb = np.empty((h, w, 3), np.uint8)
    rgb[..., 0] = u[None, :]
    rgb[..., 1] = v[:, None]
    rgb[..., 2] = 255 if inverted else 0
    return Image.fromarray(rgb, "RGB")


def locate(base, low, high, gif_path):
    """
    Emplacement du GIF dans la composition `base`, d'après les deux dessins de repérage (`low` : dégradé, `high` :
    dégradé inversé). Retourne {box, affine, mask (image L)} ou None (GIF caché ou couleurs transformées).
    """
    import numpy as np
    # Zone où les deux dessins diffèrent (bleu : 0 contre 255), puis calculs sur cette zone seulement
    spread = np.asarray(ImageChops.subtract(high.convert("RGB").getchannel("B"), low.convert("RGB").getchannel("B")))
    rows, cols = np.nonzero(spread.max(axis=1) > 12)[0], np.nonzero(spread.max(axis=0) > 12)[0]
    if not len(rows):
        return None
    ox, oy = int(cols.min()), int(rows.min())
    region = (ox, oy, int(cols.max()) + 1, int(rows.max()) + 1)
    a = np.asarray(low.convert("RGB").crop(region), dtype=np.float32)
    b = np.asarray(high.convert("RGB").crop(region), dtype=np.float32)
    alpha = np.clip((b[..., 2] - a[..., 2]) / 255.0, 0, 1)  # opacité du GIF à chaque pixel
    visible = alpha > 0.05
    solid = alpha > 0.6
    if solid.sum() < MIN_PIXELS:
        return None
    with Image.open(gif_path) as gif:
        gw, gh = gif.size
    def coords(ys, xs):
        """Points de l'écran et point du GIF montré à cet endroit (calculés pour ces pixels seulement)."""
        w = alpha[ys, xs]
        u = 0.5 + (a[ys, xs, 0] - b[ys, xs, 0]) / (510 * w)
        v = 0.5 + (a[ys, xs, 1] - b[ys, xs, 1]) / (510 * w)
        return xs + (ox + 0.5), ys + (oy + 0.5), 0.5 + u * (gw - 1), 0.5 + v * (gh - 1)

    tolerance = max(1.5, 0.006 * max(gw, gh))
    sy, sx = np.nonzero(solid)
    rng = np.random.default_rng(0)
    if len(sx) > 6000:
        pick = rng.choice(len(sx), 6000, replace=False)
        sy, sx = sy[pick], sx[pick]
    px, py, tx, ty = coords(sy, sx)
    points = np.stack([px, py, np.ones(len(px), np.float32)], axis=1).astype(np.float64)
    target = np.stack([tx, ty], axis=1).astype(np.float64)
    sample = np.arange(len(px))
    # Consensus : le GIF lui-même, plutôt que ce qui en dérive autrement (fond flou tiré de lui-même, plus agrandi)
    models, remaining = [], sample
    for _model in range(2):
        found = _consensus(points, target, remaining, rng, tolerance)
        if found is None:
            break
        coeffs, inliers = found
        if inliers.sum() >= max(MIN_PIXELS * len(sample) / max(1, int(solid.sum())), 0.12 * len(sample)):
            models.append(coeffs)
        remaining = remaining[~inliers]
        if len(remaining) < 50:
            break
    if not models:
        return None
    determinants = [abs(m[0, 0] * m[1, 1] - m[1, 0] * m[0, 1]) for m in models]
    best, det = max(zip(models, determinants), key=lambda pair: pair[1])
    if not 0.01 < det < 1e4:  # transformation écrasée (couleurs transformées par la disposition)
        return None
    # Là où le GIF doit apparaître d'après ce modèle, presque tous les pixels doivent le suivre (sinon les couleurs
    # ont été transformées par la disposition et seuls quelques morceaux tombent juste par hasard)
    mapped = points @ best
    inside = (mapped[:, 0] >= 0) & (mapped[:, 0] <= gw) & (mapped[:, 1] >= 0) & (mapped[:, 1] <= gh)
    follows = np.linalg.norm(mapped - target, axis=1) < tolerance
    if inside.sum() < 50 or float((follows & inside).sum() / inside.sum()) < MIN_COVERAGE:
        return None
    # Pixels qui montrent le GIF (tous les pixels visibles, en simple précision)
    vy, vx = np.nonzero(visible)
    px, py, tx, ty = coords(vy, vx)
    c = best.astype(np.float32)
    ex = c[0, 0] * px + c[1, 0] * py + c[2, 0] - tx
    ey = c[0, 1] * px + c[1, 1] * py + c[2, 1] - ty
    keep = ex * ex + ey * ey < (tolerance * 1.5) ** 2
    if keep.sum() < MIN_PIXELS:
        return None
    weight = alpha[vy, vx]
    ky, kx = vy[keep] + oy, vx[keep] + ox
    x0, y0, x1, y1 = int(kx.min()), int(ky.min()), int(kx.max()) + 1, int(ky.max()) + 1
    # Coefficients exprimés depuis le coin de la boîte
    affine = [float(best[0, 0]), float(best[1, 0]), float(best[2, 0] + best[0, 0] * x0 + best[1, 0] * y0),
              float(best[0, 1]), float(best[1, 1]), float(best[2, 1] + best[0, 1] * x0 + best[1, 1] * y0)]
    mask_values = np.zeros((y1 - y0, x1 - x0), np.float32)
    mask_values[ky - y0, kx - x0] = weight[keep]
    mask = Image.fromarray((mask_values * 255).round().astype(np.uint8), "L")
    item = {"gif": str(gif_path), "box": [x0, y0, x1 - x0, y1 - y0], "affine": affine, "mask": mask}
    # La première image du GIF, posée à cet endroit, doit ressembler au dessin (sinon : filtre de couleurs)
    first = np.asarray(frames(dict(item, mask=None), limit=1)[0][0], dtype=np.float32)
    drawn = np.asarray(base.convert("RGB").crop((x0, y0, x1, y1)), dtype=np.float32)
    gap = np.abs(first - drawn).mean(axis=2)
    if float((gap * mask_values).sum() / max(1.0, mask_values.sum())) > MAX_COLOR_GAP:
        return None
    return item
