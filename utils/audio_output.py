"""
Sélection de la sortie audio (HDMI ou jack) via PipeWire.

On change la sortie par défaut du système : elle s'applique ainsi aux vidéos (mpv)
comme à la musique de fond (pygame), et WirePlumber la mémorise pour les redémarrages.
"""
import json
import logging
import subprocess

logger = logging.getLogger("pimmich.audio_output")


def _list_sinks():
    """Retourne les sorties audio PipeWire : [{'id', 'name', 'card'}]."""
    result = subprocess.run(["pw-dump"], capture_output=True, text=True, timeout=10)
    sinks = []
    for obj in json.loads(result.stdout or "[]"):
        props = (obj.get("info") or {}).get("props") or {}
        if props.get("media.class") == "Audio/Sink":
            sinks.append({"id": obj["id"], "name": props.get("node.name", ""), "card": props.get("alsa.card_name", "")})
    return sinks


def _matches(sink, output):
    text = f"{sink['name']} {sink['card']}".lower()
    if output == "hdmi":
        return "hdmi" in text
    if output == "jack":
        return "headphones" in text or "bcm2835" in text
    return False


def apply_audio_output(output):
    """
    Bascule la sortie audio par défaut sur 'hdmi' ou 'jack' et la règle à 100 %
    (le volume se règle ensuite dans Pimmich). 'auto' laisse le réglage du système.
    """
    if output not in ("hdmi", "jack"):
        return
    try:
        sink = next((s for s in _list_sinks() if _matches(s, output)), None)
        if not sink:
            logger.warning(f"🔊 Aucune sortie audio '{output}' trouvée, sortie par défaut du système conservée.")
            return
        subprocess.run(["wpctl", "set-default", str(sink["id"])], check=True, capture_output=True, timeout=10)
        subprocess.run(["wpctl", "set-volume", str(sink["id"]), "1.0"], check=False, capture_output=True, timeout=10)
        subprocess.run(["wpctl", "set-mute", str(sink["id"]), "0"], check=False, capture_output=True, timeout=10)
        logger.info(f"🔊 Sortie audio réglée sur {output} ({sink['name']}).")
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        logger.warning(f"🔊 Impossible de régler la sortie audio sur {output} : {e}")
