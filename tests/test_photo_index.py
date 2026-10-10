"""Index des photos (dates, GPS) et « Ce jour-là »."""
from datetime import date, datetime

import pytest
from PIL import Image

from utils import photo_index


@pytest.fixture()
def library(tmp_path, monkeypatch):
    prepared, originals = tmp_path / "prepared", tmp_path / "photos"
    for folder in (prepared / "gdrive", prepared / "smartphone", prepared / "messages", originals / "gdrive"):
        folder.mkdir(parents=True)
    monkeypatch.setattr(photo_index, "PREPARED_DIR", prepared)
    monkeypatch.setattr(photo_index, "ORIGINALS_DIR", originals)
    monkeypatch.setattr(photo_index, "INDEX_FILE", tmp_path / "cache" / "photo_index.json")
    monkeypatch.setattr(photo_index, "_immich", lambda path: {})
    return prepared, originals


def _jpeg(path, taken=None, gps=None):
    image = Image.new("RGB", (40, 30), (120, 160, 200))
    exif = Image.Exif()
    if taken:
        exif.get_ifd(0x8769)[36867] = taken.strftime("%Y:%m:%d %H:%M:%S")
    if gps:
        exif.get_ifd(0x8825).update({1: "N", 2: (48.0, 51.0, 24.0), 3: "E", 4: (2.0, 21.0, 0.0)})
    image.save(path, "JPEG", exif=exif)


def test_dates_come_from_exif_original_or_file_name(library):
    prepared, originals = library
    _jpeg(prepared / "gdrive" / "DSC_0531.jpg")  # préparée sans date…
    _jpeg(originals / "gdrive" / "DSC_0531.JPG", datetime(2019, 10, 10, 18, 30), gps=True)  # … mais l'original en a une
    _jpeg(prepared / "gdrive" / "DSC_0531_polaroid.jpg")  # variante : pas une photo à part
    _jpeg(prepared / "smartphone" / "IMG-20211010-WA0004.jpg")  # WhatsApp : EXIF effacé, date dans le nom
    _jpeg(prepared / "smartphone" / "sans_date.jpg")
    _jpeg(prepared / "messages" / "abc.jpg", datetime(2020, 10, 10))  # les messages ne sont pas des photos
    assert photo_index.update() == 3
    index = photo_index.load()
    assert set(index) == {"gdrive/DSC_0531.jpg", "smartphone/IMG-20211010-WA0004.jpg", "smartphone/sans_date.jpg"}
    assert index["gdrive/DSC_0531.jpg"]["date"] == "2019-10-10T18:30:00" and index["gdrive/DSC_0531.jpg"]["how"] == "exif"
    assert index["gdrive/DSC_0531.jpg"]["lat"] == pytest.approx(48.8567, abs=1e-3) and index["gdrive/DSC_0531.jpg"]["lon"] == pytest.approx(2.35)
    assert index["smartphone/IMG-20211010-WA0004.jpg"]["how"] == "name"
    assert index["smartphone/sans_date.jpg"]["date"] is None
    assert photo_index.update() == 0  # rien de nouveau : rien n'est relu
    assert photo_index.taken(prepared / "gdrive" / "DSC_0531_polaroid.jpg").year == 2019
    (prepared / "smartphone" / "sans_date.jpg").unlink()
    photo_index.update()
    assert "smartphone/sans_date.jpg" not in photo_index.load()


def test_on_this_day(library):
    prepared, _ = library
    _jpeg(prepared / "gdrive" / "a.jpg", datetime(2016, 10, 10))
    _jpeg(prepared / "gdrive" / "b.jpg", datetime(2023, 10, 10))
    _jpeg(prepared / "gdrive" / "c.jpg", datetime(2023, 10, 11))
    _jpeg(prepared / "gdrive" / "d.jpg", datetime(2026, 10, 10))  # aujourd'hui : pas encore un souvenir
    photo_index.update()
    found = photo_index.on_this_day(date(2026, 10, 10))
    assert [k for k, _ in found] == ["gdrive/a.jpg", "gdrive/b.jpg"]


def test_memories_api(admin_client, library, monkeypatch):
    prepared, _ = library
    today = date.today()
    _jpeg(prepared / "gdrive" / "old.jpg", datetime(today.year - 3, today.month, min(today.day, 28)))
    if today.day > 28:
        pytest.skip("fin de mois")
    photo_index.update()
    items = admin_client.get("/api/memories/today").get_json()["items"]
    assert items == [{"thumb": "/static/prepared/gdrive/old.jpg", "year": today.year - 3, "years_ago": 3}]


def test_slideshow_memory_ribbon_and_years():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame = pytest.importorskip("pygame")
    import local_slideshow as ls
    pygame.init()
    today = datetime(2026, 10, 10, 9)
    assert ls.memory_years({"dateTimeOriginal": "2021-10-10T18:00:00"}, today) == (5, datetime(2021, 10, 10, 18))
    assert ls.memory_years({"dateTimeOriginal": "2021-10-11T18:00:00"}, today) is None
    assert ls.memory_years({}, today) is None
    screen = pygame.Surface((1920, 1080))
    now = datetime.now()
    ls.draw_memory_banner(screen, 1920, 1080, {}, {"dateTimeOriginal": now.replace(year=now.year - 2).isoformat()})
    assert screen.get_at((960, int(1080 * 0.03) + 20))[:3] != (0, 0, 0)  # ruban en haut au centre


def test_memories_board_renders():
    import random
    from utils import compositions  # noqa: F401 (ordre d'import de l'application)
    from utils.themed_compositions_extra import memories_board
    items = [(Image.new("RGB", (120, 90), c), datetime(y, 10, 10)) for c, y in (("red", 2016), ("blue", 2021))]
    assert memories_board(items, 640, 360, random.Random(1), date(2026, 10, 10)).size == (640, 360)
