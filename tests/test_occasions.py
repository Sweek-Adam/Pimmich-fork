"""Moments de famille et fêtes : dates (selon le pays), occasions du moment, dispositions correspondantes."""
import random
from datetime import date

from PIL import Image

from utils import occasions

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}
FAMILY = {"family_dates": [{"kind": "birthday", "name": "Léo", "date": "2016-03-12"},
                           {"kind": "wedding", "name": "Claire & Paul", "date": "2001-06-20"},
                           {"kind": "birth", "name": "Emma", "date": "2026-10-01"},
                           {"kind": "birthday", "name": "", "date": "2000-01-01"}, {"kind": "chien", "name": "Rex", "date": "2020-01-01"}]}


def test_mothers_and_fathers_days_by_country():
    assert occasions.mothers_day(2025, "FR") == date(2025, 5, 25)
    assert occasions.mothers_day(2023, "FR") == date(2023, 6, 4)  # dernier dimanche de mai = Pentecôte : décalée en juin
    assert occasions.mothers_day(2025, "US") == date(2025, 5, 11) and occasions.mothers_day(2025, "ES") == date(2025, 5, 4)
    assert occasions.fathers_day(2025, "FR") == date(2025, 6, 15) and occasions.fathers_day(2025, "DE") == date(2025, 5, 29)
    assert occasions.fathers_day(2025, "ES") == date(2025, 3, 19)
    assert occasions.country({"language": "de"}) == "DE" and occasions.country({"country": "es", "language": "fr"}) == "ES"


def test_family_occasions():
    themes = lambda day: [(o["theme"], o["name"], o["years"]) for o in occasions.active(FAMILY, day)]
    assert themes(date(2026, 3, 12)) == [("anniversaire_perso", "Léo", 10)]
    assert themes(date(2026, 3, 13)) == [("anniversaire_perso", "Léo", 10)]  # le lendemain encore
    assert themes(date(2026, 3, 15)) == []
    assert themes(date(2026, 6, 20)) == [("mariage", "Claire & Paul", 25), ("fete_peres", "", 0)]  # fête des pères le 21
    assert ("naissance", "Emma", 0) in themes(date(2026, 10, 11)) and not any(t[0] == "naissance" for t in themes(date(2026, 12, 31)))
    assert [t[0] for t in themes(date(2026, 2, 10))] == ["saint_valentin"]
    assert [t[0] for t in themes(date(2026, 9, 3))] == ["rentree"]
    assert occasions.in_season("fete_meres", date(2026, 5, 29), {"language": "fr"})  # fête des mères 2026 : 31 mai
    assert not occasions.in_season("fete_meres", date(2026, 5, 29), {"language": "en"})  # aux États-Unis : 10 mai
    upcoming = occasions.upcoming(FAMILY, date(2026, 2, 20))
    assert [(u["name"], u["years"]) for u in upcoming] == [("Léo", 10)]


def test_family_layouts_only_at_their_date(monkeypatch):
    from utils import compositions, layout_engine
    monkeypatch.setattr(occasions, "for_theme", lambda theme, config=None, today=None: {"name": "Léo", "years": 7} if theme == "anniversaire_perso" else None)
    plan = layout_engine.resolve({"compositions_seasonal": False})
    assert "anniversaire_perso" in plan.formats and "fete_meres" not in plan.formats
    photos = [Image.new("RGB", (400, 300), c) for c in ((200, 90, 90), (90, 160, 200), (90, 180, 90))]
    for key in ("anniversaire_perso", "mariage", "naissance", "rentree", "saint_valentin", "fete_meres", "fete_peres"):
        image = compositions.FORMATS[key][4](photos, None, 640, 360, random.Random(1))
        assert image.size == (640, 360) and key in compositions.SEASONAL


def test_family_dates_api(admin_client):
    from utils.config_manager import load_config, save_config
    original = dict(load_config())
    try:
        r = admin_client.post("/api/family_dates", json={"dates": FAMILY["family_dates"] + ["x"]}, headers=SAME_ORIGIN).get_json()
        assert r["success"] and len(load_config()["family_dates"]) == 3
        data = admin_client.get("/api/family_dates").get_json()
        assert {d["name"] for d in data["dates"]} == {"Léo", "Claire & Paul", "Emma"} and data["country"]
        assert admin_client.post("/api/family_dates", json={"dates": "non"}, headers=SAME_ORIGIN).status_code == 400
    finally:
        save_config(original)
