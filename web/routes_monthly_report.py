"""Bilan du mois par e-mail : réglages, envoi d'essai, envoi le 1er du mois (voir utils/monthly_report.py)."""
import html
from datetime import date, datetime, time as dtime

from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from utils import daily_photo, monthly_report

MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
LIBRARY_SOURCES = {"gdrive", "immich", "samba", "usb", "cloud", "icloud", "personnes", "films", "scans"}


def build_report(config, today=None):
    """(sujet, texte, html, images) du bilan du mois écoulé."""
    from utils import import_progress, members, reactions, stats, week_recap
    from utils.messages_manager import list_messages
    from utils.prepare_all_photos import is_media, prepared_name
    start, end = monthly_report.previous_month(today)
    since, until = datetime.combine(start, dtime()).timestamp(), datetime.combine(end, dtime()).timestamp()
    data = week_recap.collect(BASE_DIR / "static" / "photos", PREPARED_DIR, list_messages(), reactions.recent(reactions.RECENT),
                              prepared_name, is_media, now=until, since=since)
    views = monthly_report.views_between(stats._load().get("days"), start, end)
    month = f"{_(MONTHS[start.month - 1])} {start.year}"
    senders = []
    for source, count in data["by_source"].most_common(6):
        if source in LIBRARY_SOURCES:
            continue
        label = members.label(source) if members.is_member_source(source) else _(import_progress.SOURCE_LABELS.get(source, source))
        senders.append(f"{label} ({count})")
    lines = [_("%(count)s nouvelle(s) photo(s) et vidéo(s)", count=data["photos"]), _("%(count)s affichage(s) sur le cadre", count=views),
             _("%(count)s cœur(s) envoyé(s) depuis les téléphones", count=data["hearts"]), _("%(count)s message(s)", count=data["messages"])]
    picks = week_recap.pick_photos(data, BASE_DIR / "static", count=3)
    images = []
    for n, path in enumerate(picks):
        try:
            images.append((f"photo{n}", daily_photo.jpeg(path)))
        except OSError:
            pass
    frame = config.get("frame_name") or _("le cadre photo")
    subject = _("Le mois de %(month)s sur le cadre", month=month)
    thanks = _("Merci à %(names)s !", names=", ".join(senders)) if senders else ""
    text = "\n".join([subject, ""] + [f"• {line}" for line in lines] + (["", thanks] if thanks else []))
    body = [f'<div style="font-family:Helvetica,Arial,sans-serif;max-width:640px;margin:auto;color:#222">',
            f'<h2 style="font-weight:600">{html.escape(subject)}</h2><ul style="font-size:16px;line-height:1.6">']
    body += [f"<li>{html.escape(line)}</li>" for line in lines]
    body.append("</ul>")
    if thanks:
        body.append(f'<p style="font-size:16px">{html.escape(thanks)}</p>')
    if images:
        body.append(f'<p style="color:#777;margin-top:24px">{html.escape(_("Les photos les plus aimées du mois :"))}</p>')
        body += [f'<img src="cid:{cid}" alt="" style="width:100%;border-radius:12px;margin:6px 0">' for cid, _data in images]
    body.append(f'<p style="color:#999;font-size:13px;margin-top:24px">{html.escape(_("Envoyé par %(frame)s.", frame=frame))}</p></div>')
    return subject, text, "".join(body), images


def send_monthly_report(config, today=None):
    subject, text, body, images = build_report(config, today)
    daily_photo.send(config, monthly_report.message(config, monthly_report.recipients(config), subject, text, body, images))


@app.route('/api/monthly_report', methods=['GET', 'PUT'])
@admin_required
def monthly_report_api():
    config = load_config()
    if request.method == 'PUT':
        data = request.get_json(silent=True) or {}
        config = dict(config)
        if "enabled" in data:
            config["monthly_report_enabled"] = bool(data["enabled"])
        if "recipients" in data:
            config["monthly_report_recipients"] = sorted({a.strip().lower() for a in re.split(r"[\s,;]+", str(data["recipients"]))
                                                          if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", a.strip())})[:30]
        save_config(config)
        return jsonify({"success": True, "message": _("Bilan du mois enregistré.")})
    return jsonify({"success": True, "enabled": bool(config.get("monthly_report_enabled")), "recipients": monthly_report.recipients(config),
                    "mailbox": bool(config.get("email_user") and config.get("email_password"))})


@app.route('/api/monthly_report/test', methods=['POST'])
@admin_required
def monthly_report_test_api():
    config = load_config()
    if not monthly_report.recipients(config):
        return jsonify({"success": False, "message": _("Ajoutez d'abord au moins une adresse.")}), 400
    try:
        send_monthly_report(config)
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": _("Envoi impossible : %(error)s", error=str(e)[:200])}), 502
    return jsonify({"success": True, "message": _("Bilan envoyé à %(count)s adresse(s).", count=len(monthly_report.recipients(config)))})
