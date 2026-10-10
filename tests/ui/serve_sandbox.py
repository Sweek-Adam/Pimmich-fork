"""
Outil de développement : lance Pimmich dans une copie isolée (comptes de test) sur 127.0.0.1:5055,
pour les captures d'écran de l'interface. Option --real-photos : affiche les photos préparées du cadre (lecture seule).
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import conftest  # noqa: E402  (crée la copie isolée et s'y place)

if "--real-photos" in sys.argv:
    real = Path(os.path.expanduser("~/pimmich/static"))
    for name in ("prepared", "photos", "composition_previews"):
        target = conftest._SANDBOX / "static" / name
        if (real / name).exists() and not target.exists():
            target.symlink_to(real / name)

import app as app_module  # noqa: E402
for module in list(sys.modules.values()):  # ne jamais toucher au vrai diaporama
    if getattr(module, "restart_slideshow_process", None) is not None and module.__name__ != "utils.slideshow_manager":
        module.restart_slideshow_process = lambda: None
app_module.app.run(host="127.0.0.1", port=5055, debug=False, use_reloader=False)
