"""
Bureau Raspberry Pi OS :
- raccourci « Revenir au cadre Pimmich » (menu des applications et bureau), qui lance utils/switch_to_pimmich.sh
  (confirmation, puis redémarrage en mode cadre) ;
- démarrage automatique de Pimmich avec la session du bureau, en administration seule (PIMMICH_DESKTOP=1 : pas de
  diaporama par-dessus le bureau), pour que l'interface d'administration reste accessible.
En mode cadre photo, Sway ne lit pas ces fichiers : rien ne change.
"""
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
NAME = "pimmich-cadre.desktop"
AUTOSTART_NAME = "pimmich-admin.desktop"


def entry(project_dir=PROJECT_DIR):
    script = Path(project_dir) / "utils" / "switch_to_pimmich.sh"
    icon = Path(project_dir) / "static" / "pimmich_logo.png"
    return "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        "Version=1.0",
        "Name=Revenir au cadre Pimmich",
        "Name[en]=Back to the Pimmich frame",
        "Comment=Redémarre le Raspberry Pi en mode cadre photo",
        "Comment[en]=Restarts the Raspberry Pi in photo frame mode",
        f"Exec={script}",
        f"Icon={icon}",
        "Terminal=false",
        "Categories=Utility;",
        "",
    ])


def autostart_entry(project_dir=PROJECT_DIR):
    start = Path(project_dir) / "start_pimmich.sh"
    return "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        "Name=Pimmich (administration)",
        "Comment=Interface d'administration de Pimmich, sans diaporama",
        f"Exec=env PIMMICH_DESKTOP=1 {start}",
        "NoDisplay=true",
        "Terminal=false",
        "",
    ])


def install(home=None, project_dir=PROJECT_DIR):
    """Écrit le raccourci dans le menu et sur le bureau ; retourne les fichiers écrits."""
    home = Path(home or Path.home())
    text = entry(project_dir)
    written = []
    for folder in (home / ".local" / "share" / "applications", home / "Desktop", home / "Bureau"):
        if folder.name == "Bureau" and not folder.is_dir():
            continue  # bureau en français seulement s'il existe déjà
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / NAME
        path.write_text(text, encoding="utf-8")
        path.chmod(0o755)  # le gestionnaire de fichiers n'exécute que les raccourcis exécutables
        written.append(path)
    autostart = home / ".config" / "autostart"
    autostart.mkdir(parents=True, exist_ok=True)
    path = autostart / AUTOSTART_NAME
    path.write_text(autostart_entry(project_dir), encoding="utf-8")
    written.append(path)
    return written


if __name__ == "__main__":
    for path in install():
        print(f"Raccourci créé : {path}")
