"""Messages programmés et récurrents : « le 12 mars à 8 h : Joyeux anniversaire Mamie », chaque année."""
from datetime import datetime, timedelta

import pytest

from utils import messages_manager as mm

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}


def message(starts, repeat="none", hours=24):
    return {"id": "abcdef123456", "schedule": {"starts": starts, "repeat": repeat, "duration_hours": hours}}


def test_on_air_windows():
    at = datetime.fromisoformat
    once = message("2026-03-12T08:00")
    assert not mm.on_air(once, at("2026-03-12T07:59")) and mm.on_air(once, at("2026-03-12T08:00"))
    assert mm.on_air(once, at("2026-03-13T07:59")) and not mm.on_air(once, at("2026-03-13T08:00"))
    yearly = message("2026-03-12T08:00", "yearly")
    assert mm.on_air(yearly, at("2030-03-12T09:00")) and not mm.on_air(yearly, at("2030-03-11T09:00"))
    weekly = message("2026-10-12T18:00", "weekly", 3)  # lundi 18 h - 21 h
    assert mm.on_air(weekly, at("2026-11-02T19:30")) and not mm.on_air(weekly, at("2026-11-03T19:30"))
    daily = message("2026-10-01T07:00", "daily", 1)
    assert mm.on_air(daily, at("2026-10-20T07:30")) and not mm.on_air(daily, at("2026-10-20T08:30"))
    monthly = message("2026-01-31T10:00", "monthly", 24)
    assert mm.on_air(monthly, at("2026-02-28T12:00"))  # le 31 n'existe pas en février : le dernier jour du mois
    assert mm.on_air(monthly, at("2026-03-31T12:00")) and not mm.on_air(monthly, at("2026-03-30T12:00"))
    leap = message("2024-02-29T09:00", "yearly")
    assert mm.on_air(leap, at("2025-02-28T10:00"))
    assert mm.on_air({"id": "x"}) is True  # message non programmé : toujours affiché


def test_validate_schedule():
    assert mm.validate_schedule(None, "yearly", 24) is None
    future = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
    assert mm.validate_schedule(future, "bizarre", 5) == {"starts": future, "repeat": "none", "duration_hours": 24}
    with pytest.raises(ValueError):
        mm.validate_schedule("2001-01-01T08:00", "none", 24)  # déjà passé
    assert mm.validate_schedule("2001-01-01T08:00", "yearly", 24)["repeat"] == "yearly"  # répété : toujours d'actualité
    with pytest.raises(ValueError):
        mm.validate_schedule("pas une date", "none", 24)


def test_scheduled_message_enters_the_slideshow_on_time(admin_client, sandbox, monkeypatch, tmp_path):
    monkeypatch.setattr(mm, "PRIORITY_FILE", tmp_path / "priority.json")
    starts = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
    r = admin_client.post("/api/messages", json={"title": "Joyeux anniversaire Mamie", "body": "", "style": "festif",
                                                  "starts": starts, "repeat": "yearly", "duration_hours": 24}, headers=SAME_ORIGIN).get_json()
    assert r["success"] and "programmé" in r["message"]
    item = r["item"]
    try:
        assert mm.image_path(item["id"], True).exists() and not mm.image_path(item["id"]).exists()  # pas encore
        listed = next(m for m in admin_client.get("/api/messages").get_json()["messages"] if m["id"] == item["id"])
        assert listed["on_air"] is False
        later = datetime.fromisoformat(starts) + timedelta(minutes=5)
        shown = mm.refresh_schedule(later)
        assert [m["id"] for m in shown] == [item["id"]] and mm.image_path(item["id"]).exists()
        assert mm.pop_priority() == [str(mm.image_path(item["id"]))]  # affiché tout de suite
        assert mm.refresh_schedule(later) == []
        mm.refresh_schedule(later + timedelta(days=2))  # fin de la plage : retiré du diaporama
        assert not mm.image_path(item["id"]).exists() and mm.image_path(item["id"], True).exists()
    finally:
        mm.delete_message(item["id"])
