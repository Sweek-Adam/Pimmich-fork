"""Travail de nuit : grosses vidéos préparées quand le cadre est éteint, nouvel essai des échecs, une notification."""
import shutil
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image

from utils import import_progress, night_work
from utils import prepare_all_photos as prep

DAY = datetime(2026, 10, 21, 15, 0)     # mercredi après-midi : cadre allumé
NIGHT = datetime(2026, 10, 21, 23, 30)  # mercredi soir : cadre éteint
LATE = datetime(2026, 10, 22, 3, 0)     # même nuit, après minuit
CONFIG = {"active_start_weekday": "07:00", "active_end_weekday": "22:00", "heavy_videos_at_night": True, "video_night_above_mb": 1}


@pytest.fixture()
def source(sandbox, monkeypatch):
    folder, prepared = Path("static/photos/nuit"), Path("static/prepared/nuit")
    for d in (folder, prepared):
        shutil.rmtree(d, ignore_errors=True)
    folder.mkdir(parents=True)
    monkeypatch.setattr(prep, "ERRORS_FILE", Path("cache") / "prepare_errors_night.json")
    monkeypatch.setattr(night_work, "STATE_FILE", Path("cache") / "night_state_test.json")
    prep.ERRORS_FILE.unlink(missing_ok=True)
    night_work.STATE_FILE.unlink(missing_ok=True)
    monkeypatch.setattr(prep, "load_config", lambda: CONFIG)
    import_progress.reset()
    yield folder, prepared
    for d in (folder, prepared):
        shutil.rmtree(d, ignore_errors=True)


def test_active_hours_and_night_key():
    assert night_work.active_now(CONFIG, DAY) and not night_work.active_now(CONFIG, NIGHT)
    assert night_work.night_key(NIGHT) == night_work.night_key(LATE) == "2026-10-21"
    assert not night_work.heavy_allowed(CONFIG, DAY) and night_work.heavy_allowed(CONFIG, NIGHT)
    assert night_work.heavy_allowed(dict(CONFIG, heavy_videos_at_night=False), DAY)


def test_daytime_import_skips_heavy_videos(source, monkeypatch):
    folder, _prepared = source
    (folder / "photo.jpg").write_bytes(b"x")
    (folder / "petite.mp4").write_bytes(b"x" * 1000)
    (folder / "grosse.mp4").write_bytes(b"x" * 2 * 1024 * 1024)
    done = []
    monkeypatch.setattr(night_work, "heavy_allowed", lambda config, now=None: False)
    monkeypatch.setattr(prep, "prepare_media", lambda source, name, *a, **k: done.append(name) or ("photo", name))
    events = list(prep.prepare_all_photos_with_progress(64, 36, "nuit"))
    assert done == ["photo.jpg", "petite.mp4"]
    assert any("cette nuit" in e.get("message", "") for e in events)
    inventory = {i["name"]: i["night"] for i in prep.media_inventory("nuit", 64, 36)}
    assert inventory["grosse.mp4"] and not inventory["photo.jpg"]


def test_night_pass_prepares_heavy_then_retries_failures_once(source, monkeypatch):
    folder, prepared = source
    (folder / "grosse.mp4").write_bytes(b"x" * 2 * 1024 * 1024)
    (folder / "abimee.jpg").write_bytes(b"x")
    prep._record_error("nuit", "abimee.jpg", "illisible")
    calls, told = [], []

    def prepare(src, name, width, height, **k):
        calls.append(name)
        if name == "abimee.jpg":
            raise ValueError("toujours illisible")
        prepared.mkdir(parents=True, exist_ok=True)
        (prepared / "grosse.mp4").write_bytes(b"ok")

    # Journée : rien
    assert night_work.run_once(CONFIG, 64, 36, now=DAY, prepare=prepare, notify=told.append, still_night=lambda: True) == {"heavy": 0, "retried": 0, "notified": []}
    # Nuit : la grosse vidéo, puis un nouvel essai de la photo abîmée, puis une notification
    done = night_work.run_once(CONFIG, 64, 36, now=NIGHT, prepare=prepare, notify=told.append, still_night=lambda: True)
    assert calls == ["grosse.mp4", "abimee.jpg"] and done["heavy"] == 1 and done["retried"] == 1
    assert told == [[("nuit", "abimee.jpg")]]
    # Plus tard la même nuit : pas de nouvel essai ni de nouvelle notification
    calls.clear()
    assert night_work.run_once(CONFIG, 64, 36, now=LATE, prepare=prepare, notify=told.append, still_night=lambda: True)["retried"] == 0
    assert calls == [] and len(told) == 1


def test_morning_stops_the_night_work(source):
    folder, _prepared = source
    for name in ("a.mp4", "b.mp4"):
        (folder / name).write_bytes(b"x" * 2 * 1024 * 1024)
    calls, nights = [], iter([True, False])
    night_work.run_once(CONFIG, 64, 36, now=NIGHT, prepare=lambda s, n, *a, **k: calls.append(n), still_night=lambda: next(nights, False))
    assert calls == ["a.mp4"]
