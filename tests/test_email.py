"""Envoi par e-mail : relève IMAP, expéditeurs de confiance, photos à valider, légendes, réglages."""
from email.message import EmailMessage

import pytest

from utils import import_email

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}
CONFIG = {"email_imap_host": "imap.test", "email_user": "cadre@test.fr", "email_password": "secret",
          "email_allowed_senders": ["mamie@orange.fr"], "email_unknown_senders": "pending"}


def mail(sender, subject="", files=(("vacances.jpg", b"\xff\xd8photo"),), body="Bisous"):
    message = EmailMessage()
    message["From"], message["Subject"], message["Date"] = f"Mamie <{sender}>", subject, "Tue, 12 Aug 2025 14:03:21 +0200"
    message.set_content(body)
    for name, data in files:
        maintype, subtype = ("video", "mp4") if name.endswith(".mp4") else ("image", "jpeg")
        message.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    return message.as_bytes()


class FakeIMAP:
    """Boîte IMAP en mémoire : {uid: message}."""
    box = {}
    validity = b"7"
    logins = []

    def __init__(self, host, port, timeout):
        self.host = host

    def login(self, user, password):
        if password != "secret":
            raise import_email.imaplib.IMAP4.error("auth")
        FakeIMAP.logins.append(user)

    def select(self, folder, readonly=False):
        return ("OK", [str(len(self.box)).encode()]) if folder == "INBOX" else ("NO", [b""])

    def response(self, code):
        return code, [self.validity]

    def uid(self, command, *args):
        if command == "search":
            query = args[-1]
            low = int(query.split()[1].split(":")[0]) if query.startswith("UID") else 0
            return "OK", [" ".join(str(u) for u in sorted(self.box) if u >= low).encode()]
        return "OK", [(b"1 (BODY[] {n}", self.box[int(args[0])]), b")"]

    def logout(self):
        pass


@pytest.fixture
def mailbox(monkeypatch, tmp_path):
    monkeypatch.setattr(import_email.imaplib, "IMAP4_SSL", FakeIMAP)
    for name in ("TARGET_DIR", "PENDING_DIR"):
        monkeypatch.setattr(import_email, name, tmp_path / name.lower())
    monkeypatch.setattr(import_email, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(import_email, "CAPTIONS_FILE", tmp_path / "captions.json")
    FakeIMAP.box = {1: mail("ancien@test.fr")}
    return tmp_path


def test_first_check_skips_history_then_imports_new_mail(mailbox):
    assert import_email.check(CONFIG) == {"accepted": 0, "pending": 0, "ignored": 0}  # l'historique n'est pas importé
    FakeIMAP.box[2] = mail("Mamie@Orange.fr", "Fwd: Plage de Biarritz", files=(("a.jpg", b"1"), ("film.mp4", b"2")))
    FakeIMAP.box[3] = mail("inconnu@spam.com", "Coucou")
    FakeIMAP.box[4] = mail("mamie@orange.fr", files=())  # sans pièce jointe
    assert import_email.check(CONFIG) == {"accepted": 2, "pending": 1, "ignored": 0}
    accepted = sorted(p.name for p in (mailbox / "target_dir").iterdir())
    assert len(accepted) == 2 and accepted[0].startswith("20250812_140321_")
    assert set(import_email.captions().values()) == {"Plage de Biarritz"}
    assert len(list((mailbox / "pending_dir").iterdir())) == 1
    assert import_email.check(CONFIG) == {"accepted": 0, "pending": 0, "ignored": 0}  # déjà relevés


def test_unknown_senders_can_be_ignored_and_body_is_the_caption(mailbox):
    import_email.check(CONFIG)
    FakeIMAP.box[2] = mail("inconnu@spam.com")
    FakeIMAP.box[3] = mail("mamie@orange.fr", "", body="\nJoyeux Noël à tous\n> ancien message")
    assert import_email.check(dict(CONFIG, email_unknown_senders="ignore")) == {"accepted": 1, "pending": 0, "ignored": 1}
    assert list(import_email.captions().values()) == ["Joyeux Noël à tous"]


def test_wrong_password(mailbox):
    with pytest.raises(ValueError):
        import_email.test(dict(CONFIG, email_password="faux"))
    with pytest.raises(ValueError):
        import_email.test(dict(CONFIG, email_password=""))
    assert import_email.test(CONFIG) == 1


def test_email_api(admin_client, mailbox, monkeypatch):
    from utils.config_manager import load_config, save_config
    original = dict(load_config())
    try:
        r = admin_client.post("/api/email", json={"enabled": True, "user": "cadre@test.fr", "password": "secret", "host": "imap.test",
                                                  "port": "993", "allowed": "Mamie@orange.fr; papa@gmail.com, pas-une-adresse"},
                              headers=SAME_ORIGIN).get_json()
        assert r["success"]
        state = admin_client.get("/api/email").get_json()
        assert state["has_password"] and "password" not in state and "secret" not in str(state)
        assert state["allowed"] == ["mamie@orange.fr", "papa@gmail.com"] and state["providers"]["gmail.com"] == "imap.gmail.com"
        admin_client.post("/api/email", json={"password": ""}, headers=SAME_ORIGIN)
        assert load_config()["email_password"] == "secret"  # champ vide : mot de passe gardé
        assert admin_client.post("/api/email/test", headers=SAME_ORIGIN).get_json()["success"]
        assert admin_client.post("/api/email/check", headers=SAME_ORIGIN).get_json()["success"]
        assert admin_client.post("/api/email", json={"port": "abc"}, headers=SAME_ORIGIN).status_code == 400
    finally:
        save_config(original)
