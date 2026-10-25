"""Nouveaux médias : le diaporama refait sa liste sans redémarrer (pas d'écran figé)."""
from utils import slideshow_manager as sm


def test_content_update_asks_for_a_hot_reload(tmp_path, monkeypatch):
    monkeypatch.setattr(sm, "RELOAD_FLAG", tmp_path / "reload.flag")
    monkeypatch.setattr(sm, "is_slideshow_running", lambda: True)
    monkeypatch.setattr(sm, "_import_in_progress", lambda: False)
    monkeypatch.setitem(sm._restart_state, "last", 0)
    stopped, started = [], []
    monkeypatch.setattr(sm, "_stop_process_by_pid", lambda pid: stopped.append(pid))
    monkeypatch.setattr(sm, "start_slideshow", lambda *a, **k: started.append(1))
    sm.restart_slideshow_for_update()
    assert sm.RELOAD_FLAG.exists() and not stopped and not started


def test_explicit_start_still_restarts(tmp_path, monkeypatch):
    monkeypatch.setattr(sm, "RELOAD_FLAG", tmp_path / "reload.flag")
    monkeypatch.setattr(sm, "is_slideshow_running", lambda: False)
    monkeypatch.setitem(sm._restart_state, "last", 0)
    started = []
    monkeypatch.setattr(sm, "start_slideshow", lambda *a, **k: started.append(1))
    sm.restart_slideshow_for_update(force_start=True)
    assert started and not sm.RELOAD_FLAG.exists()
