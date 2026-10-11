"""
Météo animée : quand il pleut ou neige dehors, quelques gouttes ou flocons tombent sur la photo (animation légère,
calculée pour rester fluide sur un Raspberry Pi 3). L'effet suit l'icône de la météo actuelle (OpenWeather).
"""
import math
import random

EFFECTS = {"09": "rain", "10": "rain", "11": "storm", "13": "snow"}
ANIMATION_SECONDS = 8  # mode « au début de chaque photo »
FPS = 20


def effect_for(icon_code):
    """Effet pour une icône OpenWeather (« 10d » : pluie...), sinon None."""
    return EFFECTS.get(str(icon_code or "")[:2])


def wanted(config, elapsed):
    """L'animation doit-elle tourner à ce moment de l'affichage de la photo ?"""
    mode = config.get("weather_animation", "start")
    return mode == "always" or (mode == "start" and elapsed < ANIMATION_SECONDS)


class Particles:
    """Gouttes (traits inclinés) ou flocons (points qui ondulent), qui réapparaissent en haut une fois tombés."""

    def __init__(self, effect, width, height, seed=None):
        self.effect, self.width, self.height = effect, width, height
        self.random = random.Random(seed)
        count = {"rain": 140, "storm": 190, "snow": 110}[effect]
        scale = max(0.5, min(2.0, width * height / (1920 * 1080)))
        self.items = [self._new(spread=True) for _ in range(int(count * scale))]
        self.flash = 0.0

    def _new(self, spread=False):
        r = self.random
        y = r.uniform(0, self.height) if spread else r.uniform(-self.height * 0.2, 0)
        if self.effect == "snow":
            return {"x": r.uniform(0, self.width), "y": y, "speed": r.uniform(40, 110) * self.height / 1080,
                    "size": r.uniform(1.5, 4.5) * self.height / 1080, "phase": r.uniform(0, 6.28), "sway": r.uniform(10, 35)}
        return {"x": r.uniform(-self.width * 0.1, self.width), "y": y, "speed": r.uniform(700, 1100) * self.height / 1080,
                "length": r.uniform(12, 26) * self.height / 1080}

    def step(self, dt):
        """Avance de dt secondes."""
        for p in self.items:
            p["y"] += p["speed"] * dt
            if self.effect == "snow":
                p["phase"] += dt
            else:
                p["x"] += p["speed"] * dt * 0.18  # le vent incline la pluie
            if p["y"] > self.height + 30 or p["x"] > self.width + 30:
                p.update(self._new())
        if self.effect == "storm":
            self.flash = max(0.0, self.flash - dt * 3)
            if self.random.random() < dt * 0.08:  # un éclair de temps en temps
                self.flash = 1.0

    def shapes(self):
        """Ce qu'il faut dessiner : ("line", (x1, y1), (x2, y2)) ou ("dot", (x, y), rayon)."""
        for p in self.items:
            if self.effect == "snow":
                x = p["x"] + math.sin(p["phase"]) * p["sway"]
                yield ("dot", (int(x), int(p["y"])), max(1, int(p["size"])))
            else:
                end = (p["x"] + p["length"] * 0.18, p["y"] + p["length"])
                yield ("line", (int(p["x"]), int(p["y"])), (int(end[0]), int(end[1])))
