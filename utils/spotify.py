"""
Spotify depuis l'interface d'administration.

1. Association du cadre au compte (librespot, connexion par code sur spotify.com/pair) : le cadre apparaît
   dans les appareils Spotify du compte, même hors du Wi-Fi de la maison.
2. Pilotage par l'API Web de Spotify (application personnelle créée sur developer.spotify.com, connexion
   OAuth avec PKCE : seul l'identifiant client est nécessaire) : playlists, lecture sur le cadre, commandes.

Les identifiants sont rangés hors du dossier de Pimmich (jamais dans les sauvegardes) : ~/.config/pimmich.
"""
import base64
import hashlib
import json
import os
import re
import secrets
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

STATE_DIR = Path(os.environ.get("PIMMICH_SPOTIFY_DIR", Path.home() / ".config" / "pimmich"))
DEVICE_NAME = "Cadre photo"
SERVICE = "pimmich-spotify"
SCOPES = "playlist-read-private playlist-read-collaborative user-read-playback-state user-modify-playback-state"
API = "https://api.spotify.com/v1"
ACCOUNTS = "https://accounts.spotify.com"
CLIENT_ID = re.compile(r"^[0-9a-f]{32}$")
URI = re.compile(r"^spotify:(playlist|album|artist|show):[A-Za-z0-9]{10,40}$")
LINK_TIMEOUT = 600


class SpotifyError(Exception):
    pass


def _private_dir(path):
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def connect_cache():
    return STATE_DIR / "spotify-connect"


def tokens_file():
    return STATE_DIR / "spotify_tokens.json"


# --- 1. Association du cadre (librespot) ---

_link = {"proc": None, "url": None, "code": None, "error": None, "started": 0}
_link_lock = threading.Lock()


