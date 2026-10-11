"""Stockage sur plusieurs supports : disques détectés, déplacement d'une source (copie vérifiée + lien), retour sur la carte SD."""
import json
import os

import pytest

from utils import storage

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}
LSBLK = {"blockdevices": [
    {"name": "mmcblk0", "type": "disk", "children": [{"name": "mmcblk0p2", "type": "part", "uuid": "root", "fstype": "ext4", "size": 1}]},
    {"name": "sda", "type": "disk", "model": "Samsung T7", "children": [
        {"name": "sda1", "type": "part", "uuid": "AAAA-1111", "label": None, "fstype": "exfat", "size": 500_000_000_000, "mountpoint": None},
        {"name": "sda2", "type": "part", "uuid": "swap-x", "fstype": "swap", "size": 1}]},
    {"name": "sdb", "type": "disk", "uuid": "BBBB", "label": "PHOTOS", "fstype": "ext4", "size": 64_000_000_000, "mountpoint": "/media/pi/PHOTOS"},
]}


@pytest.fixture
def frame(monkeypatch, tmp_path):
    photos, prepared, mounts = tmp_path / "photos", tmp_path / "prepared", tmp_path / "mnt"
    for path in (photos / "gdrive", prepared / "gdrive"):
        path.mkdir(parents=True)
    for i in range(30):
        (photos / "gdrive" / f"p{i}.jpg").write_bytes(b"x" * 100)
        (prepared / "gdrive" / f"p{i}.jpg").write_bytes(b"y" * 50)
    monkeypatch.setattr(storage, "PHOTOS_DIR", photos)
    monkeypatch.setattr(storage, "PREPARED_DIR", prepared)
    monkeypatch.setattr(storage, "MOUNT_ROOT", mounts)

    def fake_mount(item):
        (mounts / item["id"] / "pimmich").mkdir(parents=True, exist_ok=True)
        return True, "monté"
    monkeypatch.setattr(storage, "mount", fake_mount)
    config = {"storages": [{"id": "usb1", "kind": "disk", "uuid": "AAAA-1111", "label": "T7"},
                           {"id": "nas", "kind": "smb", "share": "//nas/photos", "label": "NAS"}]}
    return tmp_path, config


def test_disks_ignore_the_sd_card_and_swap(monkeypatch):
    class Result:
        stdout = json.dumps(LSBLK)
    monkeypatch.setattr(storage, "_run", lambda *a, **k: Result())
    found = storage.disks()
    assert [(d["uuid"], d["label"], d["fstype"]) for d in found] == [("AAAA-1111", "Samsung T7", "exfat"), ("BBBB", "PHOTOS", "ext4")]


def test_move_to_disks_and_back(frame):
    tmp, config = frame
    seen = []
    assert storage.move("gdrive", "usb1", config, lambda done, total: seen.append((done, total))) == 60
    link = tmp / "photos" / "gdrive"
    assert link.is_symlink() and os.readlink(link) == str(tmp / "mnt" / "usb1" / "pimmich" / "photos" / "gdrive")
    assert len(list(link.iterdir())) == 30 and (tmp / "prepared" / "gdrive").is_symlink()
    assert storage.location("gdrive") == "usb1" and seen[-1] == (60, 60)
    assert not (tmp / "photos" / ".gdrive.old").exists()  # l'ancienne copie est libérée
    # D'un support à l'autre, puis retour sur la carte SD
    storage.move("gdrive", "nas", config)
    assert storage.location("gdrive") == "nas" and not (tmp / "mnt" / "usb1" / "pimmich" / "photos" / "gdrive").exists()
    storage.move("gdrive", storage.SD, config)
    assert not link.is_symlink() and len(list(link.iterdir())) == 30 and storage.location("gdrive") == storage.SD
    assert not (tmp / "mnt" / "nas" / "pimmich" / "photos" / "gdrive").exists()


