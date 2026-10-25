"""
Écrans des jeux sur le cadre (images Pillow) : salle d'attente avec le QR code, questions (photo seule, photos
côte à côte, photos à mémoriser, zoom / puzzle / flou qui se dévoilent), votes (légendes, photos du défi),
réponse et points, podium final.
"""
import random
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFilter

from utils import family_game as game
from utils.message_renderer import FONT_DIRS, N_, _font, _gradient

TITLE, HAND = "PermanentMarker-Regular.ttf", "PatrickHand-Regular.ttf"
# Texte lisible avec accents : DejaVu (Raspberry Pi OS), sinon la police manuscrite fournie avec Pimmich
BOLD = "DejaVuSans-Bold.ttf" if any((d / "DejaVuSans-Bold.ttf").exists() for d in FONT_DIRS) else HAND
PREPARED = Path(__file__).resolve().parent.parent / "static" / "prepared"
WHITE, GOLD, SOFT = (255, 255, 255), (255, 214, 110), (220, 220, 235)
_cache = {}


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


def _wrap(draw, text, font, max_width):
    words, lines, line = str(text).split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    return lines + ([line] if line else [])


def _qr(url, size):
    qr = qrcode.QRCode(border=2)
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB").resize((size, size), Image.NEAREST)


def _open(path, box):
    """Photo réduite pour tenir dans `box` (mémorisée)."""
    key = (str(path), box)
    if key not in _cache:
        if len(_cache) > 40:
            _cache.clear()
        try:
            with Image.open(path) as photo:
                photo = photo.convert("RGB")
                photo.thumbnail(box)
                _cache[key] = photo
        except Exception:
            _cache[key] = Image.new("RGB", (max(1, box[0] // 2), max(1, box[1] // 2)), (60, 60, 80))
    return _cache[key]


def _backdrop(W, H):
    return _gradient(W, H, (70, 30, 120), (16, 12, 44)).convert("RGB")


def _photo_screen(path, W, H, dim=0.0, effect=None, progress=1.0, seed=0):
    """La photo, entière sur un fond flou d'elle-même ; un effet la dévoile peu à peu (progress de 0 à 1)."""
    photo = _open(path, (W, H))
    if effect == "zoom" and progress < 1:
        rng = random.Random(seed)
        zoom = 1 + 5 * (1 - progress) ** 1.6
        cw, ch = photo.width / zoom, photo.height / zoom
        cx, cy = rng.uniform(cw / 2, photo.width - cw / 2), rng.uniform(ch / 2, photo.height - ch / 2)
        photo = photo.crop((int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2))).resize(photo.size, Image.BILINEAR)
    elif effect == "blur" and progress < 1:
        small = photo.resize((max(1, photo.width // 6), max(1, photo.height // 6)))
        photo = small.filter(ImageFilter.GaussianBlur(9 * (1 - progress))).resize(photo.size, Image.BILINEAR)
    elif effect == "puzzle" and progress < 1:
        photo = _puzzle(photo, progress, seed)
    back = photo.resize((max(1, W // 8), max(1, H // 8))).filter(ImageFilter.GaussianBlur(3)).resize((W, H))
    canvas = Image.blend(back, Image.new("RGB", (W, H)), 0.45)
    canvas.paste(photo, ((W - photo.width) // 2, (H - photo.height) // 2))
    if dim:
        canvas = Image.blend(canvas, Image.new("RGB", (W, H)), dim)
    return canvas


def _puzzle(photo, progress, seed, size=4):
    """Pièces mélangées qui reprennent leur place une à une."""
    rng = random.Random(seed)
    tw, th = photo.width // size, photo.height // size
    cells = list(range(size * size))
    shuffled = cells[:]
    rng.shuffle(shuffled)
    placed = set(rng.sample(cells, int(round(progress * len(cells)))))
    out = Image.new("RGB", photo.size, (20, 20, 30))
    free = [c for c in shuffled if c not in placed]
    spots = [c for c in cells if c not in placed]
    for cell in cells:
        source = cell if cell in placed else free[spots.index(cell)]
        sx, sy = (source % size) * tw, (source // size) * th
        tile = photo.crop((sx, sy, sx + tw, sy + th))
        out.paste(tile, ((cell % size) * tw + 1, (cell // size) * th + 1))
    return out


def _grid(canvas, paths, top, bottom, labels=None, cols=None):
    """Photos côte à côte (2, 4 ou 6), avec leur lettre."""
    W, H = canvas.size
    n = len(paths)
    cols = cols or (n if n <= 4 else 3)
    rows = (n + cols - 1) // cols
    gap = int(W * 0.015)
    cell_w, cell_h = (W - gap * (cols + 1)) / cols, (bottom - top - gap * (rows + 1)) / rows
    draw = ImageDraw.Draw(canvas)
    font = _font(TITLE, int(min(cell_w, cell_h) * 0.18))
    for i, path in enumerate(paths):
        row, col = divmod(i, cols)
        photo = _open(path, (int(cell_w), int(cell_h)))
        x = gap + col * (cell_w + gap) + (cell_w - photo.width) / 2
        y = top + gap + row * (cell_h + gap) + (cell_h - photo.height) / 2
        canvas.paste(photo, (int(x), int(y)))
        if labels:
            r = int(min(cell_w, cell_h) * 0.12)
            draw.ellipse([x + 8, y + 8, x + 8 + 2 * r, y + 8 + 2 * r], fill=(230, 60, 110))
            label = labels[i]
            draw.text((x + 8 + r - draw.textlength(label, font=font) / 2, y + 8 + r * 0.25), label, font=font, fill=WHITE)


def _band(canvas, top, height, alpha=170):
    overlay = Image.new("RGBA", (canvas.width, int(height)), (20, 12, 40, alpha))
    canvas.paste(overlay, (0, int(top)), overlay)


def _header(canvas, text, left=None):
    W, H = canvas.size
    _band(canvas, 0, H * 0.13)
    draw = ImageDraw.Draw(canvas)
    draw.text((W * 0.03, H * 0.035), text, font=_fit_font(draw, text, BOLD, int(H * 0.05), W * 0.8), fill=WHITE)
    if left is not None:
        radius = int(H * 0.07)
        cx, cy = W - radius - W * 0.03, H * 0.065
        draw.ellipse([cx - radius * 0.75, cy - radius * 0.75, cx + radius * 0.75, cy + radius * 0.75], fill=(230, 60, 110))
        seconds = str(max(0, int(left + 0.99)))
        font = _font(BOLD, int(radius * 0.8))
        draw.text((cx - draw.textlength(seconds, font=font) / 2, cy - radius * 0.48), seconds, font=font, fill=WHITE)


def _footer(canvas, text):
    W, H = canvas.size
    _band(canvas, H * 0.9, H * 0.1)
    draw = ImageDraw.Draw(canvas)
    draw.text((W * 0.03, H * 0.92), text, font=_fit_font(draw, text, BOLD, int(H * 0.04), W * 0.94), fill=WHITE)


def _ranking(draw, ranking, x, y, W, H, gained=None, limit=6):
    row = int(H * 0.065)
    font = _font(BOLD, int(row * 0.62))
    for i, (name, score) in enumerate(ranking[:limit]):
        color = GOLD if i == 0 else WHITE
        draw.text((x, y + i * row), f"{i + 1}.  {name}", font=font, fill=color)
        text = f"{score} pts" + (f"  (+{gained[name]})" if gained and gained.get(name) else "")
        draw.text((x + W * 0.36 - draw.textlength(text, font=font), y + i * row), text, font=font, fill=color)


def _challenge_photo(name):
    return game.PHOTOS_DIR / name


def lobby(state, W, H, url, translate):
    canvas = _backdrop(W, H)
    draw = ImageDraw.Draw(canvas)
    mode = (state or {}).get("mode", "classique")
    _center(draw, translate(game.MODES.get(mode, game.MODES["classique"])), H * 0.06, _fit_font(draw, translate(game.MODES.get(mode, "")), TITLE, int(H * 0.11), W * 0.9), GOLD)
    _center(draw, translate(N_("Le jeu des photos de famille")), H * 0.2, _font(HAND, int(H * 0.05)), SOFT, shadow=False)
    # QR code à gauche, règles au milieu, joueurs à droite
    side = int(min(H * 0.45, W * 0.24))
    top = int(H * 0.3)
    canvas.paste(_qr(url, side), (int(W * 0.04), top))
    draw.text((W * 0.04, top + side + H * 0.02), translate(N_("Scannez pour jouer")), font=_font(BOLD, int(H * 0.035)), fill=WHITE)
    left, width = W * 0.04 + side + W * 0.04, W * 0.68 - (W * 0.04 + side + W * 0.04)
    panel = Image.new("RGBA", (int(width + W * 0.03), int(H * 0.56)), (255, 255, 255, 28))
    canvas.paste(panel, (int(left - W * 0.015), int(top - H * 0.02)), panel)
    draw.text((left, top), translate(N_("Règles du jeu")), font=_font(BOLD, int(H * 0.042)), fill=GOLD)
    lines = game.rules(state, translate)
    size = 0.04
    while True:  # le texte le plus grand qui tient dans le cadre des règles
        font = _font(HAND, int(H * size))
        wrapped = [_wrap(draw, line, font, width - W * 0.03) for line in lines]
        height = sum(len(w) for w in wrapped) * H * size * 1.18 + len(wrapped) * H * 0.01
        if height <= H * 0.45 or size <= 0.026:
            break
        size -= 0.002
    y = top + H * 0.075
    for parts in wrapped:
        for i, part in enumerate(parts):
            draw.text((left, y), ("•  " if i == 0 else "    ") + part, font=font, fill=WHITE)
            y += H * size * 1.18
        y += H * 0.01
    players = (state or {}).get("players", {})
    px = W * 0.72
    draw.text((px, top), translate(N_("Joueurs (%(count)s)"), count=len(players)), font=_font(BOLD, int(H * 0.042)), fill=GOLD)
    for i, name in enumerate(sorted(players.values())[:9]):
        draw.text((px, top + H * 0.075 + i * H * 0.052), f"– {name}", font=_fit_font(draw, f"– {name}", BOLD, int(H * 0.038), W * 0.26), fill=WHITE)
    hint = translate(N_("Appuyez sur « Commencer » sur un téléphone")) if players else translate(N_("Entrez votre prénom sur le téléphone"))
    _center(draw, hint, H * 0.9, _font(HAND, int(H * 0.045)), SOFT, shadow=False)
    return canvas


def frame(state, now, W, H, url, translate=lambda s, **k: s % k if k else s):
    """Image de l'écran du jeu à cet instant."""
    kind, number, left = game.phase(state, now)
    if kind in ("lobby", "over", "bingo") or (number is None and kind != "podium"):
        return lobby(state, W, H, url, translate)
    if kind == "podium":
        canvas = _gradient(W, H, (90, 30, 110), (20, 10, 40)).convert("RGB")
        draw = ImageDraw.Draw(canvas)
        ranking = [(n, s) for n, s, _p in game.scores(state)]
        winner = ranking[0][0] if ranking else ""
        _center(draw, translate(N_("Bravo %(name)s !"), name=winner), H * 0.08, _font(TITLE, int(H * 0.1)), GOLD)
        _center(draw, translate(N_("Classement final")), H * 0.24, _font(HAND, int(H * 0.055)), SOFT, shadow=False)
        _ranking(draw, ranking, W * 0.3, H * 0.36, W, H, limit=8)
        return canvas

    question = state["questions"][number]
    total = len(state["questions"])
    qkind = question["kind"]
    title = f"{number + 1}/{total} · {game.question_text(question, translate)}"
    answered = len(state["answers"].get(str(number), {}))
    count_text = translate(N_("%(done)s / %(count)s ont répondu"), done=answered, count=len(state["players"]))
    duration = game.step_duration(state, number, kind)
    progress = 1 - max(0.0, left) / duration if duration else 1.0
    keys = [PREPARED / k for k in question.get("keys", [])]

    if kind == "memorize":
        canvas = _backdrop(W, H)
        _grid(canvas, keys, H * 0.13, H * 0.9)
        _header(canvas, f"{number + 1}/{total} · {translate(N_('Retenez bien ces photos !'))}", left)
        return canvas

    if kind in ("question", "vote") or kind == "reveal" and qkind not in ("caption", "challenge"):
        reveal = kind == "reveal"
        if qkind in ("older", "timeline"):
            canvas = _backdrop(W, H)
            _grid(canvas, keys, H * 0.13, H * 0.9, labels=list(game.LETTERS[:len(keys)]), cols=2 if qkind == "older" else 4)
        elif qkind == "memory":
            canvas = _backdrop(W, H)
            _grid(canvas, [PREPARED / k for k in question["choices"]], H * 0.13, H * 0.9, labels=list(game.LETTERS), cols=4)
        elif qkind == "challenge":
            canvas = _backdrop(W, H)
            draw = ImageDraw.Draw(canvas)
            if kind == "vote":
                photos = [_challenge_photo(v) for _n, _p, v in game.entries(state, number)]
                _grid(canvas, photos, H * 0.13, H * 0.9, labels=[str(n) for n, _p, _v in game.entries(state, number)])
            else:
                font = _font(TITLE, int(H * 0.09))
                for i, line in enumerate(_wrap(draw, translate(question["text"]), font, W * 0.85)):
                    _center(draw, line, H * 0.3 + i * H * 0.11, font, GOLD)
                _center(draw, translate(N_("Prenez la photo avec votre téléphone (page /jeu)")), H * 0.66, _font(HAND, int(H * 0.05)), SOFT, shadow=False)
        elif qkind == "caption" and kind == "vote":
            canvas = _photo_screen(PREPARED / question["key"], W, H, dim=0.55)
            draw = ImageDraw.Draw(canvas)
            font = _font(HAND, int(H * 0.055))
            y = H * 0.17
            for n, _p, text in game.entries(state, number)[:8]:
                for i, line in enumerate(_wrap(draw, f"{n}.  {text}", font, W * 0.9)[:2]):
                    draw.text((W * 0.05, y), line, font=font, fill=WHITE if i else GOLD)
                    y += H * 0.065
                y += H * 0.015
        elif question.get("key"):
            effect = question.get("effect") if not reveal else None
            canvas = _photo_screen(PREPARED / question["key"], W, H, dim=0.35 if reveal or qkind == "closest" else 0,
                                   effect=effect, progress=progress, seed=question.get("seed", 0))
        else:
            canvas = _backdrop(W, H)
        if qkind == "closest" and not reveal:
            draw = ImageDraw.Draw(canvas)
            font = _font(TITLE, int(H * 0.08))
            for i, line in enumerate(_wrap(draw, game.question_text(question, translate), font, W * 0.85)):
                _center(draw, line, H * 0.35 + i * H * 0.1, font, GOLD)
        _header(canvas, title, None if reveal else left)
        if not reveal:
            info = count_text
            if kind == "vote":
                voted = len(state.get("votes", {}).get(str(number), {}))
                info = translate(N_("Votez sur votre téléphone pour votre préférée · %(done)s vote(s)"), done=voted)
            elif qkind == "timeline":
                info = translate(N_("Touchez les lettres dans l'ordre sur votre téléphone")) + "     ·     " + count_text
            elif question.get("options") and qkind not in ("older", "memory"):
                info = "   ".join(question["options"]) + "     ·     " + count_text
            _footer(canvas, info)
            return canvas
        # Réponse et points
        draw = ImageDraw.Draw(canvas)
        answer = str(question["answer"])
        if qkind in ("older", "timeline", "memory"):
            answer = translate(N_("Réponse : %(answer)s"), answer=" → ".join(answer) if qkind == "timeline" else answer)
        _center(draw, answer, H * 0.2, _fit_font(draw, answer, TITLE, int(H * 0.14), W * 0.9), GOLD)
    else:
        # Légende ou défi : les gagnants
        winners = sorted(game.entries(state, number), key=lambda e: -game.round_points(state, number).get(e[1], 0))
        if qkind == "challenge" and winners:
            canvas = _photo_screen(_challenge_photo(winners[0][2]), W, H, dim=0.3)
        elif question.get("key"):
            canvas = _photo_screen(PREPARED / question["key"], W, H, dim=0.5)
        else:
            canvas = _backdrop(W, H)
        draw = ImageDraw.Draw(canvas)
        _header(canvas, title)
        if winners:
            best_player = winners[0][1]
            name = state["players"].get(best_player, "?")
            _center(draw, translate(N_("Bravo %(name)s !"), name=name), H * 0.17, _font(TITLE, int(H * 0.09)), GOLD)
            if qkind == "caption":
                font = _font(HAND, int(H * 0.07))
                for i, line in enumerate(_wrap(draw, f"« {winners[0][2]} »", font, W * 0.85)[:2]):
                    _center(draw, line, H * 0.3 + i * H * 0.08, font, WHITE)
    number_points = game.round_points(state, number)
    ranking = [(n, s) for n, s, _p in game.scores(state, number)]
    gained = {state["players"][p]: g for p, g in number_points.items() if p in state["players"]}
    _band(canvas, H * 0.47, H * 0.5, 150)
    _ranking(draw, ranking, W * 0.3, H * 0.5, W, H, gained)
    return canvas


def bingo_banner(state, now, W, H, translate=lambda s, **k: s % k if k else s):
    """Bandeau du bingo pendant le diaporama (dernier gagnant en grand quelques secondes)."""
    winners = (state or {}).get("winners", [])
    fresh = [w for w in winners if now - w["at"] < 15]
    text = translate(N_("BINGO ! %(name)s"), name=fresh[-1]["name"]) if fresh else translate(N_("Bingo souvenirs en cours · page /jeu"))
    font = _font(TITLE if fresh else BOLD, int(H * (0.08 if fresh else 0.035)))
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    w = int(probe.textlength(text, font=font)) + 40
    h = int(H * (0.12 if fresh else 0.06))
    banner = Image.new("RGBA", (w, h), (230, 60, 110, 220) if fresh else (60, 20, 90, 190))
    draw = ImageDraw.Draw(banner)
    draw.text((20, h * 0.12), text, font=font, fill=WHITE)
    return banner
