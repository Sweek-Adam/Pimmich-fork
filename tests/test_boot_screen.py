"""Écran de démarrage : thème Plymouth (4 styles), style tiré au démarrage précédent et repris jusqu'à la première photo."""
import random
from pathlib import Path

import pytest
from PIL import Image

from utils import boot_screen, platform_info


@pytest.fixture()
def boot_dirs(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(platform_info, "tmp_dir", lambda: tmp_path)
    monkeypatch.setattr(boot_screen, "CACHE_DIR", cache)
    for s in range(len(boot_screen.STYLES)):
        Image.new("RGB", (32, 18), (s * 60, 0, 0)).save(cache / f"bg{s}.png")
    return cache, tmp_path


def test_theme_has_every_style(tmp_path):
    out = boot_screen.export_theme(tmp_path / "theme", 640, 360, url="http://cadre.local/upload", address="cadre.local")
    script = (out / "cadre-photo.script").read_text()
    for s in range(len(boot_screen.STYLES)):
        assert (out / f"bg{s}.png").exists() and f'bgfile[{s}] = "bg{s}.png"' in script
        assert Image.open(out / f"bg{s}.png").size == (640, 360)
    assert "SetRootMountedFunction" in script and 'Image("pick.png")' in script
    assert "ModuleName=script" in (out / "cadre-photo.plymouth").read_text()


def test_handoff_keeps_current_style_and_picks_another(boot_dirs):
    cache, tmp = boot_dirs
    assert boot_screen.handoff(cache) is None  # pas encore installé : rien
    Image.new("L", (3, 1)).save(cache / "pick.png")  # style 2 à l'écran
    assert boot_screen.handoff(cache, rng=random.Random(1)) == 2
    assert (tmp / boot_screen.BOOT_STYLE_FILE).read_text() == "2"
    following = boot_screen._read_pick(cache)
    assert following is not None and following != 2
    boot_screen.after_boot(cache)
    assert (cache / "current.png").resolve().name == f"bg{following}.png"


def test_slideshow_takes_boot_image_once(boot_dirs):
    pytest.importorskip("pygame")
    cache, tmp = boot_dirs
    (tmp / boot_screen.BOOT_STYLE_FILE).write_text("1")
    image = boot_screen.boot_background(64, 36)
    assert image is not None and image.get_size() == (64, 36)
    assert boot_screen.boot_background(64, 36) is None  # redémarrage du diaporama ensuite : plus d'écran de démarrage
