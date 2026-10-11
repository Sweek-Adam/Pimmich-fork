"""
Orientation de l'écran : paysage, portrait (et leurs versions retournées), ou automatique.

Le cadre fait pivoter lui-même l'affichage (wlr-randr, sinon swaymsg) et prépare les photos aux bonnes dimensions.
En mode automatique, un petit accéléromètre branché sur l'I2C du Raspberry Pi (MPU-6050, ADXL345 ou LIS3DH,
quelques euros) indique comment le cadre est posé : on le tourne, l'écran suit. Le capteur se monte dans
n'importe quel sens : on mémorise une fois sa position quand le cadre est en paysage, puis en portrait.
"""
import json
import math
import os
import subprocess
import glob
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = BASE_DIR / "cache" / "orientation.json"
TRANSFORMS = {"landscape": "normal", "portrait": "90", "landscape_flipped": "180", "portrait_flipped": "270"}
ORDER = ["landscape", "portrait", "landscape_flipped", "portrait_flipped"]  # un quart de tour à chaque fois
MODES = tuple(TRANSFORMS) + ("auto",)
MIN_TILT = 0.55   # part de la pesanteur dans le plan de l'écran (cadre debout, pas à plat)
STABLE_READS = 3  # lectures identiques avant de tourner (pas de rotation en manipulant le cadre)
LIVE = {}         # dernière mesure du capteur (en mémoire seulement, pour ménager la carte SD)


def is_portrait(orientation):
    return orientation in ("portrait", "portrait_flipped")


def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state))
    tmp.replace(STATE_FILE)


def current(config):
    """Orientation en vigueur : celle choisie, ou celle détectée par le capteur en mode automatique."""
    mode = config.get("screen_orientation", "landscape")
    if mode == "auto":
        detected = load_state().get("orientation")
        return detected if detected in TRANSFORMS else "landscape"
    return mode if mode in TRANSFORMS else "landscape"


def sized(config, width, height):
    """Dimensions (largeur, hauteur) de l'écran dans l'orientation en vigueur."""
    long_side, short_side = max(width, height), min(width, height)
    return (short_side, long_side) if is_portrait(current(config)) else (long_side, short_side)


def _env():
    env = os.environ.copy()
    runtime = env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    if "WAYLAND_DISPLAY" not in env:
        sockets = sorted(p for p in glob.glob(f"{runtime}/wayland-*") if not p.endswith(".lock"))
        if sockets:
            env["WAYLAND_DISPLAY"] = Path(sockets[0]).name
    if "SWAYSOCK" not in env:
        socks = glob.glob(f"{runtime}/sway-ipc.*")
        if socks:
            env["SWAYSOCK"] = socks[0]
    return env


def _output(env):
    try:
        out = subprocess.run(["wlr-randr"], capture_output=True, text=True, timeout=5, env=env).stdout
    except (OSError, subprocess.SubprocessError):
        return None, None
    name, transform = None, None
    for line in out.splitlines():
        if line and not line[0].isspace() and name is None:
            name = line.split()[0]
        elif name and line.strip().startswith("Transform:"):
            transform = line.split(":", 1)[1].strip()
            break
    return name, transform


def apply(orientation):
    """Fait pivoter l'affichage ; renvoie True si l'écran est (déjà) dans cette orientation."""
    transform = TRANSFORMS.get(orientation, "normal")
    env = _env()
    name, now = _output(env)
    if not name:
        return False
    if now == transform:
        return True
    for command in (["wlr-randr", "--output", name, "--transform", transform],
                    ["swaymsg", "output", name, "transform", transform]):
        try:
            if subprocess.run(command, capture_output=True, text=True, timeout=10, env=env).returncode == 0:
                return True
        except (OSError, subprocess.SubprocessError):
            continue
    return False


# --- Accéléromètre (I2C) ---

def _signed(value, bits=16):
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


