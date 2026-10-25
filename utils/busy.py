"""
Le cadre est-il occupé ? (préparation ou encodage en cours, fête, partie de jeu)
Sert aux opérations qui redémarrent Pimmich (mise à jour automatique de la nuit) : elles attendent la fin.
En ligne de commande : `python -m utils.busy` affiche la raison et sort avec le code 1 si le cadre est occupé.
"""
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

WORK_FILE = Path("/tmp/pimmich_working.json")  # travail lourd en cours (mémoire vive)


@contextmanager
def working(label):
    """Marque un travail lourd en cours (préparation, encodage, animation, réduction) le temps du bloc."""
    try:
        WORK_FILE.write_text(json.dumps({"label": str(label)[:200], "pid": os.getpid(), "since": time.time()}), encoding="utf-8")
    except OSError:
        pass
    try:
        yield
    finally:
        try:
            WORK_FILE.unlink()
        except OSError:
            pass


def _alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError, TypeError):
        return False


def reasons(config=None):
    """Raisons pour lesquelles il ne faut pas redémarrer Pimmich maintenant (liste vide : libre)."""
    out = []
    try:
        work = json.loads(WORK_FILE.read_text(encoding="utf-8"))
        if _alive(work.get("pid")):
            out.append(f"travail en cours : {work.get('label')}")
    except (OSError, ValueError):
        pass
    try:
        from utils import family_game
        kind = family_game.phase(family_game.current())[0]
        if kind != "over":
            out.append("partie de jeu en cours" if kind != "bingo" else "bingo en cours")
    except Exception:
        pass
    try:
        from utils import party
        if config is None:
            from utils.config_manager import load_config
            config = load_config()
        if party.active(config):
            out.append("fête en cours")
    except Exception:
        pass
    return out


if __name__ == "__main__":
    found = reasons()
    if found:
        print(" ; ".join(found))
        sys.exit(1)
