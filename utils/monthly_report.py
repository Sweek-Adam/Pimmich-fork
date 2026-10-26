"""
Bilan du mois par e-mail (le 1er du mois, pour le mois écoulé) : photos reçues et qui les a envoyées, affichages,
cœurs, messages, et les photos les plus aimées. Envoyé depuis la boîte mail du cadre (comme la photo du jour, voir
utils/daily_photo.py) aux adresses choisies ; désactivé par défaut.
"""
import json
import time
from datetime import date, datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = PROJECT_DIR / "cache" / "monthly_report.json"
SEND_HOUR = 10


def previous_month(today=None):
    """(premier jour du mois écoulé, premier jour du mois en cours)."""
    today = today or date.today()
    end = today.replace(day=1)
    start = (end.replace(year=end.year - 1, month=12) if end.month == 1 else end.replace(month=end.month - 1))
    return start, end


def recipients(config):
    return [a for a in config.get("monthly_report_recipients") or [] if "@" in a][:30]


def due(config, now=None):
    if not config.get("monthly_report_enabled") or not recipients(config):
        return False
    now = now or datetime.now()
    try:
        sent = json.loads(STATE_FILE.read_text()).get("month")
    except (OSError, ValueError):
        sent = None
    return now.hour >= SEND_HOUR and sent != now.strftime("%Y-%m")


def mark_sent(now=None):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"month": (now or datetime.now()).strftime("%Y-%m"), "at": time.time()}))


def views_between(days, start, end):
    """Affichages du diaporama entre deux dates (compteurs par jour de utils/stats.py)."""
    return sum(n for day, n in (days or {}).items() if start.isoformat() <= day < end.isoformat())


def message(config, to, subject, text, html, images):
    """E-mail HTML avec des photos intégrées : `images` = [(identifiant, octets JPEG)], appelées cid:identifiant."""
    from email.message import EmailMessage
    mail = EmailMessage()
    mail["From"] = config.get("email_user")
    mail["To"] = config.get("email_user")
    mail["Bcc"] = ", ".join(to)
    mail["Subject"] = subject
    mail.set_content(text)
    mail.add_alternative(html, subtype="html")
    related = mail.get_payload()[1]
    for cid, data in images:
        related.add_related(data, "image", "jpeg", cid=f"<{cid}>", filename=f"{cid}.jpg")
    return mail
