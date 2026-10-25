"""
Commandes de l'interface au diaporama (photo suivante, précédente, pause) : signaux Unix sur le Raspberry Pi et le
Mac, petit fichier de commande sous Windows (pas de SIGUSR1 / SIGUSR2 / SIGTSTP).
"""
import os
import signal

from utils.platform_info import tmp_path

PID_FILE = tmp_path("pimmich_slideshow.pid")
COMMAND_FILE = tmp_path("pimmich_slideshow_command")
SIGNALS = {"next": "SIGUSR1", "previous": "SIGUSR2", "pause": "SIGTSTP"}


def _name(command):
    """Accepte « next » ou un signal (signal.SIGUSR1...) : retourne next / previous / pause."""
    if command in SIGNALS:
        return command
    for name, sig in SIGNALS.items():
        if getattr(signal, sig, None) == command:
            return name
    raise ValueError(f"commande inconnue : {command}")


def send(command):
    command = _name(command)
    sig = getattr(signal, SIGNALS[command], None)
    if sig is not None:
        os.kill(int(PID_FILE.read_text().strip()), sig)
    else:
        COMMAND_FILE.write_text(command, encoding="utf-8")


def pop():
    """Côté diaporama (Windows) : commande en attente, ou None."""
    try:
        command = COMMAND_FILE.read_text(encoding="utf-8").strip()
        COMMAND_FILE.unlink()
        return command or None
    except OSError:
        return None