def _systemctl(*args):
    try:
        subprocess.run(["systemctl", "--user", *args], capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        pass


def linked_account():
    """Compte Spotify auquel le cadre est associé (identifiants mémorisés par librespot), sinon None."""
    try:
        data = json.loads((connect_cache() / "credentials.json").read_text())
        return data.get("username") or "?"
    except (OSError, ValueError):
        return None


def link_status():
    with _link_lock:
        running = bool(_link["proc"] and _link["proc"].poll() is None)
        return {"linked": linked_account() is not None, "account": linked_account(), "pending": running,
                "url": _link["url"] if running else None, "code": _link["code"] if running else None, "error": _link["error"]}


def _read_link_output(proc):
    for line in proc.stdout:
        if match := re.search(r"Browse to:\s*(https://\S+)", line):
            _link["url"] = match.group(1)
        if match := re.search(r"enter code:\s*(\S+)", line):
            _link["code"] = match.group(1)


def _wait_for_credentials(proc):
    """Attend la validation sur spotify.com/pair, puis relance le service avec les identifiants mémorisés."""
    deadline = time.time() + LINK_TIMEOUT
    credentials = connect_cache() / "credentials.json"
    while time.time() < deadline and proc.poll() is None and not credentials.exists():
        time.sleep(2)
    time.sleep(2 if credentials.exists() else 0)  # laisser librespot finir d'écrire
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
    if not credentials.exists():
        _link["error"] = "timeout"
    _systemctl("restart", SERVICE)


def start_link(librespot="librespot"):
    """Lance la connexion par code : renvoie l'adresse et le code à saisir sur spotify.com/pair."""
    with _link_lock:
        if _link["proc"] and _link["proc"].poll() is None:
            return dict(url=_link["url"], code=_link["code"])
        _link.update(url=None, code=None, error=None, started=time.time())
        _systemctl("stop", SERVICE)  # même nom d'appareil : le service reprend une fois le compte associé
        cache = _private_dir(connect_cache())
        try:
            proc = subprocess.Popen([librespot, "--enable-device-auth", "--system-cache", str(cache), "--name", DEVICE_NAME,
                                     "--backend", "pulseaudio", "--disable-discovery"],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        except OSError as e:
            _systemctl("start", SERVICE)
            raise SpotifyError(f"librespot introuvable : {e}")
        _link["proc"] = proc
    threading.Thread(target=_read_link_output, args=(proc,), daemon=True).start()
    threading.Thread(target=_wait_for_credentials, args=(proc,), daemon=True).start()
    for _ in range(100):  # le code s'affiche en une ou deux secondes
        if _link["url"] or proc.poll() is not None:
            break
        time.sleep(0.2)
    if not _link["url"]:
        raise SpotifyError("Aucun code reçu de Spotify")
    return dict(url=_link["url"], code=_link["code"])


def unlink():
    """Oublie le compte associé au cadre (il redevient une enceinte visible seulement sur le Wi-Fi)."""
    (connect_cache() / "credentials.json").unlink(missing_ok=True)
    _systemctl("restart", SERVICE)


# --- 2. API Web de Spotify (PKCE) ---

def pkce_pair():
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def authorize_url(client_id, redirect_uri, state, challenge):
    return f"{ACCOUNTS}/authorize?" + urlencode({
        "client_id": client_id, "response_type": "code", "redirect_uri": redirect_uri, "scope": SCOPES,
        "state": state, "code_challenge_method": "S256", "code_challenge": challenge})


def _save_tokens(data, client_id, previous=None):
    tokens = {"client_id": client_id, "access_token": data["access_token"],
              "refresh_token": data.get("refresh_token") or (previous or {}).get("refresh_token"),
              "expires_at": time.time() + int(data.get("expires_in", 3600)) - 60}
    _private_dir(STATE_DIR)
    path = tokens_file()
    path.write_text(json.dumps(tokens))
    os.chmod(path, 0o600)
    return tokens


def exchange_code(client_id, code, redirect_uri, verifier):
    resp = requests.post(f"{ACCOUNTS}/api/token", timeout=15, data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri,
        "client_id": client_id, "code_verifier": verifier})
    if resp.status_code != 200:
        raise SpotifyError(f"Connexion refusée par Spotify ({resp.status_code})")
    return _save_tokens(resp.json(), client_id)


def _load_tokens():
    try:
        return json.loads(tokens_file().read_text())
    except (OSError, ValueError):
        return None


def connected():
    return _load_tokens() is not None


def disconnect():
    tokens_file().unlink(missing_ok=True)


def _access_token():
    tokens = _load_tokens()
    if not tokens:
        raise SpotifyError("not_connected")
    if time.time() < tokens.get("expires_at", 0):
        return tokens["access_token"]
    resp = requests.post(f"{ACCOUNTS}/api/token", timeout=15, data={
        "grant_type": "refresh_token", "refresh_token": tokens.get("refresh_token"), "client_id": tokens["client_id"]})
    if resp.status_code != 200:
        raise SpotifyError("expired")
    return _save_tokens(resp.json(), tokens["client_id"], tokens)["access_token"]


def api(method, path, **kwargs):
    resp = requests.request(method, API + path, timeout=15, headers={"Authorization": f"Bearer {_access_token()}"}, **kwargs)
    if resp.status_code == 404 and "/me/player" in path:
        raise SpotifyError("no_device")
    if resp.status_code == 403 and "/me/player" in path:
        raise SpotifyError("premium")
    if resp.status_code >= 400:
        raise SpotifyError(f"Spotify a répondu {resp.status_code}")
    return resp.json() if resp.content else {}


def playlists(limit=200):
    """Playlists du compte : [{name, uri, image, tracks}]."""
    items, path = [], "/me/playlists?limit=50"
    while path and len(items) < limit:
        data = api("GET", path)
        for p in data.get("items") or []:
            if not p:
                continue
            images = p.get("images") or []
            items.append({"name": p.get("name", ""), "uri": p.get("uri", ""), "image": images[-1]["url"] if images else None,
                          "tracks": (p.get("tracks") or p.get("items") or {}).get("total", 0)})
        nxt = data.get("next")
        path = nxt[len(API):] if nxt and nxt.startswith(API) else None
    return items


def frame_device_id(name=DEVICE_NAME):
    for device in api("GET", "/me/player/devices").get("devices", []):
        if device.get("name", "").lower() == name.lower():
            return device["id"]
    return None


def play_on_frame(uri, shuffle=True):
    """Lance une playlist (ou un album...) sur le cadre."""
    if not URI.match(uri or ""):
        raise SpotifyError("invalid_uri")
    device = frame_device_id()
    if not device:
        raise SpotifyError("no_device")
    try:
        api("PUT", f"/me/player/shuffle?state={'true' if shuffle else 'false'}&device_id={device}")
    except SpotifyError:
        pass  # le mode aléatoire n'est pas indispensable
    api("PUT", f"/me/player/play?device_id={device}", json={"context_uri": uri})


CONTROLS = {"pause": ("PUT", "/me/player/pause"), "resume": ("PUT", "/me/player/play"),
            "next": ("POST", "/me/player/next"), "previous": ("POST", "/me/player/previous")}


def control(action):
    if action not in CONTROLS:
        raise SpotifyError("invalid_action")
    method, path = CONTROLS[action]
    api(method, path)


def play_linked_in_background(uri, logger=None):
    """Lance la musique associée (ambiance, playlist de photos) sans faire attendre l'interface."""
    def run():
        try:
            play_on_frame(uri)
        except (SpotifyError, requests.RequestException) as e:
            if logger:
                logger.warning(f"[Spotify] Musique associée non lancée : {e}")
    if uri and connected():
        threading.Thread(target=run, daemon=True).start()
