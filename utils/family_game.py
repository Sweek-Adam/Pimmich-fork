"""
Jeu « Où et quand ? » : le cadre montre une photo de la famille, chacun répond sur son téléphone (page /jeu),
puis le cadre dévoile la réponse et les points. Questions : l'année (photos datées), le lieu (photos dont le lieu
est connu) et l'auteur (envois des comptes de la famille).

L'état de la partie tient dans un petit fichier en mémoire vive, partagé par l'interface (inscriptions, réponses)
et le diaporama (affichage). Le déroulé ne dépend que de l'heure de départ : chacun calcule où en est la partie.
"""
import fcntl
import json
import os
import random
import secrets
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from utils.message_renderer import N_

STATE_FILE = Path("/tmp/pimmich_game.json")
LOCK_FILE = Path("/tmp/pimmich_game.lock")
LOBBY_TIMEOUT = 15 * 60       # partie abandonnée dans la salle d'attente
QUESTION_SECONDS = 25
REVEAL_SECONDS = 9
PODIUM_SECONDS = 25
MAX_PLAYERS = 20
KINDS = ("year", "place", "who")
QUESTIONS = {"year": N_("En quelle année a été prise cette photo ?"), "place": N_("Où a été prise cette photo ?"),
             "who": N_("Qui a envoyé cette photo ?")}


@contextmanager
def _locked():
    LOCK_FILE.touch(exist_ok=True)
    with open(LOCK_FILE, "r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _load():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _save(state):
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, STATE_FILE)


# --- Questions ---

def _candidates(index, labels):
    """Photos utilisables : [(clé, date, lieu, auteur)] (photos préparées seulement)."""
    from utils import geocode, members
    from utils.photo_index import PREPARED_DIR, SKIP_SOURCES
    out = []
    for key, entry in index.items():
        source = key.split("/", 1)[0]
        if source in SKIP_SOURCES or not key.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        if not (PREPARED_DIR / key).exists():
            continue
        try:
            year = datetime.fromisoformat(entry["date"]).year if entry.get("date") else None
        except ValueError:
            year = None
        place = None
        if entry.get("lat") is not None:
            found = geocode.cached(entry["lat"], entry["lon"])
            place = (found or {}).get("city") or None
        author = labels.get(source) if members.is_member_source(source) else None
        out.append((key, year, place, author))
    return out


def make_rounds(index, labels, rounds=6, rng=None, kinds=KINDS):
    """Questions de la partie : [{key, kind, answer, options}] ; [] s'il n'y a pas assez de photos."""
    rng = rng or random.Random()
    photos = _candidates(index, labels)
    places = sorted({p for _k, _y, p, _a in photos if p})
    authors = sorted({a for _k, _y, _p, a in photos if a})
    pool = []
    for key, year, place, author in photos:
        if "year" in kinds and year and year >= 1900:
            pool.append({"key": key, "kind": "year", "answer": year})
        if "place" in kinds and place and len(places) >= 3:
            pool.append({"key": key, "kind": "place", "answer": place})
        if "who" in kinds and author and len(authors) >= 2:
            pool.append({"key": key, "kind": "who", "answer": author})
    rng.shuffle(pool)
    chosen, used_keys, used_years = [], set(), {}
    for question in sorted(pool, key=lambda q: used_years.get(q["answer"], 0) if q["kind"] == "year" else 0):
        if question["key"] in used_keys:
            continue
        if question["kind"] == "year" and used_years.get(question["answer"], 0) >= 2:
            continue  # des années variées
        if question["kind"] in ("place", "who"):
            others = [v for v in (places if question["kind"] == "place" else authors) if v != question["answer"]]
            question["options"] = rng.sample(others, min(3, len(others))) + [question["answer"]]
            rng.shuffle(question["options"])
        chosen.append(question)
        used_keys.add(question["key"])
        if question["kind"] == "year":
            used_years[question["answer"]] = used_years.get(question["answer"], 0) + 1
        if len(chosen) >= rounds:
            break
    rng.shuffle(chosen)
    return chosen


def points(question, value):
    """Points d'une réponse : l'année exacte vaut 100, puis 25 de moins par année d'écart ; un choix juste vaut 100."""
    if value is None:
        return 0
    if question["kind"] == "year":
        try:
            return max(0, 100 - 25 * abs(int(value) - int(question["answer"])))
        except (TypeError, ValueError):
            return 0
    return 100 if value == question["answer"] else 0


