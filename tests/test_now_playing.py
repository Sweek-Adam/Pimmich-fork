"""Lecteur « en cours de lecture » : Spotify (librespot), AirPlay (shairport-sync), musique du diaporama."""
import base64
import time

import pytest

from utils import now_playing as np

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Jamais l'état réel du cadre (/tmp/pimmich_now_playing.json)."""
    monkeypatch.setattr(np, "STATE_FILE", tmp_path / "now_playing.json")
    monkeypatch.setattr(np, "COVER_DIR", tmp_path / "covers")
    monkeypatch.setattr(np, "_download_cover", lambda urls, track_id: None)


def spotify(event, **env):
    np.handle_librespot_event({"PLAYER_EVENT": event, **env})


def test_spotify_events_follow_the_track():
    spotify("track_changed", NAME="Clair de lune", ARTISTS="Debussy\nOrchestre", ALBUM="Suite", COVERS="https://i/1\nhttps://i/2")
    spotify("playing", POSITION_MS="0")
    info = np.current()
    assert info["source"] == "spotify" and info["title"] == "Clair de lune" and info["artist"] == "Debussy, Orchestre"
    assert np.external_playing()
    spotify("paused")
    assert np.current() is None and not np.external_playing()


def test_external_sources_take_precedence_over_slideshow_music():
    np.update("pimmich", state="playing", title=np.pretty_title("ma_musique-douce.mp3"))
    assert np.current()["title"] == "ma musique douce"
    spotify("track_changed", NAME="Titre", ARTISTS="Artiste")
    spotify("playing")
    assert np.current()["source"] == "spotify"
    assert np.current(exclude=("spotify",))["source"] == "pimmich"


def _item(kind, code, data=b""):
    out = f"<item><type>{kind.encode().hex()}</type><code>{code.encode().hex()}</code><length>{len(data)}</length>"
    if data:
        out += f"\n<data encoding=\"base64\">\n{base64.b64encode(data).decode()}</data>"
    return (out + "</item>\n").encode()


def test_airplay_metadata_pipe_is_parsed_across_chunks():
    stream = (_item("ssnc", "pbeg") + _item("ssnc", "mdst") + _item("core", "minm", "Été indien".encode())
              + _item("core", "asar", b"Joe Dassin") + _item("ssnc", "mden") + _item("ssnc", "PICT", b"\xff\xd8" + b"x" * 200))
    tracker, buffer = np.AirplayTracker(), b""
    for chunk in (stream[:57], stream[57:203], stream[203:]):  # le tube livre le flux par morceaux
        items, buffer = np.parse_airplay_items(buffer + chunk)
        for item in items:
            tracker.feed(*item)
    info = np.current()
    assert info["source"] == "airplay" and info["title"] == "Été indien" and info["artist"] == "Joe Dassin"
    assert info["cover"] and np.COVER_DIR in __import__("pathlib").Path(info["cover"]).parents
    tracker.feed("ssnc", "pend", b"")
    assert np.current() is None


def test_now_playing_api_and_cover(admin_client, monkeypatch):
    from web import routes_home
    monkeypatch.setattr(routes_home, "is_slideshow_running", lambda: True)
    assert admin_client.get("/api/now_playing").get_json()["playing"] is None
    np.COVER_DIR.mkdir(parents=True)
    cover = np.COVER_DIR / "airplay_abc.jpg"
    cover.write_bytes(b"\xff\xd8jpeg")
    np.update("airplay", state="playing", title="Titre", artist="Artiste", cover=str(cover))
    playing = admin_client.get("/api/now_playing").get_json()["playing"]
    assert playing["title"] == "Titre" and playing["source_label"] == "AirPlay" and playing["cover"]
    assert admin_client.get(playing["cover"]).data == b"\xff\xd8jpeg"
    np.update("airplay", cover="/etc/passwd")  # jamais un fichier hors du dossier des pochettes
    assert admin_client.get("/api/now_playing").get_json()["playing"]["cover"] is None
    assert admin_client.get("/api/now_playing/cover").status_code == 404


def test_slideshow_music_hidden_when_slideshow_stopped(admin_client, monkeypatch):
    from web import routes_home
    monkeypatch.setattr(routes_home, "is_slideshow_running", lambda: False)
    np.update("pimmich", state="playing", title="Ancienne musique")
    assert admin_client.get("/api/now_playing").get_json()["playing"] is None


def test_display_settings_saved_without_restarting(admin_client, monkeypatch):
    from web import routes_home
    from utils.config_manager import load_config
    restarts = []
    monkeypatch.setattr(routes_home, "restart_slideshow_process", lambda: restarts.append(1))
    resp = admin_client.post("/api/sound", json={"now_playing_display": "always", "now_playing_position": "top_right"}, headers=SAME_ORIGIN)
    assert resp.get_json()["success"] and not restarts
    config = load_config()
    assert config["now_playing_display"] == "always" and config["now_playing_position"] == "top_right"
    assert admin_client.post("/api/sound", json={"now_playing_display": "partout"}, headers=SAME_ORIGIN).status_code == 400


def test_slideshow_draws_a_discreet_player(monkeypatch):
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame = pytest.importorskip("pygame")
    import local_slideshow as ls
    pygame.init()
    try:
        pygame.font.Font(None, 12)
    except Exception:
        pytest.skip("polices pygame indisponibles sur cette machine")
    np.update("spotify", state="playing", title="Un morceau", artist="Quelqu'un", changed=time.time())
    ls._now_playing_cache.update(read=0, key=None)
    screen = pygame.Surface((1920, 1080))
    config = {"now_playing_display": "change", "now_playing_position": "bottom_left", "show_guest_qr": False}
    ls.draw_now_playing(screen, 1920, 1080, config)
    assert screen.get_at((40, 1040))[:3] != (0, 0, 0)  # encart en bas à gauche
    np.update("spotify", changed=time.time() - 60)  # morceau commencé il y a une minute : plus affiché
    ls._now_playing_cache.update(read=0)
    assert ls.now_playing_visible(config) is None
    assert ls.now_playing_visible(dict(config, now_playing_display="always"))["title"] == "Un morceau"
