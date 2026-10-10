"""Synchronisation Google Drive, avec un faux Drive en mémoire."""
import json
import threading
from pathlib import Path

import pytest

import utils.import_gdrive as g


class FakeDrive:
    def __init__(self, files):
        self.files = dict(files)  # id -> nom
        self.trashed = []
        self.denied = set()       # ids appartenant à un autre compte (403)
        self.crash_after = None

    def list_media(self, folder_id, recursive):
        return [{"id": i, "name": n, "modifiedTime": "1", "remote_path": n} for i, n in self.files.items()]

    def download(self, f, dest):
        Path(dest).write_text(f["id"])

    def trash(self, f):
        if f["id"] in self.denied:
            raise RuntimeError("googleapi: Error 403: insufficientFilePermissions")
        del self.files[f["id"]]
        self.trashed.append(f["name"])
        if self.crash_after and len(self.trashed) >= self.crash_after:
            raise KeyboardInterrupt  # coupure brutale juste après la mise à la corbeille


@pytest.fixture()
def drive(tmp_path, monkeypatch):
    monkeypatch.setattr(g, "TARGET_DIR", tmp_path / "photos" / "gdrive")
    monkeypatch.setattr(g, "PREPARED_DIR", tmp_path / "prepared" / "gdrive")
    monkeypatch.setattr(g, "MANIFEST_FILE", tmp_path / "photos" / "gdrive" / ".gdrive_manifest.json")
    monkeypatch.setattr(g, "_sync_lock", threading.Lock())
    fake = FakeDrive({"a": "a.jpg", "b": "b.mp4"})
    monkeypatch.setattr(g, "get_backend", lambda config, key_info=None: fake)
    monkeypatch.setattr(g, "resolve_backend_name", lambda config: "rclone")
    return fake


def run(config):
    return list(g.import_gdrive_photos(config))


def local_files():
    return sorted(p.name for p in g.TARGET_DIR.iterdir() if p.name != g.MANIFEST_FILE.name)


CONFIG = {"gdrive_folders": [{"id": "Cadre", "name": "Cadre", "backend": "rclone"}]}


def test_mirror_mode_downloads_and_removes_deleted_files(drive):
    updates = run(CONFIG)
    assert updates[-1]["type"] == "done" and updates[-1]["changes"] == 2
    assert local_files() == ["a.jpg", "b.mp4"]
    del drive.files["a"]
    assert run(CONFIG)[-1]["changes"] == 1
    assert local_files() == ["b.mp4"]


def test_no_change_reports_zero(drive):
    run(CONFIG)
    assert run(CONFIG)[-1]["changes"] == 0


def test_trash_mode_keeps_local_copies(drive):
    config = {**CONFIG, "gdrive_trash_after_import": True}
    run(config)
    assert drive.files == {}
    assert sorted(drive.trashed) == ["a.jpg", "b.mp4"]
    assert local_files() == ["a.jpg", "b.mp4"]
    # Désactiver l'option ne fait pas disparaître les fichiers déjà retirés du Drive
    run(CONFIG)
    assert local_files() == ["a.jpg", "b.mp4"]


def test_interrupted_trash_never_deletes_local_files(drive):
    run(CONFIG)
    drive.crash_after = 1
    with pytest.raises(KeyboardInterrupt):
        run({**CONFIG, "gdrive_trash_after_import": True})
    drive.crash_after = None
    run({**CONFIG, "gdrive_trash_after_import": True})
    assert local_files() == ["a.jpg", "b.mp4"]
    assert drive.files == {}


def test_permission_denied_is_reported_once(drive):
    drive.denied.add("b")
    config = {**CONFIG, "gdrive_trash_after_import": True}
    first = [u["message"] for u in run(config) if u["type"] == "warning"]
    assert any("seul son propriétaire" in m for m in first)
    second = [u["message"] for u in run(config) if u["type"] == "warning"]
    assert second == []
    assert local_files() == ["a.jpg", "b.mp4"]


def test_remove_local_media_from_preview(drive):
    run({**CONFIG, "gdrive_trash_after_import": True})
    g.remove_local_media("a")
    assert local_files() == ["b.mp4"]
    assert "a" not in json.loads(g.MANIFEST_FILE.read_text())
    g.remove_local_media()
    assert local_files() == []


def test_concurrent_sync_is_refused(drive):
    first = g.import_gdrive_photos(CONFIG)
    next(first)  # première synchro en cours
    second = run(CONFIG)
    assert second[0]["type"] == "error" and "déjà en cours" in second[0]["message"]
    list(first)
    assert run(CONFIG)[-1]["type"] == "done"


def test_no_folder_selected_is_an_error(drive):
    assert run({"gdrive_folders": []})[-1]["type"] == "error"
