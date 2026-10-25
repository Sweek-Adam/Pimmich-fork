"""Jeu « Où et quand ? » : questions, déroulé, réponses, points, page /jeu et écran du cadre."""
import random
import time
from pathlib import Path

import pytest
from PIL import Image

from utils import family_game as game

SAME = {"Sec-Fetch-Site": "same-origin"}


@pytest.fixture()
def library(sandbox, monkeypatch, tmp_path):
    from utils import photo_index
    monkeypatch.setattr(game, "STATE_FILE", tmp_path / "game.json")
    monkeypatch.setattr(game, "LOCK_FILE", tmp_path / "game.lock")
    monkeypatch.setattr(game, "PHOTOS_DIR", tmp_path / "photos")
    prepared = photo_index.PREPARED_DIR
    index = {}
    for i, year in enumerate([2008, 2012, 2015, 2015, 2019, 2021, 2023]):
        key = f"jeu/p{i}.jpg"
        (prepared / "jeu").mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (64, 36), (30 * i, 100, 150)).save(prepared / key)
        index[key] = {"date": f"{year}-07-14T12:00:00"}
    for i, author in enumerate(["Marie", "Paul"]):
        key = f"compte_{author.lower()}/m{i}.jpg"
        (prepared / key).parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (64, 36)).save(prepared / key)
        index[key] = {}
    index["messages/x.jpg"] = {"date": "2020-01-01T00:00:00"}  # pas une photo : jamais une question
    yield index
    import shutil
    for folder in ("jeu", "compte_marie", "compte_paul"):
        shutil.rmtree(prepared / folder, ignore_errors=True)


LABELS = {"compte_marie": "Marie", "compte_paul": "Paul"}


def test_questions_are_varied_and_valid(library):
    rounds = game.make_rounds(library, LABELS, rounds=6, rng=random.Random(2))
    assert 2 <= len(rounds) <= 6 and len({q["key"] for q in rounds}) == len(rounds)
    assert all(not q["key"].startswith("messages/") for q in rounds)
    for q in rounds:
        if q["kind"] == "who":
            assert q["answer"] in q["options"] and set(q["options"]) == {"Marie", "Paul"}
    years = [q["answer"] for q in rounds if q["kind"] == "year"]
    assert all(years.count(y) <= 2 for y in years)


def test_points():
    year = {"kind": "year", "answer": 2015}
    assert [game.points(year, v) for v in (2015, 2014, 2017, 2030, None, "x")] == [100, 75, 50, 0, 0, 0]
    assert game.points({"kind": "who", "answer": "Paul"}, "Paul") == 100 and game.points({"kind": "who", "answer": "Paul"}, "Marie") == 0


def test_full_game_timeline(library):
    t0 = time.time()
    state = game.new_game(library, LABELS, rounds=3, now=t0, rng=random.Random(1), timing={"auto_reveal": False})
    assert game.phase(state, t0 + 5)[0] == "lobby" and not game.start(t0 + 5)  # personne d'inscrit
    lea, tom = game.join("Léa"), game.join("  Tom  ")
    assert lea and tom and game.join("") is None
    assert game.start(t0 + 10)
    state = game.current()
    assert game.phase(state, t0 + 11) == ("question", 0, pytest.approx(game.QUESTION_SECONDS - 1))
    first = state["questions"][0]
    good = first["answer"]
    bad = (first["answer"] - 3) if first["kind"] == "year" else next(o for o in first["options"] if o != good)
    assert game.answer(lea, good, t0 + 12) and game.answer(tom, bad, t0 + 13)
    assert not game.answer(lea, good, t0 + 14)                                     # une seule réponse
    assert not game.answer("inconnu", good, t0 + 14)
    assert game.phase(state, t0 + 10 + game.QUESTION_SECONDS + 1)[0] == "reveal"
    assert not game.answer(tom, good, t0 + 10 + game.QUESTION_SECONDS + 1)       # trop tard
    view = game.public_view(game.current(), lea, t0 + 12)
    assert "answer" not in view and view["kind"] == first["kind"]                # jamais la réponse avant le dévoilement
    view = game.public_view(game.current(), lea, t0 + 10 + game.QUESTION_SECONDS + 2)
    assert view["answer"] == good and view["gained"] == 100 and view["ranking"][0]["name"] == "Léa"
    end = t0 + 10 + 3 * (game.QUESTION_SECONDS + game.REVEAL_SECONDS)
    assert game.phase(state, end + 1)[0] == "podium" and game.phase(state, end + game.PODIUM_SECONDS + 1)[0] == "over"


