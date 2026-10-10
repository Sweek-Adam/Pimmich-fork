"""Notifications sur le téléphone (ntfy) : réglages, envoi, anti-répétition, alertes des invités."""
import io

import pytest

from utils import notify

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}


@pytest.fixture()
def sent(monkeypatch):
    posts = []

    class Now:  # envoi synchrone pour les tests
        def __init__(self, target, daemon=None):
            self.target = target

        def start(self):
            self.target()
    monkeypatch.setattr(notify.threading, "Thread", Now)
    monkeypatch.setattr(notify.requests, "post", lambda url, json, timeout: posts.append((url, json)))
    monkeypatch.setattr(notify, "_last_sent", {})
    return posts


def test_send_only_when_enabled_and_not_repeated(sent):
    config = {"notify_enabled": True, "notify_topic": "pimmich-abc"}
    assert notify.send(config, "guest", "Nouvelle photo d'invité", "2 photo(s) à valider", key="k")
    assert not notify.send(config, "guest", "Nouvelle photo d'invité", "encore", key="k")  # pas de répétition
    assert not notify.send(config, "imports", "Import terminé", "x")  # désactivé par défaut
    assert not notify.send({}, "guest", "t", "m")  # notifications désactivées
    url, payload = sent[0]
    assert url == "https://ntfy.sh" and payload["topic"] == "pimmich-abc" and payload["title"] == "Nouvelle photo d'invité"


def test_settings_api(admin_client, sent):
    from utils.config_manager import load_config
    r = admin_client.post("/api/notify", json={"enabled": True, "events": {"imports": True, "inconnu": True}}, headers=SAME_ORIGIN).get_json()
    assert r["success"]
    config = load_config()
    assert config["notify_topic"].startswith("pimmich-") and config["notify_events"] == {"imports": True}
    data = admin_client.get("/api/notify").get_json()
    assert data["url"].endswith(config["notify_topic"]) and data["app_url"].startswith("ntfy://")
    assert admin_client.post("/api/notify/test", headers=SAME_ORIGIN).get_json()["success"] and sent
    assert admin_client.get("/api/notify/qr.png").mimetype == "image/png"
    assert admin_client.post("/api/notify", json={"server": "ftp://x"}, headers=SAME_ORIGIN).status_code == 400
    admin_client.post("/api/notify", json={"enabled": False}, headers=SAME_ORIGIN)


def test_guest_upload_notifies(client, sent, sandbox):
    from utils.config_manager import load_config, save_config
    config = dict(load_config())
    config.update(notify_enabled=True, notify_topic="pimmich-xyz")
    save_config(config)
    data = {"photos": (io.BytesIO(b"\xff\xd8\xff photo"), "vacances.jpg")}
    client.post("/handle_upload", data=data, content_type="multipart/form-data", headers=SAME_ORIGIN)
    assert sent and sent[-1][1]["title"] == "Nouvelle photo d'invité" and "à valider" in sent[-1][1]["message"]
    config.update(notify_enabled=False)
    save_config(config)
