"""Comptes en JSON (nouvelle interface) : mêmes règles que les formulaires classiques."""
H = {"Sec-Fetch-Site": "same-origin"}


def login(client, username, password):  # (pas d'import de conftest : il recréerait un bac à sable)
    return client.post("/login", data={"username": username, "password": password}, headers=H)


def test_accounts_admin_flow(admin_client, app_module):
    data = admin_client.get("/api/accounts").get_json()
    assert data["admin"] and data["me"] == "admin" and isinstance(data["users"], list)
    r = admin_client.post("/api/accounts", json={"username": "paul", "password": "secret456", "role": "user"}, headers=H)
    assert r.get_json()["success"], r.get_json()
    assert any(u["username"] == "paul" and u["role"] == "user" for u in admin_client.get("/api/accounts").get_json()["users"])
    assert admin_client.post("/api/accounts", json={"username": "paul", "password": "secret456"}, headers=H).status_code == 400
    assert admin_client.post("/api/accounts/paul/role", json={"role": "admin"}, headers=H).get_json()["success"]
    assert admin_client.post("/api/accounts/paul/role", json={"role": "roi"}, headers=H).status_code == 400
    assert admin_client.post("/api/accounts/paul/password", json={"password": "123"}, headers=H).status_code == 400
    assert admin_client.post("/api/accounts/paul/password", json={"password": "nouveau789"}, headers=H).get_json()["success"]
    paul = app_module.app.test_client()
    assert login(paul, "paul", "nouveau789").status_code in (302, 303)
    assert paul.get("/api/accounts").get_json()["me"] == "paul"
    assert admin_client.delete("/api/accounts/paul", headers=H).get_json()["success"]
    assert admin_client.delete("/api/accounts/admin", headers=H).status_code == 400  # pas son propre compte


def test_accounts_user_rights(user_client):
    data = user_client.get("/api/accounts").get_json()
    assert data["me"] == "marie" and not data["admin"] and data["users"] == []
    assert user_client.post("/api/accounts", json={"username": "x", "password": "secret456"}, headers=H).status_code in (302, 403)
    assert user_client.delete("/api/accounts/admin", headers=H).status_code in (302, 403)
    r = user_client.post("/api/accounts/password", json={"new_password": "abcdefg", "confirm_password": "abcdefh"}, headers=H)
    assert r.status_code == 400
    r = user_client.post("/api/accounts/password", json={"new_password": "abcdefg", "confirm_password": "abcdefg"}, headers=H)
    assert r.get_json()["success"]