def test_game_screens_render(library):
    from utils import game_screen
    t0 = time.time()
    game.new_game(library, LABELS, rounds=2, now=t0, rng=random.Random(3))
    lobby = game_screen.frame(game.current(), t0 + 1, 640, 360, "http://cadre/jeu")
    assert lobby.size == (640, 360)
    player = game.join("Léa")
    game.start(t0 + 2)
    state = game.current()
    for moment in (3, 2 + game.QUESTION_SECONDS + 1, 2 + 2 * (game.QUESTION_SECONDS + game.REVEAL_SECONDS) + 1):
        assert game_screen.frame(state, t0 + moment, 640, 360, "http://cadre/jeu").size == (640, 360)
    assert player


def test_game_pages_for_phones(client, admin_client, library, monkeypatch):
    from utils import photo_index
    monkeypatch.setattr(photo_index, "load", lambda: library)
    assert "Jeux de famille" in client.get("/jeu").get_data(as_text=True)
    assert any(m["key"] == "bingo" for m in client.get("/jeu/modes").get_json()["modes"])
    assert client.get("/jeu/state").get_json()["phase"] == "over"
    assert client.post("/jeu/new", json={"rounds": 4}, headers=SAME).get_json()["success"]
    assert client.post("/jeu/new", json={}, headers=SAME).status_code == 409   # déjà une partie
    assert client.post("/jeu/join", json={"name": "Léa"}, headers=SAME).get_json()["success"]
    state = client.get("/jeu/state").get_json()
    assert state["phase"] == "lobby" and state["me"] == "Léa" and state["players"] == ["Léa"]
    assert client.post("/jeu/start", json={}, headers=SAME).get_json()["success"]
    state = client.get("/jeu/state").get_json()
    assert state["phase"] == "question" and state["question"] and "answer" not in state
    assert admin_client.post("/api/game/stop", headers=SAME).get_json()["success"]
    assert client.get("/jeu/state").get_json()["phase"] == "over"


def _play(state_mode, library, **kw):
    t0 = time.time()
    state = game.new_game(library, LABELS, rounds=kw.get("rounds", 3), now=t0, rng=random.Random(kw.get("seed", 4)), mode=state_mode,
                          people=kw.get("people"), timing=kw.get("timing"))
    return t0, state


def _steps_until(state, number, name):
    """Secondes depuis le départ jusqu'au milieu de l'étape `name` de la question `number`."""
    at = 0
    for n, q in enumerate(state["questions"]):
        for step, seconds in game.steps(q):
            if n == number and step == name:
                return at + seconds / 2
            at += seconds
    raise AssertionError("étape absente")


@pytest.mark.parametrize("mode", ["avant_apres", "ligne", "memoire", "proche", "zoom", "puzzle", "melange"])
def test_every_mode_builds_and_renders(library, mode):
    from utils import game_screen
    t0, state = _play(mode, library)
    assert state, mode
    lea = game.join("Léa")
    game.start(t0 + 1)
    state = game.current()
    for number, question in enumerate(state["questions"]):
        for step, _s in game.steps(question):
            moment = t0 + 1 + _steps_until(state, number, step)
            assert game_screen.frame(state, moment, 480, 270, "http://x/jeu").size == (480, 270)
            view = game.public_view(state, lea, moment)
            assert view["phase"] == step and ("answer" not in view or step == "reveal")


def test_timeline_memory_and_older_scoring(library):
    t0, state = _play("ligne", library, rounds=2)
    lea, tom = game.join("Léa"), game.join("Tom")
    game.start(t0)
    state = game.current()
    q = state["questions"][0]
    at = t0 + _steps_until(state, 0, "question")
    wrong = q["answer"][::-1]
    assert game.answer(lea, q["answer"].lower(), at) and game.answer(tom, wrong, at)
    assert not game.answer(game.join("Max"), "AAAA", at)  # pas un ordre
    points = game.round_points(game.current(), 0)
    assert points[lea] == 100 and points[tom] == sum(25 for a, b in zip(wrong, q["answer"]) if a == b)


