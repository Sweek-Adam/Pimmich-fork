"""
Jeux de la famille sur le cadre : le cadre montre, chacun répond sur son téléphone (page /jeu).

Parties en manches (le cadre affiche le jeu) :
  - classique : l'année, le lieu ou l'auteur d'une photo ;
  - avant / après : laquelle des deux photos est la plus ancienne ;
  - zoom mystère, puzzle express : la photo se dévoile peu à peu, répondre tôt rapporte plus ;
  - ligne du temps : remettre 4 photos dans l'ordre ;
  - qui est-ce ? : la personne sur la photo floutée (personnes d'Immich) ;
  - légende la plus drôle, défi photo : chacun écrit une légende ou envoie une photo, puis tout le monde vote ;
  - mémoire : 6 photos à retenir, laquelle n'y était pas ;
  - le plus proche : des nombres à deviner sur la bibliothèque ;
  - mélange : un peu de tout.
Bingo souvenirs : une grille sur chaque téléphone pendant le diaporama habituel (le cadre n'est pas interrompu).

L'état tient dans un petit fichier en mémoire vive, partagé par l'interface (inscriptions, réponses) et le
diaporama (affichage). Le déroulé ne dépend que de l'heure de départ : chacun calcule où en est la partie.
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
PHOTOS_DIR = Path("/tmp/pimmich_game_photos")  # photos du défi (mémoire vive, effacées avec la partie)
LOBBY_TIMEOUT = 15 * 60       # partie abandonnée dans la salle d'attente
QUESTION_SECONDS = 25
REVEAL_SECONDS = 9
PODIUM_SECONDS = 25
MAX_PLAYERS = 20
BINGO_MINUTES = 45
LETTERS = "ABCD"

KINDS = ("year", "place", "who")
QUESTIONS = {
    "year": N_("En quelle année a été prise cette photo ?"), "place": N_("Où a été prise cette photo ?"),
    "who": N_("Qui a envoyé cette photo ?"), "older": N_("Laquelle est la plus ancienne ?"),
    "timeline": N_("Remettez les photos dans l'ordre, de la plus ancienne à la plus récente"),
    "person": N_("Qui est sur cette photo ?"), "memory": N_("Laquelle n'était pas dans les photos ?"),
    "closest": N_("Le plus proche gagne !"), "caption": N_("Écrivez la légende la plus drôle !"),
    "challenge": N_("Défi photo !"),
}
MODES = {
    "classique": N_("Où et quand ?"), "avant_apres": N_("Avant / après"), "zoom": N_("Zoom mystère"),
    "puzzle": N_("Puzzle express"), "ligne": N_("Ligne du temps"), "qui": N_("Qui est-ce ?"),
    "legende": N_("Légende la plus drôle"), "defi": N_("Défi photo"), "memoire": N_("Mémoire"),
    "proche": N_("Le plus proche"), "melange": N_("Mélange de tout"), "bingo": N_("Bingo souvenirs"),
}
STEPS = {  # étapes de chaque question : (nom, secondes)
    "memory": [("memorize", 12), ("question", 20), ("reveal", REVEAL_SECONDS)],
    "timeline": [("question", 40), ("reveal", 11)],
    "caption": [("question", 60), ("vote", 30), ("reveal", 12)],
    "challenge": [("question", 180), ("vote", 40), ("reveal", 14)],
}
CHALLENGES = [N_("Une photo avec quelqu'un qui porte du rouge"), N_("La plus belle grimace"), N_("Un selfie à trois ou plus"),
              N_("Quelque chose de rond"), N_("Une photo de vos chaussures"), N_("La pose de super-héros"),
              N_("Un animal (même en peluche)"), N_("Quelque chose qui commence par la lettre P"), N_("Votre plus beau sourire"),
              N_("Une photo prise de très haut ou de très bas"), N_("Le plat ou la boisson du moment"), N_("Une imitation d'une photo de famille"),
              N_("Quelque chose de bleu"), N_("Un câlin"), N_("Le plus beau reflet (miroir, vitre, eau)")]
BINGO_ITEMS = [N_("À la plage"), N_("Un gâteau"), N_("Des lunettes de soleil"), N_("Un chien"), N_("Un chat"), N_("La neige"),
               N_("Un bébé"), N_("Une fête d'anniversaire"), N_("La montagne"), N_("Un selfie"), N_("Un repas en famille"),
               N_("Une voiture"), N_("Un chapeau"), N_("Des fleurs"), N_("Un coucher de soleil"), N_("Un vélo"), N_("La mer"),
               N_("Une grimace"), N_("Un sapin de Noël"), N_("Une piscine"), N_("Un pique-nique"), N_("Un déguisement"),
               N_("Quelqu'un qui dort"), N_("Un bateau"), N_("Un monument"), N_("Une photo floue"), N_("Un pouce levé"),
               N_("Une glace"), N_("Des bougies"), N_("Un jardin"), N_("Une photo en noir et blanc"), N_("Un câlin")]


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


def steps(question):
    return STEPS.get(question["kind"], [("question", QUESTION_SECONDS), ("reveal", REVEAL_SECONDS)])


# --- Questions ---

def _photos(index, labels, people):
    """Photos utilisables : [{key, year, date, place, author, people}] (photos préparées seulement)."""
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
            when = datetime.fromisoformat(entry["date"]) if entry.get("date") else None
        except ValueError:
            when = None
        place = None
        if entry.get("lat") is not None:
            place = (geocode.cached(entry["lat"], entry["lon"]) or {}).get("city") or None
        author = labels.get(source) if members.is_member_source(source) else None
        out.append({"key": key, "year": when.year if when and when.year >= 1900 else None, "date": when.isoformat() if when else None,
                    "place": place, "author": author, "people": list((people or {}).get(key, []))})
    return out


def _choice(rng, answer, others):
    others = [o for o in others if o != answer]
    options = rng.sample(others, min(3, len(others))) + [answer]
    rng.shuffle(options)
    return options


def _classic(photos, rng, kinds):
    places = sorted({p["place"] for p in photos if p["place"]})
    authors = sorted({p["author"] for p in photos if p["author"]})
    pool = []
    for p in photos:
        if "year" in kinds and p["year"]:
            pool.append({"key": p["key"], "kind": "year", "answer": p["year"]})
        if "place" in kinds and p["place"] and len(places) >= 3:
            pool.append({"key": p["key"], "kind": "place", "answer": p["place"], "options": _choice(rng, p["place"], places)})
        if "who" in kinds and p["author"] and len(authors) >= 2:
            pool.append({"key": p["key"], "kind": "who", "answer": p["author"], "options": _choice(rng, p["author"], authors)})
    return pool


def _dated(photos):
    return [p for p in photos if p["date"]]


def _older(photos, rng, count):
    dated, out = _dated(photos), []
    for _ in range(count * 4):
        if len(dated) < 2 or len(out) >= count:
            break
        a, b = rng.sample(dated, 2)
        if abs(datetime.fromisoformat(a["date"]) - datetime.fromisoformat(b["date"])).days < 60:
            continue  # trop proches : impossible à deviner
        out.append({"keys": [a["key"], b["key"]], "kind": "older", "answer": "A" if a["date"] < b["date"] else "B", "options": ["A", "B"]})
    return out


def _timeline(photos, rng, count):
    dated, out = _dated(photos), []
    for _ in range(count * 4):
        if len(dated) < 4 or len(out) >= count:
            break
        chosen = rng.sample(dated, 4)
        days = sorted(datetime.fromisoformat(p["date"]) for p in chosen)
        if min((b - a).days for a, b in zip(days, days[1:])) < 30:
            continue
        order = "".join(LETTERS[i] for i, _p in sorted(enumerate(chosen), key=lambda item: item[1]["date"]))
        out.append({"keys": [p["key"] for p in chosen], "kind": "timeline", "answer": order})
    return out


def _person(photos, rng, count):
    names = sorted({n for p in photos for n in p["people"]})
    if len(names) < 2:
        return []
    alone = [p for p in photos if len(p["people"]) == 1]
    rng.shuffle(alone)
    return [{"key": p["key"], "kind": "person", "answer": p["people"][0], "options": _choice(rng, p["people"][0], names), "effect": "blur"}
            for p in alone[:count]]


def _memory(photos, rng, count):
    out = []
    for _ in range(count):
        if len(photos) < 7:
            break
        chosen = rng.sample(photos, 7)
        shown, extra = chosen[:6], chosen[6]
        options = rng.sample(shown, 3) + [extra]
        rng.shuffle(options)
        out.append({"keys": [p["key"] for p in shown], "kind": "memory", "choices": [p["key"] for p in options],
                    "options": list(LETTERS), "answer": LETTERS[options.index(extra)]})
    return out


def _closest(photos, rng, count):
    """Nombres à deviner sur la bibliothèque (photos d'une année, envois d'un membre...)."""
    pool = []
    by_year, by_author = {}, {}
    for p in photos:
        if p["year"]:
            by_year[p["year"]] = by_year.get(p["year"], 0) + 1
        if p["author"]:
            by_author[p["author"]] = by_author.get(p["author"], 0) + 1
    for year, n in by_year.items():
        if n >= 3:
            pool.append({"kind": "closest", "text": N_("Combien de photos de %(year)s sont sur le cadre ?"), "params": {"year": year}, "answer": n})
    for author, n in by_author.items():
        pool.append({"kind": "closest", "text": N_("Combien de photos ont été envoyées par %(name)s ?"), "params": {"name": author}, "answer": n})
    if photos:
        pool.append({"kind": "closest", "text": N_("Combien de photos y a-t-il sur le cadre ?"), "params": {}, "answer": len(photos)})
    months = {}
    for p in photos:
        if p["date"]:
            months[p["date"][5:7]] = months.get(p["date"][5:7], 0) + 1
    if months:
        month, n = max(months.items(), key=lambda m: m[1])
        pool.append({"kind": "closest", "text": N_("Combien de photos ont été prises en %(month)s (toutes années confondues) ?"),
                     "params": {"month": month}, "answer": n, "month": int(month)})
    rng.shuffle(pool)
    for question in pool:
        key = rng.choice(photos)["key"] if photos else None
        if key:
            question["key"] = key  # une photo en fond
    return pool[:count]


def _caption(photos, rng, count):
    chosen = rng.sample(photos, min(count, len(photos)))
    return [{"key": p["key"], "kind": "caption"} for p in chosen]


def _challenge(rng, count):
    prompts = rng.sample(CHALLENGES, min(count, len(CHALLENGES)))
    return [{"kind": "challenge", "text": text} for text in prompts]


def make_rounds(index, labels, rounds=6, rng=None, kinds=KINDS, mode="classique", people=None):
    """Questions de la partie selon le mode ; [] s'il n'y a pas assez de photos."""
    rng = rng or random.Random()
    photos = _photos(index, labels, people)
    builders = {
        "classique": lambda n: _classic(photos, rng, kinds), "zoom": lambda n: [dict(q, effect="zoom") for q in _classic(photos, rng, kinds)],
        "puzzle": lambda n: [dict(q, effect="puzzle") for q in _classic(photos, rng, kinds)], "avant_apres": lambda n: _older(photos, rng, n),
        "ligne": lambda n: _timeline(photos, rng, n), "qui": lambda n: _person(photos, rng, n), "legende": lambda n: _caption(photos, rng, n),
        "defi": lambda n: _challenge(rng, n), "memoire": lambda n: _memory(photos, rng, n), "proche": lambda n: _closest(photos, rng, n),
    }
    if mode == "melange":
        pool = []
        for key in ("classique", "zoom", "puzzle", "avant_apres", "ligne", "qui", "memoire", "proche"):
            found = builders[key](2)
            rng.shuffle(found)
            pool += found[:2]
    elif mode in builders:
        pool = builders[mode](rounds * 2)
    else:
        return []
    rng.shuffle(pool)
    chosen, used, years = [], set(), {}
    for question in pool:
        if question["kind"] in ("closest", "challenge"):
            ident = question.get("text", "") + str(question.get("params"))
        else:  # une photo, ou plusieurs (avant / après, ligne du temps, mémoire)
            ident = question.get("key") or tuple(question.get("keys", [])) + tuple(question.get("choices", []))
        if ident in used:
            continue
        if question["kind"] == "year" and years.get(question["answer"], 0) >= 2:
            continue  # des années variées
        chosen.append(question)
        used.add(ident)
        if question["kind"] == "year":
            years[question["answer"]] = years.get(question["answer"], 0) + 1
        if len(chosen) >= rounds:
            break
    for question in chosen:
        question["seed"] = rng.randint(0, 10 ** 6)  # position du zoom, ordre du puzzle
    return chosen


def points(question, value):
    """Points d'une réponse (sans bonus de vitesse ; les votes et « le plus proche » se calculent à part)."""
    if value is None:
        return 0
    if question["kind"] == "year":
        try:
            return max(0, 100 - 25 * abs(int(value) - int(question["answer"])))
        except (TypeError, ValueError):
            return 0
    if question["kind"] == "timeline":
        return sum(25 for a, b in zip(str(value), question["answer"]) if a == b)
    return 100 if value == question["answer"] else 0


