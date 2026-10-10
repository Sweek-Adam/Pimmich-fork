"""Blocage des essais de mot de passe en série."""
from utils import login_throttle as lt
from conftest import ADMIN_USERNAME, ADMIN_PASSWORD, login


def test_lock_after_max_failures_then_unlock():
    now = 1000.0
    for _ in range(lt.MAX_FAILURES - 1):
        lt.register_failure("admin", "192.168.1.50", now)
    assert lt.seconds_locked("admin", "192.168.1.50", now) == 0
    lt.register_failure("admin", "192.168.1.50", now)
    assert lt.seconds_locked("admin", "192.168.1.50", now) == lt.BASE_LOCK
    assert lt.seconds_locked("admin", "192.168.1.50", now + lt.BASE_LOCK + 1) == 0


def test_lock_duration_doubles():
    now = 1000.0
    for round_ in range(2):
        for _ in range(lt.MAX_FAILURES):
            lt.register_failure("admin", "192.168.1.50", now)
        if round_ == 0:
            now += lt.BASE_LOCK + 1
    assert lt.seconds_locked("admin", "192.168.1.50", now) == 2 * lt.BASE_LOCK


def test_other_accounts_and_addresses_are_not_blocked():
    for _ in range(lt.MAX_FAILURES):
        lt.register_failure("admin", "192.168.1.50")
    assert lt.seconds_locked("marie", "192.168.1.50") == 0
    assert lt.seconds_locked("admin", "192.168.1.60") == 0


def test_address_blocked_after_spraying_many_accounts():
    for i in range(lt.IP_MAX_FAILURES):
        lt.register_failure(f"compte{i}", "192.168.1.50")
    assert lt.seconds_locked("nouveau", "192.168.1.50") > 0


def test_loopback_address_is_never_blocked_globally():
    for i in range(lt.IP_MAX_FAILURES):
        lt.register_failure(f"compte{i}", "127.0.0.1")
    assert lt.seconds_locked("nouveau", "127.0.0.1") == 0


def test_login_page_blocks_after_repeated_failures(client):
    for _ in range(lt.MAX_FAILURES):
        assert login(client, ADMIN_USERNAME, "mauvais").status_code == 200
    resp = login(client, ADMIN_USERNAME, ADMIN_PASSWORD)  # même le bon mot de passe est refusé pendant le blocage
    assert resp.status_code == 429
    assert "Trop de tentatives" in resp.get_data(as_text=True)
    assert client.get("/configure").status_code == 302
