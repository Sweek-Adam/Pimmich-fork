"""
Légendes personnalisables, à la manière de Snapchat : police, taille, couleurs, fond (bandeau, bulle, étiquette),
gras / italique / souligné / majuscules, contour, ombre ou halo, alignement, position libre et inclinaison.

Trois familles de légendes, chacune avec son style :
  - « photo »    : légende des photos (image de base et carte postale) et des vidéos ;
  - « polaroid » : texte écrit dans la marge du polaroïd ;
  - « metadata » : infos de la photo affichées par le diaporama (date, lieu).
Une photo ou une vidéo peut aussi avoir son propre style (cache/caption_styles.json), qui remplace celui de sa famille.

Un seul moteur de dessin (Pillow) sert aux photos, aux infos et à l'aperçu de l'interface ; les vidéos reçoivent
le même style sous forme de sous-titres ASS lus par mpv (mêmes polices, mêmes mesures).
"""
import json
import logging
import math
import re
import subprocess
import threading
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE_DIR = Path(__file__).resolve().parent.parent
FONTS_DIR = BASE_DIR / "static" / "fonts"
MEDIA_STYLES_FILE = BASE_DIR / "cache" / "caption_styles.json"
SYSTEM_FONTS = Path("/usr/share/fonts/truetype")
logger = logging.getLogger(__name__)

# Police : (nom vu par libass/mpv, fichiers régulier / gras / italique / gras-italique ; None = simulé)
FONTS = {
    "caveat": ("Caveat", [FONTS_DIR / "Caveat-Regular.ttf"]),
    "patrick": ("Patrick Hand", [FONTS_DIR / "PatrickHand-Regular.ttf"]),
    "marker": ("Permanent Marker", [FONTS_DIR / "PermanentMarker-Regular.ttf"]),
    "elite": ("Special Elite", [FONTS_DIR / "SpecialElite-Regular.ttf"]),
    "sans": ("DejaVu Sans", [SYSTEM_FONTS / "dejavu" / f"DejaVuSans{s}.ttf" for s in ("", "-Bold", "-Oblique", "-BoldOblique")]),
    "serif": ("DejaVu Serif", [SYSTEM_FONTS / "dejavu" / f"DejaVuSerif{s}.ttf" for s in ("", "-Bold", "-Italic", "-BoldItalic")]),
}
SCOPES = ("photo", "polaroid", "metadata")
BACKGROUNDS = ("none", "band", "bubble", "box")
SHADOWS = ("none", "drop", "glow")
ALIGNS = ("left", "center", "right")

DEFAULTS = {
    # L'aspect d'origine de Pimmich : bulle blanche, écriture manuscrite noire, en bas
    "photo": {"font": "caveat", "size": 5.0, "color": "#000000", "bold": False, "italic": False, "underline": False,
              "uppercase": False, "background": "bubble", "bg_color": "#ffffff", "bg_opacity": 70, "outline": 0,
              "outline_color": "#000000", "shadow": "none", "shadow_color": "#000000", "align": "center",
              "x": 50.0, "y": 90.0, "rotation": 0, "width": 90},
    "polaroid": {"font": "caveat", "size": 7.0, "color": "#505050", "bold": False, "italic": False, "underline": False,
                 "uppercase": False, "background": "none", "bg_color": "#ffffff", "bg_opacity": 0, "outline": 0,
                 "outline_color": "#000000", "shadow": "none", "shadow_color": "#000000", "align": "center",
                 "x": 50.0, "y": 50.0, "rotation": 0, "width": 92},
    "metadata": {"font": "sans", "size": 3.2, "color": "#ffffff", "bold": True, "italic": False, "underline": False,
                 "uppercase": False, "background": "box", "bg_color": "#000000", "bg_opacity": 50, "outline": 2,
                 "outline_color": "#000000", "shadow": "none", "shadow_color": "#000000", "align": "left",
                 "x": 2.0, "y": 95.0, "rotation": 0, "width": 96},
}

