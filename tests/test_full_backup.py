"""Sauvegarde complète : contenu, photos sur option, restauration limitée aux emplacements prévus."""
import io
import zipfile

import pytest

from utils import full_backup


@pytest.fixture
def project(monkeypatch, tmp_path):
    root = tmp_path / "pimmich"
    for rel, content in (("config/config.json", "{}"), ("config/users.json", "{}"), ("config/secret_key", "s"),
                         ("cache/drawings/a.png", "png"), ("static/guestbook/a.jpg", "jpg"), ("static/photos/gdrive/p.jpg", "photo"),
                         ("cache/autre.json", "{}")):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(content)
    monkeypatch.setattr(full_backup, "PROJECT_DIR", root)
    return root


def test_backup_and_restore(project, tmp_path):
    archive = tmp_path / "b.zip"
    count, _size = full_backup.build(archive)
    names = zipfile.ZipFile(archive).namelist()
    assert "config/config.json" in names and "cache/drawings/a.png" in names and "static/guestbook/a.jpg" in names
    assert "config/secret_key" not in names and "static/photos/gdrive/p.jpg" not in names and "cache/autre.json" not in names
    full_backup.build(tmp_path / "full.zip", with_photos=True)
    assert "static/photos/gdrive/p.jpg" in zipfile.ZipFile(tmp_path / "full.zip").namelist()
    (project / "cache/drawings/a.png").unlink()
    assert full_backup.restore(tmp_path / "full.zip") >= 5 and (project / "cache/drawings/a.png").read_text() == "png"


def test_restore_refuses_unexpected_paths(project, tmp_path):
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr(full_backup.MARKER, '{"photos": false}')
        zf.writestr("../../evil.txt", "x")
        zf.writestr("app.py", "pirate")
        zf.writestr("static/photos/gdrive/x.jpg", "photo")  # pas de photos dans cette sauvegarde : refusé
        zf.writestr("config/config.json", '{"ok": 1}')
    assert full_backup.restore(evil) == 1
    assert not (project / "app.py").exists() and not (tmp_path / "evil.txt").exists() and not (project / "static/photos/gdrive/x.jpg").exists()
    with pytest.raises(ValueError):
        not_backup = tmp_path / "n.zip"
        zipfile.ZipFile(not_backup, "w").writestr("a.txt", "x")
        full_backup.restore(not_backup)


def test_full_backup_api(admin_client, monkeypatch, project):
    r = admin_client.get("/api/backup/full")
    assert r.status_code == 200 and zipfile.ZipFile(io.BytesIO(r.data)).namelist()
    data = admin_client.get("/api/backup/full/storage").get_json()
    assert data["success"] and "backups" in data
