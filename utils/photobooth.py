"""
Photomaton de fête : les photos de la fête imprimées sur une imprimante Wi-Fi, en tirages 10 × 15 cm.

- Imprimante : trouvée sur le réseau (ippfind) et ajoutée à CUPS sans pilote (« IPP Everywhere », la plupart des
  imprimantes récentes) sous le nom Pimmich_Photomaton.
- Tirage : la photo d'origine, recadrée sur 10 × 15 cm avec une marge blanche, et en bas le nom de la fête et la date
  (écriture manuscrite), comme une photo de photomaton.
- Les invités impriment la photo affichée sur le cadre (un nombre de tirages limité par invité) ; sur option, chaque
  photo reçue pendant la fête est imprimée d'elle-même (avec un plafond pour toute la fête).
"""
import json
import re
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from utils.platform_info import tmp_path

QUEUE = "Pimmich_Photomaton"
DPI = 300
SIZE = (1800, 1200)       # 15 × 10 cm à 300 points par pouce
MEDIA = "w288h432"        # 4 × 6 pouces (10 × 15 cm) pour CUPS
COUNTS_FILE = tmp_path("pimmich_photobooth.json")
DEFAULTS = {"enabled": False, "uri": "", "name": "", "per_guest": 2, "auto": False, "max_auto": 50}
HAND = Path(__file__).resolve().parent.parent / "static" / "fonts" / "Caveat-Regular.ttf"
_lock = threading.Lock()


def settings(config):
    data = dict(DEFAULTS, **((config or {}).get("photobooth") or {}))
    data["per_guest"] = max(0, min(20, int(data.get("per_guest") or 0)))
    data["max_auto"] = max(1, min(500, int(data.get("max_auto") or 50)))
    return data


def discover(timeout=6):
    """Imprimantes du réseau : [{uri, name}]."""
    try:
        out = subprocess.run(["ippfind", "-T", str(timeout)], capture_output=True, text=True, timeout=timeout + 5).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    found = []
    for uri in sorted(set(out.split())):
        match = re.match(r"^ipps?://([^/:]+)", uri)
        if match:
            found.append({"uri": uri, "name": match.group(1).removesuffix(".local").replace("-", " ")})
    return found


NOT_RUNNING = "L'impression n'est pas activée sur le Raspberry Pi. Lancez une fois : sudo ~/pimmich/utils/enable_printing.sh"


def _cups_down(output):
    return "Unable to connect to server" in (output or "") or "Impossible de se connecter" in (output or "")


def setup(uri):
    """Ajoute l'imprimante à CUPS (sans pilote). (succès, message d'erreur)."""
    if not re.match(r"^ipps?://[A-Za-z0-9.\-:\[\]]+(/[\w./\-]*)?$", uri or ""):
        return False, "Adresse d'imprimante invalide."
    try:
        result = subprocess.run(["lpadmin", "-p", QUEUE, "-E", "-v", uri, "-m", "everywhere"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)
    output = (result.stderr or result.stdout).strip()
    if result.returncode != 0 and _cups_down(output):
        return False, NOT_RUNNING
    return result.returncode == 0, output[:300]


def card(image, title="", subtitle=""):
    """Tirage 10 × 15 : la photo avec une marge blanche, le titre et la date dans la bande du bas."""
    from utils.boot_screen import font
    image = ImageOps.exif_transpose(image).convert("RGB")
    portrait = image.height > image.width
    w, h = (SIZE[1], SIZE[0]) if portrait else SIZE
    page = Image.new("RGB", (w, h), (255, 255, 255))
    margin, band = 50, 170 if (title or subtitle) else 50
    photo = ImageOps.fit(image, (w - 2 * margin, h - margin - band), Image.LANCZOS, centering=(0.5, 0.42))
    page.paste(photo, (margin, margin))
    draw = ImageDraw.Draw(page)
    if title:
        hand = font(90, 400, str(HAND)) if HAND.exists() else font(70, 700)
        draw.text((margin + 10, h - band + 30), title, font=hand, fill=(40, 36, 48))
    if subtitle:
        small = font(38, 600)
        draw.text((w - margin - draw.textlength(subtitle, font=small), h - band + 72), subtitle, font=small, fill=(130, 124, 140))
    return page


def send(image, title="", subtitle="", queue=QUEUE):
    """Imprime un tirage ; retourne l'identifiant du travail CUPS. RuntimeError si l'imprimante refuse."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        card(image, title, subtitle).save(tmp.name, "JPEG", quality=95, dpi=(DPI, DPI))
        path = tmp.name
    try:
        result = subprocess.run(["lp", "-d", queue, "-o", f"media={MEDIA}", "-o", "fit-to-page", "-o", "print-quality=5", path],
                                capture_output=True, text=True, timeout=60)
    finally:
        Path(path).unlink(missing_ok=True)
    if result.returncode != 0:
        output = (result.stderr or result.stdout).strip()
        raise RuntimeError(NOT_RUNNING if _cups_down(output) else output[:300] or "impression refusée")
    match = re.search(r"(\S+-\d+)", result.stdout)
    return match.group(1) if match else result.stdout.strip()


def _counts():
    try:
        return json.loads(Path(str(COUNTS_FILE)).read_text())
    except (OSError, ValueError):
        return {}


def take(key, limit):
    """Compte un tirage pour cet invité (ou « auto ») ; False si son quota est atteint."""
    with _lock:
        counts = _counts()
        if counts.get(key, 0) >= limit:
            return False
        counts[key] = counts.get(key, 0) + 1
        Path(str(COUNTS_FILE)).write_text(json.dumps(counts))
        return True


def reset_counts():
    Path(str(COUNTS_FILE)).unlink(missing_ok=True)


def caption(config, now=None):
    """Titre et date du tirage : le nom de la fête, et la date du jour."""
    from utils import party
    months = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    now = now or time.localtime()
    return party.state(config).get("name") or "", f"{now.tm_mday} {months[now.tm_mon - 1]} {now.tm_year}"
