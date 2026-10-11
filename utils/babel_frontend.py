"""
Textes à traduire de la nouvelle interface (frontend/src, fichiers .vue et .ts) : appels t("…") ou t('…').
Sert à pybabel (babel.cfg, section [extractors]) et à /api/i18n, qui ne renvoie que les traductions utiles à l'interface.
"""
import re
from functools import lru_cache
from pathlib import Path

FRONTEND_SRC = Path(__file__).resolve().parent.parent / "frontend" / "src"
CALL = re.compile(r"""(?<![\w$.])t\(\s*(?P<q>["'])(?P<text>(?:\\.|(?!(?P=q)).)*)(?P=q)""", re.S)


def _unescape(text):
    return re.sub(r"\\(.)", r"\1", text)


def messages_in(source):
    """[(numéro de ligne, texte)] des appels t() d'un fichier source."""
    found = []
    for match in CALL.finditer(source):
        line = source.count("\n", 0, match.start()) + 1
        found.append((line, _unescape(match.group("text"))))
    return found


def extract(fileobj, keywords, comment_tags, options):
    """Extracteur pour pybabel : (ligne, fonction, message, commentaires) ; fonction None = message tel quel."""
    source = fileobj.read().decode(options.get("encoding", "utf-8"))
    for line, text in messages_in(source):
        yield line, None, text, []


@lru_cache(maxsize=1)
def frontend_msgids():
    """Tous les textes de la nouvelle interface (lus une fois)."""
    found = set()
    for path in sorted(FRONTEND_SRC.rglob("*")) if FRONTEND_SRC.is_dir() else []:
        if path.suffix in (".vue", ".ts"):
            found.update(text for _line, text in messages_in(path.read_text(encoding="utf-8")))
    return frozenset(found)