def question_points(question, answers, times=None, votes=None):
    """Points de chaque joueur pour une question : {joueur: points}."""
    times, votes = times or {}, votes or {}
    kind = question["kind"]
    if kind in ("caption", "challenge"):
        out = {player: 0 for player in answers}
        for voter, target in votes.items():
            if target in out and target != voter:
                out[target] += 100
        return out
    if kind == "closest":
        try:
            ranked = sorted(answers, key=lambda p: abs(int(answers[p]) - int(question["answer"])))
        except (TypeError, ValueError):
            return {}
        scale = [100, 60, 30, 10]
        out, previous, rank = {}, None, -1
        for i, player in enumerate(ranked):
            gap = abs(int(answers[player]) - int(question["answer"]))
            if gap != previous:
                rank, previous = i, gap
            out[player] = scale[rank] if rank < len(scale) else 0
        return out
    out = {}
    for player, value in answers.items():
        base = points(question, value)
        if question.get("effect") and base:  # se dévoile peu à peu : répondre tôt rapporte plus
            base = round(base * (0.4 + 0.6 * float(times.get(player, 0))))
        out[player] = base
    return out


# --- Partie ---

def new_game(index, labels, rounds=6, now=None, rng=None, kinds=KINDS, mode="classique", people=None):
    """Ouvre la salle d'attente d'une nouvelle partie. Retourne l'état, ou None s'il n'y a pas assez de photos."""
    rng = rng or random.Random()
    if mode == "bingo":
        state = {"id": secrets.token_hex(4), "mode": "bingo", "created": now or time.time(), "until": (now or time.time()) + BINGO_MINUTES * 60,
                 "players": {}, "grids": {}, "checked": {}, "winners": [], "seed": rng.randint(0, 10 ** 6)}
    else:
        questions = make_rounds(index, labels, rounds, rng, kinds, mode, people)
        if len(questions) < min(2, rounds):
            return None
        state = {"id": secrets.token_hex(4), "mode": mode, "created": now or time.time(), "started": None, "questions": questions,
                 "players": {}, "answers": {}, "times": {}, "votes": {}}
    with _locked():
        _clear_photos()
        _save(state)
    return state


