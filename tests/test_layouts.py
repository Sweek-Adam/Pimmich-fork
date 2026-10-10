"""Dispositions : photo unique, compositions, choix rapide et playlists."""
import random
from datetime import date

import pytest
from PIL import Image

from utils import layout_engine as le
from utils import compositions as comp

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}
SUMMER = date(2026, 7, 1)


def test_auto_uses_settings_and_in_season_formats():
    plan = le.resolve({"compositions_disabled": []}, today=SUMMER)
    assert plan.unique and "liege" in plan.formats and "noel" not in plan.formats and plan.every == 5


def test_explicit_choices():
    assert le.resolve({}, "unique").formats == [] and le.resolve({}, "unique").unique
    plan = le.resolve({}, "noel", today=SUMMER)
    assert plan.formats == ["noel"] and not plan.unique        # choisi explicitement : même hors saison
    plan = le.resolve({"compositions_disabled": [k for k in comp.FORMATS if k != "duo"]}, "compositions")
    assert plan.formats == ["duo"] and not plan.unique


def test_quick_override_and_playlist_choice():
    config = {"layout_override": "liege"}
    assert le.resolve(config).formats == ["liege"]              # choix rapide du diaporama
    assert le.resolve(config, "unique").formats == []           # la playlist a son propre choix
    assert le.resolve(config, "auto").formats == ["liege"]      # « comme le diaporama »


def test_only_compositions_when_single_photo_unchecked():
    plan = le.resolve({"unique_enabled": False, "compositions_disabled": []}, today=SUMMER)
    assert not plan.unique and plan.formats
    assert le.resolve({"unique_enabled": False, "compositions_enabled": False}).unique  # rien de coché : photo unique


def test_wants_composition():
    mixed = le.LayoutPlan(True, ["liege"], 3)
    assert [le.wants_composition(mixed, n) for n in range(5)] == [False, False, False, True, True]
    assert le.wants_composition(le.LayoutPlan(False, ["liege"], 3), 0)
    assert not le.wants_composition(le.LayoutPlan(True, [], 3), 99)


def test_take_chunk_follows_order_wraps_and_stops_before_videos():
    playlist = ["a.jpg", "b.jpg", "c.mp4", "d.jpg", "e.jpg"]
    assert le.take_chunk(playlist, 0, 4) == ["a.jpg", "b.jpg"]
    assert le.take_chunk(playlist, 3, 4) == ["d.jpg", "e.jpg", "a.jpg", "b.jpg"]
    assert le.take_chunk(playlist, 2, 3) == []


@pytest.fixture(scope="module")
def images(tmp_path_factory):
    folder = tmp_path_factory.mktemp("seq")
    paths = []
    for i in range(8):
        p = folder / f"{i}.jpg"
        Image.new("RGB", (400, 300), (i * 30, 80, 160)).save(p)
        paths.append(str(p))
    msg_dir = folder / "messages"
    msg_dir.mkdir()
    Image.new("RGB", (400, 300)).save(msg_dir / "abc123.jpg")
    return paths, str(msg_dir / "abc123.jpg")


def test_render_chunk_uses_photos_in_order_and_message_as_note(images):
    paths, message_path = images
    message = {"id": "abc123", "title": "Coucou", "body": "Bisous", "signature": "Léa"}
    image, used = le.render_chunk("liege", [paths[0], message_path, paths[1], paths[2]], {"abc123": message}, 640, 360)
    assert image.size == (640, 360) and used == 4


def test_render_chunk_keeps_extra_slides_for_later(images):
    paths, _ = images
    image, used = le.render_chunk("mur", paths[:6], {}, 640, 360)  # le mur accepte 3 à 5 cadres
    assert image is not None and used == 5


def test_pick_format_weights_seasons():
    plan = le.LayoutPlan(False, ["noel", "japon"], seasonal=True)
    picks = [le.pick_format(plan, random.Random(i), date(2026, 12, 20)) for i in range(400)]
    assert picks.count("noel") > picks.count("japon") * 2


@pytest.fixture()
def no_restart(monkeypatch):
    """Ne jamais redémarrer le vrai diaporama du cadre pendant les tests."""
    from web import routes_slideshow
    calls = []
    monkeypatch.setattr(routes_slideshow, "is_slideshow_running", lambda: True)
    monkeypatch.setattr(routes_slideshow, "restart_slideshow_for_update", lambda: calls.append(1))
    return calls


def test_quick_layout_api(admin_client, no_restart):
    from utils.config_manager import load_config
    resp = admin_client.post("/api/slideshow/layout", json={"layout": "hokusai"}, headers=SAME_ORIGIN)
    assert resp.get_json()["success"] and load_config()["layout_override"] == "hokusai" and no_restart == [1]
    assert admin_client.get("/api/slideshow/layout").get_json()["layout"] == "hokusai"
    assert admin_client.post("/api/slideshow/layout", json={"layout": "inconnu"}, headers=SAME_ORIGIN).status_code == 400
    admin_client.post("/api/slideshow/layout", json={"layout": "auto"}, headers=SAME_ORIGIN)


def test_playlist_layout_api(admin_client):
    from utils.playlist_manager import load_playlists, save_playlists
    save_playlists([{"id": "p1", "name": "Vacances", "photos": []}])
    assert admin_client.post("/api/playlists/p1/layout", json={"layout": "polaroids"}, headers=SAME_ORIGIN).get_json()["success"]
    assert load_playlists()[0]["layout"] == "polaroids"
    assert admin_client.post("/api/playlists/p1/layout", json={"layout": "nope"}, headers=SAME_ORIGIN).status_code == 400
    assert admin_client.post("/api/playlists/absente/layout", json={"layout": "auto"}, headers=SAME_ORIGIN).status_code == 404


