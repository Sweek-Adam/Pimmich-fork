"""Le JavaScript intégré aux pages doit rester valide dans toutes les langues (un texte traduit avec une
apostrophe ou des guillemets peut casser une chaîne JavaScript et désactiver tout un onglet)."""
import re
import shutil
import subprocess

import pytest

NODE = shutil.which("node")
LANGS = ["fr", "en", "es", "de", "ja"]


def check_scripts(html, tmp_path, label):
    scripts = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)
    assert scripts, f"aucun script trouvé dans {label}"
    errors = []
    for i, js in enumerate(scripts):
        path = tmp_path / f"{label}-{i}.js"
        path.write_text(js)
        result = subprocess.run([NODE, "--check", str(path)], capture_output=True, text=True)
        if result.returncode:
            errors.append(f"{label} script {i}:\n" + "\n".join(result.stderr.strip().splitlines()[:4]))
    assert not errors, "\n\n".join(errors)


@pytest.mark.skipif(not NODE, reason="Node.js absent : vérification de syntaxe JavaScript impossible")
@pytest.mark.parametrize("lang", LANGS)
def test_configure_page_scripts_are_valid(admin_client, tmp_path, lang):
    html = admin_client.get(f"/configure?lang={lang}").get_data(as_text=True)
    check_scripts(html, tmp_path, f"configure-{lang}")


@pytest.mark.skipif(not NODE, reason="Node.js absent : vérification de syntaxe JavaScript impossible")
@pytest.mark.parametrize("lang", LANGS)
def test_public_pages_scripts_are_valid(client, tmp_path, lang):
    for page in ["/upload", "/login"]:
        html = client.get(f"{page}?lang={lang}").get_data(as_text=True)
        if "<script" in html:
            check_scripts(html, tmp_path, f"{page.strip('/')}-{lang}")