def test_failed_copy_keeps_the_photos(frame, monkeypatch):
    tmp, config = frame
    monkeypatch.setattr(storage, "_verify", lambda copy, expected: (_ for _ in ()).throw(RuntimeError("Copie incomplète")))
    with pytest.raises(RuntimeError):
        storage.move("gdrive", "usb1", config)
    assert not (tmp / "photos" / "gdrive").is_symlink() and len(list((tmp / "photos" / "gdrive").iterdir())) == 30


def test_empty_dir_keeps_the_link_and_links_are_restored(frame):
    tmp, config = frame
    storage.move("gdrive", "usb1", config)
    storage.empty_dir(tmp / "photos" / "gdrive")
    assert (tmp / "photos" / "gdrive").is_symlink() and list((tmp / "photos" / "gdrive").iterdir()) == []
    (tmp / "prepared" / "gdrive").unlink()  # lien perdu (ex. dossier recréé par une mise à jour)
    storage.ensure_links(dict(config, storage_placement={"gdrive": "usb1", "../x": "usb1"}))
    assert (tmp / "prepared" / "gdrive").is_symlink() and not (tmp / "prepared" / ".." / "x").exists()
    sizes = storage.source_sizes()
    assert sizes["gdrive"]["location"] == "usb1" and sizes["gdrive"]["files"] == 30 and sizes["gdrive"]["online"]


def test_unknown_storage_or_source(frame):
    _tmp, config = frame
    with pytest.raises(ValueError):
        storage.move("gdrive", "inconnu", config)
    with pytest.raises(ValueError):
        storage.move("../etc", "usb1", config)


def test_credentials_file_is_private(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "CREDENTIALS_DIR", tmp_path / "cred")
    path = storage.save_credentials("nas", "papa", "s3cret")
    assert oct(path.stat().st_mode & 0o777) == "0o600" and "password=s3cret" in path.read_text()


def test_storage_api(admin_client, frame, monkeypatch):
    from web import routes_storage
    from utils.config_manager import load_config, save_config
    tmp, _config = frame
    original = dict(load_config())
    monkeypatch.setattr(storage, "disks", lambda: [{"uuid": "AAAA-1111", "label": "T7", "fstype": "exfat", "size": 5, "mountpoint": None, "device": "/dev/sda1"}])
    monkeypatch.setattr(storage, "is_mounted", lambda item: True)
    monkeypatch.setattr(routes_storage.threading, "Thread", lambda target, args, **k: type("T", (), {"start": lambda self: target(*args)})())
    try:
        save_config(dict(original, storages=[], storage_placement={}))
        data = admin_client.get("/api/storage").get_json()
        assert data["disks"][0]["uuid"] == "AAAA-1111" and "gdrive" in data["sources"]
        r = admin_client.post("/api/storage/add", json={"kind": "disk", "uuid": "AAAA-1111"}, headers=SAME_ORIGIN).get_json()
        assert r["success"]
        disk_id = load_config()["storages"][0]["id"]
        assert admin_client.post("/api/storage/add", json={"kind": "disk", "uuid": "AAAA-1111"}, headers=SAME_ORIGIN).status_code == 409
        assert admin_client.post("/api/storage/add", json={"kind": "smb", "share": "nas photos"}, headers=SAME_ORIGIN).status_code == 400
        r = admin_client.post("/api/storage/move", json={"source": "gdrive", "to": disk_id}, headers=SAME_ORIGIN).get_json()
        assert r["success"] and load_config()["storage_placement"] == {"gdrive": disk_id}
        assert (tmp / "photos" / "gdrive").is_symlink()
        assert admin_client.post("/api/storage/remove", json={"id": disk_id}, headers=SAME_ORIGIN).status_code == 400  # photos dessus
        admin_client.post("/api/storage/move", json={"source": "gdrive", "to": "sd"}, headers=SAME_ORIGIN)
        assert load_config()["storage_placement"] == {}
        monkeypatch.setattr(storage, "unmount", lambda item: True)
        assert admin_client.post("/api/storage/remove", json={"id": disk_id}, headers=SAME_ORIGIN).get_json()["success"]
        assert admin_client.post("/api/storage/move", json={"source": "inconnue", "to": "sd"}, headers=SAME_ORIGIN).status_code == 404
    finally:
        save_config(original)
