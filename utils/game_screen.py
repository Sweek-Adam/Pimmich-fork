"""
Écrans du jeu « Où et quand ? » sur le cadre (images Pillow) : salle d'attente avec le QR code, question avec la
photo et le compte à rebours, réponse et points, podium final.
"""
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFilter

from utils import family_game as game
from utils.message_renderer import _font, _gradient

from utils.message_renderer import FONT_DIRS

TITLE, HAND = "PermanentMarker-Regular.ttf", "PatrickHand-Regular.ttf"
# Texte lisible avec accents : DejaVu (Raspberry Pi OS), sinon la police manuscrite fournie avec Pimmich
BOLD = "DejaVuSans-Bold.ttf" if any((d / "DejaVuSans-Bold.ttf").exists() for d in FONT_DIRS) else HAND
PREPARED = Path(__file__).resolve().parent.parent / "static" / "prepared"
WHITE, GOLD, SOFT = (255, 255, 255), (255, 214, 110), (220, 220, 235)
_cache = {"key": None, "image": None}


def _center(draw, text, y, font, fill=WHITE, width=None, shadow=True):
    w = draw.textlength(text, font=font)
    x = ((width or draw.im.size[0]) - w) / 2
    if shadow:
        draw.text((x + 3, y + 3), text, font=font, fill=(0, 0, 0))
    draw.text((x, y), text, font=font, fill=fill)


def _fit_font(draw, text, name, size, max_width):
    font = _font(name, size)
    while draw.textlength(text, font=font) > max_width and size > 14:
        size = int(size * 0.9)
        font = _font(name, size)
    return font


def _qr(url, size):
    qr = qrcode.QRCode(border=2)
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB").resize((size, size), Image.NEAREST)


