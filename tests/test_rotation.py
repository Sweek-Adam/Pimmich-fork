"""Orientation de l'écran : dimensions, pivotement, capteur I2C, calibrage, nouvelle préparation des photos."""
import math

import pytest
from PIL import Image

from utils import screen_rotation as rot

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}


def gravity(degrees):
    """Pesanteur vue par le capteur quand le cadre est debout, tourné de `degrees`."""
    return (math.cos(math.radians(degrees)), math.sin(math.radians(degrees)), 0.1)


@pytest.fixture
def state_file(monkeypatch, tmp_path):
    monkeypatch.setattr(rot, "STATE_FILE", tmp_path / "orientation.json")
    return tmp_path / "orientation.json"


def test_sizes_follow_the_orientation(state_file):
    assert rot.sized({"screen_orientation": "portrait"}, 1920, 1080) == (1080, 1920)
    assert rot.sized({"screen_orientation": "landscape_flipped"}, 1080, 1920) == (1920, 1080)
    assert rot.sized({}, 1080, 1920) == (1920, 1080)
    rot.save_state({"orientation": "portrait_flipped"})
    assert rot.current({"screen_orientation": "auto"}) == "portrait_flipped"
    assert rot.sized({"screen_orientation": "auto"}, 1920, 1080) == (1080, 1920)


def test_sensor_positions_whatever_the_mounting():
    # Capteur monté de travers (30°) et « à l'envers » (le portrait tourne dans l'autre sens)
    calibration = {"landscape": 30.0, "portrait": -60.0}
    assert rot.orientation_from(gravity(32), calibration) == "landscape"
    assert rot.orientation_from(gravity(-55), calibration) == "portrait"
    assert rot.orientation_from(gravity(210), calibration) == "landscape_flipped"
    assert rot.orientation_from(gravity(120), calibration) == "portrait_flipped"
    assert rot.orientation_from((0.05, 0.02, 1.0), calibration) is None  # cadre posé à plat
    assert rot.orientation_from(gravity(30), {}) is None  # pas encore calibré
    assert rot.orientation_from(gravity(120), {"landscape": 30.0}) == "portrait"  # sens supposé tant que le portrait n'est pas mémorisé


def test_follower_waits_for_a_stable_position():
    follower = rot.Follower("landscape")
    assert [follower.update(o) for o in ("portrait", "portrait", None, "portrait", "portrait")] == [None, None, None, None, None]
    assert follower.update("portrait") == "portrait" and follower.current == "portrait"
    assert follower.update("portrait") is None


class FakeBus:
    def __init__(self, chips):
        self.chips, self.writes = chips, []

    def read_byte_data(self, address, register):
        if address not in self.chips:
            raise OSError("pas de réponse")
        return self.chips[address]["id"].get(register, 0)

    def write_byte_data(self, address, register, value):
        self.writes.append((address, register, value))

    def read_i2c_block_data(self, address, register, length):
        return self.chips[address]["data"]


def test_sensors_are_found_and_read():
    mpu = rot.Sensor.find(FakeBus({0x68: {"id": {0x75: 0x68}, "data": [0x40, 0x00, 0xC0, 0x00, 0x00, 0x00]}}))
    assert mpu.kind == "MPU-6050" and mpu.read() == (1.0, -1.0, 0.0) and mpu.bus.writes == [(0x68, 0x6B, 0)]
    adxl = rot.Sensor.find(FakeBus({0x53: {"id": {0x00: 0xE5}, "data": [0x00, 0x01, 0x00, 0xFF, 0, 0]}}))
    assert adxl.kind == "ADXL345" and adxl.read() == (1.0, -1.0, 0.0)
    lis = rot.Sensor.find(FakeBus({0x19: {"id": {0x0F: 0x33}, "data": [0x00, 0x40, 0, 0, 0, 0]}}))
    assert lis.kind == "LIS3DH" and lis.read()[0] == 1.0
    assert rot.Sensor.find(FakeBus({})) is None


def test_apply_rotates_the_output(monkeypatch):
    calls = []

    class Result:
        def __init__(self, stdout="", code=0):
            self.stdout, self.returncode = stdout, code

    def run(command, **kwargs):
        calls.append(command)
        if command == ["wlr-randr"]:
            return Result('HDMI-A-1 "écran"\n  Enabled: yes\n  Transform: normal\n')
        return Result()
    monkeypatch.setattr(rot.subprocess, "run", run)
    assert rot.apply("portrait") and calls[-1] == ["wlr-randr", "--output", "HDMI-A-1", "--transform", "90"]
    calls.clear()
    assert rot.apply("landscape") and calls == [["wlr-randr"]]  # déjà dans cette orientation


def test_wrong_size_photos_are_prepared_again(sandbox, monkeypatch):
    from utils import prepare_all_photos
    source = sandbox / "static" / "photos" / "rot"
    prepared = sandbox / "static" / "prepared" / "rot"
    source.mkdir(parents=True, exist_ok=True)
    prepared.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (400, 300)).save(source / "a.jpg")
    Image.new("RGB", (64, 36)).save(prepared / "a.jpg")  # préparée en paysage
    done = []
    monkeypatch.setattr(prepare_all_photos, "prepare_photo", lambda src, dest, w, h, **k: done.append((w, h)))
    list(prepare_all_photos.prepare_all_photos_with_progress(36, 64, source_type="rot"))
    assert done == [(36, 64)]
    done.clear()
    list(prepare_all_photos.prepare_all_photos_with_progress(64, 36, source_type="rot"))
    assert done == []  # bonne taille : rien à refaire


def test_orientation_api_and_settings(admin_client, monkeypatch, state_file):
    from utils.config_manager import load_config, save_config
    from web import workers
    original = dict(load_config())
    started = []
    monkeypatch.setattr(workers, "reprepare_all_sources", lambda: started.append(1))
    try:
        assert admin_client.post("/api/orientation/calibrate", json={"as": "landscape"}, headers=SAME_ORIGIN).status_code == 400  # pas de mesure
        rot.LIVE.update(vector=list(gravity(10)), sensor="MPU-6050", at=__import__("time").time())
        assert admin_client.post("/api/orientation/calibrate", json={"as": "landscape"}, headers=SAME_ORIGIN).get_json()["success"]
        rot.LIVE.update(vector=list(gravity(100)))
        admin_client.post("/api/orientation/calibrate", json={"as": "portrait"}, headers=SAME_ORIGIN)
        assert rot.load_state()["calibration"] == {"landscape": 10.0, "portrait": 100.0}
        data = admin_client.get("/api/orientation").get_json()
        assert data["sensor"] == "MPU-6050" and data["seen"] == "portrait"
        assert admin_client.post("/api/orientation/calibrate", json={"as": "nimporte"}, headers=SAME_ORIGIN).status_code == 400
        # Passage en portrait depuis le formulaire : dimensions inversées et photos repréparées
        save_config(dict(original, display_width=1920, display_height=1080, screen_orientation="landscape"))
        form = {"screen_orientation": "portrait", "display_width": "1920", "display_height": "1080"}
        admin_client.post("/configure", data=form, headers=dict(SAME_ORIGIN, **{"X-Autosave": "1"}))
        config = load_config()
        assert (config["display_width"], config["display_height"]) == (1080, 1920) and started
    finally:
        rot.LIVE.clear()
        save_config(original)
