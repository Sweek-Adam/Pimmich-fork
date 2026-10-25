"""
Affichage : baisse de luminosité du soir (à chaque image), battement de cœur, GIF animés rejoués par-dessus l'image.
"""
import logging
import math
import os
import threading
from pathlib import Path

import pygame
from PIL import Image, ImageChops

from utils import animated
from utils.config_manager import load_config

logger = logging.getLogger("pimmich.slideshow")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREPARED_BASE_DIR = Path(BASE_DIR) / "static" / "prepared"


# New function to perform a transition between two images
def _heartbeat(grace=0):
    """Le diaporama est vivant (surveillance : il est relancé s'il se fige)."""
    try:
        from utils import reliability
        reliability.beat(grace)
    except Exception:
        pass


# --- Luminosité du soir : les photos sont assombries au moment de l'affichage (tous écrans HDMI) ---
_DIM = {"level": 1.0, "surface": None}


_raw_flip = pygame.display.flip


def _dimmed_flip(*args):
    _heartbeat()
    level = _DIM["level"]
    screen = pygame.display.get_surface()
    if level >= 0.99 or screen is None:
        return _raw_flip()
    surface = _DIM["surface"]
    if surface is None or surface.get_size() != screen.get_size() or surface.get_alpha() != int(255 * (1 - level)):
        surface = pygame.Surface(screen.get_size())
        surface.fill((0, 0, 0))
        surface.set_alpha(int(255 * (1 - level)))
        _DIM["surface"] = surface
    backup = screen.copy()  # l'image n'est assombrie qu'à l'écran : les dessins suivants partent de l'original
    screen.blit(surface, (0, 0))
    _raw_flip()
    screen.blit(backup, (0, 0))


pygame.display.flip = _dimmed_flip


def update_brightness(config):
    """Luminosité du moment (baisse du soir), d'après l'heure ou le coucher du soleil."""
    try:
        from utils import night, sky
        sunset = sky.today(config).get("sunset") if config.get("dim_start") == "sunset" else None
        _DIM["level"] = night.brightness(config, sunset=sunset)
    except Exception as e:
        logger.debug(f"Luminosité du soir : {e}")
        _DIM["level"] = 1.0
    return _DIM["level"]


class GifPlayer:
    """
    Rejoue les GIF animés d'une image affichée (photo seule ou composition, voir utils/animated.py) par-dessus
    l'image fixe : seules les zones des GIF sont redessinées, l'horloge et la météo restent par-dessus.
    Les images sont décodées en arrière-plan (la photo reste fixe le temps de les préparer).
    """
    BUDGET = 48 * 1024 * 1024  # mémoire des images décodées : selon le profil matériel (le Raspberry Pi 3 n'a que 1 Go)

    def __init__(self, display_path, base_surface, pil_image):
        from utils import hardware_profile
        self.budget = hardware_profile.value(load_config(), "gif_budget_mb") * 1024 * 1024
        self.base = base_surface
        self.tracks = []
        self.ready = False
        self.patches = None
        items = animated.read(display_path) if display_path else []
        self.expected = bool(items) and pil_image.size == base_surface.get_size()
        if self.expected:
            threading.Thread(target=self._load, args=(items, pil_image.copy()), daemon=True, name="gif").start()
        else:
            self.ready = True

    def _load(self, items, pil_image):
        try:
            items = [item for item in items if animated.matches(item, pil_image)]
            total = sum(item["box"][2] * item["box"][3] * 4 * min(animated.MAX_FRAMES, animated.frame_count(item["gif"])) for item in items)
            scale = min(1.0, math.sqrt(self.budget / total)) if total else 1.0
            tracks = []
            for item in items:
                images = animated.frames(item, scale)
                if len(images) < 2:
                    continue
                mode = "RGBA" if item.get("mask") else "RGB"
                surfaces = [[pygame.image.frombytes(image.tobytes(), image.size, mode), duration, False] for image, duration in images]
                box = pygame.Rect(item["box"])
                tracks.append({"box": box, "frames": surfaces, "index": 0, "due": 0.0, "alpha": mode == "RGBA",
                               "clip": box.clip(self.base.get_rect())})
            self.tracks = [t for t in tracks if t["clip"].width and t["clip"].height]
            if self.tracks:
                logger.info(f"[GIF] {len(self.tracks)} animation(s), {sum(len(t['frames']) for t in self.tracks)} images (échelle {scale:.2f})")
        except Exception as e:
            logger.warning(f"[GIF] Animation impossible : {e}")
            self.tracks = []
        self.ready = True

    def set_overlay(self, screen):
        """Ce que l'habillage (heure, météo, icônes) dessine sur les zones des GIF : redessiné par-dessus chaque image."""
        if not self.ready:
            self.patches = None  # calculé à la première image, d'après l'écran à ce moment-là
            return
        self.patches = []
        for track in self.tracks:
            clip = track["clip"]
            drawn = Image.frombytes("RGB", clip.size, pygame.image.tobytes(screen.subsurface(clip), "RGB"))
            plain = Image.frombytes("RGB", clip.size, pygame.image.tobytes(self.base.subsurface(clip), "RGB"))
            mask = ImageChops.difference(drawn, plain).convert("L").point(lambda v: 255 if v > 2 else 0)
            if mask.getbbox() is None:
                self.patches.append(None)
                continue
            drawn.putalpha(mask)
            self.patches.append(pygame.image.frombytes(drawn.tobytes(), drawn.size, "RGBA"))

    def step(self, screen, now):
        """Avance les GIF dont l'image suivante est due ; retourne les zones redessinées et le délai avant la suivante."""
        if not self.ready or not self.tracks:
            return [], 0.1
        if self.patches is None:
            self.set_overlay(screen)
        rects = []
        for number, track in enumerate(self.tracks):
            if now < track["due"]:
                continue
            frame = track["frames"][track["index"]]
            if not frame[2]:  # conversion au format de l'écran (blits rapides), une fois par image
                frame[0] = frame[0].convert_alpha() if track["alpha"] else frame[0].convert()
                frame[2] = True
            surface = frame[0]
            if surface.get_size() != track["box"].size:
                surface = pygame.transform.smoothscale(surface, track["box"].size)
            clip = track["clip"]
            screen.blit(self.base, clip.topleft, clip)
            screen.blit(surface, track["box"].topleft)
            patch = self.patches[number]
            if patch is not None:
                screen.blit(patch, clip.topleft)
            track["due"] = max(track["due"] + frame[1], now) if track["due"] else now + frame[1]
            track["index"] = (track["index"] + 1) % len(track["frames"])
            rects.append(clip)
        wait = max(0.0, min(t["due"] for t in self.tracks) - now)
        return rects, min(0.1, wait)


def show_regions(screen, rects):
    """Affiche seulement ces zones (avec la baisse de luminosité du soir), sans redessiner tout l'écran."""
    if not rects:
        return
    _heartbeat()
    level = _DIM["level"]
    if level >= 0.99:
        pygame.display.update(rects)
        return
    shade = pygame.Surface((1, 1))
    shade.fill((0, 0, 0))
    shade.set_alpha(int(255 * (1 - level)))
    backups = [(rect, screen.subsurface(rect).copy()) for rect in rects]
    for rect in rects:
        screen.blit(pygame.transform.scale(shade, rect.size), rect.topleft)
    pygame.display.update(rects)
    for rect, backup in backups:  # l'image n'est assombrie qu'à l'écran
        screen.blit(backup, rect.topleft)