def _timeline_of(state):
    """[(début, question, étape, durée)] de toute la partie."""
    out, at = [], 0.0
    for number, question in enumerate(state["questions"]):
        for name, seconds in steps(question):
            out.append((at, number, name, seconds))
            at += seconds
    return out, at


def phase(state, now=None):
    """(étape, numéro de la question, secondes restantes) : lobby, memorize, question, vote, reveal, podium, bingo ou over."""
    now = now or time.time()
    if not state:
        return "over", None, 0
    if state.get("mode") == "bingo":
        return ("bingo", None, state["until"] - now) if now < state["until"] else ("over", None, 0)
    if not state.get("started"):
        return ("lobby", None, 0) if now - state["created"] < LOBBY_TIMEOUT else ("over", None, 0)
    elapsed = now - state["started"]
    timeline, total = _timeline_of(state)
    for start, number, name, seconds in timeline:
        if start <= elapsed < start + seconds:
            return name, number, start + seconds - elapsed
    left = total + PODIUM_SECONDS - elapsed
    return ("podium", None, left) if left > 0 else ("over", None, 0)


def step_duration(state, number, name):
    return dict(steps(state["questions"][number])).get(name, QUESTION_SECONDS)


def current():
    return _load()


def running(now=None):
    """Une partie en manches est ouverte (le cadre affiche le jeu à la place des photos) ?"""
    return phase(_load(), now)[0] not in ("over", "bingo")


