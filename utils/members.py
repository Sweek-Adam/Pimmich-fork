"""
Un compte par membre de la famille : les photos envoyées depuis l'interface par un compte vont dans sa propre source
(« Envois de Léa »), qui s'enrichit au fil des envois ; chacun retrouve et gère ses envois et ses playlists.
"""
import re
import unicodedata
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PREFIX = "compte_"


def slug(username):
    text = unicodedata.normalize("NFKD", str(username or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")[:30] or "membre"


def source_for(username):
    """Source des envois d'un compte (ex. « compte_lea »)."""
    return PREFIX + slug(username)


def is_member_source(source):
    return str(source).startswith(PREFIX)


def label(source, usernames=()):
    """« Envois de Léa » (le nom du compte retrouvé tel qu'il a été saisi)."""
    if not is_member_source(source):
        return source
    name = next((u for u in usernames if source_for(u) == source), source[len(PREFIX):].replace("_", " ").title())
    return name


def sources():
    """Sources de comptes existantes."""
    folder = BASE_DIR / "static" / "photos"
    return sorted(p.name for p in folder.iterdir() if p.is_dir() and is_member_source(p.name)) if folder.is_dir() else []


def unique_name(folder, filename):
    """Nom libre dans le dossier (les envois s'accumulent : jamais d'écrasement)."""
    path = Path(folder) / filename
    stem, ext, n = path.stem, path.suffix, 2
    while path.exists():
        path = Path(folder) / f"{stem}_{n}{ext}"
        n += 1
    return path
