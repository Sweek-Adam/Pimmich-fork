"""Invités de confiance : une photo validée avec « toujours accepter cet appareil », puis les suivantes passent seules."""
import io

import pytest

from utils import trusted_guests

SAME = {"Sec-Fetch-Site": "same-origin"}


@pytest.fixture
def isolated(monkeypatch, tmp_path, sandbox):
    from utils.config_manager import load_config, save_config
    monkeypatch.setattr(trusted_guests, "META_FILE", tmp_path / "meta.json")
    original = dict(load_config())
    yield
    save_config(original)


def test_trusted_device_skips_validation(client, admin_client, isolated, monkeypatch):
    from web import routes_guests
    approved = []
    monkeypatch.setattr(routes_guests, "approve_pending", lambda path: approved.append(path) or (True, "ok"))
    monkeypatch.setattr(routes_guests.threading, "Thread", lambda target, **k: type("T", (), {"start": lambda self: target()})())
    client.get("/upload")
    device = client.get_cookie(trusted_guests.COOKIE).value
    assert trusted_guests.valid(device)
    client.post("/handle_upload", data={"photos": (io.BytesIO(b"\xff\xd8 jpeg"), "plage.jpg"), "name": "Léa"},
                content_type="multipart/form-data", headers=SAME)
    pending = admin_client.get("/api/get_pending_photos").get_json()
    mine = [f for f in pending["photos"] if f.startswith("plage_")]
    assert mine and pending["meta"][mine[0]] == {"name": "Léa", "device": True} and approved == []
    r = admin_client.post("/api/manage_pending_photo", json={"filename": mine[0], "action": "trust"}, headers=SAME).get_json()
    assert r["success"] and len(approved) == 1
    trusted = admin_client.get("/api/trusted_guests").get_json()["trusted"]
    assert trusted[0]["label"] == "Léa" and trusted[0]["id"] == device
    # Photo suivante depuis le même téléphone : validée d'office
    client.post("/handle_upload", data={"photos": (io.BytesIO(b"\xff\xd8 jpeg"), "gateau.jpg")}, content_type="multipart/form-data", headers=SAME)
    assert len(approved) == 2 and "gateau_" in str(approved[1])
    assert admin_client.delete(f"/api/trusted_guests/{device}", headers=SAME).get_json()["success"]
    for f in routes_guests.PENDING_UPLOADS_DIR.glob("*"):
        if f.name.startswith(("plage_", "gateau_")):
            f.unlink()
