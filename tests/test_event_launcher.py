"""Édition ordinateur (pimmich_event.py) : dossiers choisis, compte admin, configuration de l'événement."""
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

# Chargé depuis son fichier, sans ajouter le vrai dossier du projet au chemin des modules : les autres tests doivent
# continuer d'utiliser la copie du bac à sable (jamais la vraie configuration ni les vraies photos)
_spec = importlib.util.spec_from_file_location("pimmich_event", Path(__file__).resolve().parent.parent / "pimmich_event.py")
event = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(event)


@pytest.mark.skipif(sys.platform.startswith("win"), reason="liens symboliques (jonctions sous Windows)")
def test_folders_are_linked_where_the_user_wants(tmp_path):
    link, target = tmp_path / "static" / "photos", tmp_path / "disque" / "Mariage"
    assert event.link_folder(link, target) is None
    assert link.is_symlink() and link.resolve() == target.resolve() and target.is_dir()
    assert event.link_folder(link, target) is None                      # déjà fait
    other = tmp_path / "ailleurs"
    assert event.link_folder(link, other) is None and link.resolve() == other.resolve()
    assert event.link_folder(link, link) is None and link.is_dir() and not link.is_symlink()  # retour au dossier par défaut
    (link / "photo.jpg").write_bytes(b"x")
    assert "contient déjà" in event.link_folder(link, target)            # jamais de photo perdue


def test_admin_account_created_once(tmp_path, monkeypatch):
    from werkzeug.security import check_password_hash
    monkeypatch.setattr(event, "CREDENTIALS", tmp_path / "credentials.json")
    assert event.ensure_admin("motdepasse") == "motdepasse"
    data = json.loads((tmp_path / "credentials.json").read_text())
    assert data["username"] == "admin" and check_password_hash(data["password_hash"], "motdepasse")
    assert event.ensure_admin("autre") is None                           # jamais écrasé


def test_event_configuration(sandbox):
    from utils.config_manager import load_config, save_config
    original = dict(load_config())
    try:
        settings = dict(event.DEFAULTS, name="Mariage de Zoé", hours=6, display=1)
        config = event.prepare_config(settings, [(0, 2560, 1600), (1, 1920, 1080)])
        assert (config["display_width"], config["display_height"]) == (1920, 1080) and config["desktop_display"] == 1
        assert config["party"]["name"] == "Mariage de Zoé" and config["active_end_weekday"] == "23:59"
    finally:
        save_config(original)


def test_event_process_environment():
    env = event.Event(dict(event.DEFAULTS, port=9000)).environment()
    assert env["PIMMICH_EDITION"] == "event" and env["PIMMICH_PORT"] == "9000" and env["PIMMICH_CREDENTIALS_PATH"].endswith("credentials.json")
    assert "PIMMICH_DESKTOP" not in env or env.get("PIMMICH_DESKTOP") == os.environ.get("PIMMICH_DESKTOP")
