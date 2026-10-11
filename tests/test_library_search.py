"""Recherche dans la bibliothèque : texte (sans accents), période, source, personne, favoris."""
from utils import library_search, smart_albums

SAME = {"Sec-Fetch-Site": "same-origin"}
LIB = [
    {"path": "gdrive/plage.jpg", "source": "gdrive", "date": "2025-07-14T12:00:00", "video": False, "favorite": True, "people": ["Léo"], "place": "Biarritz, France"},
    {"path": "usb/noel.jpg", "source": "usb", "date": "2024-12-24T19:00:00", "video": False, "favorite": False, "people": ["Mamie"], "place": None},
    {"path": "gdrive/film.mp4", "source": "gdrive", "date": None, "video": True, "favorite": False, "people": [], "place": None},
]


def test_search(monkeypatch, tmp_path):
    monkeypatch.setattr(smart_albums, "library", lambda favorites=(): LIB)
    texts = tmp_path / "texts.json"
    texts.write_text('{"usb/noel.jpg": "Réveillon chez Mamie"}', encoding="utf-8")
    monkeypatch.setattr(library_search, "TEXTS", texts)
    paths = lambda **kw: [i["path"] for i in library_search.search(**kw)[0]]
    assert paths(text="biarritz") == ["gdrive/plage.jpg"]
    assert paths(text="reveillon") == ["usb/noel.jpg"]  # sans accent : trouvé quand même
    assert paths(text="leo plage") == ["gdrive/plage.jpg"]
    assert paths(start="2025-01-01") == ["gdrive/plage.jpg"] and paths(end="2024-12-31") == ["usb/noel.jpg"]
    assert paths(source="gdrive") == ["gdrive/plage.jpg", "gdrive/film.mp4"]
    assert paths(person="Mamie") == ["usb/noel.jpg"] and paths(only_favorites=True) == ["gdrive/plage.jpg"]
    assert paths(media="videos") == ["gdrive/film.mp4"]


def test_search_api(admin_client, monkeypatch):
    monkeypatch.setattr(smart_albums, "library", lambda favorites=(): LIB)
    data = admin_client.get("/api/library/search?q=biarritz&from=pas-une-date").get_json()
    assert data["total"] == 1 and data["items"][0]["thumb"].endswith("gdrive/plage.jpg")
