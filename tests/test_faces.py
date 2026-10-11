"""Recadrage intelligent : la fenêtre gardée contient les visages entiers (compositions, photos très larges)."""
from PIL import Image

from utils import compositions, faces


def test_window_without_faces_is_the_old_crop():
    assert faces.window(1000, 800, 400, 400, []) == (300, 168)  # centre, légèrement remonté


def test_window_keeps_a_face_at_the_edge():
    face = [(0.85, 0.1, 0.1, 0.12)]  # visage en haut à droite
    left, top = faces.window(1000, 800, 400, 400, face)
    assert left <= 850 * 1 and left + 400 >= 950  # visage entier en largeur
    assert top <= 80 and top + 400 >= 176


def test_window_keeps_the_group_or_the_biggest_faces():
    group = [(0.1, 0.4, 0.08, 0.1), (0.3, 0.42, 0.08, 0.1)]
    left, top = faces.window(1000, 500, 400, 500, group)
    assert left <= 100 * 0.97 and left + 400 >= 380
    # Trop éloignés pour tenir ensemble : on garde le plus grand (le premier)
    apart = [(0.05, 0.4, 0.1, 0.12), (0.85, 0.4, 0.05, 0.06)]
    left, _top = faces.window(1000, 500, 300, 500, apart)
    assert left <= 50 and left + 300 >= 150


def test_cover_uses_the_attached_faces():
    image = Image.new("RGB", (1000, 500), (0, 0, 255))
    image.paste((255, 0, 0), (880, 100, 960, 200))  # le « visage », tout à droite
    faces.attach(image, [(0.88, 0.2, 0.08, 0.2)])
    cropped = compositions.cover(image, 300, 300)
    assert cropped.size == (300, 300)
    red = sum(1 for p in cropped.get_flattened_data() if p[0] > 128 and p[2] < 128)
    assert red >= 0.95 * (80 * 100 * (300 / 500) ** 2)  # le visage est dans la case
    plain = Image.new("RGB", (1000, 500), (0, 0, 255))
    plain.paste((255, 0, 0), (880, 100, 960, 200))
    assert (255, 0, 0) not in set(compositions.cover(plain, 300, 300).get_flattened_data())  # sans visages : centre


def test_smart_crop_can_be_disabled():
    image = faces.attach(Image.new("RGB", (1000, 500)), [(0.88, 0.2, 0.08, 0.2)])
    faces.set_enabled(False)
    try:
        assert faces.detect(image) == [] and faces.for_file("x.jpg", image) == []
        assert compositions.cover(image, 300, 300).size == (300, 300)
    finally:
        faces.set_enabled(True)


def test_detection_is_cached(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(faces, "CACHE_FILE", tmp_path / "faces.json")
    monkeypatch.setattr(faces, "_cache", None)
    monkeypatch.setattr(faces, "available", lambda: True)
    monkeypatch.setattr(faces, "detect", lambda image: calls.append(1) or [(0.1, 0.1, 0.2, 0.2)])
    photo = tmp_path / "p.jpg"
    Image.new("RGB", (10, 10)).save(photo)
    assert faces.for_file(photo, None) == [(0.1, 0.1, 0.2, 0.2)]
    assert faces.for_file(photo, None) == [(0.1, 0.1, 0.2, 0.2)] and len(calls) == 1


def test_wide_photo_preparation_keeps_the_face(sandbox, monkeypatch, tmp_path):
    from utils import prepare_all_photos
    monkeypatch.setattr(faces, "for_file", lambda path, image: [(0.9, 0.3, 0.06, 0.2)])
    monkeypatch.setattr(prepare_all_photos, "load_config", lambda: {"smart_crop": True})
    source = tmp_path / "pano.jpg"
    pano = Image.new("RGB", (3000, 1000), (0, 0, 255))
    pano.paste((255, 0, 0), (2700, 300, 2880, 500))
    pano.save(source)
    dest = tmp_path / "pano_out.jpg"
    prepare_all_photos.prepare_photo(str(source), str(dest), 640, 360)
    with Image.open(dest) as out:
        reds = [x for x in range(out.width) if out.getpixel((x, 140))[0] > 200 and out.getpixel((x, 140))[2] < 80]
    assert reds, "le visage doit rester dans l'image"
