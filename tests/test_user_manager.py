import pytest

from utils import user_manager


def test_create_and_authenticate(users_file):
    user_manager.create_user("marie", "secret123", "user")
    assert user_manager.authenticate("marie", "secret123") == "user"
    assert user_manager.authenticate("marie", "mauvais") is None
    assert user_manager.authenticate("inconnu", "secret123") is None


def test_password_is_hashed(users_file):
    user_manager.create_user("marie", "secret123", "user")
    assert "secret123" not in users_file.read_text()


@pytest.mark.parametrize("username,password,role", [
    ("x", "secret123", "user"),            # nom trop court
    ("marie dupont", "secret123", "user"),  # espace interdit
    ("marie", "123", "user"),               # mot de passe trop court
    ("marie", "secret123", "superadmin"),   # rôle inconnu
])
def test_create_rejects_invalid_input(users_file, username, password, role):
    with pytest.raises(ValueError):
        user_manager.create_user(username, password, role)


def test_create_rejects_duplicates_and_reserved_names(users_file):
    user_manager.create_user("marie", "secret123", "user")
    with pytest.raises(ValueError):
        user_manager.create_user("marie", "autre1234", "user")
    with pytest.raises(ValueError):
        user_manager.create_user("admin", "secret123", "user", reserved_names=("admin",))


def test_role_password_and_delete(users_file):
    user_manager.create_user("marie", "secret123", "user")
    user_manager.set_role("marie", "admin")
    assert user_manager.get_role("marie") == "admin"
    user_manager.set_password("marie", "nouveau123")
    assert user_manager.authenticate("marie", "nouveau123") == "admin"
    user_manager.delete_user("marie")
    assert user_manager.get_role("marie") is None
    assert user_manager.list_users() == []
