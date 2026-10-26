"""Photomaton : tirage 10 × 15 légendé, imprimante trouvée sur le réseau, quotas des invités (imprimante simulée)."""
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from utils import photobooth

SAME = {"Sec-Fetch-Site": "same-origin"}


@pytest.fixture(autouse=True)
def counts(tmp_path, monkeypatch):
    monkeypatch.setattr(photobooth, "COUNTS_FILE", tmp_path / "counts.json")


def test_card_is_a_captioned_print():
    landscape = photobooth.card(Image.new("RGB", (4000, 3000), (200, 40, 40)), "Les 40 ans de Léa", "26 octobre 2026")
    assert landscape.size == (1800, 1200) and landscape.getpixel((10, 10)) == (255, 255, 255)  # marge blanche
    assert landscape.getpixel((900, 500))[0] > 150                                            # la photo
    portrait = photobooth.card(Image.new("RGB", (1000, 1600)))
    assert portrait.size == (1200, 1800)
    assert photobooth.card(Image.new("RGB", (4000, 3000)), "Fête", "", paper="a4").size == (3508, 2480)  # A4 à 300 points par pouce


def test_discover_and_quota(monkeypatch):
    out = "ipp://EPSON1848C8.local:631/ipp/print\nipps://Brother-HL.local:631/ipp/print\n"
    monkeypatch.setattr(photobooth.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, out, ""))
    assert sorted(p["name"] for p in photobooth.discover(1)) == ["Brother HL", "EPSON1848C8"]
    assert photobooth.take("guest:a", 2) and photobooth.take("guest:a", 2) and not photobooth.take("guest:a", 2)
    assert photobooth.take("guest:b", 2)
    assert photobooth.setup("file:///etc/passwd")[0] is False  # seulement une imprimante réseau


def test_guest_prints_the_photo_on_screen(admin_client, client, monkeypatch, tmp_path):
    from utils import party
    from utils.config_manager import load_config, save_config
    from web import routes_guests, routes_party
    printed = []
    monkeypatch.setattr(photobooth, "send", lambda image, title="", subtitle="", **k: printed.append((image.size, title)) or "Pimmich_Photomaton-1")
    folder = Path("static/prepared/fete_test")
    folder.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (640, 360), (20, 120, 200)).save(folder / "a.jpg")
    monkeypatch.setattr(routes_guests, "_now_showing", lambda: "prepared/fete_test/a.jpg")
    original = dict(load_config())
    guest = client.application.test_client()
    try:
        assert guest.post("/upload/print", json={}, headers=SAME).status_code == 403  # pas de fête
        config = party.start(dict(original, photobooth={"enabled": True, "uri": "ipp://x.local/ipp/print", "per_guest": 1}), "Anniversaire", 2)
        save_config(config)
        r = guest.post("/upload/print", json={}, headers=SAME).get_json()
        assert r["success"] and printed[0][1] == "Anniversaire"
        assert guest.post("/upload/print", json={}, headers=SAME).status_code == 429  # un tirage par invité
        assert "Imprimer la photo" in guest.get("/upload").get_data(as_text=True)
        # Photomaton automatique : chaque photo reçue, jusqu'au plafond
        save_config(dict(config, photobooth={"enabled": True, "uri": "ipp://x.local/ipp/print", "auto": True, "max_auto": 1}))
        routes_party.auto_print(folder / "a.jpg")
        routes_party.auto_print(folder / "a.jpg")
        assert len(printed) == 2
    finally:
        save_config(original)
        import shutil
        shutil.rmtree(folder, ignore_errors=True)


def test_clear_message_when_printing_is_off(monkeypatch):
    monkeypatch.setattr(photobooth.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(
        a, 1, "", "lpadmin: Unable to connect to server: Mauvais descripteur de fichier"))
    ok, message = photobooth.setup("ipp://EPSON1848C8.local:631/ipp/print")
    assert not ok and "enable_printing.sh" in message
