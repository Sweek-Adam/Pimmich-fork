"""Météo animée (pluie, orage, neige) et icône de la lune."""
from utils import sky, weather_fx


def test_effect_follows_the_weather_icon():
    assert weather_fx.effect_for("10d") == "rain" and weather_fx.effect_for("09n") == "rain"
    assert weather_fx.effect_for("11d") == "storm" and weather_fx.effect_for("13n") == "snow"
    assert weather_fx.effect_for("01d") is None and weather_fx.effect_for(None) is None


def test_animation_window():
    assert weather_fx.wanted({}, 3) and not weather_fx.wanted({}, 9)  # par défaut : au début de la photo
    assert weather_fx.wanted({"weather_animation": "always"}, 600)
    assert not weather_fx.wanted({"weather_animation": "off"}, 0)


def test_particles_fall_and_come_back():
    for effect in ("rain", "storm", "snow"):
        particles = weather_fx.Particles(effect, 1920, 1080, seed=1)
        for _ in range(200):
            particles.step(0.05)
        shapes = list(particles.shapes())
        assert len(shapes) == len(particles.items) > 50
        assert all(-400 < s[1][1] < 1120 for s in shapes)  # toujours à l'écran ou juste au-dessus


def test_moon_icon_phases():
    def lit(image, x, y):
        return image.getpixel((x, y))[0] > 200
    full = sky.moon_image(40, 14.77)
    new = sky.moon_image(40, 0.2)
    quarter = sky.moon_image(40, 7.38)
    assert lit(full, 8, 20) and lit(full, 32, 20)
    assert not lit(new, 8, 20) and not lit(new, 32, 20)
    assert lit(quarter, 32, 20) and not lit(quarter, 8, 20)  # premier quartier : éclairée à droite
    assert full.getpixel((0, 0))[3] == 0  # coins transparents
