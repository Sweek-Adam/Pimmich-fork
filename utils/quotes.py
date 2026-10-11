"""
Citation du jour : une citation ou un proverbe (dans la langue du cadre), ou un « mot de la famille » ajouté dans
l'interface. Une image est préparée chaque jour dans la source « citation » : le diaporama la montre comme une photo,
environ une fois par tour. Tout est sur le cadre : aucun service en ligne.
"""
import hashlib
import json
from datetime import date
from pathlib import Path

from utils.message_renderer import N_, render_message

BASE_DIR = Path(__file__).resolve().parent.parent
QUOTES_FILE = BASE_DIR / "resources" / "quotes.json"
SOURCE = "citation"
OUTPUT_DIR = BASE_DIR / "static" / "prepared" / SOURCE
STYLES = ("carte", "nuit", "pastel", "ardoise", "minimal", "lettre")
MODES = ("all", "builtin", "family")
TITLES = {"builtin": N_("Citation du jour"), "family": N_("Le mot de la famille")}
PROVERB = N_("Proverbe")


def builtin(language):
    try:
        data = json.loads(QUOTES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [{"text": t, "author": a, "kind": "builtin"} for t, a in data.get(language) or data.get("fr", [])]


def family(config):
    return [{"text": str(q.get("text", "")).strip(), "author": str(q.get("author", "")).strip(), "kind": "family"}
            for q in config.get("quotes_family") or [] if str(q.get("text", "")).strip()]


def pool(config):
    mode = config.get("quote_mode", "all")
    language = (config.get("language") or "fr")[:2]
    quotes = []
    if mode in ("all", "family"):
        quotes += family(config)
    if mode in ("all", "builtin") or not quotes:
        quotes += builtin(language)
    return quotes


def of_the_day(config, day=None):
    """Citation du jour : la même toute la journée, une autre le lendemain (et les mots de la famille reviennent souvent)."""
    quotes = pool(config)
    if not quotes:
        return None
    day = day or date.today()
    family_quotes = [q for q in quotes if q["kind"] == "family"]
    if family_quotes and len(family_quotes) < len(quotes) and day.toordinal() % 3 == 0:
        quotes = family_quotes  # un jour sur trois : un mot de la famille
    index = int(hashlib.sha1(f"{day.isoformat()}|{len(quotes)}".encode()).hexdigest(), 16) % len(quotes)
    return quotes[index]


def style_of_the_day(config, day=None):
    chosen = config.get("quote_style", "auto")
    if chosen in STYLES:
        return chosen
    day = day or date.today()
    return STYLES[day.toordinal() % len(STYLES)]


def render(config, width, height, translate=lambda text: text, day=None):
    """Image de la citation du jour (Pillow), ou None s'il n'y a rien à montrer."""
    quote = of_the_day(config, day)
    if quote is None:
        return None
    author = quote["author"] or (translate(PROVERB) if quote["kind"] == "builtin" else "")
    language = (config.get("language") or "fr")[:2]
    text = {"fr": f"« {quote['text']} »", "ja": f"「{quote['text']}」", "de": f"„{quote['text']}“"}.get(language, f"“{quote['text']}”")
    return render_message(translate(TITLES[quote["kind"]]), text, author,  # le tiret de la signature est ajouté au rendu
                          style_of_the_day(config, day), width, height, seed=f"{day or date.today()}|{quote['text']}")


def refresh(config, translate=lambda text: text, day=None):
    """Prépare l'image du jour (source « citation ») ; renvoie son chemin, ou None (fonction désactivée)."""
    target = OUTPUT_DIR / "citation.jpg"
    if not config.get("quote_enabled"):
        if target.exists():
            target.unlink()
        return None
    width, height = int(config.get("display_width", 1920)), int(config.get("display_height", 1080))
    image = render(config, width, height, translate, day)
    if image is None:
        return None
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT_DIR / ".citation.jpg"
    image.save(tmp, "JPEG", quality=90)
    tmp.replace(target)
    return target
