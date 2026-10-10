"""Légendes personnalisables : styles, dessin, sous-titres des vidéos, éditeur."""
import json
from io import BytesIO

from PIL import Image, ImageFont

from utils import captions

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}


def _changed(a, b, box):
    return a.crop(box).tobytes() != b.crop(box).tobytes()


def test_clean_bounds_and_rejects_unknown_values():
    style = captions.clean({"size": 99, "font": "comic", "color": "rouge", "bg_color": "#ABCDEF", "x": -5,
                            "background": "band", "shadow": "glow", "bold": 1, "rotation": "abc"})
    assert style["size"] == 20 and style["font"] == "caveat" and style["color"] == captions.DEFAULTS["photo"]["color"]
    assert style["bg_color"] == "#abcdef" and style["x"] == 0 and style["background"] == "band" and style["shadow"] == "glow"
    assert style["bold"] is True and style["rotation"] == 0
    assert captions.clean(None, "metadata") == captions.DEFAULTS["metadata"]


def test_caption_drawn_where_placed():
    base = Image.new("RGB", (800, 450), (40, 90, 140))
    bottom = captions.draw(base, "Bonjour", captions.clean({"y": 90}))
    assert _changed(base, bottom, (0, 360, 800, 450)) and not _changed(base, bottom, (0, 0, 800, 200))
    top = captions.draw(base, "Bonjour", captions.clean({"y": 10}))
    assert _changed(base, top, (0, 0, 800, 90)) and not _changed(base, top, (0, 250, 800, 450))
    assert captions.draw(base, "   ", captions.clean({})) is base  # sans texte, rien n'est dessiné


def test_band_spans_full_width_and_every_option_renders():
    base = Image.new("RGB", (800, 450), (40, 90, 140))
    band = captions.draw(base, "Snap", captions.clean({"background": "band", "bg_color": "#000000", "bg_opacity": 100, "y": 50}))
    assert band.getpixel((2, 225)) == (0, 0, 0) and band.getpixel((797, 225)) == (0, 0, 0)
    for preset in captions.PRESETS.values():
        for extra in ({}, {"bold": True, "italic": True, "underline": True, "rotation": -20, "align": "right", "x": 100}):
            out = captions.draw(base, "Un texte assez long pour passer sur deux lignes au moins", captions.clean(dict(preset, **extra)))
            assert out.size == base.size and out.mode == "RGB"


def test_missing_glyphs_are_dropped():
    font = ImageFont.truetype(str(captions.FONTS["caveat"][1][0]), 40)
    assert captions.drawable("La mer 🌊 et le soleil — été", font) == "La mer et le soleil — été"


def test_legacy_metadata_settings_become_a_style():
    style = captions.scope_style({"photo_metadata_position": "top_right", "photo_metadata_color": "#ff0000",
                                  "photo_metadata_background_enabled": False, "photo_metadata_font_size": 36}, "metadata")
    assert style["align"] == "right" and style["x"] == 98 and style["y"] == 5 and style["color"] == "#ff0000"
    assert style["background"] == "none" and style["size"] == 5.0
    saved = captions.scope_style({"caption_styles": {"metadata": {"font": "elite"}}, "photo_metadata_color": "#ff0000"}, "metadata")
    assert saved["font"] == "elite" and saved["color"] == "#ffffff"  # le style enregistré l'emporte sur les anciens réglages


def test_ass_document_for_videos():
    style = captions.clean(dict(captions.PRESETS["bubble"], bold=True, underline=True, rotation=10))
    doc = captions.ass_document("Salut {toi}\nà la plage", style, 1920, 1080)
    assert "PlayResX: 1920" in doc and "Patrick Hand" in doc and "\\b1" in doc and "\\u1" in doc and "\\frz10" in doc
    assert "Salut (toi)\\Nà la plage" in doc  # les accolades ne peuvent pas injecter de balises
    assert "Style: Box" in doc and "\\p1}m " in doc  # bulle dessinée sous le texte
    assert doc.count("Dialogue:") == 2
    plain = captions.ass_document("Salut", captions.clean({"background": "none"}), 1280, 720)
    assert plain.count("Dialogue:") == 1


def test_video_subtitles_use_the_media_text_and_style(sandbox, monkeypatch, tmp_path):
    video = sandbox / "static" / "prepared" / "gdrive" / "clip.mp4"
    video.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(b"")
    monkeypatch.setattr(captions, "video_size", lambda path: (1080, 1920))
    out = tmp_path / "caption.ass"
    assert captions.video_subtitles(video, {}, out) is None  # pas de légende : pas de sous-titres
    states = sandbox / "config" / "text_states.json"
    states.write_text(json.dumps({"gdrive/clip.mp4": "Premier plongeon"}))
    monkeypatch.setattr(captions, "MEDIA_STYLES_FILE", tmp_path / "styles.json")
    captions.save_media_style("gdrive/clip.mp4", {"font": "marker"})
    try:
        assert captions.video_subtitles(video, {}, out) == str(out)
        doc = out.read_text()
        assert "Premier plongeon" in doc and "Permanent Marker" in doc and "PlayResY: 1920" in doc
    finally:
        states.unlink()
        video.unlink()