def bingo_active(now=None):
    return phase(_load(), now)[0] == "bingo"


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
        if state.get("mode") == "bingo" and player not in state["grids"]:
            rng = random.Random(f"{state['seed']}:{player}")
            state["grids"][player] = rng.sample(range(len(BINGO_ITEMS)), 9)
            state["checked"][player] = []
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
        kind, number, left = phase(state, now)
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
        elif question["kind"] == "closest":
            try:
                value = int(value)
            except (TypeError, ValueError):
                return False
            if not 0 <= value <= 10 ** 7:
                return False
        elif question["kind"] == "timeline":
            value = str(value or "").upper()
            if sorted(value) != list(LETTERS):
                return False
        elif question["kind"] == "caption":
            value = " ".join(str(value or "").split())[:90]
            if not value:
                return False
        elif question["kind"] == "challenge":
            return False  # une photo : voir answer_photo
        elif value not in question.get("options", []):
            return False
        answers = state["answers"].setdefault(str(number), {})
        if player in answers:
            return False
        answers[player] = value
        state.setdefault("times", {}).setdefault(str(number), {})[player] = round(max(0.0, left) / step_duration(state, number, "question"), 3)
        _save(state)
    return True


def answer_photo(player, data, now=None):
    """Photo envoyée pour le défi en cours (une seule fois, réduite). Retourne True si elle est prise en compte."""
    import io
    from PIL import Image, ImageOps
    with _locked():
        state = _load()
        kind, number, _left = phase(state, now)
        if kind != "question" or player not in (state or {}).get("players", {}) or state["questions"][number]["kind"] != "challenge":
            return False
        answers = state["answers"].setdefault(str(number), {})
        if player in answers:
            return False
        try:
            with Image.open(io.BytesIO(data)) as image:
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail((1600, 1600))
                PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
                name = f"{state['id']}_{number}_{player}.jpg"
                image.save(PHOTOS_DIR / name, quality=85)
        except Exception:
            return False
        answers[player] = name
        _save(state)
    return True