def _photo_background(key, W, H, dim):
    """La photo de la question, entière sur un fond flou d'elle-même (mémorisée pour la durée de la question)."""
    cache_key = (key, W, H, dim)
    if _cache["key"] == cache_key:
        return _cache["image"].copy()
    try:
        with Image.open(PREPARED / key) as photo:
            photo = photo.convert("RGB")
            photo.thumbnail((W, H))
            back = photo.resize((max(1, W // 8), max(1, H // 8))).filter(ImageFilter.GaussianBlur(3)).resize((W, H))
            canvas = Image.blend(back, Image.new("RGB", (W, H)), 0.45)
            canvas.paste(photo, ((W - photo.width) // 2, (H - photo.height) // 2))
    except Exception:
        canvas = _gradient(W, H, (40, 30, 80), (10, 10, 30)).convert("RGB")
    if dim:
        canvas = Image.blend(canvas, Image.new("RGB", (W, H)), dim)
    _cache["key"], _cache["image"] = cache_key, canvas
    return canvas.copy()


def _band(canvas, top, height, alpha=170):
    overlay = Image.new("RGBA", (canvas.width, int(height)), (20, 12, 40, alpha))
    canvas.paste(overlay, (0, int(top)), overlay)


def _ranking(draw, ranking, x, y, W, H, gained=None, limit=6):
    row = int(H * 0.065)
    font, score_font = _font(BOLD, int(row * 0.62)), _font(BOLD, int(row * 0.62))
    for i, (name, score) in enumerate(ranking[:limit]):
        color = GOLD if i == 0 else WHITE
        draw.text((x, y + i * row), f"{i + 1}.  {name}", font=font, fill=color)
        text = f"{score} pts" + (f"  (+{gained[name]})" if gained and gained.get(name) else "")
        draw.text((x + W * 0.36 - draw.textlength(text, font=score_font), y + i * row), text, font=score_font, fill=color)


def frame(state, now, W, H, url, translate=lambda s, **k: s % k if k else s):
    """Image de l'écran du jeu à cet instant."""
    kind, number, left = game.phase(state, now)
    if kind in ("lobby", "over") or number is None and kind != "podium":
        canvas = _gradient(W, H, (70, 30, 120), (16, 12, 44)).convert("RGB")
        draw = ImageDraw.Draw(canvas)
        _center(draw, translate("Où et quand ?"), H * 0.06, _font(TITLE, int(H * 0.11)), GOLD)
        _center(draw, translate("Le jeu des photos de famille"), H * 0.2, _font(HAND, int(H * 0.05)), SOFT, shadow=False)
        side = int(H * 0.45)
        canvas.paste(_qr(url, side), (int(W * 0.12), int(H * 0.32)))
        draw.text((W * 0.12, H * 0.32 + side + H * 0.02), translate("Scannez pour jouer"), font=_font(BOLD, int(H * 0.035)), fill=WHITE)
        players = (state or {}).get("players", {})
        draw.text((W * 0.55, H * 0.32), translate("Joueurs (%(count)s)", count=len(players)), font=_font(BOLD, int(H * 0.045)), fill=GOLD)
        for i, name in enumerate(sorted(players.values())[:10]):
            draw.text((W * 0.55, H * 0.4 + i * H * 0.055), f"– {name}", font=_font(BOLD, int(H * 0.04)), fill=WHITE)
        hint = translate("Appuyez sur « Commencer » sur un téléphone") if players else translate("Entrez votre prénom sur le téléphone")
        _center(draw, hint, H * 0.9, _font(HAND, int(H * 0.045)), SOFT, shadow=False)
        return canvas
    if kind == "podium":
        canvas = _gradient(W, H, (90, 30, 110), (20, 10, 40)).convert("RGB")
        draw = ImageDraw.Draw(canvas)
        ranking = [(n, s) for n, s, _p in game.scores(state)]
        winner = ranking[0][0] if ranking else ""
        _center(draw, translate("Bravo %(name)s !", name=winner), H * 0.08, _font(TITLE, int(H * 0.1)), GOLD)
        _center(draw, translate("Classement final"), H * 0.24, _font(HAND, int(H * 0.055)), SOFT, shadow=False)
        _ranking(draw, ranking, W * 0.3, H * 0.36, W, H, limit=8)
        return canvas
    question = state["questions"][number]
    total = len(state["questions"])
    reveal = kind == "reveal"
    canvas = _photo_background(question["key"], W, H, 0.35 if reveal else 0).convert("RGB")
    draw = ImageDraw.Draw(canvas)
    _band(canvas, 0, H * 0.13)
    text = f"{number + 1}/{total} · {translate(game.QUESTIONS[question['kind']])}"
    draw.text((W * 0.03, H * 0.035), text, font=_fit_font(draw, text, BOLD, int(H * 0.05), W * 0.8), fill=WHITE)
    if not reveal:
        # Compte à rebours et nombre de réponses
        radius = int(H * 0.07)
        cx, cy = W - radius - W * 0.03, H * 0.065
        draw.ellipse([cx - radius * 0.75, cy - radius * 0.75, cx + radius * 0.75, cy + radius * 0.75], fill=(230, 60, 110))
        seconds = str(max(0, int(left + 0.99)))
        font = _font(BOLD, int(radius * 0.8))
        draw.text((cx - draw.textlength(seconds, font=font) / 2, cy - radius * 0.48), seconds, font=font, fill=WHITE)
        answered = len(state["answers"].get(str(number), {}))
        _band(canvas, H * 0.9, H * 0.1)
        info = translate("%(done)s / %(count)s ont répondu", done=answered, count=len(state["players"]))
        if question.get("options"):
            info = "   ".join(question["options"]) + "     ·     " + info
        draw.text((W * 0.03, H * 0.92), info, font=_fit_font(draw, info, BOLD, int(H * 0.04), W * 0.94), fill=WHITE)
        return canvas
    answer = str(question["answer"])
    _center(draw, answer, H * 0.2, _fit_font(draw, answer, TITLE, int(H * 0.16), W * 0.9), GOLD)
    previous = {n: s for n, s, _p in game.scores(state, number - 1)} if number else {}
    ranking = [(n, s) for n, s, _p in game.scores(state, number)]
    gained = {n: s - previous.get(n, 0) for n, s in ranking}
    _band(canvas, H * 0.45, H * 0.5, 150)
    _ranking(draw, ranking, W * 0.3, H * 0.48, W, H, gained)
    return canvas
