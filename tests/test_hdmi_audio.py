"""Son HDMI perdu (écran éteint au démarrage du Pi) : réparé automatiquement."""
from utils import audio_output


def test_repair_when_screen_connected_but_no_hdmi_sink(monkeypatch, tmp_path):
    status = tmp_path / "status"
    status.write_text("connected\n")
    monkeypatch.setattr(audio_output, "_hdmi_connectors", lambda: [str(status)])
    sinks = [[{"id": 1, "name": "alsa_output.headphones", "card": "bcm2835 Headphones"}]]
    monkeypatch.setattr(audio_output, "_list_sinks", lambda: sinks[0])
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if args[:3] == ["systemctl", "--user", "restart"]:
            sinks[0] = sinks[0] + [{"id": 2, "name": "alsa_output.platform-3f902000.hdmi.hdmi-stereo", "card": "vc4-hdmi"}]
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    monkeypatch.setattr(audio_output.subprocess, "run", run)
    monkeypatch.setattr("time.sleep", lambda s: None)
    assert audio_output.hdmi_audio_missing()
    assert audio_output.repair_hdmi_audio()
    assert any("detect" in " ".join(c) for c in calls) and not audio_output.hdmi_audio_missing()
    audio_output.apply_audio_output("hdmi")
    assert ["wpctl", "set-default", "2"] in calls


def test_nothing_to_do_without_screen(monkeypatch, tmp_path):
    status = tmp_path / "status"
    status.write_text("disconnected\n")
    monkeypatch.setattr(audio_output, "_hdmi_connectors", lambda: [str(status)])
    assert not audio_output.hdmi_audio_missing() and not audio_output.repair_hdmi_audio()