def entries(state, number):
    """Propositions à départager (légendes ou photos), dans un ordre fixe : [(numéro affiché, joueur, valeur)]."""
    answers = state["answers"].get(str(number), {})
    players = sorted(answers, key=lambda p: random.Random(f"{state['id']}:{number}:{p}").random())
    return [(i + 1, player, answers[player]) for i, player in enumerate(players)]


def vote(player, choice, now=None):
    """Vote pour une proposition (pas la sienne). Retourne True si le vote est pris en compte."""
    with _locked():
        state = _load()
        kind, number, _left = phase(state, now)
        if kind != "vote" or player not in (state or {}).get("players", {}):
            return False
        target = next((p for n, p, _v in entries(state, number) if str(n) == str(choice)), None)
        if not target or target == player:
            return False
        votes = state.setdefault("votes", {}).setdefault(str(number), {})
        if player in votes:
            return False
        votes[player] = target
        _save(state)
    return True


def round_points(state, number):
    key = str(number)
    return question_points(state["questions"][number], state["answers"].get(key, {}), state.get("times", {}).get(key), state.get("votes", {}).get(key))


def scores(state, upto=None):
    """Classement : [(prénom, points, identifiant)] des questions jusqu'à `upto` (comprise ; toutes par défaut)."""
    total = {player: 0 for player in state["players"]}
    for number in range(len(state.get("questions", []))):
        if upto is not None and number > upto:
            break
        for player, gained in round_points(state, number).items():
            if player in total:
                total[player] += gained
    return sorted(((state["players"][p], s, p) for p, s in total.items()), key=lambda x: -x[1])


