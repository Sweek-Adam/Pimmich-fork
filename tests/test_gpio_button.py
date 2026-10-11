"""Bouton physique : détection d'un appui (anti-rebond), changement de broche, réglages et état (faux GPIO)."""
from utils import gpio_button

H = {"Sec-Fetch-Site": "same-origin"}


class FakeGPIO:
    BCM, IN, PUD_UP = "BCM", "IN", "PUD_UP"

    def __init__(self):
        self.levels, self.setups, self.cleaned = {}, [], []

    def setmode(self, mode):
        assert mode == self.BCM

    def setup(self, pin, direction, pull_up_down=None):
        assert direction == self.IN and pull_up_down == self.PUD_UP
        self.setups.append(pin)
        self.levels.setdefault(pin, 1)

    def input(self, pin):
        return self.levels[pin]

    def cleanup(self, pin):
        self.cleaned.append(pin)


def test_press_debounce_and_pin_change():
    gpio, presses, now = FakeGPIO(), [], [0.0]
    watcher = gpio_button.Watcher(gpio, lambda: presses.append(now[0]), clock=lambda: now[0])
    assert not watcher.poll()  # pas encore activé
    watcher.configure(True, 23)
    watcher.configure(True, 23)  # rien n'a changé : pas de nouvelle configuration
    assert gpio.setups == [23]
    gpio.levels[23] = 0
    assert watcher.poll() and presses == [0.0]  # appui (haut -> bas)
    assert not watcher.poll()  # bouton maintenu : un seul appui
    gpio.levels[23] = 1; watcher.poll()
    now[0] = 0.2; gpio.levels[23] = 0
    assert not watcher.poll()  # rebond : ignoré
    gpio.levels[23] = 1; watcher.poll()
    now[0] = 1.0; gpio.levels[23] = 0
    assert watcher.poll() and len(presses) == 2
    watcher.configure(True, 17)
    assert gpio.cleaned == [23] and watcher.pin == 17
    watcher.configure(False, 17)
    assert gpio.cleaned == [23, 17] and watcher.pin is None and not watcher.poll()


def test_button_settings_and_state(admin_client, app_module):
    from web import routes_settings
    before = dict(routes_settings.load_config())
    try:
        data = admin_client.post("/api/settings", json={"button_enabled": True, "button_pin": 24}, headers=H).get_json()
        assert data["values"]["button_enabled"] is True and data["values"]["button_pin"] == 24
        for bad in ({"button_pin": 1}, {"button_pin": 40}, {"button_enabled": "oui"}):
            assert admin_client.post("/api/settings", json=bad, headers=H).status_code == 400, bad
        state = admin_client.get("/api/gpio_button").get_json()
        assert state["success"] and isinstance(state["available"], bool)
    finally:
        config = dict(routes_settings.load_config())
        for key in ("button_enabled", "button_pin"):
            if key in before:
                config[key] = before[key]
            else:
                config.pop(key, None)
        routes_settings.save_config(config)