# Modèles proposés dans l'éditeur (ils ne changent que l'apparence, pas la position)
PRESETS = {
    "classic": {"font": "sans", "size": 3.6, "color": "#ffffff", "bold": False, "italic": False, "underline": False, "uppercase": False,
                "background": "band", "bg_color": "#000000", "bg_opacity": 55, "outline": 0, "shadow": "none", "align": "center"},
    "big": {"font": "sans", "size": 8.0, "color": "#ffffff", "bold": True, "italic": False, "underline": False, "uppercase": True,
            "background": "none", "outline": 3, "outline_color": "#000000", "shadow": "drop", "shadow_color": "#000000"},
    "bubble": {"font": "patrick", "size": 5.0, "color": "#111111", "bold": False, "italic": False, "underline": False, "uppercase": False,
               "background": "bubble", "bg_color": "#ffffff", "bg_opacity": 85, "outline": 0, "shadow": "none"},
    "label": {"font": "elite", "size": 4.2, "color": "#ffffff", "bold": False, "italic": False, "underline": False, "uppercase": False,
              "background": "box", "bg_color": "#111111", "bg_opacity": 80, "outline": 0, "shadow": "none"},
    "handwritten": {"font": "caveat", "size": 6.5, "color": "#ffffff", "bold": False, "italic": False, "underline": False, "uppercase": False,
                    "background": "none", "outline": 0, "shadow": "drop", "shadow_color": "#000000"},
    "neon": {"font": "marker", "size": 6.0, "color": "#ffe9fb", "bold": False, "italic": False, "underline": False, "uppercase": False,
             "background": "none", "outline": 0, "shadow": "glow", "shadow_color": "#ff3fd2"},
}

COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_restyle_lock = threading.Lock()
_restyle_again = threading.Event()


# --- Styles ---------------------------------------------------------------

def _number(value, low, high, default):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(value) else min(high, max(low, value))


def clean(style, scope="photo"):
    """Style complet et sûr : valeurs bornées, inconnues remplacées par celles par défaut de la famille."""
    base = dict(DEFAULTS.get(scope, DEFAULTS["photo"]))
    style = style if isinstance(style, dict) else {}
    out = dict(base)
    for key in ("bold", "italic", "underline", "uppercase"):
        if key in style:
            out[key] = bool(style[key])
    for key, choices in (("font", FONTS), ("background", BACKGROUNDS), ("shadow", SHADOWS), ("align", ALIGNS)):
        if style.get(key) in choices:
            out[key] = style[key]
    for key in ("color", "bg_color", "outline_color", "shadow_color"):
        if isinstance(style.get(key), str) and COLOR.match(style[key]):
            out[key] = style[key].lower()
    for key, low, high in (("size", 1, 20), ("bg_opacity", 0, 100), ("outline", 0, 10), ("x", 0, 100), ("y", 0, 100),
                           ("rotation", -45, 45), ("width", 20, 100)):
        if key in style:
            out[key] = round(_number(style[key], low, high, base[key]), 1)
    return out


def scope_style(config, scope="photo"):
    saved = (config.get("caption_styles") or {}).get(scope)
    if saved is None and scope == "metadata":
        saved = legacy_metadata_style(config)
    return clean(saved, scope)


def legacy_metadata_style(config):
    """Réglages des infos d'avant l'éditeur de légendes (police, couleurs, position...), traduits en style."""
    font_path = str(config.get("photo_metadata_font_path", ""))
    position = config.get("photo_metadata_position", "bottom_left")
    bg = str(config.get("photo_metadata_background_color", "#00000080"))
    alpha = int(bg[7:9], 16) if len(bg) == 9 and re.match(r"^#[0-9a-fA-F]{8}$", bg) else 128
    try:
        size = round(int(config.get("photo_metadata_font_size", 23)) / 7.2, 1)  # px sur un écran 720p -> % de la hauteur
    except (TypeError, ValueError):
        size = 3.2
    return {"font": "serif" if "Serif" in font_path else "sans", "bold": "Bold" in font_path or not font_path, "size": size,
            "color": config.get("photo_metadata_color", "#ffffff"), "outline_color": config.get("photo_metadata_outline_color", "#000000"),
            "outline": 2, "background": "box" if config.get("photo_metadata_background_enabled", True) else "none",
            "bg_color": bg[:7], "bg_opacity": round(alpha / 2.55),
            "align": {"left": "left", "right": "right"}.get(position.split("_")[-1], "center"),
            "x": {"left": 2, "right": 98}.get(position.split("_")[-1], 50), "y": 5 if position.startswith("top") else 95}


