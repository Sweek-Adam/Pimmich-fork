"""
Sauvegarde complète automatique (avec les photos), une fois par semaine sur un disque USB ou un NAS.

Elle a lieu le jour choisi, quand l'écran est éteint (nuit) ; si le cadre n'a pas pu la faire ce jour-là (éteint,
support absent), elle est rattrapée dès que possible. Seules les dernières sauvegardes automatiques sont gardées
(les sauvegardes faites à la main ne sont jamais effacées).
"""
import json
import time
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = PROJECT_DIR / "cache" / "auto_backup.json"
PREFIX = "pimmich-complet-auto-"
WEEK = 7 * 24 * 3600
DEFAULTS = {"enabled": False, "storage": "", "weekday": 6, "keep": 3}


def settings(config):
    data = dict(DEFAULTS, **(config.get("auto_full_backup") or {}))
    data["weekday"] = min(6, max(0, int(data.get("weekday", 6))))
    data["keep"] = min(20, max(1, int(data.get("keep", 3))))
    return data


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def due(config, state, display_active, now=None):
    """Vrai s'il est temps de faire la sauvegarde de la semaine (jour choisi ou rattrapage), écran éteint."""
    wanted = settings(config)
    if not wanted["enabled"] or not wanted["storage"] or display_active:
        return False
    now = now or datetime.now()
    last = float(state.get("last_success") or 0)
    if now.timestamp() - last >= WEEK + 24 * 3600:
        return True  # semaine manquée : rattrapage
    tried_today = state.get("last_try_day") == now.strftime("%Y-%m-%d")
    return now.weekday() == wanted["weekday"] and now.timestamp() - last > 24 * 3600 and not tried_today


def target_name(now=None):
    return f"{PREFIX}{(now or datetime.now()):%Y-%m-%d-%H%M}.zip"


def prune(folder, keep):
    """Efface les plus anciennes sauvegardes automatiques au-delà de keep ; retourne les noms effacés."""
    folder = Path(folder)
    autos = sorted(folder.glob(f"{PREFIX}*.zip")) if folder.is_dir() else []
    removed = []
    for path in autos[:-keep] if len(autos) > keep else []:
        try:
            path.unlink()
            removed.append(path.name)
        except OSError:
            pass
    return removed


def photos_size(photos_dir):
    total = 0
    for path in Path(photos_dir).rglob("*"):
        try:
            if path.is_file():
                total += path.stat().st_size
        except OSError:
            pass
    return total


def note(state, ok, message, now=None):
    now = now or datetime.now()
    state.update(last_try=time.time(), last_try_day=now.strftime("%Y-%m-%d"), ok=bool(ok), message=str(message)[:300])
    if ok:
        state["last_success"] = time.time()
    return state
