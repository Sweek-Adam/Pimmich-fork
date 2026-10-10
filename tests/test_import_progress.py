"""Notification persistante des imports : pourcentage du téléchargement, de la préparation, photos préparées."""
from utils import import_progress as ip


def setup_function():
    ip.reset()


def download_events():
    yield {"type": "progress", "stage": "SCANNING", "percent": 10, "message": "Analyse..."}
    yield {"type": "stats", "stage": "COPYING", "percent": 20, "total": 4, "message": "Début du téléchargement de 4 fichiers..."}
    for i in range(1, 5):
        yield {"type": "progress", "stage": "COPYING", "current": i, "total": 4, "message": f"({i}/4)"}
    yield {"type": "done", "stage": "IMPORT_COMPLETE", "percent": 80}


def test_download_then_preparation():
    events = ip.tracked("gdrive", "download", download_events())
    next(events); next(events); next(events)
    item = ip.snapshot()[0]
    assert item["label"] == "Google Drive" and item["active"] and item["download"]["percent"] == 25 and item["download"]["current"] == 1
    list(events)
    item = ip.snapshot()[0]
    assert item["download"]["done"] and item["download"]["percent"] == 100 and item["active"]

    def prepare():
        yield {"type": "stats", "stage": "PREPARING_START", "total": 4}
        yield {"type": "progress", "stage": "PREPARING_PHOTO", "current": 1, "total": 4}
        yield {"type": "progress", "stage": "PREPARING_PHOTO", "current": 3, "total": 4}
    events = ip.tracked("gdrive", "prepare", prepare())
    list(zip(range(3), events))
    item = ip.snapshot()[0]
    assert (item["prepare"]["current"], item["prepare"]["total"], item["prepare"]["percent"]) == (3, 4, 75)
    list(events)  # fin de la préparation : import terminé
    item = ip.snapshot()[0]
    assert not item["active"] and item["prepare"]["percent"] == 100


def test_finished_imports_disappear_and_errors_are_kept():
    list(ip.tracked("samba", "download", iter([{"type": "error", "message": "Partage introuvable"}])))
    item = ip.snapshot()[0]
    assert item["error"] == "Partage introuvable"
    now = item["updated"]
    assert ip.snapshot(now + ip.QUIET_AFTER_DOWNLOAD + 1)[0]["active"] is False  # rien à préparer ensuite
    assert ip.snapshot(now + ip.QUIET_AFTER_DOWNLOAD + ip.FORGET_AFTER + 5) == []


def test_progress_api(admin_client):
    list(ip.tracked("smartphone", "prepare", iter([{"type": "progress", "current": 2, "total": 5}])))
    data = admin_client.get("/api/imports/progress").get_json()["imports"]
    assert data[0]["label"] == "Téléphone" and data[0]["prepare"]["current"] == 2 and data[0]["prepare"]["total"] == 5
