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
        if not sink and output == "hdmi" and repair_hdmi_audio():
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


def _hdmi_connectors():
    import glob
    return [p for p in glob.glob("/sys/class/drm/card*-HDMI-A-*/status")]


def hdmi_audio_missing():
    """Un écran HDMI est branché, mais PipeWire n'a pas de sortie son HDMI (écran mal lu au démarrage du Pi)."""
    connected = False
    for status in _hdmi_connectors():
        try:
            connected = connected or open(status).read().strip() == "connected"
        except OSError:
            continue
    if not connected:
        return False
    try:
        return not any(_matches(s, "hdmi") for s in _list_sinks())
    except (OSError, subprocess.SubprocessError, ValueError):
        return False


def repair_hdmi_audio():
    """
    Écran éteint (ou en veille) au démarrage du Pi : ses informations (EDID) ne sont pas lues, et le son HDMI
    n'existe pas. On redemande l'écran, puis on relance WirePlumber pour qu'il retrouve la sortie HDMI.
    """
    import time
    if not hdmi_audio_missing():
        return False
    for status in _hdmi_connectors():
        subprocess.run(["sudo", "-n", "sh", "-c", f"echo detect > {status}"], capture_output=True, timeout=10)
    time.sleep(2)
    subprocess.run(["systemctl", "--user", "restart", "wireplumber"], capture_output=True, timeout=30)
    time.sleep(4)
    fixed = not hdmi_audio_missing()
    logger.info("🔊 Son HDMI retrouvé (écran relu)." if fixed else "🔊 Son HDMI toujours absent : l'écran est-il allumé ?")
    return fixed
