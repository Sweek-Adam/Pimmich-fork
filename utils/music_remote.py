"""
Télécommande de la musique du cadre, quelle que soit la source :
- Spotify : API Web (si l'interface est connectée à Spotify) ;
- AirPlay et Bluetooth : MPRIS via playerctl (shairport-sync et mpris-proxy) ; la commande est relayée
  à l'iPhone ou au téléphone ;
- musique du diaporama : pause et reprise, transmises au diaporama par un petit fichier de commande ;
- volume général du cadre (PipeWire, wpctl) : s'applique à toutes les sources.
"""
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from utils import now_playing, spotify

COMMAND_FILE = Path("/tmp/pimmich_music_command.json")
ACTIONS = ("previous", "pause", "play", "next")
SINK = "@DEFAULT_AUDIO_SINK@"


def _run(*args, timeout=6):
    try:
        return subprocess.run(list(args), capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None


# --- Volume général ---

def get_volume():
    """Volume du cadre en % (None si PipeWire ne répond pas), et sourdine."""
    result = _run("wpctl", "get-volume", SINK)
    match = re.search(r"Volume:\s*([\d.]+)", result.stdout if result else "")
    if not match:
        return None, False
    return round(float(match.group(1)) * 100), "MUTED" in result.stdout


def set_volume(percent):
    percent = max(0, min(100, int(percent)))
    result = _run("wpctl", "set-volume", SINK, f"{percent / 100:.2f}")
    _run("wpctl", "set-mute", SINK, "0")
    return result is not None and result.returncode == 0


# --- Lecteurs MPRIS (AirPlay, Bluetooth) ---

def _mpris_player(source):
    """Nom du lecteur playerctl correspondant à la source (AirPlay : ShairportSync ; Bluetooth : mpris-proxy)."""
    if not shutil.which("playerctl"):
        return None
    result = _run("playerctl", "--list-all")
    players = [p.strip() for p in (result.stdout if result else "").splitlines() if p.strip()]
    for player in players:
        is_airplay = "shairport" in player.lower()
        if (source == "airplay" and is_airplay) or (source == "bluetooth" and not is_airplay and "spotify" not in player.lower()):
            return player
    return None


# --- Commandes ---

def actions_for(source):
    """Commandes disponibles pour la source qui joue."""
    if source == "spotify":
        return list(ACTIONS) if spotify.connected() else []
    if source in ("airplay", "bluetooth"):
        return list(ACTIONS) if _mpris_player(source) else []
    if source in ("pimmich", "radio"):
        return ["pause", "play"]
    return []


def control(source, action):
    """Envoie la commande à la source ; renvoie un code d'erreur (ou None si c'est fait)."""
    if action not in ACTIONS:
        return "invalid_action"
    if source == "spotify":
        try:
            spotify.control("resume" if action == "play" else action)
        except spotify.SpotifyError as e:
            return str(e)
        except Exception:
            return "unreachable"
        return None
    if source in ("airplay", "bluetooth"):
        player = _mpris_player(source)
        if not player:
            return "unsupported"
        result = _run("playerctl", "--player", player, action)
        return None if result is not None and result.returncode == 0 else "unreachable"
    if source == "radio":
        from utils import radio
        if action not in ("pause", "play"):
            return "unsupported"
        if not radio.set_paused(action == "pause"):
            return "unreachable"
        now_playing.update("radio", state="paused" if action == "pause" else "playing")
        return None
    if source == "pimmich":
        if action not in ("pause", "play"):
            return "unsupported"
        COMMAND_FILE.write_text(json.dumps({"action": action, "at": time.time()}))
        now_playing.update("pimmich", state="paused" if action == "pause" else "playing")
        return None
    return "unsupported"


def pop_command(max_age=30):
    """Commande en attente pour la musique du diaporama (lue par le diaporama), sinon None."""
    try:
        data = json.loads(COMMAND_FILE.read_text())
        COMMAND_FILE.unlink(missing_ok=True)
    except (OSError, ValueError):
        return None
    return data.get("action") if time.time() - data.get("at", 0) < max_age else None
