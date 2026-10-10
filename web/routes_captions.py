"""Éditeur de légendes : styles des légendes (photos et vidéos, polaroïds, infos), style par photo, aperçu exact."""
import io
import threading

from flask import send_file
from PIL import Image, ImageDraw

from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from utils import captions
from utils.message_renderer import N_

PREVIEW_WIDTH = 960
SAMPLE_TEXT = {"photo": N_("Vacances à la mer avec mamie"), "polaroid": N_("Été 2025"), "metadata": N_("12 août 2025  •  Biarritz, France")}


def _restyle(keys=None):
    """Redessine en arrière-plan les légendes déjà posées sur les photos."""
    threading.Thread(target=captions.restyle_all, args=(PREPARED_DIR, keys), daemon=True, name="captions-restyle").start()


def _media_path(key):
    """Chemin sûr d'un média préparé (source/nom), sinon None."""
    if not key:
        return None
    base = PREPARED_DIR.resolve()
    path = (base / str(key)).resolve()
    return path if base in path.parents and path.is_file() else None


def _background(key):
    """Image de fond de l'aperçu : la photo sans sa légende (sauvegarde), la vignette d'une vidéo, sinon une photo du cadre."""
    path = _media_path(key)
    if path is not None:
        if path.suffix.lower() in VIDEO_EXTENSIONS:
            thumb = path.with_name(f"{path.stem}_thumbnail.jpg")
            path = thumb if thumb.is_file() else None
        else:
            backup = BASE_DIR / "static" / ".backups" / key
            path = backup if backup.is_file() else path
    if path is None:
        for source in sorted(PREPARED_DIR.iterdir()) if PREPARED_DIR.is_dir() else []:
            if source.is_dir() and source.name not in ("messages", "compositions"):
                path = next((p for p in sorted(source.glob("*.jpg")) if not p.stem.endswith(("_polaroid", "_postcard", "_thumbnail"))), None)
                if path:
                    break
    if path is None:
        image = Image.new("RGB", (PREVIEW_WIDTH, 540), (70, 110, 150))
        ImageDraw.Draw(image).rectangle([0, 300, PREVIEW_WIDTH, 540], fill=(200, 170, 120))
        return image
    with Image.open(path) as image:
        image = image.convert("RGB")
        image.thumbnail((PREVIEW_WIDTH, PREVIEW_WIDTH))
        return image


def _polaroid_preview(photo, text, style):
    """Polaroïd fictif (même proportions que ceux du cadre) avec le texte dans la marge du bas."""
    w, h = photo.size
    inner_h = int(h * 0.62)
    inner = photo.copy()
    inner.thumbnail((int(w * 0.6), inner_h))
    side, bottom = int(inner.height * 0.05), int(inner.height * 0.22)
    card = Image.new("RGB", (inner.width + 2 * side, inner.height + side + bottom), (255, 253, 248))
    card.paste(inner, (side, side))
    content_h = card.height
    margin = (0, content_h - int(content_h * 0.18), card.width, int(content_h * 0.18))
    card = captions.draw(card, text, style, area=margin, size_ref=content_h)
    canvas = photo.copy()
    canvas.paste(card, ((w - card.width) // 2, (h - card.height) // 2))
    return canvas


@app.route('/api/captions', methods=['GET'])
@login_required
def captions_api():
    config = load_config()
    media = request.args.get("photo")
    translate = _
    return jsonify({"success": True,
                    "styles": {scope: captions.scope_style(config, scope) for scope in captions.SCOPES},
                    "media_style": captions.load_media_styles().get(media) if media else None,
                    "presets": captions.PRESETS, "defaults": captions.DEFAULTS,
                    "samples": {scope: translate(text) for scope, text in SAMPLE_TEXT.items()}})


@app.route('/api/captions/<scope>', methods=['POST'])
@login_required
def captions_save_api(scope):
    if scope not in captions.SCOPES:
        return jsonify({"success": False, "message": _("Type de légende inconnu.")}), 400
    data = request.get_json(silent=True) or {}
    config = dict(load_config())
    styles = dict(config.get("caption_styles") or {})
    styles[scope] = captions.clean(data.get("style"), scope) if data.get("style") is not None else captions.clean(None, scope)
    config["caption_styles"] = styles
    save_config(config)
    if scope in ("photo", "polaroid"):
        _restyle()
        return jsonify({"success": True, "style": styles[scope],
                        "message": _("Style enregistré : les légendes déjà posées sont redessinées en arrière-plan.")})
    return jsonify({"success": True, "style": styles[scope], "message": _("Style enregistré : visible dès la photo suivante.")})


@app.route('/api/captions/media', methods=['POST'])
@login_required
def captions_media_api():
    """Style propre à une photo ou une vidéo (style absent : elle reprend le style général)."""
    data = request.get_json(silent=True) or {}
    key = str(data.get("photo", ""))
    if _media_path(key) is None:
        return jsonify({"success": False, "message": _("Photo introuvable.")}), 404
    captions.save_media_style(key, data.get("style"))
    _restyle({key})
    return jsonify({"success": True, "message": _("Style de cette légende enregistré.") if data.get("style") is not None
                    else _("Cette légende reprend le style général.")})


@app.route('/api/captions/preview', methods=['POST'])
@login_required
def captions_preview_api():
    """Aperçu exact (même moteur de dessin que le cadre), en JPEG."""
    data = request.get_json(silent=True) or {}
    scope = data.get("scope") if data.get("scope") in captions.SCOPES else "photo"
    style = captions.clean(data.get("style"), scope)
    translate = _
    text = str(data.get("text") or "")[:300] or translate(SAMPLE_TEXT[scope])
    photo = _background(str(data.get("photo") or ""))
    image = _polaroid_preview(photo, text, style) if scope == "polaroid" else captions.draw(photo, text, style)
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=85)
    return send_file(io.BytesIO(buffer.getvalue()), mimetype="image/jpeg")
