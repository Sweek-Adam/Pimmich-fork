"""Raccourci « Revenir au cadre Pimmich » pour le bureau Raspberry Pi OS."""
import os

from utils import desktop_launcher


def test_install_menu_and_desktop_shortcuts(tmp_path):
    written = desktop_launcher.install(home=tmp_path, project_dir="/home/adam/pimmich")
    assert {p.parent.name for p in written} == {"applications", "Desktop", "autostart"}  # « Bureau » seulement s'il existe
    autostart = (tmp_path / ".config" / "autostart" / "pimmich-admin.desktop").read_text()
    assert "Exec=env PIMMICH_DESKTOP=1 /home/adam/pimmich/start_pimmich.sh" in autostart and "NoDisplay=true" in autostart
    for path in written[:-1]:
        text = path.read_text()
        assert "Exec=/home/adam/pimmich/utils/switch_to_pimmich.sh" in text and "Type=Application" in text
        assert os.access(path, os.X_OK)
    (tmp_path / "Bureau").mkdir()
    assert len(desktop_launcher.install(home=tmp_path)) == 4


def test_switch_script_is_executable():
    assert os.access(desktop_launcher.PROJECT_DIR / "utils" / "switch_to_pimmich.sh", os.X_OK)


def test_desktop_mode_never_starts_the_slideshow(monkeypatch):
    from utils import slideshow_manager
    monkeypatch.setenv("PIMMICH_DESKTOP", "1")
    monkeypatch.setattr(slideshow_manager.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("lancé")))
    assert slideshow_manager.desktop_mode() and slideshow_manager.start_slideshow() is None
