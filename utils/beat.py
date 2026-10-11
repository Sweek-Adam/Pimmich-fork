"""
Rythme calé sur la musique : le tempo (BPM) et la position des temps d'une musique de fond locale sont mesurés une
fois (ffmpeg + numpy, quelques secondes sur un Raspberry Pi 3), puis le diaporama change de photo sur un temps,
après un nombre entier de mesures. Les musiques Spotify et les radios ne donnent pas accès au son : pas de synchro.
"""
import json
import subprocess
import threading
from pathlib import Path

import numpy

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_FILE = BASE_DIR / "cache" / "beats.json"
RATE = 11025
HOP = 128
MIN_BPM, MAX_BPM = 70, 170
BEATS_PER_BAR = 4
_lock = threading.Lock()


def _decode(path, seconds=150):
    """Son de la musique en mono, 11 kHz (les 2 min 30 premières suffisent pour le tempo)."""
    result = subprocess.run(["ffmpeg", "-v", "quiet", "-t", str(seconds), "-i", str(path), "-ac", "1", "-ar", str(RATE),
                             "-f", "s16le", "-"], capture_output=True, timeout=120)
    if result.returncode != 0 or not result.stdout:
        raise ValueError("musique illisible")
    return numpy.frombuffer(result.stdout, dtype=numpy.int16).astype(numpy.float32) / 32768


def _duration(path):
    try:
        out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                             capture_output=True, text=True, timeout=30).stdout
        return float(out.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def onset_envelope(samples):
    """Montée d'énergie à chaque attaque (batterie, notes) : la courbe dont on tire le tempo."""
    frames = len(samples) // HOP
    if frames < 64:
        raise ValueError("musique trop courte")
    energy = numpy.sqrt(numpy.mean(samples[:frames * HOP].reshape(frames, HOP) ** 2, axis=1))
    flux = numpy.maximum(0, numpy.diff(numpy.log1p(100 * energy), prepend=0))
    return flux - numpy.convolve(flux, numpy.ones(16) / 16, mode="same")  # retire la tendance lente


def tempo(envelope):
    """(BPM, décalage du premier temps en secondes) : autocorrélation pondérée vers les tempos courants, puis peigne de phase."""
    fps = RATE / HOP
    env = envelope - envelope.mean()
    corr = numpy.correlate(env, env, mode="full")[len(env) - 1:]
    corr = corr / (corr[0] or 1)
    low, high = int(fps * 60 / MAX_BPM), int(fps * 60 / MIN_BPM) + 1
    lags = numpy.arange(low, high + 1)
    prior = numpy.exp(-0.5 * (numpy.log2((60 * fps / lags) / 120) / 0.9) ** 2)  # préférence douce autour de 120 BPM
    k = low + int(numpy.argmax(corr[low:high + 1] * prior))
    # Période affinée entre deux pas d'analyse (sinon le calage dériverait au fil de la musique)
    a, b, c = corr[k - 1], corr[k], corr[k + 1]
    denominator = a - 2 * b + c
    period = k + (0.5 * (a - c) / denominator if denominator else 0.0)
    # Période et position des temps cherchées ensemble (une petite erreur de période brouillerait la position)
    best, offset, best_period = -numpy.inf, 0.0, period
    for candidate in numpy.linspace(period * 0.99, period * 1.01, 21):
        count = int((len(envelope) - 1) / candidate)
        grid = candidate * numpy.arange(count)
        for start in numpy.arange(0, candidate, 0.5):
            total = envelope[numpy.round(start + grid).astype(int).clip(0, len(envelope) - 1)].sum()
            if total > best:
                best, offset, best_period = total, start, candidate
    period = best_period
    return round(float(60 * fps / period), 2), round(float(offset / fps), 3)


def _load():
    try:
        return json.loads(CACHE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def analyse(path):
    """Tempo d'un fichier musical (mis en cache) : {bpm, offset, length} ou None."""
    path = Path(path)
    try:
        key = f"{path.name}|{int(path.stat().st_mtime)}|{path.stat().st_size}"
    except OSError:
        return None
    with _lock:
        cache = _load()
        if key in cache:
            return cache[key]
        try:
            bpm, offset = tempo(onset_envelope(_decode(path)))
            info = {"bpm": bpm, "offset": offset, "length": _duration(path)}
        except (OSError, ValueError, subprocess.SubprocessError):
            info = None
        cache[key] = info
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(cache))
        return info


def beat_seconds(info):
    return 60 / info["bpm"]


def snap_duration(info, seconds):
    """Durée d'affichage arrondie à un nombre entier de mesures (4 temps), au moins une mesure."""
    bar = beat_seconds(info) * BEATS_PER_BAR
    return max(1, round(seconds / bar)) * bar


def until_next_beat(info, position):
    """Secondes avant le prochain temps, la musique étant à `position` secondes (elle tourne en boucle)."""
    if info.get("length"):
        position %= info["length"]
    beat = beat_seconds(info)
    since = (position - info["offset"]) % beat
    return (beat - since) % beat


def transition_seconds(info, wanted):
    """Durée de transition proche de celle choisie, en nombre entier de temps (au moins un)."""
    beat = beat_seconds(info)
    return max(1, round(wanted / beat)) * beat
