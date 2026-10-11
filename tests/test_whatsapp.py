"""Import WhatsApp : lecture des exports iPhone et Android, légendes, doublons, interface, partage depuis le téléphone."""
import io
import zipfile

import pytest

from utils import import_whatsapp

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}

IOS_CHAT = (
    "[12/08/2025, 14:03:21] Mamie: ‎<attaché : 00000012-PHOTO-2025-08-12-14-03-21.jpg>\n"
    "[12/08/2025, 14:05:00] Léo Martin: Trop bien !\n"
    "[13/08/2025, 09:15:02] Léo Martin: La mer était bonne ‎<attaché : 00000013-VIDEO-2025-08-13-09-15-02.mp4>\n"
    "[13/08/2025, 09:16:00] Léo Martin: ‎<attaché : 00000014-STICKER-2025-08-13-09-16-00.webp>\n"
)
ANDROID_CHAT = (
    "8/12/25, 2:03 PM - Mamie: IMG-20250812-WA0003.jpg (file attached)\n"
    "Coucher de soleil\n"
    "sur la plage\n"
    "8/13/25, 9:15 AM - Léo: Bonne nuit\n"
    "8/13/25, 9:20 AM - Léo: PTT-20250813-WA0001.opus (file attached)\n"
)


def make_zip(chat, media, chat_name="_chat.txt"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(chat_name, chat)
        for name, data in media.items():
            archive.writestr(name, data)
    buffer.seek(0)
    return buffer


@pytest.fixture
def wa_dirs(monkeypatch, tmp_path):
    monkeypatch.setattr(import_whatsapp, "TARGET_DIR", tmp_path / "whatsapp")
    monkeypatch.setattr(import_whatsapp, "MANIFEST_FILE", tmp_path / "whatsapp" / ".manifest.json")
    monkeypatch.setattr(import_whatsapp, "CAPTIONS_FILE", tmp_path / "captions.json")
    monkeypatch.setattr(import_whatsapp, "CANCEL_FLAG", tmp_path / "cancel.flag")
    return tmp_path / "whatsapp"


def test_parse_iphone_export():
    archive = zipfile.ZipFile(make_zip(IOS_CHAT, {"00000012-PHOTO-2025-08-12-14-03-21.jpg": b"a", "00000013-VIDEO-2025-08-13-09-15-02.mp4": b"b",
                                                  "00000014-STICKER-2025-08-13-09-16-00.webp": b"c"}))
    info = import_whatsapp.parse(archive)
    assert set(info["media"]) == {"00000012-PHOTO-2025-08-12-14-03-21.jpg", "00000013-VIDEO-2025-08-13-09-15-02.mp4"}  # pas d'autocollant
    photo = info["media"]["00000012-PHOTO-2025-08-12-14-03-21.jpg"]
    assert photo == {"sender": "Mamie", "date": "2025-08-12T14:03:21", "caption": ""}
    assert info["media"]["00000013-VIDEO-2025-08-13-09-15-02.mp4"]["caption"] == "La mer était bonne"
    assert info["senders"] == {"Mamie": 1, "Léo Martin": 1}


def test_parse_android_export_month_first_and_multiline_caption():
    archive = zipfile.ZipFile(make_zip(ANDROID_CHAT, {"IMG-20250812-WA0003.jpg": b"a", "PTT-20250813-WA0001.opus": b"v"},
                                       chat_name="Discussion WhatsApp avec Famille.txt"))
    info = import_whatsapp.parse(archive)
    assert list(info["media"]) == ["IMG-20250812-WA0003.jpg"]  # pas de message vocal
    assert info["media"]["IMG-20250812-WA0003.jpg"] == {"sender": "Mamie", "date": "2025-08-12T14:03:00", "caption": "Coucher de soleil sur la plage"}


def test_import_names_captions_and_duplicates(wa_dirs, tmp_path):
    path = tmp_path / "export.zip"
    path.write_bytes(make_zip(IOS_CHAT, {"00000012-PHOTO-2025-08-12-14-03-21.jpg": b"photo", "00000013-VIDEO-2025-08-13-09-15-02.mp4": b"video"}).getvalue())
    events = list(import_whatsapp.import_export(path, caption_mode="both"))
    assert events[-1]["type"] == "done" and events[-1]["changes"] == 2
    names = sorted(p.name for p in wa_dirs.iterdir() if not p.name.startswith("."))
    assert names == ["00000012-PHOTO-2025-08-12-14-03-21.jpg", "00000013-VIDEO-2025-08-13-09-15-02.mp4"]  # date déjà dans le nom
    assert import_whatsapp.captions() == {"00000012-PHOTO-2025-08-12-14-03-21.jpg": "Mamie",
                                          "00000013-VIDEO-2025-08-13-09-15-02.mp4": "Léo : La mer était bonne"}
    assert list(import_whatsapp.import_export(path))[-1]["changes"] == 0  # même export : rien de nouveau
    # Expéditeurs choisis
    for f in wa_dirs.iterdir():
        f.unlink()
    events = list(import_whatsapp.import_export(path, senders=["Mamie"]))
    assert events[-1]["changes"] == 1 and len([p for p in wa_dirs.iterdir() if not p.name.startswith(".")]) == 1


def test_local_name_adds_the_date():
    assert import_whatsapp._local_name("photo.jpg", {"date": "2024-01-02T03:04:05"}) == "20240102_030405_photo.jpg"
    assert import_whatsapp._local_name("../../x y.jpg", {"date": None}) == "x_y.jpg"


def test_not_a_zip(wa_dirs, tmp_path):
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"pas un zip")
    assert list(import_whatsapp.import_export(bad))[-1]["type"] == "error"