def load_media_styles():
    try:
        return json.loads(MEDIA_STYLES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_media_style(key, style):
    """Style propre à une photo / vidéo (None : revient au style général)."""
    styles = load_media_styles()
    if style is None:
        styles.pop(key, None)
    else:
        styles[key] = clean(style, "photo")
    MEDIA_STYLES_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = MEDIA_STYLES_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(styles, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(MEDIA_STYLES_FILE)


def style_for(config, scope="photo", key=None):
    if scope == "photo" and key:
        own = load_media_styles().get(key)
        if own:
            return clean(own, "photo")
    return scope_style(config, scope)


# --- Dessin ---------------------------------------------------------------

def _rgba(hex_color, opacity=100):
    hex_color = hex_color if COLOR.match(str(hex_color)) else "#000000"
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5)) + (round(255 * opacity / 100),)


def font_file(style):
    """(chemin de police, gras simulé, italique simulé)."""
    files = FONTS.get(style["font"], FONTS["caveat"])[1]
    wanted = (1 if style["bold"] else 0) + (2 if style["italic"] else 0)
    if wanted < len(files) and files[wanted].is_file():
        return files[wanted], False, False
    for i in (2, 1):  # une seule des deux variantes disponible
        if wanted == 3 and i < len(files) and files[i].is_file():
            return files[i], i == 2, i == 1
    regular = files[0] if files[0].is_file() else FONTS["caveat"][1][0]
    return regular, style["bold"], style["italic"]


def _font(style, px):
    path, fake_bold, fake_italic = font_file(style)
    try:
        return ImageFont.truetype(str(path), max(6, px)), fake_bold, fake_italic
    except OSError:
        return ImageFont.load_default(max(6, px)), style["bold"], style["italic"]


def drawable(text, font):
    """Retire les caractères absents de la police (emoji...), qui sortiraient en carrés vides."""
    def glyph(ch):
        box = font.getbbox(ch)
        im = Image.new("L", (max(1, box[2]) + 2, max(1, box[3]) + 2))
        ImageDraw.Draw(im).text((0, 0), ch, font=font, fill=255)
        return im.tobytes()
    try:
        missing = glyph("\U0010fffd")
    except Exception:
        return text
    kept = []
    for ch in str(text):
        if ord(ch) < 0x250 or ch.isspace():
            kept.append(ch)
            continue
        try:
            if glyph(ch) != missing:
                kept.append(ch)
        except Exception:
            pass
    return re.sub(r"[ \t]{2,}", " ", "".join(kept))


def wrap(text, font, max_width):
    """Coupe le texte en lignes tenant dans max_width (les retours à la ligne saisis sont gardés)."""
    lines = []
    for paragraph in str(text).splitlines() or [""]:
        words, line = paragraph.split(), ""
        for word in words:
            attempt = f"{line} {word}".strip()
            if line and font.getlength(attempt) > max_width:
                lines.append(line)
                line = word
            else:
                line = attempt
        lines.append(line)
    return [l for l in lines if l.strip()] or [""]


def _text_layer(lines, style, font, px, fake_bold, fake_italic):
    """Calque transparent contenant le texte (contour, gras simulé, soulignement, italique simulé)."""
    ascent, descent = font.getmetrics()
    line_h = int((ascent + descent) * 1.08)
    stroke = round(px * 0.045 * style["outline"]) if style["outline"] else 0
    bold = max(1, round(px * 0.035)) if fake_bold else 0
    pad = stroke + bold + 2
    widths = [font.getlength(l) for l in lines]
    w, h = int(max(widths) + 2 * pad) + 1, int(line_h * len(lines) + 2 * pad)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    color = _rgba(style["color"])
    for i, (line, lw) in enumerate(zip(lines, widths)):
        x = {"left": pad, "right": w - pad - lw}.get(style["align"], (w - lw) / 2)
        y = pad + i * line_h
        if stroke:
            draw.text((x, y), line, font=font, fill=_rgba(style["outline_color"]), stroke_width=stroke + bold,
                      stroke_fill=_rgba(style["outline_color"]))
        draw.text((x, y), line, font=font, fill=color, stroke_width=bold, stroke_fill=color)
        if style["underline"] and line:
            thick = max(1, round(px * 0.06))
            uy = y + ascent + max(thick, round(descent * 0.35))
            draw.rectangle([x, uy, x + lw, uy + thick], fill=color)
    if fake_italic:
        slant = 0.2
        extra = int(h * slant)
        wide = Image.new("RGBA", (w + extra, h), (0, 0, 0, 0))
        wide.paste(layer, (0, 0))
        # le haut du texte glisse vers la droite
        layer = wide.transform(wide.size, Image.Transform.AFFINE, (1, slant, -extra, 0, 1, 0), resample=Image.Resampling.BICUBIC)
    return layer


