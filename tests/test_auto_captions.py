"""Légendes proposées : mots-clés d'Immich, descriptions de Claude (client simulé), recherche, clé jamais renvoyée."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from utils import auto_captions

SAME = {"Sec-Fetch-Site": "same-origin"}


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(auto_captions, "STORE", tmp_path / "auto.json")


def test_parse_answer():
    assert auto_captions.parse("Trois enfants jouent sur la plage.\nMots-clés : plage, été, enfants, mer") == \
        ("Trois enfants jouent sur la plage.", ["plage", "été", "enfants", "mer"])
    assert auto_captions.parse("Keywords: snow, ski")[1] == ["snow", "ski"]


def test_immich_tags(monkeypatch):
    from utils import immich_search
    monkeypatch.setattr(immich_search, "smart_search", lambda config, query, size=40: ["img_1"] if query in ("beach", "sunset") else [])
    found = auto_captions.immich_tags({}, ["immich/IMG_1.jpg", "immich/IMG_2.jpg", "gdrive/IMG_1.jpg"])
    assert found == {"immich/IMG_1.jpg": {"tags": ["plage", "coucher de soleil"], "how": "immich"}}


def test_claude_caption_with_fake_client(tmp_path):
    photo = tmp_path / "p.jpg"
    Image.new("RGB", (2000, 1500), (90, 140, 200)).save(photo)
    sent = {}

    class FakeMessages:
        def create(self, **kwargs):
            sent.update(kwargs)
            return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="Un ciel bleu.\nMots-clés : ciel, bleu")])

    client = SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages()))
    assert auto_captions.claude_caption({"language": "fr"}, photo, client=client) == ("Un ciel bleu.", ["ciel", "bleu"])
    assert sent["model"] == "claude-opus-5-5" and sent["fallbacks"] == "default" and sent["output_config"] == {"effort": "low"}
    image = sent["messages"][0]["content"][0]
    assert image["type"] == "image" and len(image["source"]["data"]) < 400_000  # copie réduite
    FakeMessages.create = lambda self, **k: SimpleNamespace(stop_reason="refusal", content=[])
    assert auto_captions.claude_caption({}, photo, client=client) is None


def test_settings_search_and_secret(admin_client, monkeypatch):
    from utils import library_search, smart_albums
    from utils.config_manager import load_config, save_config
    original = dict(load_config())
    try:
        r = admin_client.put("/api/auto_captions", json={"enabled": True, "mode": "claude", "api_key": "sk-ant-secret"}, headers=SAME).get_json()
        assert r["success"]
        state = admin_client.get("/api/auto_captions").get_json()
        assert state["has_key"] and "sk-ant-secret" not in str(state) and state["mode"] == "claude"
        auto_captions.store({"gdrive/a.jpg": {"caption": "Pique-nique au bord du lac", "tags": ["lac", "été"], "how": "claude"}})
        monkeypatch.setattr(smart_albums, "library", lambda favorites=(): [
            {"path": "gdrive/a.jpg", "source": "gdrive", "people": [], "favorite": False, "video": False, "date": "2025-07-01", "place": None},
            {"path": "gdrive/b.jpg", "source": "gdrive", "people": [], "favorite": False, "video": False, "date": "2025-07-02", "place": None}])
        items, total = library_search.search(text="lac")
        assert [i["path"] for i in items] == ["gdrive/a.jpg"]
    finally:
        save_config(original)
