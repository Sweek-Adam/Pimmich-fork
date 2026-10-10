"""Musique : enceinte Bluetooth (bluetoothctl simulé) et compte Spotify."""
import pytest

from utils import bluetooth_control as bt

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}

SHOW = "Controller B8:27:EB:76:7E:0B (public)\n\tName: Cadre-photo\n\tPowered: yes\n\tDiscoverable: no\n\tPairable: no\n"


@pytest.fixture()
def fake_bluetoothctl(monkeypatch):
    calls = []
    answers = {
        ("show",): SHOW,
        ("devices", "Paired"): "Device 11:22:33:44:55:66 Pixel de Léa\nDevice AA:BB:CC:DD:EE:FF Galaxy\n",
        ("info", "11:22:33:44:55:66"): "Device 11:22:33:44:55:66\n\tConnected: yes\n",
        ("info", "AA:BB:CC:DD:EE:FF"): "Device AA:BB:CC:DD:EE:FF\n\tConnected: no\n",
        ("discoverable", "on"): "Changing discoverable on succeeded\n",
        ("remove", "AA:BB:CC:DD:EE:FF"): "Device has been removed\n",
    }

    def ctl(*args, timeout=8):
        calls.append(args)
        return answers.get(args, "")
    monkeypatch.setattr(bt, "_ctl", ctl)
    return calls


def test_bluetooth_status_lists_paired_phones(fake_bluetoothctl):
    state = bt.status()
    assert state["available"] and state["powered"] and not state["discoverable"]
    assert state["devices"] == [{"mac": "11:22:33:44:55:66", "name": "Pixel de Léa", "connected": True},
                                {"mac": "AA:BB:CC:DD:EE:FF", "name": "Galaxy", "connected": False}]


def test_pairing_window_and_forget(fake_bluetoothctl):
    assert bt.open_pairing()
    assert ("discoverable-timeout", str(bt.PAIRING_SECONDS)) in fake_bluetoothctl
    assert bt.forget("AA:BB:CC:DD:EE:FF")
    with pytest.raises(ValueError):
        bt.forget("AA:BB; reboot")  # jamais d'argument arbitraire passé à bluetoothctl


def test_bluetooth_api(admin_client, fake_bluetoothctl, monkeypatch):
    from web import routes_music
    monkeypatch.setattr(routes_music, "_service_active", lambda name: True)
    data = admin_client.get("/api/bluetooth").get_json()
    assert data["service"] and len(data["devices"]) == 2
    assert admin_client.post("/api/bluetooth/pair", headers=SAME_ORIGIN).get_json()["success"]
    assert admin_client.post("/api/bluetooth/forget", json={"mac": "AA:BB:CC:DD:EE:FF"}, headers=SAME_ORIGIN).get_json()["success"]
    assert admin_client.post("/api/bluetooth/forget", json={"mac": "../../x"}, headers=SAME_ORIGIN).status_code == 400
    monkeypatch.setattr(routes_music, "_service_active", lambda name: False)
    assert admin_client.post("/api/bluetooth/pair", headers=SAME_ORIGIN).status_code == 400


def test_bluetooth_receiver_maps_avrcp_tracks():
    pytest.importorskip("dbus")
    from utils import bluetooth_receiver
    assert bluetooth_receiver.track_fields({"Title": "Titre", "Artist": "Artiste"})["title"] == "Titre"


# --- Spotify ---

class FakeResponse:
    def __init__(self, status=200, data=None):
        self.status_code, self._data = status, data
        self.content = b"" if data is None else b"{}"

    def json(self):
        return self._data or {}


@pytest.fixture()
def sp(tmp_path, monkeypatch):
    from utils import spotify
    monkeypatch.setattr(spotify, "STATE_DIR", tmp_path / "pimmich")
    monkeypatch.setattr(spotify, "_systemctl", lambda *args: None)
    return spotify


def test_frame_linked_with_a_pairing_code(sp, tmp_path, monkeypatch):
    """Faux librespot : affiche le code, puis « Spotify » valide et les identifiants apparaissent."""
    fake = tmp_path / "librespot"
    fake.write_text("#!/bin/sh\n"
                    "echo 'Browse to: https://spotify.com/pair?code=ABC123'\necho 'If prompted, enter code: ABC123'\n"
                    "while [ \"$1\" != --system-cache ]; do shift; done\n"
                    "sleep 1; echo '{\"username\": \"lea\"}' > \"$2/credentials.json\"; sleep 30\n")
    fake.chmod(0o755)
    restarts = []
    monkeypatch.setattr(sp, "_systemctl", lambda *args: restarts.append(args))
    started = sp.start_link(librespot=str(fake))
    assert started == {"url": "https://spotify.com/pair?code=ABC123", "code": "ABC123"}
    assert sp.link_status()["pending"]
    for _ in range(50):
        if ("restart", sp.SERVICE) in restarts:
            break
        __import__("time").sleep(0.2)
    status = sp.link_status()
    assert status["linked"] and status["account"] == "lea" and not status["pending"]
    sp.unlink()
    assert not sp.link_status()["linked"]