def _block(text, style, px, max_width):
    """Le bloc de légende prêt à poser (texte, ombre / halo, bulle ou étiquette), et sa marge intérieure."""
    font, fake_bold, fake_italic = _font(style, px)
    text = drawable(str(text).upper() if style["uppercase"] else str(text), font)
    pad_x, pad_y = (round(px * 0.6), round(px * 0.3)) if style["background"] in ("bubble", "box", "band") else (0, 0)
    lines = wrap(text, font, max(px * 2, max_width - 2 * pad_x))
    layer = _text_layer(lines, style, font, px, fake_bold, fake_italic)
    if style["shadow"] != "none":
        glow = style["shadow"] == "glow"
        margin = round(px * (0.5 if glow else 0.25))
        shadowed = Image.new("RGBA", (layer.width + 2 * margin, layer.height + 2 * margin), (0, 0, 0, 0))
        tint = Image.new("RGBA", layer.size, _rgba(style["shadow_color"], 100 if glow else 70))
        mask = layer.split()[3]
        offset = (margin, margin) if glow else (margin + round(px * 0.06), margin + round(px * 0.08))
        shadowed.paste(tint, offset, mask)
        shadowed = shadowed.filter(ImageFilter.GaussianBlur(px * (0.18 if glow else 0.07)))
        if glow:  # halo plus dense
            shadowed = Image.alpha_composite(Image.alpha_composite(shadowed, shadowed), shadowed)
        shadowed.alpha_composite(layer, (margin, margin))
        layer = shadowed
    if style["background"] in ("bubble", "box"):
        block = Image.new("RGBA", (layer.width + 2 * pad_x, layer.height + 2 * pad_y), (0, 0, 0, 0))
        radius = round(px * 0.45) if style["background"] == "bubble" else 0
        ImageDraw.Draw(block).rounded_rectangle([0, 0, block.width - 1, block.height - 1], radius=radius,
                                                fill=_rgba(style["bg_color"], style["bg_opacity"]))
        block.alpha_composite(layer, (pad_x, pad_y))
        layer = block
    elif style["background"] == "band":
        canvas = Image.new("RGBA", (layer.width, layer.height + 2 * pad_y), (0, 0, 0, 0))
        canvas.alpha_composite(layer, (0, pad_y))
        layer = canvas
    return layer


def place(block_size, style, area):
    """Coin haut-gauche du bloc dans la zone (x, y : point d'ancrage en %, le bloc reste entier dans la zone)."""
    ax, ay, aw, ah = area
    bw, bh = block_size
    px, py = ax + aw * style["x"] / 100, ay + ah * style["y"] / 100
    left = {"left": px, "right": px - bw}.get(style["align"], px - bw / 2)
    top = py - bh / 2
    left = min(max(left, ax), ax + aw - bw) if bw <= aw else ax + (aw - bw) / 2
    top = min(max(top, ay), ay + ah - bh) if bh <= ah else ay + (ah - bh) / 2
    return round(left), round(top)


