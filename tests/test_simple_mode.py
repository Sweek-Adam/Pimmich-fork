"""Mode grands-parents : lien spécial, page à gros boutons, actions sur le cadre sans mot de passe."""
SAME = {"Sec-Fetch-Site": "same-origin"}


def test_link_opens_the_page_and_drives_the_frame(admin_client, client, monkeypatch):
    from utils import reactions, slideshow_commands
    from utils.config_manager import load_config, save_config
    from web import routes_simple
    original = dict(load_config())
    try:
        r = admin_client.post("/api/simple_link", json={"name": "Mamie"}, headers=SAME).get_json()
        link = r["link"]
        assert "/simple?k=" in link and r["name"] == "Mamie"
        phone = client.application.test_client()
        assert phone.get("/simple").status_code == 401                         # sans le lien : rien
        assert phone.get("/simple?k=faux").status_code == 401
        assert phone.post("/simple/action", json={"action": "next"}, headers=SAME).status_code == 401
        opened = phone.get("/simple?k=" + link.split("k=", 1)[1])
        assert opened.status_code == 302 and "pimmich_simple" in opened.headers.get("Set-Cookie", "")
        page = phone.get("/simple")
        assert page.status_code == 200 and "Mamie" in page.get_data(as_text=True)
        sent, loved = [], []
        monkeypatch.setattr(slideshow_commands, "send", sent.append)
        monkeypatch.setattr(reactions, "add", lambda photo, kind, who="": loved.append((photo, kind, who)))
        monkeypatch.setattr(routes_simple, "is_slideshow_running", lambda: True)
        assert phone.post("/simple/action", json={"action": "next"}, headers=SAME).get_json()["success"]
        assert sent == ["next"]
        assert phone.post("/simple/action", json={"action": "danse"}, headers=SAME).status_code == 400
        # Nouveau lien : l'ancien téléphone n'est plus reconnu
        admin_client.post("/api/simple_link", json={"renew": True}, headers=SAME)
        assert phone.post("/simple/action", json={"action": "next"}, headers=SAME).status_code == 401
        # Le jeton ne part jamais dans les réglages renvoyés au navigateur
        assert "simple_link_token" not in admin_client.get("/api/settings").get_data(as_text=True)
    finally:
        save_config(original)


def test_message_from_simple_mode(admin_client, monkeypatch):
    from utils import messages_manager
    from web import routes_simple
    monkeypatch.setattr(routes_simple, "is_slideshow_running", lambda: False)
    r = admin_client.post("/simple/message", json={"text": "Je vous embrasse"}, headers=SAME).get_json()
    assert r["success"]
    created = [m for m in messages_manager.list_messages() if m.get("body") == "Je vous embrasse"]
    assert created
    for m in created:
        messages_manager.delete_message(m["id"])
