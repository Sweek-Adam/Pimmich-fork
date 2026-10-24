"""Adresses du cadre qui ne dépendent pas de son IP (.local, nom donné par la box, Tailscale)."""
from types import SimpleNamespace

from utils import network_names


def runner(out):
    return lambda *a, **k: SimpleNamespace(stdout=out, returncode=0)


def test_local_box_and_tailscale_names():
    names = network_names.addresses(runner("IP4.DOMAIN[1]:home\nIP4.DOMAIN[1]:\nIP4.DOMAIN[1]:home\n"),
                                    local_ips=["192.168.1.31", "100.127.227.116"], hostname="Cadre-photo")
    assert names == [{"name": "cadre-photo.local", "where": "local"}, {"name": "cadre-photo.home", "where": "box"},
                     {"name": "cadre-photo", "where": "tailscale"}]


def test_without_box_domain_or_tailscale():
    names = network_names.addresses(runner(""), local_ips=["192.168.1.31"], hostname="cadre")
    assert names == [{"name": "cadre.local", "where": "local"}]


def test_odd_domains_are_ignored():
    def broken(*a, **k):
        raise OSError("nmcli absent")
    assert network_names.addresses(broken, local_ips=[], hostname="cadre") == [{"name": "cadre.local", "where": "local"}]
    names = network_names.addresses(runner("IP4.DOMAIN[1]:local\nIP4.DOMAIN[1]:bad domain;rm\nIP4.DOMAIN[1]:a-b;c\n"), local_ips=[], hostname="cadre")
    assert names == [{"name": "cadre.local", "where": "local"}]