def draw(image, text, style, area=None, size_ref=None):
    """Pose la légende sur l'image (copie). area : (x, y, l, h) où la placer (toute l'image par défaut) ;
    size_ref : hauteur servant à la taille du texte (celle de la zone par défaut)."""
    if not text or not str(text).strip():
        return image
    mode = image.mode
    canvas = image.convert("RGBA")
    area = area or (0, 0, canvas.width, canvas.height)
    px = round((size_ref or area[3]) * style["size"] / 100)
    block = _block(text, style, px, area[2] * style["width"] / 100)
    if style["rotation"] and style["background"] != "band":
        block = block.rotate(style["rotation"], expand=True, resample=Image.Resampling.BICUBIC)
    left, top = place(block.size, style, area)
    if style["background"] == "band":
        band = Image.new("RGBA", (area[2], block.height), _rgba(style["bg_color"], style["bg_opacity"]))
        canvas.alpha_composite(band, (area[0], max(0, top)))
    canvas.alpha_composite(block, (max(0, left), max(0, top)))
    return canvas if mode == "RGBA" else canvas.convert(mode if mode in ("RGB", "L") else "RGB")


def overlay(text, style, width, height):
    """Calque transparent de la taille de l'écran avec la légende (infos du diaporama)."""
    return draw(Image.new("RGBA", (width, height), (0, 0, 0, 0)), text, style)


# --- Vidéos : sous-titres ASS pour mpv ------------------------------------

def _ass_color(hex_color, opacity=100):
    r, g, b, a = _rgba(hex_color, opacity)
    return f"&H{255 - a:02X}{b:02X}{g:02X}{r:02X}"


def _c(hex_color):
    """Couleur pour une balise ASS (\\1c, \\3c...) : &HBBGGRR&."""
    return f"&H{_ass_color(hex_color)[4:]}&"


def _ass_escape(text):
    return str(text).replace("\\", "⧵").replace("{", "(").replace("}", ")")


def _rounded_rect(w, h, r):
    """Rectangle (arrondi) en dessin vectoriel ASS, coin haut-gauche en 0,0."""
    if r <= 0:
        return f"m 0 0 l {w} 0 {w} {h} 0 {h}"
    k = r * 0.45  # approximation du quart de cercle
    return (f"m {r} 0 l {w - r} 0 b {w - k} 0 {w} {k} {w} {r} l {w} {h - r} b {w} {h - k} {w - k} {h} {w - r} {h} "
            f"l {r} {h} b {k} {h} 0 {h - k} 0 {h - r} l 0 {r} b 0 {k} {k} 0 {r} 0")


def ass_document(text, style, width, height):
    """Fichier de sous-titres ASS affichant la légende pendant toute la vidéo (mesures faites avec Pillow)."""
    px = round(height * style["size"] / 100)
    font, _, _ = _font(style, px)
    shown = drawable(str(text).upper() if style["uppercase"] else str(text), font)
    lines = wrap(shown, font, width * style["width"] / 100 - (2 * round(px * 0.6) if style["background"] != "none" else 0))
    block = _block(text, style, px, width * style["width"] / 100)
    left, top = place(block.size, style, (0, 0, width, height))
    cx = {"left": left, "right": left + block.width}.get(style["align"], left + block.width / 2)
    cy = top + block.height / 2
    an = {"left": 4, "right": 6}.get(style["align"], 5)
    ascent, descent = font.getmetrics()
    ass_size = round((ascent + descent) * 1.0)  # libass : taille = hauteur de ligne
    bord = round(px * 0.045 * style["outline"], 1)
    tags = [f"\\an{an}", f"\\pos({cx:.0f},{cy:.0f})", f"\\fs{ass_size}", f"\\b{int(style['bold'])}", f"\\i{int(style['italic'])}",
            f"\\u{int(style['underline'])}", f"\\1c{_c(style['color'])}", f"\\1a&H00&"]
    if style["rotation"] and style["background"] != "band":
        tags.append(f"\\frz{style['rotation']:.0f}")
    if style["shadow"] == "glow":
        tags += [f"\\bord{max(bord, round(px * 0.12, 1))}", f"\\3c{_c(style['shadow_color'])}", f"\\blur{round(px * 0.15, 1)}", "\\shad0"]
    else:
        tags += [f"\\bord{bord}", f"\\3c{_c(style['outline_color'])}"]
        tags += [f"\\shad{round(px * 0.07, 1)}", f"\\4c{_c(style['shadow_color'])}", "\\4a&H50&"] if style["shadow"] == "drop" else ["\\shad0"]
    dialogue = "{" + "".join(tags) + "}" + "\\N".join(_ass_escape(l) for l in lines)
    events = []
    if style["background"] != "none":
        bg = _ass_color(style["bg_color"], style["bg_opacity"])
        if style["background"] == "band":
            shape, x0, y0 = _rounded_rect(width, block.height, 0), 0, top
        else:
            r = round(px * 0.45) if style["background"] == "bubble" else 0
            shape, x0, y0 = _rounded_rect(block.width, block.height, r), left, top
        rot = f"\\org({cx:.0f},{cy:.0f})\\frz{style['rotation']:.0f}" if style["rotation"] and style["background"] != "band" else ""
        events.append(f"Dialogue: 0,0:00:00.00,9:59:59.00,Box,,0,0,0,,{{\\an7\\pos({x0},{y0}){rot}\\bord0\\shad0"
                      f"\\1c&H{bg[4:]}&\\1a&H{bg[2:4]}&\\p1}}{shape}{{\\p0}}")
    events.append(f"Dialogue: 1,0:00:00.00,9:59:59.00,Caption,,0,0,0,,{dialogue}")
    name = FONTS.get(style["font"], FONTS["caveat"])[0]
    return "\n".join([
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}", "WrapStyle: 2",
        "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
        "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Caption,{name},{ass_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1",
        f"Style: Box,{name},{ass_size},&H00000000,&H00000000,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text", *events, ""])


