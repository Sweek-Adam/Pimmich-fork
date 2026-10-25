#!/usr/bin/env python3
"""
Pimmich « événement » : le cadre photo sur un ordinateur (Mac, Windows, Linux), pour un mariage, un anniversaire...
Le diaporama s'affiche sur l'écran choisi (portable, télé, vidéoprojecteur) ; les invités scannent le QR code et
déposent leurs photos depuis leur téléphone (même Wi-Fi que l'ordinateur).

    python pimmich_event.py                 fenêtre de réglages, puis lancement
    python pimmich_event.py --no-gui ...    sans fenêtre (voir --help)

Les photos déposées et les photos préparées peuvent être rangées où l'on veut (disque externe, dossier
synchronisé...) : Pimmich y accède par un lien depuis static/photos et static/prepared.
"""
import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SETTINGS = ROOT / "config" / "event.json"
CREDENTIALS = ROOT / "config" / "credentials.json"
DEFAULTS = {"photos_dir": str(ROOT / "static" / "photos"), "prepared_dir": str(ROOT / "static" / "prepared"),
            "display": 0, "windowed": False, "name": "", "hours": 12, "port": 8080, "only_party": True, "auto_approve": True}


# --- Réglages ---

def load_settings():
    try:
        return dict(DEFAULTS, **json.loads(SETTINGS.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return dict(DEFAULTS)


def save_settings(settings):
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def displays():
    """Écrans branchés : [(numéro, largeur, hauteur)]."""
    try:
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        import pygame
        pygame.display.init()
        sizes = pygame.display.get_desktop_sizes()
        pygame.display.quit()
        return [(i, w, h) for i, (w, h) in enumerate(sizes)]
    except Exception:
        return [(0, 1920, 1080)]


def local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("192.0.2.1", 80))  # aucune donnée envoyée : sert à connaître l'adresse sur le réseau
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


# --- Dossiers des photos ---

def _is_link(path):
    try:
        return path.is_symlink() or (sys.platform.startswith("win") and os.path.isjunction(path))
    except AttributeError:  # Python < 3.12
        return path.is_symlink()


def link_folder(link, target):
    """static/photos (ou prepared) mène au dossier choisi. Retourne un message d'erreur, ou None."""
    link = Path(link)
    if Path(target).expanduser().absolute() == link.absolute():  # retour au dossier par défaut
        if _is_link(link):
            link.unlink() if link.is_symlink() else os.rmdir(link)
        link.mkdir(parents=True, exist_ok=True)
        return None
    target = Path(target).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    if link.exists() and not _is_link(link) and link.resolve() == target:
        return None  # dossier par défaut, dans Pimmich
    if _is_link(link):
        if link.resolve() == target:
            return None
        link.unlink() if link.is_symlink() else os.rmdir(link)
    elif link.exists():
        if any(link.iterdir()):
            return (f"Le dossier {link} contient déjà des fichiers : déplacez-les dans {target}, "
                    f"ou gardez le dossier par défaut.")
        link.rmdir()
    link.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):  # jonction : pas besoin des droits administrateur
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True)
        if result.returncode != 0:
            return f"Impossible de relier {link} à {target} : {result.stderr.strip() or result.stdout.strip()}"
    else:
        os.symlink(target, link, target_is_directory=True)
    return None


# --- Compte administrateur ---

def ensure_admin(password=None):
    """Crée le compte « admin » au premier lancement. Retourne le mot de passe s'il vient d'être créé."""
    if CREDENTIALS.exists():
        return None
    from werkzeug.security import generate_password_hash
    password = password or secrets.token_urlsafe(9)
    CREDENTIALS.parent.mkdir(parents=True, exist_ok=True)
    CREDENTIALS.write_text(json.dumps({"username": "admin", "password_hash": generate_password_hash(password),
                                       "flask_secret_key": secrets.token_hex(24)}, indent=2), encoding="utf-8")
    try:
        os.chmod(CREDENTIALS, 0o600)
    except OSError:
        pass
    return password


# --- Configuration de Pimmich pour l'événement ---

def prepare_config(settings, screens):
    from utils import party
    from utils.config_manager import load_config, save_config
    config = dict(load_config())
    size = next(((w, h) for i, w, h in screens if i == settings["display"]), screens[0][1:] if screens else (1920, 1080))
    config.update(desktop_display=settings["display"], desktop_windowed=bool(settings["windowed"]),
                  display_width=int(size[0]), display_height=int(size[1]),
                  # le diaporama tourne pendant tout l'événement (pas d'heures de veille)
                  active_start_weekday="00:00", active_end_weekday="23:59", active_start_weekend="00:00", active_end_weekend="23:59",
                  show_guest_qr=True, heavy_videos_at_night=False)
    if settings.get("name"):
        config = party.start(config, settings["name"], settings["hours"], settings["only_party"], settings["auto_approve"])
    save_config(config)
    return config


