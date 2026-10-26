"""Rappels d'anniversaire : trois jours avant et le jour J, avec le texte de la notification."""
from datetime import date


CONFIG = {"family_dates": [{"kind": "birthday", "name": "Léa", "date": "2018-10-31"},
                           {"kind": "wedding", "name": "Marie et Paul", "date": "2001-10-28"},
                           {"kind": "birthday", "name": "Tom", "date": "2015-12-25"}]}


def test_reminders_three_days_before_and_on_the_day():
    from utils import occasions
    found = occasions.reminders(CONFIG, date(2026, 10, 28))
    assert [(o["name"], o["delta"], o["years"]) for o in found] == [("Marie et Paul", 0, 25), ("Léa", 3, 8)]
    assert occasions.reminders(CONFIG, date(2026, 10, 29)) == []


def test_reminder_text(app_module):
    from utils import occasions
    from web.workers import occasion_reminder_text
    with app_module.app.test_request_context():
        later, today = occasions.reminders(CONFIG, date(2026, 10, 28))[::-1]
        title, text = occasion_reminder_text(later)
        assert "3" in title and "Léa" in text and "8" in text and text.startswith("Samedi")
        assert "Marie et Paul" in occasion_reminder_text(today)[1]
