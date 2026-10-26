"""
Occasions de la famille et du calendrier : anniversaires (avec prénom et âge), anniversaires de mariage, naissances,
rentrée, Saint-Valentin, fête des mères et des pères (à la date du pays). Les dispositions à thème correspondantes
n'apparaissent qu'à ces moments-là (plus souvent ce jour-là).
"""
from datetime import date, timedelta

KINDS = ("birthday", "wedding", "birth")
BIRTHDAY_DAYS = 1        # la veille, le jour J et le lendemain
NEWBORN_DAYS = 45        # « Bienvenue » pendant six semaines après la naissance
COUNTRY_OF_LANGUAGE = {"fr": "FR", "en": "US", "de": "DE", "es": "ES", "ja": "JP"}
THEMES = ("anniversaire_perso", "mariage", "naissance", "rentree", "saint_valentin", "fete_meres", "fete_peres")


def _sunday(year, month, nth):
    """n-ième dimanche du mois (nth négatif : en partant de la fin)."""
    if nth > 0:
        first = date(year, month, 1)
        return first + timedelta(days=(6 - first.weekday()) % 7 + 7 * (nth - 1))
    last = (date(year, month % 12 + 1, 1) if month < 12 else date(year + 1, 1, 1)) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - 6) % 7 + 7 * (-nth - 1))


def country(config):
    return (config.get("country") or COUNTRY_OF_LANGUAGE.get((config.get("language") or "fr")[:2], "FR")).upper()


def easter(year):
    """Date de Pâques (algorithme de Meeus/Jones/Butcher, calendrier grégorien)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def mothers_day(year, where="FR"):
    if where == "FR":
        day = _sunday(year, 5, -1)
        return day + timedelta(days=7) if day == easter(year) + timedelta(days=49) else day  # pas le jour de la Pentecôte
    if where == "ES":
        return _sunday(year, 5, 1)
    return _sunday(year, 5, 2)  # États-Unis, Allemagne, Japon...


def fathers_day(year, where="FR"):
    if where == "DE":
        return easter(year) + timedelta(days=39)  # Vatertag : jeudi de l'Ascension
    if where == "ES":
        return date(year, 3, 19)  # San José
    return _sunday(year, 6, 3)


def _parse(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def family_dates(config):
    """Dates de la famille valides : [{kind, name, date}]."""
    found = []
    for item in config.get("family_dates") or []:
        day = _parse(item.get("date"))
        if item.get("kind") in KINDS and day and str(item.get("name", "")).strip():
            found.append({"kind": item["kind"], "name": str(item["name"]).strip()[:60], "date": day})
    return found


def _this_year(day, today):
    """Date anniversaire la plus proche d'aujourd'hui (cette année, ou l'an dernier / prochain autour du 1er janvier)."""
    candidates = []
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            candidates.append(day.replace(year=year))
        except ValueError:  # 29 février
            candidates.append(date(year, 3, 1))
    return min(candidates, key=lambda d: abs((d - today).days))


def active(config, today=None):
    """Occasions du moment : [{theme, name, years, date}], la plus proche du jour J d'abord."""
    today = today or date.today()
    found = []
    for item in family_dates(config):
        if item["kind"] == "birth":
            age = (today - item["date"]).days
            if 0 <= age <= NEWBORN_DAYS:
                found.append({"theme": "naissance", "name": item["name"], "years": 0, "date": item["date"], "gap": age})
            continue
        when = _this_year(item["date"], today)
        gap = abs((when - today).days)
        if gap <= BIRTHDAY_DAYS and when.year >= item["date"].year:
            theme = "anniversaire_perso" if item["kind"] == "birthday" else "mariage"
            found.append({"theme": theme, "name": item["name"], "years": when.year - item["date"].year, "date": when, "gap": gap})
    where = country(config)
    calendar = {"saint_valentin": (date(today.year, 2, 14), 7), "rentree": (date(today.year, 9, 1), 10),
                "fete_meres": (mothers_day(today.year, where), 6), "fete_peres": (fathers_day(today.year, where), 6)}
    for theme, (day, before) in calendar.items():
        if theme == "rentree":
            if day <= today <= day + timedelta(days=before):  # les premiers jours de septembre
                found.append({"theme": theme, "name": "", "years": 0, "date": day, "gap": (today - day).days})
        elif day - timedelta(days=before) <= today <= day:  # la semaine qui précède, jusqu'au jour J
            found.append({"theme": theme, "name": "", "years": 0, "date": day, "gap": (day - today).days})
    return sorted(found, key=lambda o: o["gap"])


def for_theme(theme, config=None, today=None):
    """L'occasion du moment pour une disposition (ex. l'anniversaire de qui ?), sinon None."""
    if config is None:
        from utils.config_manager import load_config
        config = load_config()
    return next((o for o in active(config, today) if o["theme"] == theme), None)


def in_season(theme, today=None, config=None):
    return for_theme(theme, config, today) is not None


def upcoming(config, today=None, days=60):
    """Prochaines occasions de la famille : [{kind, name, date, years}] dans les `days` jours."""
    today = today or date.today()
    found = []
    for item in family_dates(config):
        if item["kind"] == "birth":
            continue
        for year in (today.year, today.year + 1):
            try:
                when = item["date"].replace(year=year)
            except ValueError:
                when = date(year, 3, 1)
            if today <= when <= today + timedelta(days=days) and when.year >= item["date"].year:
                found.append({"kind": item["kind"], "name": item["name"], "date": when, "years": when.year - item["date"].year})
                break
    return sorted(found, key=lambda o: o["date"])


REMIND_DAYS = 3


def reminders(config, today=None, days_before=REMIND_DAYS):
    """Occasions à rappeler aujourd'hui : [{kind, name, date, years, delta}] (delta = jours restants : days_before ou 0)."""
    today = today or date.today()
    return [dict(o, delta=(o["date"] - today).days) for o in upcoming(config, today, days_before)
            if (o["date"] - today).days in (0, days_before)]
