"""Espace disque, nettoyage automatique et sauvegarde des réglages sur Google Drive."""
import io
import json
import os
import zipfile
from collections import namedtuple
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from utils import disk_monitor, drive_backup, import_gdrive

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}
Usage = namedtuple("Usage", "total used free")
GB = disk_monitor.GB


@pytest.fixture()
def gdrive_files(tmp_path, monkeypatch):
    """Trois médias Drive importés : a (ancien, retiré du Drive), b (récent, retiré), c (encore sur le Drive)."""
    target = tmp_path / "photos" / "gdrive"
    prepared = tmp_path / "prepared" / "gdrive"
    target.mkdir(parents=True), prepared.mkdir(parents=True)
    monkeypatch.setattr(import_gdrive, "TARGET_DIR", target)
    monkeypatch.setattr(import_gdrive, "MANIFEST_FILE", target / ".gdrive_manifest.json")
    monkeypatch.setattr(disk_monitor, "PREPARED_GDRIVE", prepared)
    monkeypatch.setattr(disk_monitor, "BACKUPS_GDRIVE", tmp_path / "backups")
    monkeypatch.setattr(disk_monitor, "FAVORITES_FILE", tmp_path / "favorites.json")
    manifest = {}
    for i, (name, trashed) in enumerate([("a.jpg", True), ("b.jpg", True), ("c.jpg", False)]):
        for f in (target / name, prepared / name):
            f.write_bytes(b"x" * 1000)
            os.utime(f, (1000 + i, 1000 + i))
        manifest[name] = {"name": name, "modifiedTime": "1", **({"trashed": True} if trashed else {})}
    (target / ".gdrive_manifest.json").write_text(json.dumps(manifest))
    return target, prepared


def test_candidates_are_trashed_files_oldest_first_without_favorites(gdrive_files):
    assert [stem for _, stem, _, _ in disk_monitor.cleanup_candidates()] == ["a", "b"]
    disk_monitor.FAVORITES_FILE.write_text(json.dumps(["gdrive/a.jpg"]))
    assert [stem for _, stem, _, _ in disk_monitor.cleanup_candidates()] == ["b"]


def test_free_space_stops_once_threshold_is_reached(gdrive_files, monkeypatch):
    target, prepared = gdrive_files
    monkeypatch.setattr(disk_monitor, "CLEANUP_MARGIN", 0)
    monkeypatch.setattr(disk_monitor.shutil, "disk_usage", lambda p: Usage(100 * GB, 0, 2 * GB - 1500))
    removed = disk_monitor.free_space({"disk_alert_free_gb": 2})
    assert removed == ["a"]  # 2 000 octets libérés suffisent
    assert not (target / "a.jpg").exists() and not (prepared / "a.jpg").exists()
    assert (target / "b.jpg").exists() and (target / "c.jpg").exists()


def test_disk_status_flags_low_space(monkeypatch):
    monkeypatch.setattr(disk_monitor.shutil, "disk_usage", lambda p: Usage(100 * GB, 99 * GB, 1 * GB))
    status = disk_monitor.disk_status({"disk_alert_free_gb": 2})
    assert status["low"] and status["free_gb"] == 1.0


@pytest.fixture()
def config_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(drive_backup, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(drive_backup, "STATUS_FILE", tmp_path / "backup_status.json")
    (tmp_path / "config.json").write_text('{"display_duration": 10}')
    (tmp_path / "users.json").write_text('{"users": {}}')
    (tmp_path / ".internal_api_token").write_text("secret-local")
    return tmp_path


def test_archive_contains_settings_but_not_local_tokens(config_dir):
    names = zipfile.ZipFile(io.BytesIO(drive_backup.build_archive())).namelist()
    assert "config.json" in names and "users.json" in names
    assert ".internal_api_token" not in names


def test_restore_writes_only_expected_files(config_dir):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("pimmich_backup.json", "{}")
        zf.writestr("config.json", '{"display_duration": 42}')
        zf.writestr("../evil.json", "{}")
        zf.writestr("autre.txt", "x")
    restored = drive_backup.restore_archive(buffer.getvalue())
    assert restored == ["config.json"]
    assert json.loads((config_dir / "config.json").read_text())["display_duration"] == 42
    assert not (config_dir.parent / "evil.json").exists()


def test_restore_refuses_foreign_archives(config_dir):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("config.json", "{}")
    with pytest.raises(ValueError):
        drive_backup.restore_archive(buffer.getvalue())


def test_backup_uploads_and_keeps_only_the_latest(config_dir, monkeypatch):
    drive = {f"pimmich-sauvegarde-2026-01-0{i}_00-00-00.zip" for i in range(1, 4)}
    calls = []

    def fake_rclone(*args, timeout=300):
        calls.append(args)
        if args[0] == "copyto":
            drive.add(Path(args[2]).name)
        elif args[0] == "deletefile":
            drive.discard(Path(args[1]).name)
        elif args[0] == "lsjson":
            return json.dumps([{"Name": n} for n in drive])
        return ""
    monkeypatch.setattr(drive_backup, "_rclone", fake_rclone)
    config = {"gdrive_rclone_remote": "gdrive", "backup_drive_folder": "Sauvegardes", "backup_drive_keep": 2}
    status = drive_backup.backup_now(config)
    assert status["last_name"] in drive and status["last_error"] is None
    assert sorted(drive) == sorted(drive_backup.list_backups(config)) and len(drive) == 2
    assert "pimmich-sauvegarde-2026-01-03_00-00-00.zip" in drive  # la plus récente des anciennes est gardée
    assert all(a[0] != "copyto" or a[2].startswith("gdrive:Sauvegardes/") for a in calls)


def test_backup_schedule(config_dir):
    assert not drive_backup.is_due({"backup_drive_enabled": False})
    assert drive_backup.is_due({"backup_drive_enabled": True})
    drive_backup._save_status(last_attempt=datetime(2026, 1, 1, 12).isoformat())
    config = {"backup_drive_enabled": True, "backup_drive_interval_hours": 24}
    assert not drive_backup.is_due(config, now=datetime(2026, 1, 2, 11))
    assert drive_backup.is_due(config, now=datetime(2026, 1, 2, 12))


def test_maintenance_routes_are_admin_only(user_client, admin_client):
    assert user_client.get("/api/maintenance/status").status_code == 403
    data = admin_client.get("/api/maintenance/status").get_json()
    assert data["success"] and "free_gb" in data["disk"]
    resp = admin_client.post("/api/maintenance/settings", json={"backup_drive_folder": "../x"}, headers=SAME_ORIGIN)
    assert resp.status_code == 400
    resp = admin_client.post("/api/maintenance/settings", json={"disk_alert_free_gb": 3, "backup_drive_keep": 5}, headers=SAME_ORIGIN)
    assert resp.get_json()["success"]


def test_maintenance_worker_purges_expired_messages(app_module):
    from utils import messages_manager
    from web import workers
    messages_manager.delete_all_messages()
    message = messages_manager.create_message("A", "a", "", "nuit", (datetime.now() + timedelta(days=1)).date().isoformat(), "admin", 320, 180)
    messages = json.loads(messages_manager.MESSAGES_FILE.read_text())
    messages[0]["expires"] = "2000-01-01"
    messages_manager.MESSAGES_FILE.write_text(json.dumps(messages))
    workers.run_maintenance_once()
    assert messages_manager.list_messages() == []
    assert not messages_manager.image_path(message["id"]).exists()
