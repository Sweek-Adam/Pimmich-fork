"""Calendrier photo : une photo par mois prise les années précédentes, anniversaires de la famille, PDF A4."""
from datetime import date

from PIL import Image

from utils import photo_calendar

INDEX = {f"essai/m{m}.jpg": {"date": f"2024-{m:02d}-10T12:00:00", "q": {"s": 300}} for m in (1, 4, 7)}
INDEX["essai/cette_annee.jpg"] = {"date": "2027-02-01T12:00:00", "q": {"s": 900}}
INDEX["essai/capture.jpg"] = {"date": "2023-02-01T12:00:00", "q": {"s": 900, "shot": True}}


def test_one_photo_per_month_from_past_years():
    chosen = photo_calendar.month_photos(INDEX, 2027)
    assert chosen[1] == "essai/m1.jpg" and chosen[4] == "essai/m4.jpg" and chosen[7] == "essai/m7.jpg"
    assert "essai/cette_annee.jpg" not in chosen.values() and "essai/capture.jpg" not in chosen.values()
    assert len(set(chosen.values())) == len(chosen) == 3  # trois photos seulement : pas de doublon pour les autres mois


def test_family_dates_on_the_calendar():
    config = {"family_dates": [{"kind": "birthday", "name": "Léa", "date": "2019-03-14"}, {"kind": "wedding", "name": "Marie et Paul", "date": "2010-06-20"}],
              "language": "fr"}
    marks = photo_calendar.events(config, 2027)
    assert marks[date(2027, 3, 14)] == ["Léa (8 ans)"] and "Mariage Marie et Paul" in marks[date(2027, 6, 20)]  # aussi la fête des pères ce jour-là
    assert any("mères" in t for texts in marks.values() for t in texts)


def test_build_writes_thirteen_pages(tmp_path):
    (tmp_path / "static" / "photos" / "essai").mkdir(parents=True)
    for m in (1, 4, 7):
        Image.new("RGB", (400, 300), (30 * m, 100, 160)).save(tmp_path / "static" / "photos" / "essai" / f"m{m}.jpg")
    pages = photo_calendar.build(INDEX, {}, 2027, tmp_path / "cal.pdf", tmp_path)
    data = (tmp_path / "cal.pdf").read_bytes()
    assert pages == 13 and data.count(b"/Type /Page ") == 13 and b"/MediaBox [0 0 595 842]" in data
