"""Photo du jour par e-mail pour les proches sans cadre : réglages, essai, envoi quotidien (voir utils/daily_photo.py)."""
import html
import time

from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from utils import daily_photo

MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def _recent_keys(days=daily_photo.RECENT_DAYS):
    from utils.prepare_all_photos import is_media, is_video, prepared_name
    since, keys = time.time() - days * 86400, []
    photos = BASE_DIR / "static" / "photos"
    for folder in photos.iterdir() if photos.is_dir() else []:
        if not folder.is_dir() or folder.name == "messages":
            continue
        for path in folder.iterdir():
            try:
                if path.is_file() and is_media(path.name) and not is_video(path.name) and path.stat().st_mtime >= since:
                    key = f"{folder.name}/{prepared_name(path.name)}"
                    if (PREPARED_DIR / key).is_file():
                        keys.append(key)
            except OSError:
                pass
    return keys


def send_daily_photo(config, to=None):
    """Envoie la photo du jour (à `to`, sinon aux destinataires choisis). Retourne la clé de la photo envoyée."""
    from utils import photo_book, photo_index, reactions
    index = photo_index.load()
    state = daily_photo.load_state()
    loved = photo_book.loved_by_key(photo_book.load_json(reactions.STORE, {}))
    choice = daily_photo.pick(index, loved=loved, favorites=photo_book.favorites_keys(load_favorites()),
                              recent_files=_recent_keys(), sent=state.get("sent") or {})
    if not choice:
        raise ValueError(_("Aucune photo à envoyer pour l'instant."))
    key, reason, years = choice
    path = PREPARED_DIR / key
    image = daily_photo.jpeg(path)
    entry = index.get(key) or {}
    caption = ""
    try:
        when = datetime.fromisoformat(entry["date"]) if entry.get("date") else None
    except ValueError:
        when = None
    if when:
        caption = f"{when.day} {_(MONTHS[when.month - 1])} {when.year}"
    try:
        from utils import geocode
        place = (geocode.cached(entry.get("lat"), entry.get("lon")) or {}).get("city")
        caption = f"{caption} · {place}" if place and caption else place or caption
    except Exception:
        pass
    today = datetime.now()
    headline = {"memory": _("Ce jour-là, il y a %(years)s ans", years=years) if years > 1 else _("Ce jour-là, il y a un an"),
                "new": _("Arrivée cette semaine sur le cadre"), "loved": _("Une des photos préférées de la famille")}[reason]
    frame = config.get("frame_name") or _("le cadre photo")
    subject = _("La photo du jour · %(day)s %(month)s", day=today.day, month=_(MONTHS[today.month - 1]))
    text = f"{headline}\n{caption}\n\n{_('Envoyée par %(frame)s.', frame=frame)}"
    body = (f'<div style="font-family:Helvetica,Arial,sans-serif;max-width:640px;margin:auto;color:#222">'
            f'<h2 style="font-weight:600;margin:0 0 12px">{html.escape(headline)}</h2>'
            f'<img src="cid:{{cid}}" alt="" style="width:100%;border-radius:12px">'
            f'<p style="color:#777;margin:10px 0 24px">{html.escape(caption)}</p>'
            f'<p style="color:#999;font-size:13px">{html.escape(_("Envoyée par %(frame)s.", frame=frame))}</p></div>')
    daily_photo.send(config, daily_photo.message(config, to or daily_photo.recipients(config), subject, text, body, image))
    sent = {k: v for k, v in (state.get("sent") or {}).items() if v > time.time() - daily_photo.NO_REPEAT_DAYS * 86400}
    sent[key] = time.time()
    state.update(sent=sent, last_key=key, last_at=time.time())
    daily_photo.save_state(state)
    return key


@app.route('/api/daily_photo', methods=['GET', 'PUT'])
@admin_required
def daily_photo_api():
    config = load_config()
    if request.method == 'PUT':
        data = request.get_json(silent=True) or {}
        config = dict(config)
        if "enabled" in data:
            config["daily_photo_enabled"] = bool(data["enabled"])
        if "recipients" in data:
            config["daily_photo_recipients"] = sorted({a.strip().lower() for a in re.split(r"[\s,;]+", str(data["recipients"]))
                                                       if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", a.strip())})[:30]
        if "time" in data:
            if not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", str(data["time"])):
                return jsonify({"success": False, "message": _("Heure invalide.")}), 400
            config["daily_photo_time"] = data["time"]
        save_config(config)
        return jsonify({"success": True, "message": _("Photo du jour enregistrée.")})
    state = daily_photo.load_state()
    return jsonify({"success": True, "enabled": bool(config.get("daily_photo_enabled")), "recipients": daily_photo.recipients(config),
                    "time": config.get("daily_photo_time") or "08:00", "mailbox": bool(config.get("email_user") and config.get("email_password")),
                    "last_at": state.get("last_at"), "last_error": state.get("last_error")})


@app.route('/api/daily_photo/test', methods=['POST'])
@admin_required
def daily_photo_test_api():
    """Envoie tout de suite la photo du jour aux destinataires (essai)."""
    config = load_config()
    if not daily_photo.recipients(config):
        return jsonify({"success": False, "message": _("Ajoutez d'abord au moins une adresse.")}), 400
    try:
        send_daily_photo(config)
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": _("Envoi impossible : %(error)s", error=str(e)[:200])}), 502
    return jsonify({"success": True, "message": _("Photo envoyée à %(count)s adresse(s).", count=len(daily_photo.recipients(config)))})