# --- Lancement ---

class Event:
    def __init__(self, settings):
        self.settings = settings
        self.process = None

    def environment(self):
        return dict(os.environ, PIMMICH_EDITION="event", PIMMICH_PORT=str(self.settings["port"]), PIMMICH_CREDENTIALS_PATH=str(CREDENTIALS))

    def start(self):
        self.process = subprocess.Popen([sys.executable, "-u", "app.py"], cwd=ROOT, env=self.environment())
        url = f"http://127.0.0.1:{self.settings['port']}/login"
        for _ in range(120):
            try:
                with urllib.request.urlopen(url, timeout=2) as response:
                    if response.status == 200:
                        return True
            except OSError:
                pass
            if self.process.poll() is not None:
                return False
            time.sleep(0.5)
        return False

    def stop(self):
        try:
            import psutil
        except ImportError:
            psutil = None
        for proc in psutil.process_iter(attrs=["cmdline"]) if psutil else []:
            try:
                cmdline = proc.info.get("cmdline") or []
                if any("local_slideshow.py" in part for part in cmdline) and Path(proc.cwd()).resolve() == ROOT:
                    proc.terminate()  # le diaporama lancé par ce Pimmich
            except Exception:
                continue
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(10)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def urls(self):
        base = f"http://{local_ip()}:{self.settings['port']}"
        return {"admin": f"http://localhost:{self.settings['port']}/app", "guests": f"{base}/upload", "games": f"{base}/jeu"}


def launch(settings, password=None, on_message=print):
    screens = displays()
    for link, key in ((ROOT / "static" / "photos", "photos_dir"), (ROOT / "static" / "prepared", "prepared_dir")):
        error = link_folder(link, settings[key])
        if error:
            raise RuntimeError(error)
    created = ensure_admin(password)
    if created and not password:
        on_message(f"Compte administrateur créé : admin / {created} (notez-le)")
    prepare_config(settings, screens)
    save_settings(settings)
    event = Event(settings)
    if not event.start():
        event.stop()
        raise RuntimeError("Pimmich n'a pas démarré : voir logs/pimmich.log")
    return event


# --- Fenêtre de réglages ---

