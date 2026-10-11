"""Rythme calé sur la musique (tempo mesuré sur le cadre) et nouvelles transitions."""
import numpy
import pytest

from utils import beat


def click_track(bpm, offset, seconds=60):
    """Batterie simple : un coup sur chaque temps (plus fort sur le premier de la mesure), charleston à contretemps."""
    rng = numpy.random.default_rng(1)
    samples = rng.normal(0, 0.01, int(beat.RATE * seconds)).astype(numpy.float32)
    period, t, n = 60 / bpm, offset, 0
    while t < seconds - 0.1:
        i = int(t * beat.RATE)
        click = (0.9 if n % 4 == 0 else 0.6) * numpy.exp(-numpy.arange(800) / 120) * numpy.sin(numpy.arange(800) * 0.9)
        samples[i:i + 800] += click[:len(samples[i:i + 800])]
        j = int((t + period / 2) * beat.RATE)
        samples[j:j + 200] += 0.25 * rng.normal(0, 1, len(samples[j:j + 200]))
        t, n = t + period, n + 1
    return samples


@pytest.mark.parametrize("bpm,offset", [(120, 0.2), (140, 0.1), (100, 0.0), (128, 0.3)])
def test_tempo_and_first_beat(bpm, offset):
    found, start = beat.tempo(beat.onset_envelope(click_track(bpm, offset)))
    assert abs(found - bpm) < 0.5
    period = 60 / bpm
    gap = abs((start - offset + period / 2) % period - period / 2)
    assert gap < 0.05  # sur le temps (à 50 ms près)


def test_grid_helpers():
    info = {"bpm": 120.0, "offset": 0.2, "length": 30.0}
    assert beat.snap_duration(info, 10) == 10.0 and beat.snap_duration(info, 9) == 8.0 and beat.snap_duration(info, 0.5) == 2.0
    assert abs(beat.until_next_beat(info, 1.0) - 0.2) < 1e-9  # temps à 0,2 + 0,5 k : le prochain est à 1,2
    assert abs(beat.until_next_beat(info, 31.0) - 0.2) < 1e-9  # la musique tourne en boucle
    assert beat.transition_seconds(info, 1.2) == 1.0 and beat.transition_seconds(info, 0.1) == 0.5


def test_analyse_is_cached(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(beat, "CACHE_FILE", tmp_path / "beats.json")
    monkeypatch.setattr(beat, "_decode", lambda path: calls.append(path) or click_track(120, 0.2, 20))
    monkeypatch.setattr(beat, "_duration", lambda path: 20.0)
    music = tmp_path / "fete.mp3"
    music.write_bytes(b"x")
    first = beat.analyse(music)
    assert abs(first["bpm"] - 120) < 0.5 and first["length"] == 20.0
    assert beat.analyse(music) == first and len(calls) == 1
    assert beat.analyse(tmp_path / "absente.mp3") is None


def test_every_transition_draws(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    import pygame
    import local_slideshow as ls
    pygame.display.init()
    try:
        target = pygame.Surface((160, 90))
        old, new = pygame.Surface((160, 90)), pygame.Surface((160, 90))
        old.fill((255, 0, 0))
        new.fill((0, 0, 255))
        for kind in ls.EXTRA_TRANSITIONS:
            ls.draw_extra_transition(target, old, new, kind, 0.0, 160, 90)
            start = target.get_at((80, 45))[:3]
            ls.draw_extra_transition(target, old, new, kind, 1.0, 160, 90)
            end = target.get_at((80, 45))[:3]
            assert end == (0, 0, 255), kind  # à la fin : la nouvelle photo
            assert start != (0, 0, 255) or kind == "zoom", kind  # au début : pas encore la nouvelle
        assert set(ls.RANDOM_TRANSITIONS) >= set(ls.EXTRA_TRANSITIONS)
    finally:
        pygame.display.quit()
