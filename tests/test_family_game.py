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
    state = game.new_game(library, LABELS, rounds=3, now=t0, rng=random.Random(1))
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
    assert "Où et quand" in client.get("/jeu").get_data(as_text=True)
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