class Sensor:
    """Accéléromètre trouvé sur le bus I2C : read() renvoie (x, y, z) en g (approximativement)."""

    KINDS = (("MPU-6050", (0x68, 0x69), 0x75, (0x68, 0x70, 0x98)), ("ADXL345", (0x53, 0x1D), 0x00, (0xE5,)),
             ("LIS3DH", (0x18, 0x19), 0x0F, (0x33,)))

    def __init__(self, bus, kind, address):
        self.bus, self.kind, self.address = bus, kind, address
        if kind == "MPU-6050":
            bus.write_byte_data(address, 0x6B, 0x00)  # sortie de veille
        elif kind == "ADXL345":
            bus.write_byte_data(address, 0x2D, 0x08)  # mesure
        else:
            bus.write_byte_data(address, 0x20, 0x57)  # 100 Hz, 3 axes

    @classmethod
    def find(cls, bus):
        for kind, addresses, register, expected in cls.KINDS:
            for address in addresses:
                try:
                    if bus.read_byte_data(address, register) in expected:
                        return cls(bus, kind, address)
                except OSError:
                    continue
        return None

    def read(self):
        if self.kind == "MPU-6050":
            raw = self.bus.read_i2c_block_data(self.address, 0x3B, 6)
            return tuple(_signed(raw[i] << 8 | raw[i + 1]) / 16384 for i in (0, 2, 4))
        if self.kind == "ADXL345":
            raw = self.bus.read_i2c_block_data(self.address, 0x32, 6)
            return tuple(_signed(raw[i + 1] << 8 | raw[i]) / 256 for i in (0, 2, 4))
        raw = self.bus.read_i2c_block_data(self.address, 0x28 | 0x80, 6)
        return tuple(_signed(raw[i + 1] << 8 | raw[i]) / 16384 for i in (0, 2, 4))


def open_sensor():
    """Premier accéléromètre trouvé sur les bus I2C du Raspberry Pi, sinon None."""
    try:
        from smbus2 import SMBus
    except ImportError:
        return None
    for path in sorted(glob.glob("/dev/i2c-*")):
        try:
            bus = SMBus(int(path.rsplit("-", 1)[1]))
        except (OSError, ValueError):
            continue
        sensor = Sensor.find(bus)
        if sensor:
            return sensor
        bus.close()
    return None


def angle(vector):
    """Direction de la pesanteur dans le plan du capteur (degrés), None si le cadre est posé à plat."""
    x, y, z = vector
    norm = math.sqrt(x * x + y * y + z * z) or 1
    if math.hypot(x, y) / norm < MIN_TILT:
        return None
    return math.degrees(math.atan2(y, x))


def _gap(a, b):
    return abs((a - b + 180) % 360 - 180)


def positions_from(calibration):
    """Angle du capteur pour chaque orientation, d'après les positions mémorisées (les autres s'en déduisent)."""
    known = {k: float(v) for k, v in (calibration or {}).items() if k in TRANSFORMS and isinstance(v, (int, float))}
    if not known:
        return {}
    opposite = {"landscape": "landscape_flipped", "landscape_flipped": "landscape", "portrait": "portrait_flipped", "portrait_flipped": "portrait"}
    for name, value in list(known.items()):
        known.setdefault(opposite[name], (value + 180) % 360)
    if not any(is_portrait(k) for k in known):  # seul le paysage est connu : sens de rotation supposé
        base = known.get("landscape", (known.get("landscape_flipped", 0) + 180) % 360)
        known.update(portrait=(base + 90) % 360, portrait_flipped=(base + 270) % 360)
    if not any(not is_portrait(k) for k in known):
        base = known.get("portrait", (known.get("portrait_flipped", 0) + 180) % 360)
        known.update(landscape=(base - 90) % 360, landscape_flipped=(base + 90) % 360)
    return known


def orientation_from(vector, calibration):
    """Orientation du cadre d'après le capteur : la position mémorisée la plus proche (à 45° près)."""
    now = angle(vector)
    positions = positions_from(calibration)
    if now is None or not positions:
        return None
    name, value = min(positions.items(), key=lambda item: _gap(now, item[1]))
    return name if _gap(now, value) <= 45 else None


class Follower:
    """Suit le capteur et ne signale un changement qu'après plusieurs lectures concordantes."""

    def __init__(self, start=None):
        self.current, self.candidate, self.count = start, None, 0

    def update(self, orientation):
        if orientation is None or orientation == self.current:
            self.candidate, self.count = None, 0
            return None
        if orientation != self.candidate:
            self.candidate, self.count = orientation, 0
        self.count += 1
        if self.count >= STABLE_READS:
            self.current, self.candidate, self.count = orientation, None, 0
            return orientation
        return None
