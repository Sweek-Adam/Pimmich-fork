"""Bilan du mois par e-mail : période, chiffres, photos intégrées (serveur d'envoi simulé)."""
import os
import time
from datetime import date, datetime
from pathlib import Path

from PIL import Image

from utils import daily_photo, monthly_report

SAME = {"Sec-Fetch-Site": "same-origin"}


def test_previous_month_and_due(tmp_path, monkeypatch):
    assert monthly_report.previous_month(date(2026, 11, 1)) == (date(2026, 10, 1), date(2026, 11, 1))
    assert monthly_report.previous_month(date(2027, 1, 15)) == (date(2026, 12, 1), date(2027, 1, 1))
    monkeypatch.setattr(monthly_report, "STATE_FILE", tmp_path / "state.json")
    config = {"monthly_report_enabled": True, "monthly_report_recipients": ["lea@exemple.fr"]}
    assert not monthly_report.due(config, datetime(2026, 11, 1, 8, 0))
    assert monthly_report.due(config, datetime(2026, 11, 1, 10, 30))
    monthly_report.mark_sent(datetime(2026, 11, 1, 10, 30))
    assert not monthly_report.due(config, datetime(2026, 11, 2, 10, 30))
    assert monthly_report.views_between({"2026-10-03": 40, "2026-10-31": 10, "2026-11-01": 7}, date(2026, 10, 1), date(2026, 11, 1)) == 50


def test_send_now(admin_client, monkeypatch, tmp_path):
    from utils.config_manager import load_config, save_config
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def login(self, user, password):
            pass

        def send_message(self, mail):
            sent.append(mail)

    monkeypatch.setattr(daily_photo.smtplib, "SMTP_SSL", FakeSMTP)
    folder, prepared = Path("static/photos/invités_mois"), Path("static/prepared/invités_mois")
    folder.mkdir(parents=True, exist_ok=True)
    prepared.mkdir(parents=True, exist_ok=True)
    start, end = monthly_report.previous_month()
    middle = datetime.combine(start, datetime.min.time()).timestamp() + 5 * 86400
    for name in ("a.jpg", "b.jpg"):
        Image.new("RGB", (400, 300), (200, 100, 50)).save(folder / name)
        Image.new("RGB", (400, 300), (200, 100, 50)).save(prepared / name)
        os.utime(folder / name, (middle, middle))
    original = dict(load_config())
    try:
        save_config(dict(original, email_user="cadre@exemple.fr", email_password="x", email_imap_host="imap.exemple.fr"))
        assert admin_client.post("/api/monthly_report/test", headers=SAME).status_code == 400
        admin_client.put("/api/monthly_report", json={"recipients": "lea@exemple.fr"}, headers=SAME)
        assert admin_client.post("/api/monthly_report/test", headers=SAME).get_json()["success"]
        mail = sent[0]
        html = mail.get_body(("html",)).get_content()
        assert mail["Bcc"] == "lea@exemple.fr" and "2 nouvelle(s) photo(s)" in html
        assert sum(1 for part in mail.walk() if part.get_content_type() == "image/jpeg") == 2
    finally:
        save_config(original)
        import shutil
        shutil.rmtree(folder, ignore_errors=True)
        shutil.rmtree(prepared, ignore_errors=True)
