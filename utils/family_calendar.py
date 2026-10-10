"""
Agenda familial et comptes à rebours, affichés sur le cadre (diapositive « Cette semaine »).

- Agenda : adresse iCal secrète d'un agenda (Google Agenda : Paramètres > « Adresse secrète au format iCal »),
  lue sans compte ni connexion ; événements récurrents annuels (anniversaires) et hebdomadaires gérés ;
- comptes à rebours : événements saisis dans l'interface (vacances, mariage...).
"""
import re
import time
from datetime import date, datetime, timedelta

import requests

CACHE_SECONDS = 30 * 60
_cache = {"url": None, "at": 0, "events": []}


def _unfold(text):
    """Lignes iCal repliées (continuations commençant par un espace) -> lignes complètes."""
    return re.sub(r"\r?\n[ \t]", "", text).splitlines()


def _parse_date(value):
    value = value.strip()
    try:
        if "T" in value:
            return datetime.strptime(value[:15], "%Y%m%dT%H%M%S"), False
        return datetime.strptime(value[:8], "%Y%m%d"), True
    except ValueError:
        return None, True


def _unescape(text):
    return text.replace("\\,", ",").replace("\\;", ";").replace("\\n", " ").replace("\\N", " ").replace("\\\\", "\\").strip()


def parse_ics(text):
    """Événements d'un fichier iCal : [{title, start (datetime), all_day, rrule}]."""
    events, current = [], None
    for line in _unfold(text):
        if line == "BEGIN:VEVENT":
            current = {}
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
    return events


def occurrences(events, start, days):
    """Occurrences entre `start` (date) et `start + days` : [{title, when (datetime), all_day}], dans l'ordre."""
    end = start + timedelta(days=days)
    found = []
    for e in events:
        first, rule = e["start"], e.get("rrule", "")
        candidates = []
        if "FREQ=YEARLY" in rule:
            for year in (start.year, start.year + 1):
                try:
                    candidates.append(first.replace(year=year))
                except ValueError:  # 29 février
                    candidates.append(first.replace(year=year, day=28))
        elif "FREQ=WEEKLY" in rule:
            delta = (start - first.date()).days
            if delta > 0:
                first = first + timedelta(days=7 * (delta // 7))
            candidates = [first + timedelta(days=7 * k) for k in range(0, days // 7 + 2)]
        else:
            candidates = [first]
        for when in candidates:
            if when >= datetime.combine(first.date(), datetime.min.time()) and start <= when.date() < end:
                found.append({"title": e["title"], "when": when, "all_day": e.get("all_day", True)})
    return sorted(found, key=lambda o: o["when"])


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
