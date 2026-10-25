"""
Scanner de vieilles photos papier : une photo d'un tirage prise au téléphone devient une photo numérique propre.

1. Bords du tirage : contours de l'image réduite (OpenCV), le plus grand quadrilatère qui couvre au moins 15 % de
   l'image ; à défaut, le plus grand contour (rectangle qui l'entoure au plus juste).
2. Redressement : perspective corrigée sur l'image en pleine taille (le tirage devient un vrai rectangle).
3. Couleurs ravivées : balance des blancs (les vieux tirages virent au jaune ou au rouge), contraste local
   (CLAHE sur la luminosité) et un peu de saturation.
Sans OpenCV, la photo est seulement orientée et ravivée (Pillow).
"""
import io

from PIL import Image, ImageEnhance, ImageOps

MIN_AREA = 0.15
WORK_SIDE = 1000
MAX_SIDE = 4000


def _order(points):
    """Coins dans l'ordre : haut-gauche, haut-droit, bas-droit, bas-gauche."""
    import numpy as np
    points = np.array(points, dtype="float32").reshape(4, 2)
    total, diff = points.sum(axis=1), np.diff(points, axis=1).ravel()
    return np.array([points[total.argmin()], points[diff.argmin()], points[total.argmax()], points[diff.argmax()]], dtype="float32")


def find_corners(rgb):
    """Coins du tirage dans l'image (tableau numpy RGB), ou None si rien de net n'est trouvé."""
    import cv2
    import numpy as np
    h, w = rgb.shape[:2]
    scale = WORK_SIDE / max(h, w)
    small = cv2.resize(rgb, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
    gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_RGB2GRAY), (5, 5), 0)
    edges = cv2.dilate(cv2.Canny(gray, 30, 120), np.ones((5, 5), np.uint8), iterations=2)
    contours, _hierarchy = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area_min = MIN_AREA * small.shape[0] * small.shape[1]
    best = None
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:8]:
        if cv2.contourArea(contour) < area_min:
            break
        approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            best = approx.reshape(4, 2)
            break
        if best is None:
            best = cv2.boxPoints(cv2.minAreaRect(contour))
    if best is None:
        return None
    corners = _order(best) / scale
    # Tirage qui remplit déjà toute l'image : rien à redresser
    if (corners[:, 0].min() < 0.01 * w and corners[:, 0].max() > 0.99 * w and corners[:, 1].min() < 0.01 * h and corners[:, 1].max() > 0.99 * h):
        return None
    return corners


def straighten(rgb, corners):
    import cv2
    import numpy as np
    tl, tr, br, bl = corners
    width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    target = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype="float32")
    matrix = cv2.getPerspectiveTransform(corners.astype("float32"), target)
    return cv2.warpPerspective(rgb, matrix, (width, height), flags=cv2.INTER_CUBIC)


def revive(rgb):
    """Balance des blancs (monde gris), contraste local, un peu plus de couleur."""
    import cv2
    import numpy as np
    image = rgb.astype("float32")
    means = image.reshape(-1, 3).mean(axis=0)
    image *= means.mean() / np.maximum(means, 1)
    image = np.clip(image, 0, 255).astype("uint8")
    lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
    lab[:, :, 0] = cv2.createCLAHE(clipLimit=1.6, tileGridSize=(8, 8)).apply(lab[:, :, 0])
    image = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
    return np.array(ImageEnhance.Color(Image.fromarray(image)).enhance(1.15))


def scan(data):
    """Photo du tirage (octets) -> (JPEG redressé et ravivé, tirage trouvé : bool)."""
    with Image.open(io.BytesIO(data)) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    found = False
    try:
        import numpy as np
        rgb = np.array(image)
        corners = find_corners(rgb)
        if corners is not None:
            rgb, found = straighten(rgb, corners), True
        image = Image.fromarray(revive(rgb))
    except ImportError:
        image = ImageEnhance.Color(ImageOps.autocontrast(image, cutoff=1)).enhance(1.15)
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=92)
    return buffer.getvalue(), found