def test_whatsapp_api(admin_client, monkeypatch):
    from web import routes_imports
    started = []
    monkeypatch.setattr(routes_imports, "run_whatsapp_import", lambda *args: started.append(args))
    data = {"export": (make_zip(IOS_CHAT, {"00000012-PHOTO-2025-08-12-14-03-21.jpg": b"a"}), "WhatsApp Chat.zip")}
    r = admin_client.post("/api/whatsapp/upload", data=data, content_type="multipart/form-data", headers=SAME_ORIGIN).get_json()
    assert r["success"] and r["summary"]["photos"] == 1 and r["summary"]["senders"][0]["name"] == "Mamie"
    r = admin_client.post("/api/whatsapp/import", json={"senders": ["Mamie"], "caption": "sender"}, headers=SAME_ORIGIN).get_json()
    assert r["success"] and started and started[0][1:] == (["Mamie"], "sender")
    started[0][0].unlink(missing_ok=True)
    assert admin_client.post("/api/whatsapp/import", json={}, headers=SAME_ORIGIN).status_code == 400  # export déjà consommé
    bad = {"export": (io.BytesIO(b"nope"), "x.zip")}
    assert admin_client.post("/api/whatsapp/upload", data=bad, content_type="multipart/form-data", headers=SAME_ORIGIN).status_code == 400


def test_share_target(client, admin_client, monkeypatch, sandbox):
    from web import routes_imports
    monkeypatch.setattr(routes_imports, "run_whatsapp_prepare", lambda: None)
    started = []
    monkeypatch.setattr(routes_imports, "run_whatsapp_import", lambda *args: started.append(args))
    files = {"photos": [(io.BytesIO(b"jpg"), "IMG_1.jpg"), (make_zip(IOS_CHAT, {}), "export.zip")]}
    r = admin_client.post("/upload/share", data=files, content_type="multipart/form-data", headers={"Sec-Fetch-Site": "none"})
    assert r.status_code == 302 and len(started) == 1
    started[0][0].unlink(missing_ok=True)
    received = list((sandbox / "static" / "photos" / "whatsapp").glob("*_IMG_1_*.jpg"))
    assert len(received) == 1
    received[0].unlink()
