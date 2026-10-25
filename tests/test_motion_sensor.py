"""Détecteur de mouvement : écran éteint après un moment sans personne, rallumé au premier mouvement."""
from utils import motion_sensor


def test_screen_goes_off_then_back_on():
    idle = motion_sensor.Idle(600, now=0)
    assert idle.decide(False, 300, True) is None
    assert idle.decide(True, 400, True) is None          # quelqu'un passe : le délai repart
    assert idle.decide(False, 900, True) is None
    assert idle.decide(False, 1000, True) == "off"
    assert idle.decide(False, 1100, True) is None        # déjà éteint
    assert idle.decide(True, 1200, True) == "on"
    assert idle.decide(True, 1201, True) is None


def test_nothing_happens_outside_display_hours():
    idle = motion_sensor.Idle(60, now=0)
    assert idle.decide(False, 1000, False) is None       # nuit ou cadre en veille : le planning décide
    assert idle.decide(False, 1030, True) is None        # le délai repart à la reprise
    assert idle.decide(False, 1061, True) == "off"
    assert idle.decide(False, 1100, False) is None and not idle.off


class FakeGPIO:
    BCM, IN, PUD_DOWN = "bcm", "in", "down"

    def __init__(self):
        self.level, self.setups, self.cleaned = 0, [], []

    def setmode(self, mode):
        pass

    def setup(self, pin, mode, pull_up_down=None):
        self.setups.append((pin, pull_up_down))

    def cleanup(self, pin):
        self.cleaned.append(pin)

    def input(self, pin):
        return self.level


def test_watcher_reads_the_pin():
    gpio = FakeGPIO()
    watcher = motion_sensor.Watcher(gpio)
    assert watcher.motion() is False
    watcher.configure(True, 24)
    assert gpio.setups == [(24, "down")]
    gpio.level = 1
    assert watcher.motion() is True
    watcher.configure(False, 24)
    assert gpio.cleaned == [24] and watcher.motion() is False