def test_closest_ranks_the_nearest_guesses():
    q = {"kind": "closest", "answer": 40}
    assert game.question_points(q, {"a": 41, "b": 39, "c": 50, "d": 100, "e": 0}) == {"a": 100, "b": 100, "c": 30, "e": 10, "d": 0}


def test_zoom_rewards_fast_answers():
    q = {"kind": "year", "answer": 2015, "effect": "zoom"}
    assert game.question_points(q, {"a": 2015, "b": 2015}, {"a": 0.9, "b": 0.1}) == {"a": 94, "b": 46}


def test_caption_and_vote(library):
    t0, state = _play("legende", library, rounds=1, timing={"auto_reveal": False})
    lea, tom, max_ = game.join("Léa"), game.join("Tom"), game.join("Max")
    game.start(t0)
    state = game.current()
    write = t0 + _steps_until(state, 0, "question")
    assert game.answer(lea, "  Quand le chat   voit le gâteau  ", write) and game.answer(tom, "Vive les vacances", write)
    assert game.current()["answers"]["0"][lea] == "Quand le chat voit le gâteau"
    vote_at = t0 + _steps_until(state, 0, "vote")
    entries = {p: n for n, p, _v in game.entries(game.current(), 0)}
    assert not game.vote(lea, entries[lea], vote_at)              # pas pour soi
    assert game.vote(lea, entries[tom], vote_at) and game.vote(max_, entries[tom], vote_at) and game.vote(tom, entries[lea], vote_at)
    assert not game.vote(max_, entries[lea], vote_at)             # un seul vote
    assert game.round_points(game.current(), 0) == {lea: 100, tom: 200}
    reveal = game.public_view(game.current(), tom, t0 + _steps_until(state, 0, "reveal"))
    assert reveal["best"][0] == {"name": "Tom", "text": "Vive les vacances", "votes": 2}


def test_photo_challenge(library):
    import io
    t0, state = _play("defi", library, rounds=1)
    lea, tom = game.join("Léa"), game.join("Tom")
    game.start(t0)
    state = game.current()
    at = t0 + _steps_until(state, 0, "question")
    buffer = io.BytesIO()
    Image.new("RGB", (3000, 2000), (200, 30, 30)).save(buffer, "JPEG")
    assert game.answer_photo(lea, buffer.getvalue(), at) and not game.answer_photo(lea, buffer.getvalue(), at)
    assert not game.answer_photo(tom, b"pas une image", at)
    saved = game.PHOTOS_DIR / game.current()["answers"]["0"][lea]
    with Image.open(saved) as image:
        assert max(image.size) == 1600
    from utils import game_screen
    assert game_screen.frame(game.current(), t0 + _steps_until(state, 0, "vote"), 480, 270, "x").size == (480, 270)
    game.stop()
    assert not saved.exists()


def test_person_needs_known_faces(library):
    assert game.new_game(library, LABELS, rounds=3, mode="qui") is None
    people = {k: [["Léa", "Tom", "Zoé"][i % 3]] for i, k in enumerate(k for k in library if k.startswith("jeu/"))}
    state = game.new_game(library, LABELS, rounds=3, mode="qui", people=people, rng=random.Random(1))
    assert state and all(q["kind"] == "person" and q["effect"] == "blur" and q["answer"] in q["options"] for q in state["questions"])


def test_bingo_runs_alongside_the_slideshow(library):
    t0, state = _play("bingo", library)
    assert game.phase(state, t0 + 5)[0] == "bingo" and not game.running(t0 + 5) and game.bingo_active(t0 + 5)
    lea = game.join("Léa")
    view = game.public_view(game.current(), lea)
    assert len(view["grid"]) == 9 and len(set(view["grid"])) == 9
    assert not game.check_bingo(lea, 0)["bingo"] and not game.check_bingo(lea, 1)["bingo"]
    assert game.check_bingo(lea, 2)["bingo"]                     # première ligne complète
    assert not game.check_bingo(lea, 4)["bingo"]                  # déjà gagné
    assert game.public_view(game.current(), lea)["winners"] == ["Léa"]
    from utils import game_screen
    assert game_screen.bingo_banner(game.current(), time.time(), 1280, 720).size[1] > 0
    assert game.phase(game.current(), t0 + game.BINGO_MINUTES * 60 + 1)[0] == "over"