def test_single_photo_checkbox_is_saved(admin_client):
    from utils.config_manager import load_config
    admin_client.post("/configure", data={"compositions_form": "1", "compositions_styles": ["liege"]}, headers=SAME_ORIGIN)
    assert load_config()["unique_enabled"] is False
    admin_client.post("/configure", data={"compositions_form": "1", "compositions_styles": ["unique", "liege"]}, headers=SAME_ORIGIN)
    config = load_config()
    assert config["unique_enabled"] and comp.enabled_formats(config) == ["liege"]


def test_slow_composition_is_still_shown(monkeypatch, sandbox):
    """Préparation plus longue que l'affichage d'une photo : la composition attendue passe quand même."""
    import os
    import time
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pytest.importorskip("pygame")
    import local_slideshow as ls
    monkeypatch.setattr(comp, "OUTPUT_DIR", sandbox / "static" / "compositions")
    monkeypatch.setattr(ls, "list_messages", lambda: [])
    monkeypatch.setattr(ls, "publish_queue", lambda **_: None)

    def slow_render(style, chunk, messages, width, height, include_messages, rng):
        time.sleep(0.5)
        return Image.new("RGB", (32, 18)), len(chunk)
    monkeypatch.setattr(le, "render_chunk", slow_render)
    plan = le.resolve({"unique_enabled": True, "compositions_every": 2, "composition_formats": ["mosaique"]})
    playlist = [f"p{i}.jpg" for i in range(8)]
    ls.prepare_composition({}, plan, playlist, 2, 64, 36)
    path, used = ls.take_composition(playlist, 2, wait_seconds=40)
    assert path and used >= 2


def test_zero_means_back_to_back_compositions():
    plan = le.resolve({"unique_enabled": True, "compositions_every": 0})
    assert plan.unique and plan.every == 0 and plan.formats
    assert all(le.wants_composition(plan, n) for n in range(4))  # aucune photo seule entre deux compositions
    assert le.resolve({"compositions_every": "abc"}).every == 5


def test_compositions_stay_long_enough_to_look_at_each_photo():
    assert le.composition_seconds({"display_duration": 1}, 4) == 10      # durée allongée automatiquement
    assert le.composition_seconds({"display_duration": 30}, 4) == 30     # jamais raccourcie


def test_empty_every_field_is_not_saved_as_zero(admin_client):
    from utils.config_manager import load_config
    headers = {"Sec-Fetch-Site": "same-origin", "X-Autosave": "1"}
    admin_client.post("/configure", data={"compositions_every": "3"}, headers=headers)
    admin_client.post("/configure", data={"compositions_every": ""}, headers=headers)  # champ vidé pendant la saisie
    assert load_config()["compositions_every"] == 3
    admin_client.post("/configure", data={"compositions_every": "0"}, headers=headers)
    assert load_config()["compositions_every"] == 0


def test_a_message_is_shown_inside_a_layout_that_accepts_messages():
    only = lambda keys: [k for k in comp.FORMATS if k not in keys]  # réglage : formats décochés
    plan = le.resolve({"unique_enabled": True, "compositions_every": 50, "compositions_disabled": only({"pellicule", "liege", "halloween"}),
                       "compositions_seasonal": False})
    wanted, used = le.plan_for_slide(plan, "/static/prepared/messages/abc.jpg", 0)
    assert wanted and "pellicule" not in used.formats and set(used.formats) <= {"liege", "halloween"}  # pas en photo unique
    assert le.plan_for_slide(plan, "/static/prepared/photos/a.jpg", 0) == (False, plan)
    assert le.plan_for_slide(plan, "/static/prepared/messages/abc.jpg", 0, include_messages=False) == (False, plan)
    only_film = le.resolve({"unique_enabled": True, "compositions_every": 50, "compositions_disabled": only({"pellicule"})})
    assert le.plan_for_slide(only_film, "/static/prepared/messages/abc.jpg", 0) == (False, only_film)  # aucune ne convient : seul
    assert not le.plan_for_slide(plan, "/static/prepared/photos/film.mp4", 99)[0]


def test_halloween_shows_several_messages_in_ghosts(tmp_path):
    folder, messages = tmp_path / "messages", {}
    folder.mkdir()
    chunk = []
    for i, text in enumerate(["Bouh !", "Joyeux Halloween à tous"]):
        (folder / f"m{i}.jpg").write_bytes(b"")
        messages[f"m{i}"] = {"id": f"m{i}", "title": "", "body": text, "signature": "Léa"}
        chunk.append(str(folder / f"m{i}.jpg"))
    for i in range(4):
        path = tmp_path / f"p{i}.jpg"
        Image.new("RGB", (120, 90), (40 * i, 90, 160)).save(path)
        chunk.append(str(path))
    image, used = le.render_chunk("halloween", chunk, messages, 640, 360, rng=random.Random(1))
    assert image is not None and used == 5  # 2 messages + 3 photos (la 4e reste pour la suite)
    from utils import themed_compositions as t
    ghost = t._ghost(messages["m1"], 200, random.Random(1))
    assert ghost.mode == "RGBA" and ghost.getpixel((ghost.width // 2, int(ghost.height * 0.65)))[3] > 200  # ventre opaque, texte lisible


def test_layout_picker_marks_layouts_with_messages(admin_client):
    html = admin_client.get("/configure").get_data(as_text=True)
    assert 'data-layout="halloween" data-group="theme"' in html and 'data-filter="messages"' in html
    assert 'data-layout="photomaton" data-group="format" data-label="photomaton" data-messages="0"' in html
