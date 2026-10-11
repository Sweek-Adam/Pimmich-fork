"""Nouvelle interface (Vue, static/app) : page /app, traductions, extracteur des textes, version compilée cohérente."""
import io
import re
from pathlib import Path

import polib
import pytest

from utils import babel_frontend

ROOT = Path(__file__).resolve().parent.parent


def test_extractor():
    source = '''<b>{{ t("Bonjour") }}</b> :title="t('L\\'interface')" x.t("pas ça") t(`gabarit`) t("Il y a {n} ans", { n })'''
    assert [text for _line, text in babel_frontend.messages_in(source)] == ["Bonjour", "L'interface", "Il y a {n} ans"]
    lines = list(babel_frontend.extract(io.BytesIO('a\nt("Deux")'.encode()), [], [], {}))
    assert lines == [(2, None, "Deux", [])]


def test_frontend_strings_are_translated():
    msgids = babel_frontend.frontend_msgids()
    assert "Interface classique" in msgids and len(msgids) > 50
    for lang in ("en", "es", "de", "ja"):
        catalog = {e.msgid: e.msgstr for e in polib.pofile(ROOT / "translations" / lang / "LC_MESSAGES" / "messages.po")}
        missing = sorted(m for m in msgids if not catalog.get(m))
        assert not missing, f"{lang} : {missing[:5]}"


def test_built_app_is_consistent():
    index = (ROOT / "static" / "app" / "index.html").read_text()
    assert "<!--PIMMICH_BOOT-->" in index
    for asset in re.findall(r'(?:src|href)="/static/app/(assets/[^"]+)"', index):
        assert (ROOT / "static" / "app" / asset).is_file(), asset


def test_app_requires_login(client):
    assert client.get("/app").status_code in (302, 401)
    assert client.get("/api/i18n").status_code in (302, 401)


def test_app_page(admin_client):
    page = admin_client.get("/app")
    assert page.status_code == 200 and page.headers["Cache-Control"] == "no-store"
    html = page.get_data(as_text=True)
    assert 'window.PIMMICH = {"lang"' in html and '"admin": true' in html and "<!--PIMMICH_BOOT-->" not in html
    assert '"classic": "/configure"' in html


def test_i18n_api(admin_client):
    data = admin_client.get("/api/i18n?lang=en").get_json()
    assert data["lang"] == "en" and data["messages"]["Interface classique"] == "Classic interface"
    assert set(data["messages"]) <= babel_frontend.frontend_msgids()
    assert admin_client.get("/api/i18n?lang=fr").get_json()["messages"] == {}
