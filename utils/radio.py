"""
Radios internet et podcasts, joués par mpv sur la sortie son du cadre (PipeWire).

- Radios prêtes à l'emploi, recherche dans l'annuaire libre radio-browser.info, favoris ;
- podcasts : flux RSS, lecture du dernier épisode ;
- le titre diffusé (métadonnées ICY) est transmis au lecteur affiché à l'écran et à la télécommande.
"""
import json
import os
import socket
import subprocess
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

from utils import now_playing

SOCKET = "/tmp/pimmich-radio.sock"
STATE_FILE = Path("/tmp/pimmich_radio.json")
DIRECTORY = "https://de1.api.radio-browser.info"
USER_AGENT = "Pimmich/1.0 (cadre photo)"

STATIONS = [
    {"name": "FIP", "url": "https://icecast.radiofrance.fr/fip-hifi.aac", "genre": "Éclectique"},
    {"name": "France Inter", "url": "https://icecast.radiofrance.fr/franceinter-hifi.aac", "genre": "Généraliste"},
    {"name": "France Culture", "url": "https://icecast.radiofrance.fr/franceculture-hifi.aac", "genre": "Culture"},
    {"name": "France Musique", "url": "https://icecast.radiofrance.fr/francemusique-hifi.aac", "genre": "Classique"},
    {"name": "FIP Jazz", "url": "https://icecast.radiofrance.fr/fipjazz-hifi.aac", "genre": "Jazz"},
    {"name": "FIP Groove", "url": "https://icecast.radiofrance.fr/fipgroove-hifi.aac", "genre": "Groove"},
    {"name": "Radio Nova", "url": "https://novazz.ice.infomaniak.ch/novazz-128.mp3", "genre": "Éclectique"},
    {"name": "TSF Jazz", "url": "https://tsfjazz.ice.infomaniak.ch/tsfjazz-high.mp3", "genre": "Jazz"},
    {"name": "Radio Classique", "url": "https://radioclassique.ice.infomaniak.ch/radioclassique-high.mp3", "genre": "Classique"},
    {"name": "Mouv'", "url": "https://icecast.radiofrance.fr/mouv-hifi.aac", "genre": "Hip-hop"},
]
_poller = {"thread": None}


def _valid_url(url):
    return isinstance(url, str) and url.startswith(("http://", "https://")) and len(url) < 1000 and not any(c in url for c in "\n\r ")


def _load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def _ipc(*command):
    """Commande à mpv par sa socket de contrôle, sinon None."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(2)
            sock.connect(SOCKET)
            sock.sendall((json.dumps({"command": list(command)}) + "\n").encode())
            data = sock.recv(65536).decode(errors="replace")
    except OSError:
        return None
    for line in data.splitlines():
        try:
            reply = json.loads(line)
        except ValueError:
            continue
        if "error" in reply:
            return reply.get("data") if reply["error"] == "success" else None
    return None


def playing():
    """Ce que joue la radio en ce moment : {name, url, kind, paused}, sinon None."""
    state = _load_state()
    pid = state.get("pid")
    if not pid:
        return None
    try:
        os.kill(pid, 0)  # le lecteur tourne-t-il encore ?
    except OSError:
        return None
    paused = _ipc("get_property", "pause")
    return dict(state, paused=bool(paused))


def stop():
    state = _load_state()
    if state.get("pid"):
        try:
            subprocess.run(["kill", str(state["pid"])], capture_output=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            pass
    STATE_FILE.unlink(missing_ok=True)
    now_playing.update("radio", state="stopped")


def play(url, name, kind="radio", volume=80, mpv="mpv"):
    """Lance une radio ou un épisode de podcast (remplace ce qui jouait)."""
    if not _valid_url(url):
        raise ValueError("Adresse invalide.")
    stop()
    proc = subprocess.Popen([mpv, "--no-video", "--no-terminal", "--really-quiet", f"--volume={int(volume)}",
                             f"--input-ipc-server={SOCKET}", "--cache=yes", url],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    STATE_FILE.write_text(json.dumps({"pid": proc.pid, "url": url, "name": name[:80], "kind": kind, "started": time.time()}))
    now_playing.update("radio", state="playing", title=name[:80], artist="", album="", cover=None, changed=time.time())
    _start_poller()
    return proc.pid


def set_paused(paused):
    return _ipc("set_property", "pause", bool(paused)) is not None or playing() is not None


def _start_poller():
    """Suit le titre diffusé (ICY) tant que la radio joue, pour le lecteur à l'écran."""
    if _poller["thread"] and _poller["thread"].is_alive():
        return

    def run():
        last = None
        while True:
            current = playing()
            if not current:
                now_playing.update("radio", state="stopped")
                return
            meta = _ipc("get_property", "metadata") or {}
            title = meta.get("icy-title") or meta.get("title") or ""
            state = "paused" if current.get("paused") else "playing"
            key = (title, state)
            if key != last:
                if title and title != current["name"]:
                    artist, _sep, song = title.partition(" - ")
                    now_playing.update("radio", state=state, title=(song or title)[:120], artist=(artist if song else current["name"])[:120])
                else:
                    now_playing.update("radio", state=state, title=current["name"], artist="")
                last = key
            time.sleep(8)
    _poller["thread"] = threading.Thread(target=run, daemon=True)
    _poller["thread"].start()


def search(query, limit=20):
    """Recherche de radios dans l'annuaire libre radio-browser.info."""
    query = (query or "").strip()[:80]
    if len(query) < 2:
        return []
    resp = requests.get(f"{DIRECTORY}/json/stations/search", timeout=10, headers={"User-Agent": USER_AGENT},
                        params={"name": query, "limit": limit, "hidebroken": "true", "order": "clickcount", "reverse": "true"})
    resp.raise_for_status()
    stations = []
    for s in resp.json():
        url = s.get("url_resolved") or s.get("url")
        if _valid_url(url):
            stations.append({"name": (s.get("name") or "").strip()[:80], "url": url, "genre": (s.get("tags") or "").split(",")[0][:30],
                             "country": s.get("countrycode") or "", "logo": s.get("favicon") or None})
    return stations


def latest_episode(feed_url):
    """Dernier épisode d'un podcast (flux RSS) : {title, url, show}."""
    if not _valid_url(feed_url):
        raise ValueError("Adresse invalide.")
    resp = requests.get(feed_url, timeout=15, headers={"User-Agent": USER_AGENT}, stream=True)
    resp.raise_for_status()
    content = resp.raw.read(5_000_000 + 1, decode_content=True)  # flux démesuré : refusé
    if len(content) > 5_000_000 or b"<!ENTITY" in content[:5000]:  # pas d'entités XML (expansion abusive)
        raise ValueError("Flux trop volumineux ou invalide.")
    root = ET.fromstring(content)
    channel = root.find("channel")
    if channel is None:
        raise ValueError("Ce n'est pas un flux de podcast.")
    show = (channel.findtext("title") or "").strip()
    for item in channel.findall("item"):
        enclosure = item.find("enclosure")
        if enclosure is not None and _valid_url(enclosure.get("url")):
            return {"title": (item.findtext("title") or "").strip()[:150], "url": enclosure.get("url"), "show": show[:80]}
    raise ValueError("Aucun épisode trouvé.")
