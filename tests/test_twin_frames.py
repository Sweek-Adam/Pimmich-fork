"""Cadres jumelés : les nouveautés partent automatiquement vers les cadres choisis, sans jamais revenir en boucle."""
import shutil
import time
from pathlib import Path

from PIL import Image

from test_frames import SAME, restore_config  # noqa: F401 (fixture)
from utils import frame_share, messages_manager


def _link_to_self(admin_client, monkeypatch):
    """L'« autre cadre » est ici la même application (comme dans test_frames)."""
    from web import routes_frames
    remote = admin_client.application.test_client()
    token = admin_client.post("/api/frame/pairing", json={}, headers=SAME).get_json()["codes"][-1]["token"]
    calls = []

    class Response:
        def __init__(self, r):
            self.status_code, self.ok, self._r = r.status_code, r.status_code < 400, r

        def json(self):
            return self._r.get_json()

    def fake_request(method, url, headers, timeout, verify, **kwargs):
        path = "/" + url.split("/", 3)[3]
        calls.append(path)
        if "files" in kwargs:
            data = dict(kwargs.get("data") or {}, photos=[(f[1][1], f[1][0]) for f in kwargs["files"]])
            return Response(remote.open(path, method=method, headers=headers, data=data, content_type="multipart/form-data"))
        return Response(remote.open(path, method=method, headers=headers, json=kwargs.get("json")))
    monkeypatch.setattr(routes_frames.requests, "request", fake_request)
    monkeypatch.setattr(routes_frames.threading, "Thread", lambda target, **k: type("T", (), {"start": lambda self: None})())
    assert admin_client.post("/api/frames", json={"url": "https://100.1.2.3", "token": token, "name": "Chez Mamie"}, headers=SAME).get_json()["success"]
    return admin_client.get("/api/frames").get_json()["frames"][-1]["id"], calls


def test_new_photos_and_messages_are_shared_once(admin_client, restore_config, monkeypatch, tmp_path):  # noqa: F811
    from web import routes_frames
    monkeypatch.setattr(frame_share, "STATE_FILE", tmp_path / "share.json")
    frame_id, calls = _link_to_self(admin_client, monkeypatch)
    phone = Path("static/photos/smartphone")
    phone.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (40, 30)).save(phone / "avant.jpg")  # déjà là avant l'activation : pas envoyée
    old = time.time() - 3600
    import os
    os.utime(phone / "avant.jpg", (old, old))
    created = []
    try:
        assert routes_frames.share_with_frames() == 0  # rien d'activé : rien n'est envoyé
        r = admin_client.put(f"/api/frames/{frame_id}/share", json={"share_photos": True, "share_messages": True}, headers=SAME).get_json()
        assert r["success"]
        Image.new("RGB", (40, 30)).save(phone / "noel.jpg")
        message = messages_manager.create_message("", "Joyeux Noël", "Léa", "pastel", None, "Léa", 320, 180)
        created.append(message["id"])
        assert routes_frames.share_with_frames() == 2
        received = list(Path("static/photos/cadres").glob("*noel.jpg"))
        assert received and not list(Path("static/photos/cadres").glob("*avant.jpg"))
        copies = [m for m in messages_manager.list_messages() if m.get("body") == "Joyeux Noël" and m["id"] != message["id"]]
        assert len(copies) == 1 and copies[0].get("from_frame")
        created += [m["id"] for m in copies]
        # Deuxième passage : ni l'original (déjà envoyé) ni ce qui vient de l'autre cadre ne repartent
        calls.clear()
        assert routes_frames.share_with_frames() == 0 and not calls
        frames = admin_client.get("/api/frames").get_json()["frames"]
        assert frames[-1]["share_photos"] and frames[-1]["shared"] == {"photos": 1, "messages": 1}
    finally:
        for message_id in created:
            messages_manager.delete_message(message_id)
        shutil.rmtree(phone, ignore_errors=True)
        shutil.rmtree("static/photos/cadres", ignore_errors=True)


def test_batches_respect_size(tmp_path, monkeypatch):
    monkeypatch.setattr(frame_share, "MAX_BYTES", 100)
    items = []
    for i, size in enumerate((60, 30, 50, 10, 10, 10, 10, 10)):
        path = tmp_path / f"{i}.jpg"
        path.write_bytes(b"x" * size)
        items.append(("smartphone", path.name, path))
    sizes = [[p.stat().st_size for _s, _n, p in b] for b in frame_share.batches(items)]
    assert sizes == [[60, 30], [50, 10, 10, 10, 10], [10]]
    assert not frame_share.shared_source("cadres") and not frame_share.shared_source("gdrive") and frame_share.shared_source("invités")