def video_size(path):
    """Largeur et hauteur de la vidéo (ffprobe), sinon 1920x1080."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                              "-of", "csv=p=0:s=x", str(path)], capture_output=True, text=True, timeout=10).stdout.strip()
        w, h = (int(v) for v in out.split("x")[:2])
        return w, h
    except (OSError, ValueError, subprocess.SubprocessError):
        return 1920, 1080


def media_text(key):
    """Légende saisie pour un média (config/text_states.json, sinon cache/user_texts.json)."""
    for path in (BASE_DIR / "config" / "text_states.json", BASE_DIR / "cache" / "user_texts.json"):
        try:
            text = json.loads(path.read_text(encoding="utf-8")).get(key)
        except (OSError, ValueError):
            continue
        if text and str(text).strip():
            return str(text)
    return ""


def video_subtitles(video_path, config, out_path):
    """Écrit les sous-titres de la légende d'une vidéo préparée ; retourne le chemin, ou None sans légende."""
    video_path = Path(video_path)
    key = f"{video_path.parent.name}/{video_path.name}"
    text = media_text(key)
    if not text:
        return None
    width, height = video_size(video_path)
    Path(out_path).write_text(ass_document(text, style_for(config, "photo", key), width, height), encoding="utf-8")
    return str(out_path)


# --- Réapplication du style aux légendes déjà posées ----------------------

def restyle_all(prepared_dir, keys=None):
    """Redessine les légendes des photos (et polaroïds) avec le style actuel. keys : seulement ces photos.
    Un seul passage à la fois ; une demande pendant un passage en relance un autre à la fin."""
    from utils.image_filters import add_text_to_image, add_text_to_polaroid
    if not _restyle_lock.acquire(blocking=False):
        _restyle_again.set()
        return 0
    done = 0
    try:
        while True:
            _restyle_again.clear()
            for name, apply, suffix in (("text_states.json", add_text_to_image, ""), ("polaroid_texts.json", add_text_to_polaroid, "_polaroid")):
                try:
                    texts = json.loads((BASE_DIR / "config" / name).read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                for key, text in texts.items():
                    if keys is not None and key not in keys or not str(text).strip():
                        continue
                    path = Path(prepared_dir) / key
                    if suffix:
                        path = path.with_name(f"{path.stem}{suffix}.jpg")
                    if not path.is_file() or path.suffix.lower() not in (".jpg", ".jpeg"):
                        continue
                    try:
                        apply(str(path), text)
                        done += 1
                    except Exception as e:
                        logger.warning(f"[Légendes] {key} : {e}")
            if not _restyle_again.is_set():
                return done
    finally:
        _restyle_lock.release()
