"""Historique : actions notées, regroupées, annulées ; photos affichées récemment."""
import pytest

from utils import history

SAME = {"Sec-Fetch-Site": "same-origin"}


@pytest.fixture
def store(monkeypatch, tmp_path):
    monkeypatch.setattr(history, "STORE", tmp_path / "history.json")
    monkeypatch.setattr(history, "UNDO_DIR", tmp_path / "undo")
    monkeypatch.setattr(history, "DISPLAYED", tmp_path / "displayed.json")
    return tmp_path


def test_record_merge_and_undo(store, monkeypatch):
    undone = []
    monkeypatch.setitem(history.UNDO_HANDLERS, "test", lambda data: undone.append(data))
    history.record("settings", "Réglages modifiés", "papa", {"type": "test", "data": "avant"}, merge=True)
    history.record("settings", "Réglages modifiés", "papa", {"type": "test", "data": "pendant"}, merge=True)  # regroupé
    assert len(history.events()) == 1
    history.record("guest", "2 photos", "Léa")  # pas annulable
    assert history.last_undoable()["text"] == "Réglages modifiés"
    assert history.undo_last("papa")["text"] == "Réglages modifiés" and undone == ["avant"]
    assert history.undo_last("papa") is None
    assert history.events()[0]["text"].startswith("↶")


def test_displayed(store):
    for i in range(5):
        history.displayed(f"prepared/gdrive/{i}.jpg")
    assert [d["path"] for d in history.recently_displayed(2)] == ["prepared/gdrive/4.jpg", "prepared/gdrive/3.jpg"]


def test_undo_playlist_and_settings(admin_client, store):
    from utils.config_manager import load_config, save_config
    from utils.playlist_manager import load_playlists, save_playlists
    original_config, original_playlists = dict(load_config()), load_playlists()
    try:
        r = admin_client.post("/api/playlists", json={"name": "À annuler", "photos": []}, headers=SAME).get_json()
        assert any(p["id"] == r["playlist"]["id"] for p in load_playlists())
        data = admin_client.get("/api/history").get_json()
        assert "À annuler" in data["undo"]
        assert admin_client.post("/api/history/undo", headers=SAME).get_json()["success"]
        assert not any(p["id"] == r["playlist"]["id"] for p in load_playlists())
        save_config(dict(load_config(), display_duration=10))
        admin_client.post("/configure", data={"display_duration": "33"}, headers=dict(SAME, **{"X-Autosave": "1"}))
        assert load_config()["display_duration"] == 33
        admin_client.post("/api/history/undo", headers=SAME)
        assert load_config()["display_duration"] == 10  # réglages d'avant
    finally:
        save_config(original_config)
        save_playlists(original_playlists)