def check_bingo(player, cell, now=None):
    """Bingo : coche (ou décoche) une case. Retourne {checked, bingo} ; bingo = nouvelle ligne complète."""
    lines = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]
    with _locked():
        state = _load()
        if phase(state, now)[0] != "bingo" or player not in state["players"]:
            return None
        try:
            cell = int(cell)
        except (TypeError, ValueError):
            return None
        if not 0 <= cell < 9:
            return None
        checked = set(state["checked"].get(player, []))
        checked.symmetric_difference_update({cell})
        state["checked"][player] = sorted(checked)
        done = [line for line in lines if set(line) <= checked]
        won = bool(done) and not any(w["player"] == player for w in state["winners"])
        if won:
            state["winners"].append({"player": player, "name": state["players"][player], "at": now or time.time()})
        _save(state)
    return {"checked": sorted(checked), "bingo": won}


def _clear_photos():
    if PHOTOS_DIR.is_dir():
        for f in PHOTOS_DIR.iterdir():
            f.unlink(missing_ok=True)


def stop():
    with _locked():
        STATE_FILE.unlink(missing_ok=True)
        _clear_photos()


def question_text(question, translate=lambda s, **k: s % k if k else s):
    if question["kind"] == "closest":
        params = dict(question.get("params") or {})
        if question.get("month"):
            months = [N_("janvier"), N_("février"), N_("mars"), N_("avril"), N_("mai"), N_("juin"), N_("juillet"), N_("août"),
                      N_("septembre"), N_("octobre"), N_("novembre"), N_("décembre")]
            params["month"] = translate(months[question["month"] - 1])
        return translate(question["text"], **params)
    if question["kind"] == "challenge":
        return translate(question["text"])
    return translate(QUESTIONS[question["kind"]])


def public_view(state, player=None, now=None, translate=lambda s, **k: s % k if k else s):
    """Ce que voit un joueur sur son téléphone (jamais la bonne réponse avant le dévoilement)."""
    kind, number, left = phase(state, now)
    view = {"phase": kind, "left": round(left), "players": sorted(state["players"].values()) if state else [],
            "me": (state or {}).get("players", {}).get(player), "total": len((state or {}).get("questions", [])),
            "mode": (state or {}).get("mode", "classique")}
    if not state:
        return view
    if kind == "bingo":
        cells = state["grids"].get(player, [])
        view.update(grid=[translate(BINGO_ITEMS[i]) for i in cells], checked=state["checked"].get(player, []),
                    winners=[w["name"] for w in state["winners"]], minutes=round(left / 60))
        return view
    if number is not None:
        question = state["questions"][number]
        answers = state["answers"].get(str(number), {})
        view.update(number=number + 1, kind=question["kind"], question=question_text(question, translate), options=question.get("options"),
                    answered=player in answers, answered_count=len(answers))
        if kind == "vote":
            view["entries"] = [{"n": n, "text": value if question["kind"] == "caption" else None, "mine": p == player}
                               for n, p, value in entries(state, number)]
            view["voted"] = player in state.get("votes", {}).get(str(number), {})
        if kind == "reveal":
            gained = round_points(state, number)
            mine = answers.get(player)
            view.update(answer=question.get("answer"), mine=mine if question["kind"] != "challenge" else None, gained=gained.get(player, 0))
            if question["kind"] in ("caption", "challenge"):
                ranked = sorted(entries(state, number), key=lambda e: -gained.get(e[1], 0))
                view["best"] = [{"name": state["players"].get(p, "?"), "text": v if question["kind"] == "caption" else None,
                                 "votes": gained.get(p, 0) // 100} for _n, p, v in ranked[:3]]
    if kind in ("reveal", "podium"):
        view["ranking"] = [{"name": n, "score": s} for n, s, _p in scores(state, number)]
    return view
