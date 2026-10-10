"""
Morceau en cours de lecture, quelle que soit la source :
- « spotify » : librespot (Spotify Connect) appelle `utils/librespot_event.sh` à chaque événement ;
- « airplay » : shairport-sync écrit ses métadonnées dans un tube, lu par `python -m utils.now_playing airplay` ;
- « bluetooth » : titres AVRCP du téléphone, transmis par utils/bluetooth_receiver.py ;
- « pimmich » : la musique de fond du diaporama (local_slideshow.py).
L'état est partagé par un petit fichier JSON (lu par le diaporama et l'interface d'administration).
Bibliothèque standard uniquement : le module est lancé par librespot, hors de l'application.
"""
import base64
import fcntl
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

STATE_FILE = Path("/tmp/pimmich_now_playing.json")
COVER_DIR = Path("/tmp/pimmich_covers")
AIRPLAY_PIPE = Path("/tmp/shairport-sync-metadata")
SOURCES = ("spotify", "airplay", "bluetooth", "pimmich")
EXTERNAL = ("spotify", "airplay", "bluetooth")


def _load():
    try:
        data = json.loads(STATE_FILE.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def update(source, **fields):
    """Met à jour l'état d'une source (verrou : plusieurs processus écrivent). Faux si l'écriture échoue."""
    try:
        _update(source, fields)
        return True
    except OSError:
        return False


def _update(source, fields):
    lock_path = STATE_FILE.with_suffix(".lock")
    with open(lock_path, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = _load()
        entry = dict(data.get(source) or {})
        if "title" in fields and fields["title"] != entry.get("title"):
            fields.setdefault("changed", time.time())  # nouveau morceau : affiché quelques secondes
        entry.update(fields, updated=time.time())
        data[source] = entry
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False))
        tmp.replace(STATE_FILE)


def current(exclude=()):
    """Le morceau qui joue (la source extérieure la plus récente passe avant la musique du diaporama), sinon None."""
    playing = [dict(entry, source=source) for source, entry in _load().items()
               if source in SOURCES and source not in exclude and isinstance(entry, dict)
               and entry.get("state") == "playing" and entry.get("title")]
    if not playing:
        return None
    playing.sort(key=lambda e: (e["source"] in EXTERNAL, e.get("changed", 0)), reverse=True)
    return playing[0]


def external_playing():
    """Vrai si Spotify ou AirPlay joue (la musique du diaporama se met alors en pause)."""
    return any(_load().get(s, {}).get("state") == "playing" for s in EXTERNAL)


def pretty_title(filename):
    """« ma_musique-douce.mp3 » -> « ma musique douce » (musique du diaporama, sans étiquettes)."""
    return re.sub(r"[_\-]+", " ", Path(filename).stem).strip() or Path(filename).name


def _save_cover(source, data, key):
    COVER_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{source}_{hashlib.sha1(key.encode()).hexdigest()[:16]}.jpg"
    path = COVER_DIR / name
    if not path.exists():
        path.write_bytes(data)
    for old in COVER_DIR.glob(f"{source}_*.jpg"):  # une seule pochette gardée par source
        if old != path:
            old.unlink(missing_ok=True)
    return str(path)


# --- Spotify (librespot --onevent) ---

def _download_cover(urls, track_id):
    urls = [u for u in urls if u.startswith("https://")]
    if not urls:
        return None
    url = urls[1] if len(urls) > 1 else urls[0]  # taille moyenne (environ 300 px)
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return _save_cover("spotify", resp.read(3_000_000), track_id or url)
    except OSError:
        return None


def handle_librespot_event(env):
    """Traduit un événement de librespot (variables d'environnement) en état « en cours de lecture »."""
    event = env.get("PLAYER_EVENT", "")
    if event == "track_changed":
        artists = env.get("ARTISTS") or env.get("SHOW_NAME") or ""
        update("spotify", title=env.get("NAME", ""), artist=", ".join(a for a in artists.splitlines() if a),
               album=env.get("ALBUM", ""), cover=_download_cover((env.get("COVERS") or "").split(), env.get("TRACK_ID", "")),
               changed=time.time())
    elif event in ("playing", "started"):
        update("spotify", state="playing")
    elif event == "paused":
        update("spotify", state="paused")
    elif event in ("stopped", "session_disconnected", "unavailable"):
        update("spotify", state="stopped")


# --- AirPlay (tube de métadonnées de shairport-sync) ---

_ITEM = re.compile(rb"<item><type>([0-9a-f]{8})</type><code>([0-9a-f]{8})</code><length>(\d+)</length>"
                   rb"(?:\s*<data encoding=\"base64\">\s*([A-Za-z0-9+/=\s]*?)</data>)?\s*</item>")


def parse_airplay_items(buffer):
    """Découpe le flux du tube : ([(type, code, données)], reste non encore complet)."""
    items, end = [], 0
    for match in _ITEM.finditer(buffer):
        kind, code = bytes.fromhex(match.group(1).decode()).decode("latin-1"), bytes.fromhex(match.group(2).decode()).decode("latin-1")
        data = base64.b64decode(re.sub(rb"\s", b"", match.group(4))) if match.group(4) else b""
        items.append((kind, code, data))
        end = match.end()
    return items, buffer[end:]


class AirplayTracker:
    """Assemble les métadonnées d'un morceau AirPlay et suit l'état de lecture."""
    TEXT = {"minm": "title", "asar": "artist", "asal": "album"}

    def __init__(self):
        self.pending = {}

    def feed(self, kind, code, data):
        if kind == "core" and code in self.TEXT:
            self.pending[self.TEXT[code]] = data.decode("utf-8", "replace").strip()
        elif kind == "ssnc" and code == "mden" and self.pending.get("title"):  # fin d'un lot de métadonnées
            update("airplay", **self.pending)
            self.pending = {}
        elif kind == "ssnc" and code == "PICT" and len(data) > 100:
            update("airplay", cover=_save_cover("airplay", data, hashlib.sha1(data).hexdigest()))
        elif kind == "ssnc" and code in ("pbeg", "prsm"):
            update("airplay", state="playing")
        elif kind == "ssnc" and code in ("pfls", "paus"):
            update("airplay", state="paused")
        elif kind == "ssnc" and code == "pend":
            update("airplay", state="stopped")


def follow_airplay_pipe(pipe=AIRPLAY_PIPE):
    """Lit le tube de shairport-sync sans fin (service pimmich-airplay-meta)."""
    tracker = AirplayTracker()
    while True:
        try:
            if not pipe.exists():
                os.mkfifo(pipe)
            with open(pipe, "rb") as stream:  # attend que shairport-sync ouvre le tube
                buffer = b""
                while chunk := stream.read1(65536):
                    buffer += chunk
                    items, buffer = parse_airplay_items(buffer)
                    for item in items:
                        tracker.feed(*item)
                    buffer = buffer[-4_000_000:]  # garde-fou (pochette en cours de réception)
        except OSError:
            time.sleep(5)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "spotify":
        handle_librespot_event(os.environ)
    elif command == "airplay":
        follow_airplay_pipe()
    else:
        print("Usage : python -m utils.now_playing spotify|airplay", file=sys.stderr)
        sys.exit(2)
