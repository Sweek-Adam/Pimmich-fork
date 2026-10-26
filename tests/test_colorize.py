"""Colorisation : téléchargement vérifié (empreintes), réseau reconstruit en ONNX, photo noir et blanc colorisée en copie."""
import hashlib
import os
import time
from pathlib import Path

import pytest
from PIL import Image

from utils import colorize

SAME = {"Sec-Fetch-Site": "same-origin"}
MODEL_DIR = os.environ.get("PIMMICH_COLORIZE_MODEL")  # dossier avec les fichiers d'origine (essai réel, facultatif)


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, size):
        yield self.data


def test_install_checks_fingerprints(tmp_path, monkeypatch):
    good, bad = b"bons poids", b"poids pieges"
    monkeypatch.setattr(colorize, "FILES", {"model.bin": (["https://miroir-1/x", "https://miroir-2/x"], hashlib.sha256(good).hexdigest())})
    monkeypatch.setattr(colorize, "build_onnx", lambda model_dir: (Path(model_dir) / colorize.ONNX_NAME).write_bytes(b"onnx"))
    served = {"https://miroir-1/x": bad, "https://miroir-2/x": good}
    colorize.install(tmp_path, get=lambda url, **k: FakeResponse(served[url]))
    assert (tmp_path / "model.bin").read_bytes() == good and colorize.installed(tmp_path)  # le miroir piégé est refusé
    served["https://miroir-2/x"] = bad
    (tmp_path / "model.bin").unlink()
    with pytest.raises(ValueError):
        colorize.install(tmp_path, get=lambda url, **k: FakeResponse(served[url]))
    assert not (tmp_path / "model.bin").exists()


def test_grayscale_detection():
    from PIL import ImageDraw, ImageOps
    scene = Image.new("RGB", (120, 90), (40, 120, 200))
    ImageDraw.Draw(scene).rectangle([0, 50, 120, 90], fill=(60, 160, 60))
    ImageDraw.Draw(scene).ellipse([40, 20, 80, 60], fill=(220, 80, 50))
    assert not colorize.is_grayscale(scene)                                              # photo en couleur
    gray = scene.convert("L")
    assert colorize.is_grayscale(gray.convert("RGB"))                                    # noir et blanc
    assert colorize.is_grayscale(ImageOps.colorize(gray, (60, 40, 20), (240, 220, 180)))  # tirage sépia


@pytest.mark.skipif(not MODEL_DIR or not Path(MODEL_DIR or ".").is_dir(), reason="modèle de colorisation absent")
def test_real_model(tmp_path):
    import shutil
    for name in ("deploy.prototxt", "pts_in_hull.npy", "colorization_release_v2.caffemodel"):
        shutil.copy(Path(MODEL_DIR) / name, tmp_path / name)
    colorize.build_onnx(tmp_path)
    out = colorize.colorize(Image.new("RGB", (320, 240), (128, 128, 128)), model_dir=tmp_path)
    assert out.size == (320, 240)


def test_colorize_api(admin_client, monkeypatch):
    from web import routes_colorize
    prepared = Path("static/prepared/vieux")
    prepared.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 48), (100, 100, 100)).save(prepared / "mamie.jpg")
    from PIL import ImageDraw
    colourful = Image.new("RGB", (64, 48), (40, 120, 200))
    ImageDraw.Draw(colourful).rectangle([0, 30, 64, 48], fill=(220, 80, 50))
    colourful.save(prepared / "couleur.jpg")
    monkeypatch.setattr(colorize, "installed", lambda model_dir=None: True)
    def fake_colorize(image, model_dir=None):
        out = Image.new("RGB", image.size, (40, 120, 200))
        ImageDraw.Draw(out).rectangle([0, 30, image.size[0], image.size[1]], fill=(220, 80, 50))
        return out
    monkeypatch.setattr(colorize, "colorize", fake_colorize)
    monkeypatch.setattr(routes_colorize, "_publish", lambda: None)
    try:
        assert admin_client.post("/api/colorize", json={"path": "vieux/couleur.jpg"}, headers=SAME).status_code == 400
        assert admin_client.post("/api/colorize", json={"path": "../x.jpg"}, headers=SAME).status_code == 404
        assert admin_client.post("/api/colorize", json={"path": "vieux/mamie.jpg"}, headers=SAME).get_json()["success"]
        target = Path("static/photos/colorisees/mamie_couleur.jpg")
        for _ in range(100):
            if target.exists():
                break
            time.sleep(0.05)
        assert target.exists() and not colorize.is_grayscale(Image.open(target))
        assert Image.open(prepared / "mamie.jpg").getpixel((5, 5)) == (100, 100, 100)  # l'original n'a pas bougé
    finally:
        import shutil
        shutil.rmtree(prepared, ignore_errors=True)
        shutil.rmtree("static/photos/colorisees", ignore_errors=True)
