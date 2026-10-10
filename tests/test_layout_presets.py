"""Configurations de dispositions enregistrées : enregistrer, activer, reconnaître la configuration active."""
from utils import compositions, layout_presets

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}


def test_save_activate_and_detect_active():
    config = {"layout_override": "auto"}
    config = layout_presets.save(config, "Soirée", selection={"formats": ["liege", "halloween", "inconnu"], "unique": False, "every": 0})
    config = layout_presets.save(config, "Calme", selection={"formats": [], "unique": False, "every": 5})
    soiree, calme = config["layout_presets"]
    assert soiree["formats"] == ["liege", "halloween"] and not soiree["unique"]
    assert calme["unique"]  # jamais aucune disposition : la photo unique reste
    config = layout_presets.activate(config, soiree["id"])
    assert compositions.enabled_formats(config) == ["liege", "halloween"] and config["compositions_every"] == 0
    listing = layout_presets.listing(config)
    assert [p["active"] for p in listing] == [True, False]
    config["layout_override"] = "noel"  # une disposition forcée : plus aucune configuration active
    assert not any(p["active"] for p in layout_presets.listing(config))


def test_presets_api(admin_client):
    from utils.config_manager import load_config
    r = admin_client.post("/api/layout_presets", json={"name": "Noël en famille", "selection": {"formats": ["noel", "hiver"], "unique": True, "every": 2}}, headers=SAME_ORIGIN).get_json()
    assert r["success"] and r["presets"][-1]["name"] == "Noël en famille"
    assert admin_client.post("/api/layout_presets", json={"name": "noël en famille"}, headers=SAME_ORIGIN).status_code == 400  # nom déjà pris
    preset_id = r["presets"][-1]["id"]
    r = admin_client.post(f"/api/layout_presets/{preset_id}/activate", headers=SAME_ORIGIN).get_json()
    assert r["success"] and compositions.enabled_formats(load_config()) == ["noel", "hiver"]
    assert any(p["active"] for p in admin_client.get("/api/layout_presets").get_json()["presets"])
    assert admin_client.post("/api/layout_presets/inconnu/activate", headers=SAME_ORIGIN).status_code == 404
    assert admin_client.delete(f"/api/layout_presets/{preset_id}", headers=SAME_ORIGIN).get_json()["presets"] == [
        p for p in admin_client.get("/api/layout_presets").get_json()["presets"]]
