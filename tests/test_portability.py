"""Édition ordinateur : fichiers d'échange, verrous et commandes au diaporama sans les particularités de Linux."""
import signal
import threading
import time

from utils import file_lock, platform_info, slideshow_commands


def test_tmp_path_is_unchanged_on_linux(monkeypatch):
    monkeypatch.setattr(platform_info, "LINUX", True)
    assert str(platform_info.tmp_path("pimmich_game.json")) == "/tmp/pimmich_game.json"
    monkeypatch.setattr(platform_info, "LINUX", False)
    assert platform_info.tmp_path("x").parent.name == "pimmich"


def test_guest_url_has_the_port_on_a_computer(monkeypatch):
    monkeypatch.setenv("PIMMICH_PORT", "8080")
    assert platform_info.guest_base_url("192.168.1.20") == "http://192.168.1.20:8080"
    monkeypatch.setenv("PIMMICH_PORT", "80")
    assert platform_info.guest_base_url("cadre.local") == "http://cadre.local"


def test_file_lock_serialises(tmp_path):
    order = []

    def worker(name):
        with file_lock.locked(tmp_path / "l.lock"):
            order.append(name + "+")
            time.sleep(0.05)
            order.append(name + "-")
    threads = [threading.Thread(target=worker, args=(n,)) for n in "ab"]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert order in (["a+", "a-", "b+", "b-"], ["b+", "b-", "a+", "a-"])


def test_commands_by_file_when_signals_are_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(slideshow_commands, "COMMAND_FILE", tmp_path / "cmd")
    monkeypatch.delattr(signal, "SIGUSR1", raising=False)
    monkeypatch.delattr(signal, "SIGUSR2", raising=False)
    monkeypatch.delattr(signal, "SIGTSTP", raising=False)
    slideshow_commands.send("next")
    assert slideshow_commands.pop() == "next" and slideshow_commands.pop() is None
    slideshow_commands.send("pause")
    assert slideshow_commands.pop() == "pause"


def test_commands_by_signal_on_unix(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(slideshow_commands, "PID_FILE", tmp_path / "pid")
    (tmp_path / "pid").write_text("4242")
    monkeypatch.setattr(slideshow_commands.os, "kill", lambda pid, sig: sent.append((pid, sig)))
    slideshow_commands.send(signal.SIGUSR2)
    assert sent == [(4242, signal.SIGUSR2)]
