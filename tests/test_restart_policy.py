"""Le diaporama n'est pas réveillé par un changement de réglages, ni redémarré pendant un import."""
import pytest

from utils import import_progress, slideshow_manager as sm


@pytest.fixture()
def calls(monkeypatch):
    log = []
    monkeypatch.setattr(sm, "start_slideshow", lambda: log.append("start"))
    monkeypatch.setattr(sm, "_stop_process_by_pid", lambda pid: log.append("stop"))
    monkeypatch.setattr(sm.subprocess, "Popen", lambda *a, **k: None)
    monkeypatch.setattr(sm.time, "sleep", lambda s: None)
    monkeypatch.setattr(sm, "_restart_state", {"pending": False, "last": 0.0})
    import_progress.reset()
    yield log
    import_progress.reset()


def test_a_sleeping_slideshow_is_not_woken_up(calls, monkeypatch):
    monkeypatch.setattr(sm, "is_slideshow_running", lambda: False)
    sm.restart_slideshow_process()
    sm.restart_slideshow_for_update()
    assert calls == []
    sm.restart_slideshow_for_update(force_start=True)  # action explicite (lancer une playlist)
    assert calls == ["start"]


def test_restart_waits_for_the_end_of_the_import(calls, monkeypatch):
    monkeypatch.setattr(sm, "is_slideshow_running", lambda: True)
    events = import_progress.tracked("gdrive", "prepare", iter([{"type": "progress", "current": 1, "total": 3}]))
    next(events)  # préparation en cours
    sm.restart_slideshow_process()
    sm.restart_slideshow_process()
    assert calls == [] and sm._restart_state["pending"]
    list(events)  # toutes les photos sont préparées : un seul redémarrage
    assert calls.count("start") == 1 and not sm._restart_state["pending"]


def test_two_quick_requests_make_one_restart(calls, monkeypatch):
    monkeypatch.setattr(sm, "is_slideshow_running", lambda: True)
    sm.restart_slideshow_process()
    sm.restart_slideshow_process()
    assert calls.count("start") == 1
