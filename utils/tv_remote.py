"""
Télécommande de la télévision (HDMI-CEC) : les touches de la télécommande pilotent le cadre.

La TV envoie ses touches par le câble HDMI quand le cadre est l'entrée choisie ; le noyau du Raspberry Pi les
présente comme un petit clavier (« vc4-hdmi »). Ce clavier est lu par l'application web, toujours lancée (comme le
bouton physique), pour pouvoir aussi réveiller le cadre ; il est réservé au cadre (EVIOCGRAB) pour que le diaporama
ne reçoive pas chaque touche une seconde fois.

    ▶ / ◀ (et avance, retour, chaîne + / -)   photo suivante / précédente
    OK, lecture, pause                          pause / reprise
    ▲ ou touche rouge                           ❤️ sur la photo affichée
    touche bleue                                « je pense à toi » vers les autres cadres de la famille
    stop, retour, sortie                        mise en veille du cadre
    n'importe quelle touche (cadre en veille)   réveil
"""
import fcntl
import os
import re
import struct
import time
from pathlib import Path

EVENT_FORMAT = "llHHi"  # struct input_event (temps, type, code, valeur)
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)
EV_KEY = 1
EVIOCGRAB = 0x40044590
DEVICES_FILE = "/proc/bus/input/devices"
STATE = {"device": None, "last_key": None, "last_action": None, "at": None, "error": None}  # pour l'interface

ACTIONS = {
    106: "next", 208: "next", 163: "next", 402: "next",          # droite, avance rapide, piste suivante, chaîne +
    105: "previous", 168: "previous", 165: "previous", 403: "previous",  # gauche, retour rapide, piste précédente, chaîne -
    352: "pause", 353: "pause", 28: "pause", 207: "pause", 119: "pause", 164: "pause", 201: "pause",  # OK, lecture, pause
    103: "love", 398: "love",                                     # haut, touche rouge
    401: "heart",                                                 # touche bleue : « je pense à toi » aux autres cadres
    128: "sleep", 158: "sleep", 174: "sleep", 1: "sleep",         # stop, retour, sortie, échap
}


def find_device(devices_file=DEVICES_FILE):
    """Clavier CEC de la prise HDMI (/dev/input/eventN), ou None."""
    try:
        text = Path(devices_file).read_text()
    except OSError:
        return None
    for block in text.split("\n\n"):
        name = re.search(r'^N: Name="([^"]*)"', block, re.M)
        sysfs = re.search(r"^S: Sysfs=(\S+)", block, re.M)
        handler = re.search(r"^H: Handlers=.*\b(event\d+)\b", block, re.M)
        if name and sysfs and handler and "/rc/" in sysfs.group(1) and "hdmi" in name.group(1).lower():
            return f"/dev/input/{handler.group(1)}"
    return None


def action_for(code):
    return ACTIONS.get(code)


def decode(data):
    """Touches enfoncées (codes) contenues dans un bloc lu sur le clavier ; les répétitions sont ignorées."""
    codes = []
    for offset in range(0, len(data) - EVENT_SIZE + 1, EVENT_SIZE):
        _sec, _usec, kind, code, value = struct.unpack_from(EVENT_FORMAT, data, offset)
        if kind == EV_KEY and value == 1:
            codes.append(code)
    return codes


def listen(path, on_key, grab=True):
    """Lit le clavier jusqu'à une erreur (appareil disparu) : on_key(code) à chaque touche enfoncée."""
    fd = os.open(path, os.O_RDONLY)
    try:
        if grab:
            try:
                fcntl.ioctl(fd, EVIOCGRAB, 1)
            except OSError:
                pass  # déjà réservé : les touches arrivent quand même
        while True:
            data = os.read(fd, EVENT_SIZE * 16)
            if not data:
                return
            for code in decode(data):
                on_key(code)
    finally:
        os.close(fd)


def note(code, action):
    STATE.update(last_key=code, last_action=action, at=time.time())
