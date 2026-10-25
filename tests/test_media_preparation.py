"""Préparation des médias : petits d'abord, inventaire (préparés ou non), bouton Préparer, détails de l'import."""
import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from PIL import Image

from utils import import_progress
from utils import prepare_all_photos as prep

SAME = {"Sec-Fetch-Site": "same-origin"}


@pytest.fixture()
def source(sandbox, monkeypatch):
    """Une source « essai » dans le bac à sable, sans vraie préparation coûteuse."""
    folder = Path("static/photos/essai")
    prepared = Path("static/prepared/essai")
    shutil.rmtree(folder, ignore_errors=True)
    shutil.rmtree(prepared, ignore_errors=True)
    folder.mkdir(parents=True)
    import_progress.reset()
    monkeypatch.setattr(prep, "ERRORS_FILE", Path("cache") / "prepare_errors_test.json")
    prep.ERRORS_FILE.unlink(missing_ok=True)
    yield folder, prepared
    shutil.rmtree(folder, ignore_errors=True)
    shutil.rmtree(prepared, ignore_errors=True)


def fake_photo(src, dest, width, height, source_type=None, caption=None):
    Image.new("RGB", (width, height), (10, 20, 30)).save(dest)


def test_small_media_are_prepared_first(source, monkeypatch):
    folder, _prepared = source
    (folder / "gros.jpg").write_bytes(b"x" * 5000)
    (folder / "petit.jpg").write_bytes(b"x" * 10)
    (folder / "moyen.png").write_bytes(b"x" * 900)
    order = []
    monkeypatch.setattr(prep, "prepare_photo", lambda src, dest, *a, **k: (order.append(Path(src).name), fake_photo(src, dest, 64, 36)))
    events = list(prep.prepare_all_photos_with_progress(64, 36, "essai"))
    assert order == ["petit.jpg", "moyen.png", "gros.jpg"]
    assert events[-1]["type"] == "done"
    # Préparés : plus rien à faire la fois suivante
    order.clear()
    list(prep.prepare_all_photos_with_progress(64, 36, "essai"))
    assert order == []


def test_inventory_states_and_errors(source, monkeypatch):
    folder, prepared = source
    for name in ("pret.jpg", "absent.jpg", "vide.jpg", "ancien.jpg", "film.mp4", "rate.jpg"):
        (folder / name).write_bytes(b"x")
    (folder / ".cache.jpg").write_bytes(b"x")
    (folder / "notes.txt").write_text("pas un média")
    prepared.mkdir(parents=True)
    Image.new("RGB", (64, 36)).save(prepared / "pret.jpg")
    (prepared / "vide.jpg").write_bytes(b"")
    Image.new("RGB", (36, 64)).save(prepared / "ancien.jpg")
    (prepared / "film.mp4").write_bytes(b"video")
    monkeypatch.setattr(prep, "prepare_photo", lambda *a, **k: (_ for _ in ()).throw(ValueError("image abîmée")))
    with pytest.raises(ValueError):
        prep.prepare_media("essai", "rate.jpg", 64, 36)
    states = {i["name"]: (i["state"], i["error"]) for i in prep.media_inventory("essai", 64, 36)}
    assert states == {"pret.jpg": ("ok", None), "absent.jpg": ("missing", None), "vide.jpg": ("empty", None),
                      "ancien.jpg": ("stale", None), "film.mp4": ("ok", None), "rate.jpg": ("missing", "image abîmée")}
    detail = import_progress.work("essai")
    assert detail["failed"][0]["name"] == "rate.jpg" and detail["current"] is None
    # Réussite ensuite : l'échec est oublié
    monkeypatch.setattr(prep, "prepare_photo", fake_photo)
    prep.prepare_media("essai", "rate.jpg", 64, 36)
    assert {i["name"]: i["error"] for i in prep.media_inventory("essai", 64, 36)}["rate.jpg"] is None


