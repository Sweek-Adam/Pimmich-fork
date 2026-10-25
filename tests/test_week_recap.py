"""« Votre semaine sur le cadre » : chiffres des sept derniers jours et diapositive du dimanche soir."""
import os
import random
import time
from datetime import datetime

from PIL import Image

from utils import week_recap
from utils.prepare_all_photos import is_media, prepared_name


def test_shown_on_sunday_evening_only():
    assert week_recap.showing(datetime(2026, 10, 25, 18, 0))      # dimanche 18 h
    assert not week_recap.showing(datetime(2026, 10, 25, 11, 0))  # dimanche matin
    assert not week_recap.showing(datetime(2026, 10, 24, 20, 0))  # samedi


def test_collect_counts_the_week(tmp_path):
    photos, prepared, static = tmp_path / "static" / "photos", tmp_path / "static" / "prepared", tmp_path / "static"
    for source, names in {"invités": ["a.jpg", "b.jpg"], "gdrive": ["c.jpg"], "messages": ["m.jpg"]}.items():
        (photos / source).mkdir(parents=True)
        (prepared / source).mkdir(parents=True)
        for name in names:
            Image.new("RGB", (20, 20)).save(photos / source / name)
            Image.new("RGB", (20, 20)).save(prepared / source / name)
    old = time.time() - 10 * 86400
    os.utime(photos / "gdrive" / "c.jpg", (old, old))  # il y a 10 jours : pas cette semaine
    now = time.time()
    messages = [{"created": time.strftime("%Y-%m-%d %H:%M")}, {"created": "2020-01-01 10:00"}]
    hearts = [{"photo": "prepared/invités/b.jpg", "at": now}, {"photo": "prepared/invités/b.jpg", "at": now}, {"photo": "x", "at": 0}]
    stats = week_recap.collect(photos, prepared, messages, hearts, prepared_name, is_media)
    assert stats["photos"] == 2 and dict(stats["by_source"]) == {"invités": 2}
    assert stats["messages"] == 1 and stats["hearts"] == 2 and stats["loved"][0] == "prepared/invités/b.jpg"
    picked = week_recap.pick_photos(stats, static, rng=random.Random(1))
    assert picked[0].endswith("invités/b.jpg") and len(picked) == 2  # la plus aimée d'abord


def test_board_renders():
    from utils import compositions  # noqa: F401 (charge les compositions dans le même ordre que le diaporama)
    from utils.themed_compositions_extra import week_recap_board
    images = [Image.new("RGB", (300, 200), (40 * i, 100, 160)) for i in range(4)]
    board = week_recap_board(images, {"photos": 12, "messages": 3, "hearts": 7, "senders": [("Léa", 8), ("Invités", 4)]}, 640, 360, random.Random(2))
    assert board.size == (640, 360)
