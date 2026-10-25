"""Bilan du jour : contenu et une seule fois par jour, à partir de l'heure choisie."""
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

from utils import daily_summary


def test_summary_counts_and_once_a_day(sandbox, monkeypatch):
    folder = Path("static/photos/bilan")
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    for name in ("a.jpg", "b.HEIC", "c.mp4", ".cache.jpg", "notes.txt"):
        (folder / name).write_bytes(b"x")
    old = folder / "ancienne.jpg"
    old.write_bytes(b"x")
    os.utime(old, (time.time() - 3 * 86400,) * 2)
    from utils import hardware
    monkeypatch.setattr(hardware, "temperature", lambda: 52.4)
    monkeypatch.setattr(hardware, "throttled", lambda: hardware.UNDERVOLT_SINCE_BOOT)
    title, text = daily_summary.build({})
    assert title == "Bilan du jour" and "2 photo(s), 1 vidéo(s)" in text and "52 °C" in text and "alimentation" in text
    shutil.rmtree(folder)
    monkeypatch.setattr(daily_summary, "STATE_FILE", Path("cache") / "daily_summary_test.json")
    daily_summary.STATE_FILE.unlink(missing_ok=True)
    evening, morning = datetime(2026, 10, 25, 20, 30).timestamp(), datetime(2026, 10, 25, 9, 0).timestamp()
    assert not daily_summary.due({"daily_summary_time": "20:00"}, morning)
    assert daily_summary.due({"daily_summary_time": "20:00"}, evening)
    daily_summary.mark_sent(evening)
    assert not daily_summary.due({"daily_summary_time": "20:00"}, evening + 600)
    assert daily_summary.due({"daily_summary_time": "20:00"}, evening + 86400)