def test_inventory_api_and_prepare_button(admin_client, source, monkeypatch):
    folder, prepared = source
    (folder / "a.jpg").write_bytes(b"x")
    (folder / "b.jpg").write_bytes(b"xx")
    monkeypatch.setattr(prep, "prepare_photo", lambda src, dest, w, h, **k: fake_photo(src, dest, w, h))
    from web import routes_media
    monkeypatch.setattr(routes_media, "is_slideshow_running", lambda: False)
    data = admin_client.get("/api/media/inventory").get_json()
    essai = next(s for s in data["sources"] if s["source"] == "essai")
    assert essai["total"] == 2 and essai["prepared"] == 0
    # Noms refusés : autre dossier, fichier absent, non-média
    for bad in (["../x.jpg"], ["absent.jpg"], ["notes.txt"]):
        assert admin_client.post("/api/media/prepare", json={"source": "essai", "names": bad}, headers=SAME).status_code == 400
    assert admin_client.post("/api/media/prepare", json={"source": "inconnue", "names": ["a.jpg"]}, headers=SAME).status_code == 400
    r = admin_client.post("/api/media/prepare", json={"source": "essai", "names": ["a.jpg", "b.jpg"]}, headers=SAME)
    assert r.get_json()["success"]
    for _ in range(100):
        if all(i["state"] == "ok" for i in prep.media_inventory("essai", *routes_media._screen())):
            break
        time.sleep(0.05)
    data = admin_client.get("/api/media/inventory").get_json()
    essai = next(s for s in data["sources"] if s["source"] == "essai")
    assert essai["prepared"] == 2 and not any(i["queued"] for i in essai["items"])
    # Détails de l'import : derniers médias traités
    progress = admin_client.get("/api/imports/progress").get_json()["imports"]
    job = next(i for i in progress if i["source"] == "essai")
    assert {r["name"] for r in job["work"]["recent"]} == {"a.jpg", "b.jpg"}


def test_inventory_requires_login(client):
    assert client.get("/api/media/inventory").status_code in (302, 401)


def test_heavy_video_is_encoded_light(source, monkeypatch, tmp_path):
    folder, prepared = source
    video = folder / "lourde.mp4"
    video.write_bytes(b"x" * 3 * 1024 * 1024)
    commands = []

    def fake_run(command, duration=None, on_progress=None):
        commands.append(command)
        if on_progress:
            on_progress(50, "1.5x")
        Path(command[-1]).write_bytes(b"ok")
        return 0, ""
    monkeypatch.setattr(prep, "run_ffmpeg", fake_run)
    monkeypatch.setattr(prep, "video_duration", lambda path: 10.0)
    monkeypatch.setattr(prep, "get_pi_model", lambda: None)
    monkeypatch.setattr(prep.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""))
    prepared.mkdir(parents=True)
    seen = []
    prep.prepare_video(str(video), str(prepared / "lourde.mp4"), 1920, 1080, on_progress=lambda p, info: seen.append(p), light_above_mb=2)
    light = " ".join(commands[-1])
    assert "1280:720" in light and "-fpsmax 30" in light and "superfast" in light and "-threads 2" in light
    assert seen == [50]
    prep.prepare_video(str(video), str(prepared / "lourde.mp4"), 1920, 1080, light_above_mb=0)  # 0 : jamais allégé
    normal = " ".join(commands[-1])
    assert "1920:1080" in normal and "-fpsmax" not in normal and "veryfast" in normal


def test_run_ffmpeg_reports_progress(tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg absent")
    seen = []
    code, _errors = prep.run_ffmpeg(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=160x120:rate=25", "-t", "2",
                                     "-pix_fmt", "yuv420p", str(tmp_path / "t.mp4")], 2.0, lambda p, s: seen.append(p))
    assert code == 0 and seen and max(seen) >= 90
    code, errors = prep.run_ffmpeg(["ffmpeg", "-y", "-i", str(tmp_path / "absent.mp4"), str(tmp_path / "x.mp4")])
    assert code != 0 and "absent.mp4" in errors


def test_delete_failed_media_only(admin_client, source, monkeypatch):
    folder, prepared = source
    for name in ("casse.jpg", "pret.jpg", "attente.jpg"):
        (folder / name).write_bytes(b"x")
    prepared.mkdir(parents=True)
    Image.new("RGB", (64, 36)).save(prepared / "pret.jpg")
    monkeypatch.setattr(prep, "prepare_photo", lambda *a, **k: (_ for _ in ()).throw(ValueError("illisible")))
    from web import routes_media
    monkeypatch.setattr(routes_media, "_screen", lambda: (64, 36))
    with pytest.raises(ValueError):
        prep.prepare_media("essai", "casse.jpg", 64, 36)
    # Ni un média prêt, ni un média seulement en attente, ni un autre dossier
    for bad in (["pret.jpg"], ["attente.jpg"], ["../essai/casse.jpg"]):
        assert admin_client.post("/api/media/delete_failed", json={"source": "essai", "names": bad}, headers=SAME).status_code == 400
    r = admin_client.post("/api/media/delete_failed", json={"source": "essai", "names": ["casse.jpg", "pret.jpg"]}, headers=SAME)
    assert r.get_json()["success"]
    assert not (folder / "casse.jpg").exists() and (folder / "pret.jpg").exists() and (folder / "attente.jpg").exists()
    assert "essai/casse.jpg" not in prep.preparation_errors()
