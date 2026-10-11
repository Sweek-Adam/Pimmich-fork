"""Home Assistant (MQTT) : découverte des entités et commandes reçues."""
import json

from utils import mqtt_bridge

SAME = {"Sec-Fetch-Site": "same-origin"}


class FakeClient:
    def __init__(self):
        self.published, self.subscribed = [], []

    def publish(self, topic, payload, retain=False):
        self.published.append((topic, payload))

    def subscribe(self, topic):
        self.subscribed.append(topic)


def bridge(calls):
    actions = {"slideshow": lambda on: calls.append(("slideshow", on)), "next": lambda: calls.append(("next",)),
               "ambiance": lambda key: calls.append(("ambiance", key)), "alert": lambda text: calls.append(("alert", text))}
    state = lambda: {"slideshow": True, "ambiance": "fete", "ambiances": ["calme", "fete"], "photo": "a.jpg", "music": "FIP"}
    return mqtt_bridge.Bridge({"mqtt_node_id": "Salon!", "mqtt_device_name": "Cadre du salon"}, actions, state, client_factory=FakeClient)


def test_discovery():
    b = bridge([])
    topics = dict(b.discovery())
    assert b.base == "pimmich/salon_"
    select = json.loads(topics["homeassistant/select/pimmich_salon_/ambiance/config"])
    assert select["options"] == ["calme", "fete"] and select["device"]["name"] == "Cadre du salon"
    assert {t.split("/")[1] for t in topics} == {"switch", "select", "button", "text", "sensor"}


def test_commands_and_state():
    calls = []
    b = bridge(calls)
    b._on_connect(b.client, None, None, 0)
    assert "pimmich/salon_/alert/set" in b.client.subscribed and ("pimmich/salon_/status", "online") in b.client.published
    assert b.handle("pimmich/salon_/slideshow/set", b"OFF") and b.handle("pimmich/salon_/ambiance/set", b"calme")
    assert b.handle("pimmich/salon_/next/press", b"PRESS") and b.handle("pimmich/salon_/alert/set", "Garage ouvert".encode())
    assert calls == [("slideshow", False), ("ambiance", "calme"), ("next",), ("alert", "Garage ouvert")]
    assert not b.handle("pimmich/autre/topic", b"x")
    assert ("pimmich/salon_/music/state", "FIP") in b.client.published


def test_settings_api(admin_client, monkeypatch):
    from utils.config_manager import load_config, save_config
    from web import routes_homeassistant
    monkeypatch.setattr(routes_homeassistant, "restart_bridge", lambda: True)
    original = dict(load_config())
    try:
        r = admin_client.post("/api/homeassistant", json={"enabled": True, "host": "ha.local", "port": "1883", "user": "pimmich", "password": "s3cret"},
                              headers=SAME).get_json()
        assert r["success"]
        data = admin_client.get("/api/homeassistant").get_json()
        assert data["host"] == "ha.local" and data["has_password"] and "s3cret" not in json.dumps(data)
        assert admin_client.post("/api/homeassistant", json={"port": "x"}, headers=SAME).status_code == 400
    finally:
        save_config(original)
