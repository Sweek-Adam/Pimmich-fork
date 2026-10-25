"""Le cadre est-il occupé ? (la mise à jour de la nuit attend la fin des travaux, fêtes et parties)"""
import time

from utils import busy, family_game, party


def test_working_marks_and_clears(tmp_path, monkeypatch):
    monkeypatch.setattr(busy, "WORK_FILE", tmp_path / "work.json")
    monkeypatch.setattr(family_game, "STATE_FILE", tmp_path / "game.json")
    assert busy.reasons({}) == []
    with busy.working("préparation de gdrive/film.mp4"):
        assert busy.reasons({}) == ["travail en cours : préparation de gdrive/film.mp4"]
    assert busy.reasons({}) == []
    # Fichier laissé par un processus disparu : ignoré
    busy.WORK_FILE.write_text('{"label": "x", "pid": 999999999}')
    assert busy.reasons({}) == []


def test_party_and_game_count_as_busy(tmp_path, monkeypatch):
    monkeypatch.setattr(busy, "WORK_FILE", tmp_path / "work.json")
    monkeypatch.setattr(family_game, "STATE_FILE", tmp_path / "game.json")
    monkeypatch.setattr(family_game, "LOCK_FILE", tmp_path / "game.lock")
    config = party.start({}, "Mariage", 3)
    assert busy.reasons(config) == ["fête en cours"]
    family_game._save({"id": "x", "mode": "bingo", "created": time.time(), "until": time.time() + 600, "players": {}})
    assert "bingo en cours" in busy.reasons({})

