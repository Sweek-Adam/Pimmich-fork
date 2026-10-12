"""
Agenda familial et comptes à rebours, affichés sur le cadre (diapositive « Cette semaine »).

- Agenda : adresse iCal secrète d'un agenda (Google Agenda : Paramètres > « Adresse secrète au format iCal »),
  lue sans compte ni connexion ; répétitions iCal complètes (python-dateutil), exceptions et occurrences déplacées ;
- comptes à rebours : événements saisis dans l'interface (vacances, mariage...).
"""
import re
import time
from datetime import date, datetime, timedelta, timezone

import requests
from dateutil.rrule import rrulestr

CACHE_SECONDS = 30 * 60
_cache = {"url": None, "at": 0, "events": []}


def _unfold(text):
    """Lignes iCal repliées (continuations commençant par un espace) -> lignes complètes."""
    return re.sub(r"\r?\n[ \t]", "", text).splitlines()


def _parse_date(value):
    """Date iCal -> (datetime local sans fuseau, journée entière ?). Les heures UTC (« Z ») passent à l'heure locale."""
    value = value.strip()
    try:
        if "T" in value:
            moment = datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
            if value.endswith("Z"):
                moment = moment.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
            return moment, False
        return datetime.strptime(value[:8], "%Y%m%d"), True
    except ValueError:
        return None, True


def _unescape(text):
    return text.replace("\\,", ",").replace("\\;", ";").replace("\\n", " ").replace("\\N", " ").replace("\\\\", "\\").strip()


def parse_ics(text):
    """
    Événements d'un fichier iCal : [{title, start (datetime), all_day, rrule, uid, exdates, recurrence_id, cancelled}].
    `recurrence_id` : occurrence d'une série modifiée à part (déplacée, renommée) ; elle remplace celle de la série.
    """
    events, current = [], None
    for line in _unfold(text):
        if line == "BEGIN:VEVENT":
            current = {"exdates": []}
        elif line == "END:VEVENT" and current is not None:
            if current.get("start") and current.get("title"):
                events.append(current)
            current = None
        elif current is not None and ":" in line:
            key, value = line.split(":", 1)
            name = key.split(";", 1)[0].upper()
            if name == "SUMMARY":
                current["title"] = _unescape(value)[:120]
            elif name == "DTSTART":
                current["start"], current["all_day"] = _parse_date(value)
            elif name == "RRULE":
                current["rrule"] = value.upper()
            elif name == "UID":
                current["uid"] = value.strip()
            elif name == "EXDATE":
                current["exdates"] += [d for d, _ in map(_parse_date, value.split(",")) if d]
            elif name == "RECURRENCE-ID":
                current["recurrence_id"] = _parse_date(value)[0]
            elif name == "STATUS":
                current["cancelled"] = value.strip().upper() == "CANCELLED"
    return events


def _local_rule(rule):
    """Règle RRULE avec une fin (UNTIL) à l'heure locale sans fuseau, comme les dates de début."""
    def until(match):
        moment, _all_day = _parse_date(match.group(1))
        return f"UNTIL={moment:%Y%m%dT%H%M%S}" if moment else ""
    return re.sub(r"UNTIL=([0-9TZ]+)", until, rule).strip(";")


def occurrences(events, start, days):
    """
    Occurrences entre `start` (date) et `start + days` : [{title, when (datetime), all_day}], dans l'ordre, sans doublon.
    Répétitions complètes (fréquence, intervalle, jours, fin, nombre), dates exclues, occurrences déplacées et
    événements annulés sont pris en compte.
    """
    window_start = datetime.combine(start, datetime.min.time())
    window_end = window_start + timedelta(days=days)
    replaced = {(e.get("uid"), e["recurrence_id"]) for e in events if e.get("recurrence_id")}
    found = []
    for e in events:
        if e.get("cancelled"):
            continue
        first, rule = e["start"], e.get("rrule", "")
        if rule and not e.get("recurrence_id"):
            try:
                series = rrulestr(_local_rule(rule), dtstart=first)
                candidates = series.between(window_start, window_end - timedelta(seconds=1), inc=True)
            except (ValueError, TypeError):
                candidates = [first]
            skipped = set(e.get("exdates") or [])
            candidates = [when for when in candidates if when not in skipped and (e.get("uid"), when) not in replaced]
        else:
            candidates = [first]
        for when in candidates:
            if window_start <= when < window_end:
                found.append({"title": e["title"], "when": when, "all_day": e.get("all_day", True)})
    unique = {(o["title"], o["when"]): o for o in found}  # un même événement présent dans deux agendas
    return sorted(unique.values(), key=lambda o: o["when"])


def upcoming(config, today=None, days=7):
    """Événements de l'agenda des prochains jours (lecture mise en cache 30 minutes)."""
    url = (config.get("calendar_ics_url") or "").strip()
    if not url.startswith(("https://", "http://", "webcal://")):
        return []
    url = url.replace("webcal://", "https://", 1)
    if _cache["url"] != url or time.time() - _cache["at"] > CACHE_SECONDS:
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            _cache.update(url=url, at=time.time(), events=parse_ics(resp.text[:3_000_000]))
        except requests.RequestException:
            _cache.update(url=url, at=time.time())  # on garde l'ancienne version ; nouvel essai dans 30 min
    return occurrences(_cache["events"], today or date.today(), days)


def countdowns(config, today=None):
    """Comptes à rebours à venir : [{title, date, days}] (les plus proches d'abord)."""
    today = today or date.today()
    out = []
    for c in config.get("countdowns") or []:
        try:
            when = date.fromisoformat(c.get("date", ""))
        except ValueError:
            continue
        if c.get("yearly") and when < today:
            when = when.replace(year=today.year if when.replace(year=today.year) >= today else today.year + 1)
        days = (when - today).days
        if days >= 0:
            out.append({"title": c.get("title", "")[:80], "date": when, "days": days, "emoji": c.get("emoji", "")})
    return sorted(out, key=lambda c: c["days"])
