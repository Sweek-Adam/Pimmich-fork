"""Télécommande de la TV (HDMI-CEC) : clavier « vc4-hdmi », touches -> actions du cadre."""
import struct

from utils import tv_remote

DEVICES = """I: Bus=0000 Vendor=0000 Product=0000 Version=0000
N: Name="Clavier USB"
S: Sysfs=/devices/platform/usb/input/input3
H: Handlers=sysrq kbd event3

I: Bus=001e Vendor=0000 Product=0000 Version=0001
N: Name="vc4-hdmi"
P: Phys=vc4-hdmi/input0
S: Sysfs=/devices/platform/soc/3f902000.hdmi/rc/rc0/input0
H: Handlers=kbd event0

I: Bus=0000 Vendor=0000 Product=0000 Version=0000
N: Name="vc4-hdmi HDMI Jack"
S: Sysfs=/devices/platform/soc/3f902000.hdmi/sound/card0/input1
H: Handlers=event1
"""


def event(code, value, kind=tv_remote.EV_KEY):
    return struct.pack(tv_remote.EVENT_FORMAT, 0, 0, kind, code, value)


def test_finds_the_hdmi_remote_only(tmp_path):
    path = tmp_path / "devices"
    path.write_text(DEVICES)
    assert tv_remote.find_device(path) == "/dev/input/event0"
    path.write_text(DEVICES.split("\n\n")[0])
    assert tv_remote.find_device(path) is None
    assert tv_remote.find_device(tmp_path / "absent") is None


def test_decode_keeps_presses_only():
    data = event(106, 1) + event(0, 0, kind=0) + event(106, 2) + event(106, 0) + event(352, 1)
    assert tv_remote.decode(data) == [106, 352]
    assert [tv_remote.action_for(c) for c in (106, 105, 352, 103, 128, 999)] == ["next", "previous", "pause", "love", "sleep", None]


def test_keys_drive_the_frame(monkeypatch, tmp_path):
    from utils import reactions, slideshow_commands
    from web import routes_slideshow, workers
    sent, loved, toggles = [], [], []
    monkeypatch.setattr(slideshow_commands, "send", sent.append)
    monkeypatch.setattr(reactions, "add", lambda photo, kind, who="": loved.append((photo, kind)))
    monkeypatch.setattr(routes_slideshow, "toggle_sleep", lambda: toggles.append(1))
    current = tmp_path / "current.txt"
    current.write_text("prepared/gdrive/a.jpg")
    monkeypatch.setattr(workers, "CURRENT_PHOTO_FILE", str(current))
    monkeypatch.setattr(workers, "is_slideshow_running", lambda: True)
    assert workers.tv_remote_action(106) == "next" and workers.tv_remote_action(352) == "pause"
    assert workers.tv_remote_action(103) == "love" and loved == [("prepared/gdrive/a.jpg", "love")]
    assert sent == ["next", "pause"]
    workers.tv_remote_action(128)  # stop : veille
    monkeypatch.setattr(workers, "is_slideshow_running", lambda: False)
    assert workers.tv_remote_action(106) == "wake"  # cadre en veille : n'importe quelle touche le réveille
    import time
    for _ in range(50):
        if len(toggles) == 2:
            break
        time.sleep(0.02)
    assert len(toggles) == 2 and sent == ["next", "pause"]
