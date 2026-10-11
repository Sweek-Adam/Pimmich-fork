"""Jukebox et karaoké : position de lecture Spotify, paroles LRCLIB, rendu de l'écran."""
import time

from PIL import Image

from utils import jukebox, lyrics, now_playing

LRC = "[00:01.00]Première ligne\n[00:05.50]Deuxième ligne\n[00:09.00][00:20.00]Refrain\n"


def test_parse_lrc_and_line_index():
    lines = lyrics.parse_lrc(LRC)
    assert lines == [(1.0, "Première ligne"), (5.5, "Deuxième ligne"), (9.0, "Refrain"), (20.0, "Refrain")]
    assert lyrics.line_index(lines, 0.5) == -1 and lyrics.line_index(lines, 6) == 1 and lyrics.line_index(lines, 25) == 3


def test_fetch_uses_lrclib_then_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(lyrics, "CACHE_DIR", tmp_path)
    calls = []

    class Session:
        def get(self, url, params, headers, timeout):
            calls.append((url, params))
            return type("R", (), {"status_code": 200, "json": lambda self: {"syncedLyrics": LRC}})()
    assert len(lyrics.fetch("Titre", "Artiste", "Album", 180, Session())) == 4
    assert calls[0][1]["duration"] == 180
    assert len(lyrics.fetch("Titre", "Artiste", session=Session())) == 4 and len(calls) == 1  # en cache


def test_spotify_position_from_librespot(monkeypatch, tmp_path):
    monkeypatch.setattr(now_playing, "STATE_FILE", tmp_path / "np.json", raising=False)
    entry = {"state": "playing", "position_ms": 10000, "position_at": time.time() - 2}
    assert 11.9 < now_playing.position(entry) < 12.5
    assert now_playing.position(dict(entry, state="paused")) == 10.0
    assert now_playing.position({"state": "playing"}) is None


def test_frames(tmp_path):
    cover = tmp_path / "c.jpg"
    Image.new("RGB", (300, 300), (200, 50, 80)).save(cover)
    info = {"title": "Chanson", "artist": "Groupe", "cover": str(cover), "duration_ms": 200000}
    bg = jukebox.background(info, 640, 360)
    for mode, lines in (("jukebox", None), ("karaoke", lyrics.parse_lrc(LRC)), ("karaoke", [])):
        assert jukebox.frame(bg, info, 640, 360, mode, lines, 6).size == (640, 360)
    assert jukebox.background({"title": "Sans pochette"}, 640, 360).size == (640, 360)
