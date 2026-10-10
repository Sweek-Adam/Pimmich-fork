"""
Enceinte Bluetooth « Cadre photo » (service utilisateur pimmich-bluetooth, lancé avec le Python du système
qui fournit dbus et gi : /usr/bin/python3 -m utils.bluetooth_receiver).

- Agent d'appairage sans écran ni clavier : un téléphone peut s'associer uniquement pendant que le cadre
  est visible (bouton « Associer un téléphone » de l'interface, 3 minutes) ; il est alors mémorisé
  (appareil de confiance) et se reconnecte ensuite tout seul.
- Le son (A2DP) est joué par PipeWire ; le titre en cours (AVRCP) est transmis au lecteur affiché à l'écran.
"""
import logging

import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib

from utils import now_playing

BUS_NAME = "org.bluez"
AGENT_PATH = "/pimmich/agent"
AUDIO_UUIDS = {
    "0000110a-0000-1000-8000-00805f9b34fb",  # A2DP source (le téléphone)
    "0000110b-0000-1000-8000-00805f9b34fb",  # A2DP sink
    "0000110c-0000-1000-8000-00805f9b34fb",  # AVRCP cible
    "0000110e-0000-1000-8000-00805f9b34fb",  # AVRCP télécommande
    "0000110d-0000-1000-8000-00805f9b34fb",  # A2DP
}
DEVICE_NAME = "Cadre photo"
logger = logging.getLogger("pimmich.bluetooth")


class Rejected(dbus.DBusException):
    _dbus_error_name = "org.bluez.Error.Rejected"


def find_adapter(bus):
    manager = dbus.Interface(bus.get_object(BUS_NAME, "/"), "org.freedesktop.DBus.ObjectManager")
    for path, interfaces in manager.GetManagedObjects().items():
        if "org.bluez.Adapter1" in interfaces:
            return path
    return None


class Agent(dbus.service.Object):
    """Accepte l'appairage seulement quand l'adaptateur est visible (fenêtre ouverte depuis l'interface)."""

    def __init__(self, bus, adapter_path):
        super().__init__(bus, AGENT_PATH)
        self.bus, self.adapter_path = bus, adapter_path

    def _pairing_open(self):
        props = dbus.Interface(self.bus.get_object(BUS_NAME, self.adapter_path), "org.freedesktop.DBus.Properties")
        return bool(props.Get("org.bluez.Adapter1", "Discoverable"))

    def _trust(self, device):
        props = dbus.Interface(self.bus.get_object(BUS_NAME, device), "org.freedesktop.DBus.Properties")
        props.Set("org.bluez.Device1", "Trusted", dbus.Boolean(True))

    def _accept_pairing(self, device):
        if not self._pairing_open():
            logger.info(f"Appairage refusé (cadre non visible) : {device}")
            raise Rejected("Cadre non visible")
        self._trust(device)
        logger.info(f"Appareil associé : {device}")

    @dbus.service.method("org.bluez.Agent1", in_signature="", out_signature="")
    def Release(self):
        pass

    @dbus.service.method("org.bluez.Agent1", in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        if str(uuid).lower() not in AUDIO_UUIDS:
            raise Rejected("Service non audio")

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        self._accept_pairing(device)
        return "0000"

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        self._accept_pairing(device)
        return dbus.UInt32(0)

    @dbus.service.method("org.bluez.Agent1", in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device, passkey, entered):
        pass

    @dbus.service.method("org.bluez.Agent1", in_signature="os", out_signature="")
    def DisplayPinCode(self, device, pincode):
        pass

    @dbus.service.method("org.bluez.Agent1", in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        self._accept_pairing(device)

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        self._accept_pairing(device)

    @dbus.service.method("org.bluez.Agent1", in_signature="", out_signature="")
    def Cancel(self):
        pass


def track_fields(track):
    """Propriété « Track » d'AVRCP -> champs du lecteur affiché."""
    return {"title": str(track.get("Title", "")), "artist": str(track.get("Artist", "")),
            "album": str(track.get("Album", "")), "cover": None}


STATUS = {"playing": "playing", "paused": "paused", "stopped": "stopped", "error": "stopped"}


def on_properties_changed(interface, changed, invalidated, path=None):
    """Titre et état de lecture envoyés par le téléphone (AVRCP), connexion et déconnexion."""
    if interface == "org.bluez.MediaPlayer1":
        if "Track" in changed and changed["Track"].get("Title"):
            now_playing.update("bluetooth", **track_fields(changed["Track"]))
        if "Status" in changed:
            now_playing.update("bluetooth", state=STATUS.get(str(changed["Status"]), "stopped"))
    elif interface == "org.bluez.Device1" and "Connected" in changed and not changed["Connected"]:
        now_playing.update("bluetooth", state="stopped")
    elif interface == "org.bluez.Adapter1" and "Discoverable" in changed:
        # Fin de la fenêtre d'association : on n'accepte plus de nouvel appareil
        try:
            props = dbus.Interface(dbus.SystemBus().get_object(BUS_NAME, path), "org.freedesktop.DBus.Properties")
            props.Set("org.bluez.Adapter1", "Pairable", dbus.Boolean(bool(changed["Discoverable"])))
        except dbus.DBusException as e:
            logger.warning(f"Réglage de l'appairage impossible : {e}")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    adapter = find_adapter(bus)
    if not adapter:
        raise SystemExit("Aucun adaptateur Bluetooth")
    props = dbus.Interface(bus.get_object(BUS_NAME, adapter), "org.freedesktop.DBus.Properties")
    props.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(True))
    # Le nom est fixé après la mise sous tension : BlueZ reprend sinon le nom de la machine
    GLib.timeout_add_seconds(2, lambda: props.Set("org.bluez.Adapter1", "Alias", dbus.String(DEVICE_NAME)) and False)
    props.Set("org.bluez.Adapter1", "DiscoverableTimeout", dbus.UInt32(180))
    props.Set("org.bluez.Adapter1", "Pairable", dbus.Boolean(bool(props.Get("org.bluez.Adapter1", "Discoverable"))))

    Agent(bus, adapter)
    manager = dbus.Interface(bus.get_object(BUS_NAME, "/org/bluez"), "org.bluez.AgentManager1")
    manager.RegisterAgent(AGENT_PATH, "NoInputNoOutput")
    manager.RequestDefaultAgent(AGENT_PATH)
    bus.add_signal_receiver(on_properties_changed, dbus_interface="org.freedesktop.DBus.Properties",
                            signal_name="PropertiesChanged", path_keyword="path")
    now_playing.update("bluetooth", state="stopped")
    logger.info(f"Enceinte Bluetooth « {DEVICE_NAME} » prête ({adapter})")
    GLib.MainLoop().run()


if __name__ == "__main__":
    main()
