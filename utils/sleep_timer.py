"""
Minuteur de sommeil : « arrêter la musique dans 30 min ». À l'heure dite, le volume baisse doucement pendant
30 secondes, toutes les sources se mettent en pause, puis le volume revient à son niveau (pour la prochaine fois).
"""
import threading
import time

from utils import music_remote

FADE_SECONDS = 30
_state = {"ends": None, "timer": None}
_lock = threading.Lock()


def remaining():
    """Secondes restantes, ou None si aucun minuteur."""
    ends = _state["ends"]
    return max(0, int(ends - time.time())) if ends else None


def cancel():
    with _lock:
        if _state["timer"]:
            _state["timer"].cancel()
        _state.update(ends=None, timer=None)


def _expire():
    volume, _muted = music_remote.get_volume()
    if volume:
        for step in range(1, 11):  # fondu
            music_remote.set_volume(volume * (1 - step / 10))
            time.sleep(FADE_SECONDS / 10)
    music_remote.pause_everything()
    if volume:
        music_remote.set_volume(volume)
    _state.update(ends=None, timer=None)


def start(minutes):
    """Arrête la musique dans `minutes` minutes (remplace un minuteur en cours)."""
    minutes = max(1, min(240, int(minutes)))
    cancel()
    with _lock:
        delay = max(0, minutes * 60 - FADE_SECONDS)
        timer = threading.Timer(delay, _expire)
        timer.daemon = True
        timer.start()
        _state.update(ends=time.time() + minutes * 60, timer=timer)
    return remaining()
