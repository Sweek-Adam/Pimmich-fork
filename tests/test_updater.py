"""Mises à jour : changements disponibles, validation et retour à la version précédente."""
import json
import subprocess

import pytest

from utils import updater

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """Dépôt « GitHub » + clone local avec deux nouveautés à récupérer."""
    def git(cwd, *args):
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=cwd, check=True, capture_output=True)
    remote, local = tmp_path / "remote", tmp_path / "local"
    remote.mkdir()
    git(remote, "init", "-q", "-b", "main")
    (remote / "a.txt").write_text("1")
    git(remote, "add", "."); git(remote, "commit", "-q", "-m", "Version initiale")
    git(tmp_path, "clone", "-q", str(remote), str(local))
    for n in (2, 3):
        (remote / "a.txt").write_text(str(n))
        git(remote, "commit", "-q", "-am", f"Nouveauté {n}")
    monkeypatch.setattr(updater, "BASE_DIR", local)
    monkeypatch.setattr(updater, "STATE_FILE", local / "config" / ".update_state.json")
    return local


def test_changes_available(repo):
    data = updater.check()
    assert data["success"] and data["behind"] == 2
    assert [c["title"] for c in data["changes"]] == ["Nouveauté 3", "Nouveauté 2"]


def test_update_validation_and_previous_version(repo):
    assert updater.previous_version() is None and not updater.mark_healthy()
    updater.save_state(previous="abc1234", status="pending")
    assert updater.previous_version() == "abc1234"
    assert updater.mark_healthy() and updater.load_state()["status"] == "ok"
    assert not updater.mark_healthy()  # déjà validée


def test_rollback_api_needs_a_previous_version(admin_client, repo):
    assert admin_client.post("/api/update/rollback", headers=SAME_ORIGIN).status_code == 409


def test_start_script_rolls_back_after_repeated_crashes():
    """start_pimmich.sh : la logique de retour arrière est présente et le script reste valide."""
    from pathlib import Path
    script = (Path(__file__).resolve().parent.parent / "start_pimmich.sh").read_text()
    assert "rollback_if_broken_update" in script and "QUICK_CRASHES -ge 3" in script
    assert subprocess.run(["bash", "-n", str(Path(__file__).resolve().parent.parent / "start_pimmich.sh")]).returncode == 0
    assert subprocess.run(["bash", "-n", str(Path(__file__).resolve().parent.parent / "update_script.sh")]).returncode == 0
