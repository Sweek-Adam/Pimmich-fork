"""
Bouton physique : un appui met le cadre en veille ou le réveille.

Le bouton est surveillé par l'application web, toujours lancée, et non par le diaporama : sinon, le diaporama arrêté
par un appui ne pourrait plus voir l'appui suivant (le réveil). Câblage : une patte du bouton sur la broche choisie
(numérotation BCM), l'autre sur une masse (GND) ; la résistance de tirage interne du Raspberry Pi est utilisée.

La broche est lue 20 fois par seconde (pas de fil d'interruption) : un appui est un passage du niveau haut au niveau
bas, au plus un toutes les DEBOUNCE secondes (anti-rebond).
"""
import time

POLL = 0.05
DEBOUNCE = 0.5
STATE = {"available": None, "pin": None, "error": None, "last_press": None}  # pour l'interface


def load_gpio():
    """Module RPi.GPIO (fourni par rpi-lgpio sur les Raspberry Pi OS récents), ou None s'il manque."""
    try:
        import RPi.GPIO as GPIO
        return GPIO
    except Exception:  # absent, ou pas sur un Raspberry Pi
        return None


class Watcher:
    def __init__(self, gpio, on_press, clock=time.monotonic):
        self.gpio, self.on_press, self.clock = gpio, on_press, clock
        self.pin = None
        self.level = 1
        self.last_press = float("-inf")

    def configure(self, enabled, pin):
        """Active, déplace ou libère la broche surveillée (sans rien faire si rien n'a changé)."""
        wanted = int(pin) if enabled else None
        if wanted == self.pin:
            return
        if self.pin is not None:
            try:
                self.gpio.cleanup(self.pin)
            except Exception:
                pass
        self.pin = None
        if wanted is not None:
            self.gpio.setmode(self.gpio.BCM)
            self.gpio.setup(wanted, self.gpio.IN, pull_up_down=self.gpio.PUD_UP)
            self.pin = wanted
            self.level = self.gpio.input(wanted)

    def poll(self):
        """Lit la broche ; True (et action) si le bouton vient d'être enfoncé."""
        if self.pin is None:
            return False
        level = self.gpio.input(self.pin)
        now = self.clock()
        pressed = self.level and not level and now - self.last_press >= DEBOUNCE
        self.level = level
        if pressed:
            self.last_press = now
            self.on_press()
        return bool(pressed)