# --- Partie ---

def new_game(index, labels, rounds=6, now=None, rng=None, kinds=KINDS):
    """Ouvre la salle d'attente d'une nouvelle partie. Retourne l'état, ou None s'il n'y a pas assez de photos."""
    questions = make_rounds(index, labels, rounds, rng, kinds)
    if len(questions) < 2:
        return None
    state = {"id": secrets.token_hex(4), "created": now or time.time(), "started": None, "questions": questions,
             "players": {}, "answers": {}}
    with _locked():
        _save(state)
    return state


def phase(state, now=None):
    """(phase, numéro de la question, secondes restantes) : lobby, question, reveal, podium ou over."""
    now = now or time.time()
    if not state:
        return "over", None, 0
    if not state.get("started"):
        return ("lobby", None, 0) if now - state["created"] < LOBBY_TIMEOUT else ("over", None, 0)
    elapsed = now - state["started"]
    step = QUESTION_SECONDS + REVEAL_SECONDS
    number = int(elapsed // step)
    if number < len(state["questions"]):
        within = elapsed - number * step
        if within < QUESTION_SECONDS:
            return "question", number, QUESTION_SECONDS - within
        return "reveal", number, step - within
    left = len(state["questions"]) * step + PODIUM_SECONDS - elapsed
    return ("podium", None, left) if left > 0 else ("over", None, 0)


def current():
    return _load()


def running(now=None):
    return phase(_load(), now)[0] != "over"


def join(name, player=None):
    """Inscription (ou changement de prénom) : retourne l'identifiant du joueur, ou None (partie absente, pleine)."""
    name = " ".join(str(name or "").split())[:24]
    if not name:
        return None
    with _locked():
        state = _load()
        if phase(state)[0] == "over":
            return None
        if player not in state["players"]:
            if len(state["players"]) >= MAX_PLAYERS:
                return None
            player = secrets.token_hex(6)
        state["players"][player] = name
        _save(state)
    return player


def start(now=None):
    with _locked():
        state = _load()
        if phase(state, now)[0] != "lobby" or not state["players"]:
            return False
        state["started"] = now or time.time()
        _save(state)
    return True


def answer(player, value, now=None):
    """Réponse à la question en cours (une seule fois). Retourne True si elle est prise en compte."""
    with _locked():
        state = _load()
        kind, number, _left = phase(state, now)
        if kind != "question" or player not in (state or {}).get("players", {}):
            return False
        question = state["questions"][number]
        if question["kind"] == "year":
            try:
                value = int(value)
            except (TypeError, ValueError):
                return False
            if not 1900 <= value <= datetime.now().year:
                return False
        elif value not in question.get("options", []):
            return False
        answers = state["answers"].setdefault(str(number), {})
        if player in answers:
            return False
        answers[player] = value
        _save(state)
    return True


def scores(state, upto=None):
    """Classement : [(prénom, points, identifiant)] des questions jusqu'à `upto` (comprise ; toutes par défaut)."""
    total = {player: 0 for player in state["players"]}
    for number, question in enumerate(state["questions"]):
        if upto is not None and number > upto:
            break
        for player, value in state["answers"].get(str(number), {}).items():
            if player in total:
                total[player] += points(question, value)
    return sorted(((state["players"][p], s, p) for p, s in total.items()), key=lambda x: -x[1])


def stop():
    with _locked():
        STATE_FILE.unlink(missing_ok=True)


def public_view(state, player=None, now=None):
    """Ce que voit un joueur sur son téléphone (jamais la bonne réponse avant le dévoilement)."""
    kind, number, left = phase(state, now)
    view = {"phase": kind, "left": round(left), "players": sorted(state["players"].values()) if state else [],
            "me": (state or {}).get("players", {}).get(player), "total": len(state["questions"]) if state else 0}
    if not state:
        return view
    if number is not None:
        question = state["questions"][number]
        view.update(number=number + 1, kind=question["kind"], options=question.get("options"),
                    answered=player in state["answers"].get(str(number), {}),
                    answered_count=len(state["answers"].get(str(number), {})))
        if kind == "reveal":
            mine = state["answers"].get(str(number), {}).get(player)
            view.update(answer=question["answer"], mine=mine, gained=points(question, mine) if player else 0)
    if kind in ("reveal", "podium"):
        view["ranking"] = [{"name": n, "score": s} for n, s, _p in scores(state, number)]
    return view
