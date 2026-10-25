"""Textes affichés sur le cadre dans la langue choisie (catalogues de l'interface)."""
import os

import pytest


def test_frame_texts_follow_the_language_setting(monkeypatch):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pytest.importorskip("pygame")
    import local_slideshow as ls
    monkeypatch.setattr(ls, "load_config", lambda: {"language": "en"})
    assert ls._("Scannez pour jouer") == "Scan to play"
    assert ls._("Bravo %(name)s !", name="Léa") == "Well done Léa!"
    monkeypatch.setattr(ls, "load_config", lambda: {"language": "de"})
    assert ls._("Règles du jeu") == "Spielregeln"
    monkeypatch.setattr(ls, "load_config", lambda: {})
    assert ls._("Règles du jeu") == "Règles du jeu"            # français par défaut
    assert ls._("Texte inconnu %(x)s", x=1) == "Texte inconnu 1"
