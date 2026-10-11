"""Citation du jour : citations intégrées (5 langues), mots de la famille, image du jour, réglages."""
import json
from datetime import date, timedelta

from utils import quotes

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}
FAMILY = [{"text": "On n'est pas aux pièces !", "author": "Papi"}, {"text": "  "}]


def test_builtin_quotes_exist_in_every_language():
    data = json.loads(quotes.QUOTES_FILE.read_text(encoding="utf-8"))
    assert set(data) == {"fr", "en", "es", "de", "ja"} and all(len(v) >= 10 for v in data.values())
    assert all(isinstance(t, str) and t and isinstance(a, str) for v in data.values() for t, a in v)
    assert quotes.builtin("en")[0]["kind"] == "builtin" and quotes.builtin("xx") == quotes.builtin("fr")


def test_same_quote_all_day_and_family_words_come_back():
    config = {"language": "fr", "quotes_family": FAMILY}
    day = date(2025, 10, 13)
    assert quotes.of_the_day(config, day) == quotes.of_the_day(config, day)
    picked = [quotes.of_the_day(config, day + timedelta(days=i)) for i in range(30)]
    assert len({q["text"] for q in picked}) > 5
    assert sum(q["kind"] == "family" for q in picked) >= 10  # un jour sur trois
    only_family = quotes.of_the_day(dict(config, quote_mode="family"), day)
    assert only_family["text"] == "On n'est pas aux pièces !"
    assert quotes.of_the_day({"quote_mode": "family"}, day)["kind"] == "builtin"  # pas encore de mots de la famille
    assert all(q["kind"] == "builtin" for q in (quotes.of_the_day(dict(config, quote_mode="builtin"), day + timedelta(days=i)) for i in range(9)))


def test_image_of_the_day(monkeypatch, tmp_path):
    monkeypatch.setattr(quotes, "OUTPUT_DIR", tmp_path / "citation")
    image = quotes.render({"language": "en"}, 640, 360, day=date(2025, 1, 1))
    assert image.size == (640, 360)
    config = {"quote_enabled": True, "display_width": 320, "display_height": 480}
    path = quotes.refresh(config)
    assert path.exists() and path.name == "citation.jpg"
    assert quotes.refresh(dict(config, quote_enabled=False)) is None and not path.exists()


def test_quotes_api(admin_client, monkeypatch, tmp_path):
    from utils.config_manager import load_config, save_config
    from web import routes_quotes
    monkeypatch.setattr(routes_quotes, "refresh_quote", lambda config=None: None)
    original = dict(load_config())
    try:
        r = admin_client.post("/api/quotes", json={"enabled": True, "mode": "family", "style": "ardoise",
                                                   "family": FAMILY + ["pas un objet"]}, headers=SAME_ORIGIN).get_json()
        assert r["success"]
        config = load_config()
        assert "citation" in config["display_sources"] and config["quote_style"] == "ardoise"
        assert config["quotes_family"] == [{"text": "On n'est pas aux pièces !", "author": "Papi"}]
        data = admin_client.get("/api/quotes").get_json()
        assert data["today"]["author"] == "Papi" and data["enabled"]
        preview = admin_client.get("/api/quotes/preview")
        assert preview.status_code == 200 and preview.mimetype == "image/jpeg"
        admin_client.post("/api/quotes", json={"enabled": False}, headers=SAME_ORIGIN)
        assert "citation" not in load_config()["display_sources"]
    finally:
        save_config(original)
