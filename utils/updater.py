"""
Mises à jour depuis GitHub, avec retour automatique à la version précédente si la nouvelle ne démarre pas.

- `check()` : version installée, version disponible, liste des changements (titres des commits) ;
- avant une mise à jour, update_script.sh note la version en cours dans config/.update_state.json (« pending ») ;
- l'application, une fois démarrée et stable, marque la mise à jour comme réussie (`mark_healthy`) ;
- si elle plante en boucle juste après une mise à jour, start_pimmich.sh revient seul à la version notée.
"""
import json
import subprocess
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = BASE_DIR / "config" / ".update_state.json"
BRANCH = "main"


def _git(*args, timeout=60):
    try:
        result = subprocess.run(["git", *args], cwd=BASE_DIR, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def current_version():
    sha = _git("rev-parse", "--short", "HEAD")
    when = _git("log", "-1", "--format=%cI")
    return {"sha": sha, "date": when}


def check(fetch=True):
    """Version installée et mises à jour disponibles : {current, latest, behind, changes: [{sha, title, date}]}."""
    if fetch and _git("fetch", "--quiet", "origin", BRANCH, timeout=90) is None:
        return {"success": False, "current": current_version(), "error": "fetch"}
    log = _git("log", "--format=%h%x09%cI%x09%s", f"HEAD..origin/{BRANCH}", "-n", "40") or ""
    changes = []
    for line in log.splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3:
            changes.append({"sha": parts[0], "date": parts[1], "title": parts[2]})
    behind = _git("rev-list", "--count", f"HEAD..origin/{BRANCH}")
    return {"success": True, "current": current_version(), "latest": _git("rev-parse", "--short", f"origin/{BRANCH}"),
            "behind": int(behind) if behind and behind.isdigit() else len(changes), "changes": changes, "state": load_state()}


def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(**fields):
    state = dict(load_state(), **fields)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    return state


def mark_healthy():
    """Appelé quand l'application tourne depuis un moment : la mise à jour en cours est validée."""
    state = load_state()
    if state.get("status") == "pending":
        save_state(status="ok", confirmed=time.time())
        return True
    return False


def previous_version():
    """Version à laquelle revenir (celle d'avant la dernière mise à jour), sinon None."""
    return load_state().get("previous")
