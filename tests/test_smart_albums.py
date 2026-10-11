"""Albums intelligents : règles, périodes à cheval sur deux années, suggestions, mise à jour automatique, API."""
from utils import smart_albums as sa

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}


def item(path, day=None, people=(), source="gdrive", favorite=False, place=None, video=False):
    return {"path": path, "date": f"{day}T12:00:00" if day else None, "people": list(people), "source": source,
            "favorite": favorite, "place": place, "video": video}


LIBRARY = [
    item("gdrive/plage.jpg", "2025-07-14", ["Léo", "Emma"], place="Biarritz, France"),
    item("gdrive/rentree.jpg", "2025-09-25", ["Léo"]),
    item("gdrive/sapin.jpg", "2024-12-24", ["Mamie"], favorite=True),
    item("gdrive/reveillon.jpg", "2025-01-01", ["Mamie", "Léo"]),
    item("usb/film.mp4", "2025-08-02", ["Emma"], source="usb", video=True),
    item("gdrive/sans_date.jpg"),
]


def paths(rules):
    return sa.select(LIBRARY, sa.clean_rules(rules))


def test_rules():
    summer = sa.EVENTS["summer"]
    assert paths({"from": summer["from"], "to": summer["to"], "years": [2025]}) == ["gdrive/plage.jpg", "usb/film.mp4"]
    christmas = {"from": "12-20", "to": "01-02"}
    assert paths(dict(christmas, years=[2024])) == ["gdrive/sapin.jpg", "gdrive/reveillon.jpg"]  # le 1er janvier compte pour Noël 2024
    assert paths({"people": ["Léo", "Emma"]}) == ["gdrive/reveillon.jpg", "gdrive/plage.jpg", "usb/film.mp4", "gdrive/rentree.jpg"]
    assert paths({"people": ["Léo", "Emma"], "people_all": True}) == ["gdrive/plage.jpg"]
    assert paths({"place": "biarritz"}) == ["gdrive/plage.jpg"]
    assert paths({"favorites": True}) == ["gdrive/sapin.jpg"]
    assert paths({"media": "videos"}) == ["usb/film.mp4"]
    assert paths({"sources": ["usb"]}) == ["usb/film.mp4"]
    assert paths({"years": [2025], "media": "photos"}) == ["gdrive/reveillon.jpg", "gdrive/plage.jpg", "gdrive/rentree.jpg"]  # toute l'année


def test_clean_rules_rejects_garbage():
    assert sa.clean_rules({"from": "13-40", "to": "01-01", "years": ["abc", 1800, "2025"], "people": ["", " Léo "],
                           "people_all": True, "media": "sons", "place": "  "}) == {"years": [2025], "people": ["Léo"], "people_all": True}
    assert sa.clean_rules(None) == {} and sa.clean_rules({"people_all": True}) == {}


def test_suggestions(monkeypatch):
    monkeypatch.setattr(sa, "MIN_SUGGESTED", 2)
    library = LIBRARY + [item(f"gdrive/s{i}.jpg", f"2023-07-0{i}") for i in range(1, 4)] + [item("gdrive/n.jpg", "2023-12-25")] * 3
    found = sa.suggestions(library)
    events = [(s["event"], s.get("year")) for s in found]
    assert ("summer", 2025) in events and ("summer", 2023) in events and ("christmas", 2024) in events
    assert ("christmas_all", None) in events  # Noëls de plusieurs années : « Noël en famille »
    summer_2023 = next(s for s in found if s["event"] == "summer" and s["year"] == 2023)
    assert sa.select(library, summer_2023["rules"]) == ["gdrive/s1.jpg", "gdrive/s2.jpg", "gdrive/s3.jpg"]


def test_refresh_updates_only_smart_playlists(monkeypatch):
    monkeypatch.setattr(sa, "library", lambda favorites=(): LIBRARY)
    playlists = [{"id": "a", "name": "Manuelle", "photos": ["x.jpg"]},
                 {"id": "smart-1", "name": "Les enfants", "photos": [], "smart": {"people": ["Emma"]}}]
    saved = []
    assert sa.refresh(lambda: playlists, saved.append) == 1
    assert saved[0][1]["photos"] == ["gdrive/plage.jpg", "usb/film.mp4"] and saved[0][0]["photos"] == ["x.jpg"]
    assert sa.refresh(lambda: saved[0], saved.append) == 0  # rien de nouveau : pas d'écriture


def test_smart_albums_api(admin_client, monkeypatch):
    from utils.playlist_manager import load_playlists, save_playlists
    original = load_playlists()
    monkeypatch.setattr(sa, "library", lambda favorites=(): LIBRARY)
    monkeypatch.setattr(sa, "MIN_SUGGESTED", 1)
    try:
        save_playlists([])
        data = admin_client.get("/api/smart_albums").get_json()
        summer = sa.EVENTS["summer"]
        assert any(s["name"].endswith(" 2025") and s["rules"] == {"from": summer["from"], "to": summer["to"], "years": [2025]}
                   for s in data["suggestions"])  # « Été 2025 » (dans la langue de l'interface)
        assert data["people"] == ["Emma", "Léo", "Mamie"] and data["years"] == [2025, 2024] and "christmas" in data["events"]
        r = admin_client.post("/api/smart_albums/preview", json={"rules": {"people": ["Emma"]}}, headers=SAME_ORIGIN).get_json()
        assert r["count"] == 2 and r["thumbs"][-1].endswith("usb/film_thumbnail.jpg")
        r = admin_client.post("/api/smart_albums", json={"name": "Les enfants", "rules": {"people": ["Léo", "Emma"]}}, headers=SAME_ORIGIN).get_json()
        assert r["success"] and r["count"] == 4
        album = next(p for p in load_playlists() if p["name"] == "Les enfants")
        assert album["id"].startswith("smart-") and album["smart"] == {"people": ["Emma", "Léo"]}
        r = admin_client.post("/api/smart_albums", json={"id": album["id"], "name": "Les enfants", "rules": {"people": ["Emma"]}}, headers=SAME_ORIGIN).get_json()
        assert r["count"] == 2 and len([p for p in load_playlists() if p["name"] == "Les enfants"]) == 1
        assert admin_client.post("/api/smart_albums", json={"name": "Vide", "rules": {}}, headers=SAME_ORIGIN).status_code == 400
        assert admin_client.post("/api/smart_albums", json={"name": "les enfants", "rules": {"favorites": True}}, headers=SAME_ORIGIN).status_code == 409
        names = [s["name"] for s in admin_client.get("/api/smart_albums").get_json()["suggestions"]]
        assert "Les enfants" not in names
    finally:
        save_playlists(original)
