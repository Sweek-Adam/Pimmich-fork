"""
Home Assistant (MQTT) : le cadre apparaît tout seul dans Home Assistant (découverte MQTT), avec
- un interrupteur « Diaporama » (allumer / endormir le cadre),
- un choix « Ambiance », un bouton « Photo suivante »,
- un texte « Alerte » : le message envoyé s'affiche tout de suite sur le cadre (ex. « La porte du garage est ouverte »),
- des capteurs « Photo affichée » et « Musique ».
Les actions sont fournies par l'application (fonctions), ce module ne gère que MQTT.
"""
import json
import logging
import re
import threading

logger = logging.getLogger("pimmich.mqtt")
NODE = re.compile(r"[^a-z0-9_]")


class Bridge:
    def __init__(self, config, actions, state, client_factory=None):
        """`actions` : {"slideshow": f(bool), "next": f(), "ambiance": f(clé), "alert": f(texte)} ;
        `state` : f() -> {"slideshow": bool, "ambiance": clé, "ambiances": [clés], "photo": str, "music": str}."""
        self.config, self.actions, self.state = config, actions, state
        self.node = NODE.sub("_", (config.get("mqtt_node_id") or "pimmich").lower())[:40] or "pimmich"
        self.base = f"pimmich/{self.node}"
        self.prefix = config.get("mqtt_discovery_prefix") or "homeassistant"
        self.client = (client_factory or self._paho)()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self._stop = threading.Event()
        self.connected = False

    def _paho(self):
        import paho.mqtt.client as mqtt
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"pimmich-{self.node}")
        if self.config.get("mqtt_user"):
            client.username_pw_set(self.config["mqtt_user"], self.config.get("mqtt_password") or None)
        client.will_set(f"pimmich/{NODE.sub('_', (self.config.get('mqtt_node_id') or 'pimmich').lower())}/status", "offline", retain=True)
        return client

    # --- Découverte Home Assistant ---

    def discovery(self):
        """Messages de découverte : [(topic, payload)]."""
        device = {"identifiers": [f"pimmich_{self.node}"], "name": self.config.get("mqtt_device_name") or "Pimmich",
                  "manufacturer": "Pimmich", "model": "Cadre photo"}
        common = {"availability_topic": f"{self.base}/status", "device": device}
        entities = [
            ("switch", "slideshow", {"name": "Diaporama", "icon": "mdi:image-multiple", "command_topic": f"{self.base}/slideshow/set",
                                     "state_topic": f"{self.base}/slideshow/state"}),
            ("select", "ambiance", {"name": "Ambiance", "icon": "mdi:palette", "command_topic": f"{self.base}/ambiance/set",
                                    "state_topic": f"{self.base}/ambiance/state", "options": self.state().get("ambiances") or []}),
            ("button", "next", {"name": "Photo suivante", "icon": "mdi:skip-next", "command_topic": f"{self.base}/next/press"}),
            ("text", "alert", {"name": "Alerte", "icon": "mdi:alert", "command_topic": f"{self.base}/alert/set", "max": 255, "mode": "text"}),
            ("sensor", "photo", {"name": "Photo affichée", "icon": "mdi:image", "state_topic": f"{self.base}/photo/state"}),
            ("sensor", "music", {"name": "Musique", "icon": "mdi:music", "state_topic": f"{self.base}/music/state"}),
        ]
        messages = []
        for component, key, payload in entities:
            payload = dict(common, **payload, unique_id=f"pimmich_{self.node}_{key}", object_id=f"pimmich_{self.node}_{key}")
            messages.append((f"{self.prefix}/{component}/pimmich_{self.node}/{key}/config", json.dumps(payload, ensure_ascii=False)))
        return messages

    # --- MQTT ---

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        self.connected = (not reason_code.is_failure) if hasattr(reason_code, "is_failure") else reason_code == 0
        if not self.connected:
            logger.warning(f"[MQTT] Connexion refusée : {reason_code}")
            return
        for topic, payload in self.discovery():
            client.publish(topic, payload, retain=True)
        client.publish(f"{self.base}/status", "online", retain=True)
        for topic in ("slideshow/set", "ambiance/set", "next/press", "alert/set"):
            client.subscribe(f"{self.base}/{topic}")
        self.publish_state()
        logger.info(f"[MQTT] Connecté : le cadre est visible dans Home Assistant ({self.base}).")

    def handle(self, topic, payload):
        """Commande reçue de Home Assistant."""
        text = payload.decode("utf-8", errors="replace").strip() if isinstance(payload, bytes) else str(payload).strip()
        command = topic[len(self.base) + 1:] if topic.startswith(self.base + "/") else ""
        try:
            if command == "slideshow/set":
                self.actions["slideshow"](text.upper() == "ON")
            elif command == "ambiance/set":
                self.actions["ambiance"](text)
            elif command == "next/press":
                self.actions["next"]()
            elif command == "alert/set" and text:
                self.actions["alert"](text[:255])
            else:
                return False
        except Exception as e:
            logger.warning(f"[MQTT] Commande {command} : {e}")
            return False
        self.publish_state()
        return True

    def _on_message(self, client, userdata, message):
        self.handle(message.topic, message.payload)

    def publish_state(self):
        state = self.state()
        self.client.publish(f"{self.base}/slideshow/state", "ON" if state.get("slideshow") else "OFF", retain=True)
        self.client.publish(f"{self.base}/ambiance/state", state.get("ambiance") or "", retain=True)
        self.client.publish(f"{self.base}/photo/state", (state.get("photo") or "")[:250], retain=True)
        self.client.publish(f"{self.base}/music/state", (state.get("music") or "")[:250], retain=True)

    def run(self):
        """Boucle (fil dédié) : connexion, reconnexion automatique, état publié toutes les 30 s."""
        self.client.connect_async(self.config.get("mqtt_host"), int(self.config.get("mqtt_port") or 1883), keepalive=60)
        self.client.loop_start()
        while not self._stop.wait(30):
            if self.connected:
                try:
                    self.publish_state()
                except Exception as e:
                    logger.debug(f"[MQTT] État : {e}")
        self.client.publish(f"{self.base}/status", "offline", retain=True)
        self.client.loop_stop()
        self.client.disconnect()

    def stop(self):
        self._stop.set()
