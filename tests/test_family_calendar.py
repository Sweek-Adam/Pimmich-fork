"""Agenda familial (iCal) et comptes à rebours."""
from datetime import date, datetime

from utils import family_calendar as fc

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}
ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART;VALUE=DATE:19500311
RRULE:FREQ=YEARLY
SUMMARY:Anniversaire de Mamie
END:VEVENT
BEGIN:VEVENT
DTSTART:20261013T200000
SUMMARY:Dîner chez Julie\\, Thomas
  et les enfants
END:VEVENT
BEGIN:VEVENT
DTSTART:20260902T173000
RRULE:FREQ=WEEKLY
SUMMARY:Piscine
END:VEVENT
BEGIN:VEVENT
DTSTART:20261201T100000
SUMMARY:Trop loin
END:VEVENT
END:VCALENDAR"""


def test_parse_and_upcoming_week():
    events = fc.parse_ics(ICS)
    assert [e["title"] for e in events][:2] == ["Anniversaire de Mamie", "Dîner chez Julie, Thomas et les enfants"]
    week = fc.occurrences(events, date(2026, 3, 9), 7)
    assert [(o["title"], o["when"].date()) for o in week] == [("Anniversaire de Mamie", date(2026, 3, 11))]  # piscine : à partir de septembre
    week = fc.occurrences(events, date(2026, 10, 10), 7)
    titles = [o["title"] for o in week]
    assert "Dîner chez Julie, Thomas et les enfants" in titles and "Piscine" in titles and "Trop loin" not in titles


def test_countdowns():
    config = {"countdowns": [{"title": "Noël", "date": "2025-12-25", "yearly": True}, {"title": "Vacances", "date": "2026-10-17"},
                             {"title": "Passé", "date": "2026-01-01"}]}
    result = fc.countdowns(config, date(2026, 10, 10))
    assert [(c["title"], c["days"]) for c in result] == [("Vacances", 7), ("Noël", 76)]


def test_calendar_api(admin_client, monkeypatch):
    from utils.config_manager import load_config
    r = admin_client.post("/api/calendar", json={"url": "javascript:alert(1)"}, headers=SAME_ORIGIN)
    assert r.status_code == 400
    r = admin_client.post("/api/calendar", json={"url": "webcal://example.com/basic.ics", "countdowns": [{"title": "Vacances", "date": "2026-10-17"}]}, headers=SAME_ORIGIN).get_json()
    assert r["success"] and load_config()["countdowns"] == [{"title": "Vacances", "date": "2026-10-17", "yearly": False}]
    assert admin_client.post("/api/calendar", json={"countdowns": [{"title": "x", "date": "demain"}]}, headers=SAME_ORIGIN).status_code == 400

    class Resp:
        text = ICS
        def raise_for_status(self):
            pass
    monkeypatch.setattr(fc.requests, "get", lambda url, timeout: Resp())
    monkeypatch.setattr(fc, "_cache", {"url": None, "at": 0, "events": []})
    assert isinstance(admin_client.get("/api/calendar?preview=1").get_json()["preview"], list)


def test_week_board_renders():
    import random
    from utils import compositions  # noqa: F401 (ordre d'import de l'application)
    from utils.themed_compositions_extra import week_board
    image = week_board([{"title": "Piscine", "when": datetime(2026, 10, 11, 17), "all_day": False}],
                       [{"title": "Vacances", "days": 7}], 640, 360, random.Random(1), date(2026, 10, 10))
    assert image.size == (640, 360)


GOOGLE = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:jdr-a
DTSTART;TZID=Europe/Paris:20260728T210000
RRULE:FREQ=WEEKLY;UNTIL=20261019T215959Z;INTERVAL=3;BYDAY=TU
SUMMARY:Jdr Poudlard
END:VEVENT
BEGIN:VEVENT
UID:jdr-b
DTSTART;TZID=Europe/Paris:20260303T210000
RRULE:FREQ=WEEKLY;UNTIL=20260413T215959Z;INTERVAL=3;BYDAY=TU
SUMMARY:Jdr Poudlard
END:VEVENT
BEGIN:VEVENT
UID:jdr-c
DTSTART;TZID=Europe/Paris:20261027T210000
RRULE:FREQ=WEEKLY;INTERVAL=3;BYDAY=TU
SUMMARY:Jdr Poudlard
END:VEVENT
BEGIN:VEVENT
UID:karate-old
DTSTART;TZID=Europe/Paris:20241028T193000
RRULE:FREQ=WEEKLY;WKST=MO;UNTIL=20241124T225959Z;INTERVAL=1;BYDAY=MO,TH
SUMMARY:[Montigny] Karaté
END:VEVENT
BEGIN:VEVENT
UID:karate
DTSTART;TZID=Europe/Paris:20241125T193000
RRULE:FREQ=WEEKLY;WKST=MO;INTERVAL=1;BYDAY=MO,TH
EXDATE;TZID=Europe/Paris:20261015T193000
SUMMARY:[Montigny] Karaté
END:VEVENT
BEGIN:VEVENT
UID:karate
RECURRENCE-ID;TZID=Europe/Paris:20261012T193000
DTSTART;TZID=Europe/Paris:20261012T180000
SUMMARY:[Montigny] Karaté (avancé)
END:VEVENT
BEGIN:VEVENT
UID:annule
DTSTART;TZID=Europe/Paris:20261014T120000
STATUS:CANCELLED
SUMMARY:Annulé
END:VEVENT
END:VCALENDAR"""


def test_google_calendar_series():
    """Séries découpées (UNTIL), toutes les 3 semaines, plusieurs jours, exclusions, occurrence déplacée, annulation."""
    week = fc.occurrences(fc.parse_ics(GOOGLE), date(2026, 10, 12), 7)
    got = [(o["title"], o["when"].strftime("%a %d %H:%M")) for o in week]
    # déplacée (remplace celle de 19:30) ; jeudi 15 exclu ; pas de Jdr : toutes les 3 semaines (29/09, puis fin le 19/10)
    assert got == [("[Montigny] Karaté (avancé)", "Mon 12 18:00")]
    three_weeks = fc.occurrences(fc.parse_ics(GOOGLE), date(2026, 10, 19), 21)
    jdr = [o["when"].date() for o in three_weeks if o["title"] == "Jdr Poudlard"]
    assert jdr == [date(2026, 10, 27)]  # la 1re série s'arrête le 19/10 (pas de 20/10), la nouvelle commence le 27/10
    karate = [o["when"].date() for o in three_weeks if o["title"] == "[Montigny] Karaté"]
    assert len(karate) == 6 and all(d.weekday() in (0, 3) for d in karate)  # lundi et jeudi, sans doublon