def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    settings = load_settings()
    screens = displays()
    first_run = not CREDENTIALS.exists()
    root = tk.Tk()
    root.title("Pimmich – événement")
    frame = ttk.Frame(root, padding=16)
    frame.grid(sticky="nsew")
    values = {key: tk.StringVar(value=str(settings[key])) for key in ("photos_dir", "prepared_dir", "name", "hours", "port")}
    windowed = tk.BooleanVar(value=bool(settings["windowed"]))
    only_party = tk.BooleanVar(value=bool(settings["only_party"]))
    password = tk.StringVar()
    screen_labels = [f"Écran {i + 1} : {w} × {h}" + (" (celui-ci)" if i == 0 else "") for i, w, h in screens]
    screen_choice = tk.StringVar(value=screen_labels[min(int(settings["display"]), len(screen_labels) - 1)])
    row = 0

    def line(label, widget, button=None):
        nonlocal row
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4)
        widget.grid(row=row, column=1, sticky="ew", padx=8)
        if button:
            button.grid(row=row, column=2)
        row += 1

    def chooser(var):
        return lambda: var.set(filedialog.askdirectory(initialdir=var.get()) or var.get())

    ttk.Label(frame, text="Le cadre photo sur cet ordinateur", font=("", 15, "bold")).grid(row=row, column=0, columnspan=3, sticky="w")
    row += 1
    line("Nom de la fête", ttk.Entry(frame, textvariable=values["name"], width=40))
    line("Durée (heures)", ttk.Spinbox(frame, from_=1, to=48, textvariable=values["hours"], width=6))
    line("Écran du diaporama", ttk.Combobox(frame, values=screen_labels, textvariable=screen_choice, state="readonly", width=38))
    line("", ttk.Checkbutton(frame, text="Dans une fenêtre (plutôt qu'en plein écran)", variable=windowed))
    line("", ttk.Checkbutton(frame, text="Montrer seulement les photos de la fête", variable=only_party))
    line("Photos déposées", ttk.Entry(frame, textvariable=values["photos_dir"], width=40), ttk.Button(frame, text="Choisir…", command=chooser(values["photos_dir"])))
    line("Photos préparées", ttk.Entry(frame, textvariable=values["prepared_dir"], width=40), ttk.Button(frame, text="Choisir…", command=chooser(values["prepared_dir"])))
    line("Port", ttk.Entry(frame, textvariable=values["port"], width=8))
    if first_run:
        line("Mot de passe admin", ttk.Entry(frame, textvariable=password, show="•", width=24))
    status = ttk.Label(frame, text="", foreground="#555", wraplength=520, justify="left")
    status.grid(row=row + 1, column=0, columnspan=3, sticky="w", pady=(10, 0))
    state = {"event": None}

    def start():
        try:
            new = dict(settings, photos_dir=values["photos_dir"].get(), prepared_dir=values["prepared_dir"].get(),
                       name=values["name"].get().strip(), hours=int(values["hours"].get() or 12), port=int(values["port"].get() or 8080),
                       windowed=windowed.get(), only_party=only_party.get(), display=screen_labels.index(screen_choice.get()))
        except ValueError:
            messagebox.showerror("Pimmich", "Durée et port : des nombres, s'il vous plaît.")
            return
        if first_run and len(password.get()) < 6:
            messagebox.showerror("Pimmich", "Choisissez un mot de passe administrateur (6 caractères au moins).")
            return
        launch_button.config(state="disabled")
        status.config(text="Démarrage… (préparation des dossiers, du diaporama et du serveur)")

        def work():
            try:
                event = launch(new, password.get() or None)
            except Exception as e:
                root.after(0, lambda: (messagebox.showerror("Pimmich", str(e)), launch_button.config(state="normal"), status.config(text="")))
                return
            state["event"] = event
            urls = event.urls()
            webbrowser.open(urls["admin"])
            root.after(0, lambda: (status.config(text=f"C'est parti ! Invités : {urls['guests']}  ·  Jeux : {urls['games']}\n"
                                                       f"Administration : {urls['admin']}  ·  Fermer cette fenêtre arrête Pimmich."),
                                   stop_button.config(state="normal")))
        threading.Thread(target=work, daemon=True).start()

    def stop():
        if state["event"]:
            state["event"].stop()
            state["event"] = None
        status.config(text="Pimmich est arrêté.")
        launch_button.config(state="normal")
        stop_button.config(state="disabled")

    buttons = ttk.Frame(frame)
    buttons.grid(row=row, column=0, columnspan=3, sticky="w", pady=(12, 0))
    launch_button = ttk.Button(buttons, text="Lancer", command=start)
    launch_button.pack(side="left")
    stop_button = ttk.Button(buttons, text="Arrêter", command=stop, state="disabled")
    stop_button.pack(side="left", padx=8)
    root.protocol("WM_DELETE_WINDOW", lambda: (stop(), root.destroy()))
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description="Pimmich sur un ordinateur, pour un événement.")
    parser.add_argument("--no-gui", action="store_true", help="sans fenêtre de réglages")
    parser.add_argument("--name", help="nom de la fête (mode fête : QR code, photos des invités affichées aussitôt)")
    parser.add_argument("--hours", type=int, help="durée de la fête")
    parser.add_argument("--display", type=int, help="numéro de l'écran (0 = celui de l'ordinateur)")
    parser.add_argument("--windowed", action="store_true", help="dans une fenêtre plutôt qu'en plein écran")
    parser.add_argument("--photos", help="dossier des photos déposées")
    parser.add_argument("--prepared", help="dossier des photos préparées")
    parser.add_argument("--port", type=int, help="port du serveur (8080 par défaut)")
    parser.add_argument("--password", help="mot de passe administrateur (premier lancement)")
    parser.add_argument("--list-displays", action="store_true", help="affiche les écrans branchés et quitte")
    args = parser.parse_args()
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:  # modules de Pimmich (utils/...) : seulement au lancement, jamais à l'import
        sys.path.insert(0, str(ROOT))
    if args.list_displays:
        for i, w, h in displays():
            print(f"{i} : {w} × {h}")
        return
    if not args.no_gui:
        try:
            return gui()
        except ImportError:
            print("Tkinter absent : lancement sans fenêtre (voir --help).")
    settings = load_settings()
    for key, value in (("name", args.name), ("hours", args.hours), ("display", args.display), ("photos_dir", args.photos),
                       ("prepared_dir", args.prepared), ("port", args.port)):
        if value is not None:
            settings[key] = value
    if args.windowed:
        settings["windowed"] = True
    event = launch(settings, args.password)
    import signal as signals  # arrêt par le système (fermeture de session, kill) : on arrête aussi le diaporama
    for name in ("SIGTERM", "SIGHUP"):
        if hasattr(signals, name):
            signals.signal(getattr(signals, name), lambda *_: sys.exit(0))
    urls = event.urls()
    print(f"\nPimmich est lancé.\n  Administration : {urls['admin']}\n  Invités : {urls['guests']}\n  Jeux : {urls['games']}\n"
          "Ctrl+C pour arrêter.")
    webbrowser.open(urls["admin"])
    try:
        while event.process.poll() is None:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        event.stop()


if __name__ == "__main__":
    main()
