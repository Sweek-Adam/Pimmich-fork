"""Effet Ken Burns : zoom lent vers les visages, toujours à l'intérieur de la photo."""
import random

import pytest

pygame = pytest.importorskip("pygame")
from slideshow.display import KenBurns  # noqa: E402


def inside(rect, size):
    x, y, w, h = rect
    return x >= -1e-6 and y >= -1e-6 and x + w <= size[0] + 1e-6 and y + h <= size[1] + 1e-6


def test_zoom_in_towards_the_faces():
    size = (1920, 1080)
    effect = KenBurns(size, 1.2, faces=[(0.7, 0.2, 0.1, 0.15)], zoom_in=True)
    assert effect.rect(0) == (0, 0, 1920, 1080)          # photo entière au début
    x, y, w, h = effect.rect(1)
    assert w == pytest.approx(1600) and h == pytest.approx(900)
    assert x == pytest.approx(320)                          # le cadrage est allé vers le visage, jusqu au bord droit
    for i in range(11):
        assert inside(effect.rect(i / 10), size)


def test_zoom_out_and_drawing():
    effect = KenBurns((320, 180), 1.15, rng=random.Random(4), zoom_in=False)
    assert effect.rect(0)[2] < 320 and effect.rect(1) == (0, 0, 320, 180)
    base, screen = pygame.Surface((320, 180)), pygame.Surface((320, 180))
    base.fill((200, 40, 40))
    effect.draw(screen, base, 0.5)
    assert screen.get_at((160, 90))[:3] == (200, 40, 40)
