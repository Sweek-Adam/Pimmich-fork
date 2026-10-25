"""Photo du jour par e-mail : choix de la photo, heure d'envoi, message envoyé (serveur SMTP simulé)."""
import time
from datetime import date, datetime
from pathlib import Path

from PIL import Image

from utils import daily_photo

SAME = {"Sec-Fetch-Site": "same-origin"}
INDEX = {"a/souvenir.jpg": {"date": "2021-10-26T10:00:00"}, "a/autre.jpg": {"date": "2023-03-01T10:00:00"},
         "a/capture.jpg": {"date": "2020-10-26T10:00:00", "q": {"shot": True}}}


def test_pick_prefers_memories_then_new_then_loved():
    today = date(2026, 10, 26)
    assert daily_photo.pick(INDEX, today) == ("a/souvenir.jpg", "memory", 5)
    sent = {"a/souvenir.jpg": time.time()}  # déjà envoyée récemment
    assert daily_photo.pick(INDEX, today, recent_files=["a/autre.jpg"], sent=sent) == ("a/autre.jpg", "new", 0)
    assert daily_photo.pick(INDEX, today, loved={"a/autre.jpg": 3}, sent=sent)[0] == "a/autre.jpg"
    assert daily_photo.pick(INDEX, today, sent={k: time.time() for k in INDEX}) is None


def test_due_once_a_day_after_the_hour():
    config = {"daily_photo_enabled": True, "daily_photo_recipients": ["mamie@exemple.fr"], "daily_photo_time": "08:30"}
    assert not daily_photo.due(config, {}, datetime(2026, 10, 26, 8, 0))
    assert daily_photo.due(config, {}, datetime(2026, 10, 26, 9, 0))
    assert not daily_photo.due(config, {"last_day": "2026-10-26"}, datetime(2026, 10, 26, 9, 0))
    assert not daily_photo.due(dict(config, daily_photo_enabled=False), {}, datetime(2026, 10, 26, 9, 0))
    assert daily_photo.smtp_host({"email_imap_host": "imap.gmail.com"}) == "smtp.gmail.com"


def test_send_now(admin_client, monkeypatch, tmp_path):
    from utils import photo_index
    from utils.config_manager import load_config, save_config
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            self.host = host

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def login(self, user, password):
            pass

        def send_message(self, mail):
            sent.append((self.host, mail))

    monkeypatch.setattr(daily_photo.smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.setattr(daily_photo, "STATE_FILE", tmp_path / "state.json")
    prepared = Path("static/prepared/a")
    prepared.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (800, 600), (120, 80, 60)).save(prepared / "souvenir.jpg")
    monkeypatch.setattr(photo_index, "load", lambda: {"a/souvenir.jpg": {"date": f"2020-{date.today():%m-%d}T10:00:00"}})
    original = dict(load_config())
    try:
        save_config(dict(original, email_user="cadre@exemple.fr", email_password="x", email_imap_host="imap.exemple.fr"))
        assert admin_client.post("/api/daily_photo/test", headers=SAME).status_code == 400  # aucune adresse
        r = admin_client.put("/api/daily_photo", json={"recipients": "mamie@exemple.fr, pas-une-adresse, tonton@exemple.fr", "time": "07:45"},
                             headers=SAME).get_json()
        assert r["success"] and admin_client.get("/api/daily_photo").get_json()["recipients"] == ["mamie@exemple.fr", "tonton@exemple.fr"]
        assert admin_client.post("/api/daily_photo/test", headers=SAME).get_json()["success"]
        host, mail = sent[0]
        assert host == "smtp.exemple.fr" and mail["Bcc"] == "mamie@exemple.fr, tonton@exemple.fr" and "photo" in mail["Subject"].lower()
        assert any(part.get_content_type() == "image/jpeg" for part in mail.walk())
    finally:
        save_config(original)
        import shutil
        shutil.rmtree(prepared, ignore_errors=True)
