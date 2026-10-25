"""Sauvegarde complète automatique de la semaine : quand la faire, combien en garder, réglages."""
import time
from datetime import datetime

from utils import auto_backup

SAME = {"Sec-Fetch-Site": "same-origin"}
ON = {"auto_full_backup": {"enabled": True, "storage": "disque", "weekday": 6, "keep": 2}}


def test_due_on_the_chosen_night_only():
    sunday = datetime(2026, 10, 25, 3, 0)
    assert not auto_backup.due({}, {}, False, sunday)                      # désactivée
    assert not auto_backup.due(ON, {}, True, sunday)                       # écran allumé : on attend
    assert auto_backup.due(ON, {"last_success": sunday.timestamp() - 7 * 86400}, False, sunday)
    monday = datetime(2026, 10, 26, 3, 0)
    assert not auto_backup.due(ON, {"last_success": sunday.timestamp()}, False, monday)
    # Dimanche manqué (cadre éteint) : rattrapée dès que possible
    assert auto_backup.due(ON, {"last_success": sunday.timestamp() - 9 * 86400}, False, monday)
    # Un échec ce jour-là : pas de nouvel essai toutes les demi-heures
    state = auto_backup.note({"last_success": sunday.timestamp() - 7 * 86400}, False, "disque absent", sunday)
    assert not auto_backup.due(ON, state, False, sunday)


def test_prune_keeps_the_latest_automatic_backups(tmp_path):
    for name in ("pimmich-complet-auto-2026-10-04-0300.zip", "pimmich-complet-auto-2026-10-11-0300.zip",
                 "pimmich-complet-auto-2026-10-18-0300.zip", "pimmich-complet-2026-01-01-1200.zip"):
        (tmp_path / name).write_bytes(b"zip")
    assert auto_backup.prune(tmp_path, 2) == ["pimmich-complet-auto-2026-10-04-0300.zip"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["pimmich-complet-2026-01-01-1200.zip", "pimmich-complet-auto-2026-10-11-0300.zip",
                                                          "pimmich-complet-auto-2026-10-18-0300.zip"]  # faite à la main : gardée


def test_auto_settings_api(admin_client):
    from utils.config_manager import load_config, save_config
    original = dict(load_config())
    try:
        save_config(dict(original, storages=[{"id": "disque", "label": "Disque USB", "kind": "usb"}]))
        assert admin_client.put("/api/backup/full/auto", json={"enabled": True, "storage": "inconnu"}, headers=SAME).status_code == 400
        r = admin_client.put("/api/backup/full/auto", json={"enabled": True, "storage": "disque", "weekday": 9, "keep": 0}, headers=SAME).get_json()
        assert r["success"] and r["settings"] == {"enabled": True, "storage": "disque", "weekday": 6, "keep": 1}
        assert admin_client.get("/api/backup/full/auto").get_json()["settings"]["enabled"]
    finally:
        save_config(original)
