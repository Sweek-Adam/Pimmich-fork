"""
Extraits des longues vidéos : au lieu de 3 minutes, le cadre montre le passage le plus animé (20 secondes par
défaut). La vidéo n'est pas modifiée (la version complète reste dans la bibliothèque) : mpv la lit de `start` à
`start + length`, d'après un petit fichier à côté de la vidéo préparée (<nom>_excerpt.json).

Le mouvement est mesuré sur les seules images clés de la vidéo (décodage très rapide, même sur un Raspberry Pi 3) :
différence moyenne entre deux images clés réduites à 64 × 36 en niveaux de gris.
"""
import json
import shutil
import subprocess
from pathlib import Path

SAMPLE = (64, 36)


def sidecar(video_path):
    path = Path(video_path)
    return path.with_name(f"{path.stem}_excerpt.json")


def read(video_path):
    try:
        data = json.loads(sidecar(video_path).read_text())
        return data if data.get("length", 0) > 0 else None
    except (OSError, ValueError):
        return None


def motion_profile(video_path, timeout=300):
    """Mouvement au fil de la vidéo : [(seconde, score)], une valeur par seconde (images clés seulement)."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return []
    w, h = SAMPLE
    command = ["nice", "-n", "19"] if shutil.which("nice") else []
    command += [ffmpeg, "-v", "error", "-skip_frame", "nokey", "-i", str(video_path), "-an",
                "-vf", f"fps=1,scale={w}:{h},format=gray", "-f", "rawvideo", "-"]
    try:
        raw = subprocess.run(command, capture_output=True, timeout=timeout).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    size = w * h
    frames = [raw[i:i + size] for i in range(0, len(raw) - size + 1, size)]
    profile = []
    for second in range(1, len(frames)):
        a, b = frames[second - 1], frames[second]
        profile.append((second, sum(abs(x - y) for x, y in zip(a[::4], b[::4])) / (size / 4)))
    return profile


def best_window(profile, length, duration):
    """Début du passage de `length` secondes où il se passe le plus de choses (un peu après le tout début si égal)."""
    if duration <= length or not profile:
        return 0.0
    scores = {second: score for second, score in profile}
    best, best_score = 0, -1.0
    for start in range(0, int(duration - length) + 1):
        total = sum(scores.get(s, 0.0) for s in range(start + 1, start + int(length) + 1))
        if total > best_score + 1e-9:
            best, best_score = start, total
    return float(best)


def make(video_path, duration, length=20):
    """Calcule et enregistre l'extrait de cette vidéo ; retourne {start, length, duration}, ou None."""
    if not duration or duration <= length * 1.5:
        return None
    profile = motion_profile(video_path)
    if not profile:
        return None
    data = {"start": best_window(profile, length, duration), "length": float(length), "duration": float(duration)}
    sidecar(video_path).write_text(json.dumps(data))
    return data
