"""Plusieurs cadres : code d'association, API protégée par ce code, pilotage d'un autre cadre."""
import io

import pytest
from PIL import Image

SAME = {"Sec-Fetch-Site": "same-origin"}


@pytest.fixture
def restore_config():
    from utils.config_manager import load_config, save_config
    original = dict(load_config())
    yield
    save_config(original)


def jpeg():
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), (10, 120, 200)).save(buffer, "JPEG")
    return buffer.getvalue()


def test_pairing_code_protects_the_frame_api(client, admin_client, restore_config, monkeypatch):
    from web import routes_frames
    codes = admin_client.post("/api/frame/pairing", json={"label": "Chez nous"}, headers=SAME).get_json()["codes"]
    token = codes[-1]["token"]
    assert len(token) > 20
    anonymous = client.application.test_client()
    assert anonymous.get("/api/frame/status").status_code == 401
    assert anonymous.get("/api/frame/status", headers={"X-Pimmich-Frame-Token": "faux"}).status_code == 401
    status = anonymous.get("/api/frame/status", headers={"X-Pimmich-Frame-Token": token}).get_json()
    assert status["success"] and "running" in status
    monkeypatch.setattr(routes_frames.threading, "Thread", lambda target, **k: type("T", (), {"start": lambda self: None})())
    r = anonymous.post("/api/frame/photos", data={"photos": (io.BytesIO(jpeg()), "noel.jpg"), "from": "Mamie"},
                       headers={"X-Pimmich-Frame-Token": token}, content_type="multipart/form-data").get_json()
    assert r["success"]
    assert anonymous.post("/api/frame/command", json={"action": "danse"}, headers={"X-Pimmich-Frame-Token": token}).status_code == 400
    admin_client.delete("/api/frame/pairing", json={"token": token}, headers=SAME)
    assert anonymous.get("/api/frame/status", headers={"X-Pimmich-Frame-Token": token}).status_code == 401


def test_pilot_another_frame(admin_client, restore_config, monkeypatch):
    from web import routes_frames
    remote = admin_client.application.test_client()  # l'« autre cadre » est ici la même application
    token = admin_client.post("/api/frame/pairing", json={}, headers=SAME).get_json()["codes"][-1]["token"]

    class Response:
        def __init__(self, r):
            self.status_code, self.ok, self.content, self._r = r.status_code, r.status_code < 400, r.data, r

        def json(self):
            return self._r.get_json()

    def fake_request(method, url, headers, timeout, verify, **kwargs):
        path = "/" + url.split("/", 3)[3]
        if "files" in kwargs:
            data = dict(kwargs.get("data") or {}, photos=[(f[1][1], f[1][0]) for f in kwargs["files"]])
            return Response(remote.open(path, method=method, headers=headers, data=data, content_type="multipart/form-data"))
        return Response(remote.open(path, method=method, headers=headers, json=kwargs.get("json")))
    monkeypatch.setattr(routes_frames.requests, "request", fake_request)
    monkeypatch.setattr(routes_frames.threading, "Thread", lambda target, **k: type("T", (), {"start": lambda self: None})())
    assert admin_client.post("/api/frames", json={"url": "pas une adresse", "token": token}, headers=SAME).status_code == 400
    assert admin_client.post("/api/frames", json={"url": "https://100.1.2.3", "token": "faux"}, headers=SAME).status_code == 400
    r = admin_client.post("/api/frames", json={"url": "https://100.1.2.3", "token": token, "name": "Chez Mamie"}, headers=SAME).get_json()
    assert r["success"]
    frames = admin_client.get("/api/frames").get_json()["frames"]
    assert frames[0]["name"] == "Chez Mamie" and frames[0]["online"]
    frame_id = frames[0]["id"]
    r = admin_client.post(f"/api/frames/{frame_id}/message", json={"title": "", "body": "Bisous de Paris", "style": "pastel"}, headers=SAME).get_json()
    assert r["success"]
    r = admin_client.post(f"/api/frames/{frame_id}/photos", data={"photos": (io.BytesIO(jpeg()), "a.jpg")}, content_type="multipart/form-data", headers=SAME).get_json()
    assert r["success"]
    assert admin_client.delete(f"/api/frames/{frame_id}", headers=SAME).get_json()["success"]
    from utils import messages_manager
    for m in messages_manager.list_messages():
        if m.get("body") == "Bisous de Paris":
            messages_manager.delete_message(m["id"])