def test_custom_timing_is_frozen_in_the_game(library):
    t0 = time.time()
    state = game.new_game(library, LABELS, rounds=2, now=t0, rng=random.Random(5), timing={"question": 10, "reveal": 4, "podium": 6})
    game.join("Léa")
    game.start(t0)
    state = game.current()
    assert game.phase(state, t0 + 9)[0] == "question" and game.phase(state, t0 + 11)[0] == "reveal"
    assert game.phase(state, t0 + 2 * 14 + 5)[0] == "podium" and game.phase(state, t0 + 2 * 14 + 7)[0] == "over"
    assert game.timing_from({"game_question_seconds": 40, "game_speed_bonus": False}) == dict(game.TIMING, question=40, speed_bonus=False)


def test_skip_and_admin_view(library):
    t0 = time.time()
    game.new_game(library, LABELS, rounds=2, rng=random.Random(5))
    assert game.admin_view(game.current())["phase"] == "lobby" and not game.skip()
    game.join("Léa")
    game.start()
    view = game.admin_view(game.current())
    assert view["phase"] == "question" and view["number"] == 1 and view["answer"] is not None and view["players"] == [{"name": "Léa", "score": 0}]
    assert game.skip() and game.phase(game.current())[0] == "reveal"
    assert game.skip() and game.admin_view(game.current())["number"] == 2


def test_no_speed_bonus_when_disabled(library):
    t0 = time.time()
    game.new_game(library, LABELS, rounds=2, now=t0, rng=random.Random(5), mode="zoom", timing={"speed_bonus": False})
    lea = game.join("Léa")
    game.start(t0)
    state = game.current()
    q = state["questions"][0]
    assert game.answer(lea, q["answer"], t0 + game.QUESTION_SECONDS - 1)   # réponse tardive
    assert game.round_points(game.current(), 0)[lea] == 100


def test_games_admin_api(admin_client, library, monkeypatch):
    from utils import photo_index
    monkeypatch.setattr(photo_index, "load", lambda: library)
    assert admin_client.get("/api/game/status").get_json()["phase"] == "over"
    assert admin_client.post("/api/settings", json={"game_question_seconds": 15, "game_reveal_seconds": 5}, headers=SAME).get_json()["success"]
    assert admin_client.post("/jeu/new", json={"mode": "avant_apres", "rounds": 2}, headers=SAME).get_json()["success"]
    assert game.current()["timing"]["question"] == 15
    assert admin_client.post("/api/game/start", headers=SAME).status_code == 400       # personne
    admin_client.post("/jeu/join", json={"name": "Léa"}, headers=SAME)
    assert admin_client.post("/api/game/start", headers=SAME).get_json()["success"]
    status = admin_client.get("/api/game/status").get_json()
    assert status["phase"] == "question" and status["mode"] == "avant_apres" and status["answer"] in ("A", "B")
    assert admin_client.post("/api/game/skip", headers=SAME).get_json()["success"]
    assert admin_client.get("/api/game/status").get_json()["phase"] == "reveal"
    admin_client.post("/api/game/stop", headers=SAME)
    admin_client.post("/api/settings", json={"game_question_seconds": 25, "game_reveal_seconds": 9}, headers=SAME)


def test_answer_shown_as_soon_as_everyone_answered(library):
    t0 = time.time()
    game.new_game(library, LABELS, rounds=2, now=t0, rng=random.Random(5))
    lea, tom = game.join("Léa"), game.join("Tom")
    game.start(t0)
    q = game.current()["questions"][0]
    value = q["answer"] if q["kind"] == "year" else q["options"][0]
    assert game.answer(lea, value, t0 + 2) and game.phase(game.current(), t0 + 3)[0] == "question"   # Tom n'a pas répondu
    assert game.answer(tom, value, t0 + 3) and game.phase(game.current(), t0 + 3.5)[0] == "reveal"   # tout le monde : réponse


def test_auto_reveal_can_be_disabled(library):
    t0 = time.time()
    game.new_game(library, LABELS, rounds=2, now=t0, rng=random.Random(5), timing={"auto_reveal": False})
    lea = game.join("Léa")
    game.start(t0)
    q = game.current()["questions"][0]
    assert game.answer(lea, q["answer"] if q["kind"] == "year" else q["options"][0], t0 + 2)
    assert game.phase(game.current(), t0 + 3)[0] == "question"
