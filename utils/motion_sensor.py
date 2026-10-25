"""
Détecteur de mouvement (capteur infrarouge PIR, ex. HC-SR501, quelques euros) : l'écran s'éteint quand personne n'est
passé devant le cadre depuis un moment, et se rallume dès que quelqu'un entre dans la pièce.

Seul l'écran s'éteint (veille de l'écran, et TV en veille si le HDMI-CEC est activé) : le diaporama continue, si
bien que le réveil est immédiat. Rien ne se passe en dehors des heures d'affichage (le planning décide alors).
Câblage : VCC sur 5 V, GND sur une masse, OUT sur la broche choisie (numérotation BCM) ; la sortie du capteur passe au
niveau haut tant qu'il voit du mouvement.
"""
import time

POLL = 0.2
STATE = {"available": None, "pin": None, "error": None, "last_motion": None, "screen_off": False}  # pour l'interface


class Watcher:
    def __init__(self, gpio):
        self.gpio = gpio
        self.pin = None

    def configure(self, enabled, pin):
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
            self.gpio.setup(wanted, self.gpio.IN, pull_up_down=self.gpio.PUD_DOWN)
            self.pin = wanted

    def motion(self):
        return self.pin is not None and bool(self.gpio.input(self.pin))


class Idle:
    """Décide d'éteindre ou de rallumer l'écran : decide(mouvement, maintenant, cadre_actif) -> "off", "on" ou None."""

    def __init__(self, delay_seconds, now=None):
        self.delay = delay_seconds
        self.last_motion = time.monotonic() if now is None else now
        self.off = False

    def decide(self, motion, now, active):
        if motion:
            self.last_motion = now
            if self.off:
                self.off = False
                return "on"
            return None
        if not active:
            self.off = False  # le planning a la main (nuit, cadre en veille) : l'écran sera rallumé par lui
            self.last_motion = now
            return None
        if not self.off and now - self.last_motion >= self.delay:
            self.off = True
            return "off"
        return None