def test_pkce_and_tokens_refresh(sp, monkeypatch):
    import base64, hashlib
    verifier, challenge = sp.pkce_pair()
    assert challenge == base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    posts = []

    def post(url, data, timeout):
        posts.append(data)
        return FakeResponse(200, {"access_token": f"tok{len(posts)}", "refresh_token": "r1", "expires_in": 3600})
    monkeypatch.setattr(sp.requests, "post", post)
    sp.exchange_code("a" * 32, "code", "https://cadre/spotify/callback", verifier)
    assert sp.connected() and sp._access_token() == "tok1"
    assert oct(sp.tokens_file().stat().st_mode)[-3:] == "600"
    tokens = sp._load_tokens(); tokens["expires_at"] = 0
    sp.tokens_file().write_text(__import__("json").dumps(tokens))
    assert sp._access_token() == "tok2" and posts[-1]["grant_type"] == "refresh_token"


def test_play_on_the_frame_device(sp, monkeypatch):
    calls = []

    def api(method, path, **kw):
        calls.append((method, path, kw.get("json")))
        return {"devices": [{"id": "d1", "name": "Cadre photo"}]} if path == "/me/player/devices" else {}
    monkeypatch.setattr(sp, "api", api)
    sp.play_on_frame("spotify:playlist:37i9dQZF1DXcBWIGoYBM5M")
    assert ("PUT", "/me/player/play?device_id=d1", {"context_uri": "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"}) in calls
    with pytest.raises(sp.SpotifyError):
        sp.play_on_frame("javascript:alert(1)")
    monkeypatch.setattr(sp, "api", lambda method, path, **kw: {"devices": []})
    with pytest.raises(sp.SpotifyError, match="no_device"):
        sp.play_on_frame("spotify:playlist:37i9dQZF1DXcBWIGoYBM5M")


def test_spotify_settings_api(admin_client, sp, monkeypatch):
    from utils.config_manager import load_config
    status = admin_client.get("/api/spotify").get_json()
    assert not status["connected"] and status["redirect_uri"].startswith("https://") and status["redirect_uri"].endswith("/spotify/callback")
    assert admin_client.post("/api/spotify/client_id", json={"client_id": "pas-bon"}, headers=SAME_ORIGIN).status_code == 400
    assert admin_client.post("/api/spotify/client_id", json={"client_id": "A" * 32}, headers=SAME_ORIGIN).get_json()["success"]
    resp = admin_client.get("/spotify/login")
    assert resp.status_code == 302 and "code_challenge=" in resp.headers["Location"] and "client_id=" + "a" * 32 in resp.headers["Location"]
    resp = admin_client.get("/spotify/callback?code=x&state=faux")  # état différent : refusé
    assert resp.status_code == 302 and not sp.connected()
    assert admin_client.post("/api/spotify/links", json={"key": "ambiance:fete", "uri": "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"}, headers=SAME_ORIGIN).get_json()["success"]
    assert load_config()["spotify_links"] == {"ambiance:fete": "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"}
    assert admin_client.post("/api/spotify/links", json={"key": "ambiance:inconnue", "uri": ""}, headers=SAME_ORIGIN).status_code == 400
    assert admin_client.post("/api/spotify/links", json={"key": "ambiance:fete", "uri": "http://x"}, headers=SAME_ORIGIN).status_code == 400
    monkeypatch.setattr(sp, "playlists", lambda: [{"name": "Été", "uri": "spotify:playlist:abc1234567", "image": None, "tracks": 3}])
    assert admin_client.get("/api/spotify/playlists").get_json()["playlists"][0]["name"] == "Été"
    resp = admin_client.post("/api/spotify/control", json={"action": "next"}, headers=SAME_ORIGIN)  # pas encore connecté
    assert resp.status_code == 400 and resp.get_json()["message"] == "Spotify n'est pas connecté."


def test_ambiance_starts_its_spotify_playlist(admin_client, sp, monkeypatch):
    from web import routes_home
    started = []
    monkeypatch.setattr(routes_home.spotify, "play_linked_in_background", lambda uri, logger=None: started.append(uri))
    admin_client.post("/api/spotify/links", json={"key": "ambiance:zen", "uri": "spotify:playlist:37i9dQZF1DWZqd5JICZI0u"}, headers=SAME_ORIGIN)
    admin_client.post("/api/ambiance", json={"ambiance": "zen"}, headers=SAME_ORIGIN)
    assert started == ["spotify:playlist:37i9dQZF1DWZqd5JICZI0u"]
    admin_client.post("/api/ambiance", json={"ambiance": "perso"}, headers=SAME_ORIGIN)