def test_media_style_overrides_scope(monkeypatch, tmp_path):
    monkeypatch.setattr(captions, "MEDIA_STYLES_FILE", tmp_path / "styles.json")
    config = {"caption_styles": {"photo": {"font": "elite"}}}
    captions.save_media_style("gdrive/a.jpg", {"font": "marker", "size": 300})
    assert captions.style_for(config, "photo", "gdrive/a.jpg")["font"] == "marker"
    assert captions.style_for(config, "photo", "gdrive/a.jpg")["size"] == 20
    assert captions.style_for(config, "photo", "gdrive/b.jpg")["font"] == "elite"
    captions.save_media_style("gdrive/a.jpg", None)
    assert captions.style_for(config, "photo", "gdrive/a.jpg")["font"] == "elite"


def test_restyle_redraws_saved_captions(sandbox, monkeypatch):
    from utils import image_filters
    calls = []
    monkeypatch.setattr(image_filters, "add_text_to_image", lambda path, text: calls.append(("image", path, text)))
    monkeypatch.setattr(image_filters, "add_text_to_polaroid", lambda path, text: calls.append(("polaroid", path, text)))
    prepared = sandbox / "static" / "prepared"
    (prepared / "usb").mkdir(parents=True, exist_ok=True)
    for name in ("a.jpg", "a_polaroid.jpg", "b.jpg"):
        Image.new("RGB", (10, 10)).save(prepared / "usb" / name)
    (sandbox / "config" / "text_states.json").write_text(json.dumps({"usb/a.jpg": "Coucou", "usb/b.jpg": " ", "usb/v.mp4": "Vidéo"}))
    (sandbox / "config" / "polaroid_texts.json").write_text(json.dumps({"usb/a.jpg": "Été"}))
    try:
        assert captions.restyle_all(prepared) == 2
        assert ("image", str(prepared / "usb" / "a.jpg"), "Coucou") in calls
        assert ("polaroid", str(prepared / "usb" / "a_polaroid.jpg"), "Été") in calls
        calls.clear()
        assert captions.restyle_all(prepared, {"usb/b.jpg"}) == 0 and calls == []
    finally:
        (sandbox / "config" / "text_states.json").unlink()
        (sandbox / "config" / "polaroid_texts.json").unlink()


def test_photo_caption_uses_the_style(sandbox, monkeypatch, tmp_path):
    """La légende saisie sous une photo est dessinée avec le style de la photo (ici : bandeau noir opaque en haut)."""
    from utils import image_filters
    monkeypatch.setattr(captions, "MEDIA_STYLES_FILE", tmp_path / "styles.json")
    monkeypatch.setattr(image_filters, "USER_TEXT_MAP_CACHE_FILE", tmp_path / "user_texts.json")
    photo = sandbox / "static" / "prepared" / "usb" / "styled.jpg"
    photo.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (800, 450), (200, 200, 200)).save(photo)
    captions.save_media_style("usb/styled.jpg", {"background": "band", "bg_color": "#000000", "bg_opacity": 100, "y": 8})
    image_filters.add_text_to_image(str(photo), "Hello")
    with Image.open(photo) as out:
        assert max(out.getpixel((3, 20))) < 30 and min(out.getpixel((3, 400))) > 170
    image_filters.add_text_to_image(str(photo), "")  # légende effacée : la photo d'origine revient
    with Image.open(photo) as out:
        assert min(out.getpixel((3, 20))) > 170


def test_captions_api(admin_client, monkeypatch):
    from web import routes_captions
    from utils.config_manager import load_config
    restyled = []
    monkeypatch.setattr(routes_captions, "_restyle", lambda keys=None: restyled.append(keys))
    data = admin_client.get("/api/captions").get_json()
    assert set(data["styles"]) == {"photo", "polaroid", "metadata"} and "classic" in data["presets"]
    r = admin_client.post("/api/captions/photo", json={"style": {"font": "marker", "size": 7}}, headers=SAME_ORIGIN).get_json()
    assert r["success"] and load_config()["caption_styles"]["photo"]["font"] == "marker" and restyled == [None]
    r = admin_client.post("/api/captions/metadata", json={"style": {"align": "right"}}, headers=SAME_ORIGIN).get_json()
    assert r["success"] and restyled == [None]  # les infos sont dessinées par le diaporama : rien à redessiner
    assert admin_client.post("/api/captions/autre", json={}, headers=SAME_ORIGIN).status_code == 400
    assert admin_client.post("/api/captions/media", json={"photo": "../config/config.json", "style": {}}, headers=SAME_ORIGIN).status_code == 404
    for scope in ("photo", "polaroid", "metadata"):
        resp = admin_client.post("/api/captions/preview", json={"scope": scope, "style": {"background": "band"}, "text": "Test"}, headers=SAME_ORIGIN)
        assert resp.status_code == 200 and resp.mimetype == "image/jpeg"
        assert Image.open(BytesIO(resp.data)).format == "JPEG"
