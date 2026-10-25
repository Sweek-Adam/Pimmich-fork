"""Recherche par contenu via Immich (analyse des images sur le serveur Immich, pas sur le Raspberry Pi)."""
from types import SimpleNamespace

from utils import immich_search, library_search

CONFIG = {"immich_url": "http://immich.local:2283/", "immich_token": "jeton"}


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, json, headers, timeout):
        self.calls.append((url, json, headers))
        items = [{"originalFileName": "IMG_0003.HEIC"}, {"originalFileName": "IMG_0001.jpg"}, {"originalFileName": "img_0003.heic"}]
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"assets": {"items": items}})


def test_smart_search_and_cache():
    immich_search._cache.clear()
    session = FakeSession()
    assert immich_search.smart_search(CONFIG, "  la   plage ", session=session) == ["img_0003", "img_0001"]
    url, body, headers = session.calls[0]
    assert url == "http://immich.local:2283/api/search/smart" and body["query"] == "la plage" and headers["x-api-key"] == "jeton"
    immich_search.smart_search(CONFIG, "LA PLAGE", session=session)
    assert len(session.calls) == 1   # même recherche : pas de nouvel appel pendant 10 minutes
    assert immich_search.smart_search({}, "plage", session=session) == [] and not immich_search.available({})


def test_library_results_follow_immich_relevance(monkeypatch):
    library = [{"path": p, "source": p.split("/")[0], "people": [], "favorite": False, "video": False, "date": d, "place": None}
               for p, d in (("immich/IMG_0001.jpg", "2024-01-01"), ("immich/IMG_0003.jpg", "2020-01-01"),
                            ("immich/IMG_0009.jpg", "2025-01-01"), ("gdrive/IMG_0001.jpg", "2024-01-01"))]
    monkeypatch.setattr(library_search.smart_albums, "library", lambda favorites: library)
    items, total = library_search.search(smart=["img_0003", "img_0001"])
    assert [i["path"] for i in items] == ["immich/IMG_0003.jpg", "immich/IMG_0001.jpg"] and total == 2
