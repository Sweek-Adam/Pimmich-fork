"""
Outil de développement : captures de l'interface (ordinateur et téléphone) avec Playwright.
Usage : python screenshots.py <dossier de sortie> <écran1> [<écran2> ...]
Un écran est « page » (ex. /configure) ou « page#onglet » (ex. /configure#tab-sources).
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5055"
VIEWPORTS = {"ordi": {"width": 1366, "height": 900}, "tel": {"width": 390, "height": 844}}
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
screens = sys.argv[2:]

with sync_playwright() as p:
    browser = p.chromium.launch()
    for device, viewport in VIEWPORTS.items():
        context = browser.new_context(viewport=viewport, device_scale_factor=1, is_mobile=device == "tel", has_touch=device == "tel")
        page = context.new_page()
        page.set_default_timeout(180000)  # le Pi 3 est lent à servir la page de configuration
        page.goto(f"{BASE}/login", wait_until="domcontentloaded")
        page.fill("input[name=username]", "admin")
        page.fill("input[name=password]", "admin-test-pass")
        with page.expect_navigation(wait_until="domcontentloaded"):
            page.press("input[name=password]", "Enter")
        for screen in screens:
            url, _, tab = screen.partition("#")
            page.goto(BASE + url, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)  # scripts d'initialisation de la page
            if tab:
                page.evaluate("""(tab) => {
                    const button = document.querySelector(`[onclick*="'${tab}'"], [data-tab="${tab}"]`);
                    const group = button && button.closest('.sub-nav-group');
                    if (group && window.switchMainGroup) window.switchMainGroup(group.id);
                    if (window.openTab) window.openTab(null, tab);
                }""", tab)
                page.wait_for_timeout(600)
            name = (tab or url.strip("/") or "accueil").replace("/", "_")
            page.screenshot(path=str(out / f"{device}_{name}.png"), full_page=device == "tel")
        context.close()
    browser.close()
print("captures :", ", ".join(sorted(f.name for f in out.iterdir())))
