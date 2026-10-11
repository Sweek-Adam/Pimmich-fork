"""Un compte par membre : envois dans sa propre source, « Mes envois », playlists personnelles."""
import io

from PIL import Image

from utils import members

SAME = {"Sec-Fetch-Site": "same-origin"}


def jpeg():
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), (200, 80, 60)).save(buffer, "JPEG")
    return buffer.getvalue()


def test_slug_and_unique_names(tmp_path):
    assert members.source_for("Léa Martin") == "compte_lea_martin" and members.source_for("") == "compte_membre"
    assert members.label("compte_lea_martin", ["Léa Martin"]) == "Léa Martin"
    (tmp_path / "photo.jpg").write_bytes(b"x")
    assert members.unique_name(tmp_path, "photo.jpg").name == "photo_2.jpg"


def test_member_uploads_and_playlists(client, admin_client, sandbox, monkeypatch):
    from conftest import login
    from utils import user_manager
    from utils.playlist_manager import load_playlists, save_playlists
    original = load_playlists()
    user_manager.create_user("lea", "motdepasse-lea-1", "user")
    try:
        login(client, "lea", "motdepasse-lea-1")
        for _ in range(2):  # deux envois du même nom : les deux sont gardés
            resp = client.post("/import-smartphone", data={"photos": (io.BytesIO(jpeg()), "plage.jpg")}, content_type="multipart/form-data", headers=SAME)
            resp.get_data()
        items = client.get("/api/my_uploads").get_json()["items"]
        assert sorted(i["name"] for i in items) == ["plage.jpg", "plage_2.jpg"]
        assert client.delete("/api/my_uploads/plage_2.jpg", headers=SAME).get_json()["success"]
        assert client.delete("/api/my_uploads/..%2Fconfig.json", headers=SAME).status_code == 404
        r = client.post("/api/playlists", json={"name": "Mes vacances", "photos": []}, headers=SAME)
        mine = r.get_json()["playlist"]
        assert mine["owner"] == "lea"
        save_playlists(load_playlists() + [{"id": "autre1", "name": "Celle de papa", "photos": [], "owner": "papa"}])
        assert client.delete("/api/playlists/autre1", headers=SAME).status_code == 403  # pas la sienne
        assert client.post(f"/api/playlists/{mine['id']}/rename", json={"name": "Été"}, headers=SAME).status_code == 200
    finally:
        user_manager.delete_user("lea")
        save_playlists(original)
        import shutil
        for folder in ("photos", "prepared"):
            shutil.rmtree(sandbox / "static" / folder / "compte_lea", ignore_errors=True)
