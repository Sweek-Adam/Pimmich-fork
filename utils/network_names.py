"""
Noms sous lesquels on ouvre l'interface du cadre sans connaître son adresse IP (elle change d'une box à l'autre) :
  - <nom>.local : annoncé par le cadre lui-même (avahi), sur tout réseau local ;
  - <nom>.home, <nom>.lan... : enregistré par la box (domaine donné avec l'adresse IP) ;
  - <nom> : avec Tailscale (MagicDNS), depuis n'importe où.
"""
import ipaddress
import re
import socket
import subprocess

TAILSCALE_NET = ipaddress.ip_network("100.64.0.0/10")


def _domains(runner):
    try:
        out = runner(["nmcli", "-t", "-f", "IP4.DOMAIN", "dev", "show"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    found = []
    for line in out.splitlines():
        domain = line.split(":", 1)[-1].strip().lower().strip(".")
        if domain and domain != "local" and domain not in found and re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)*", domain):
            found.append(domain)
    return found


def _tailscale(addresses):
    for address in addresses:
        try:
            if ipaddress.ip_address(address) in TAILSCALE_NET:
                return True
        except ValueError:
            continue
    return False


def addresses(runner=subprocess.run, local_ips=None, hostname=None):
    """[{name, where}] : where = « local », « box » ou « tailscale »."""
    host = (hostname or socket.gethostname()).lower()
    names = [{"name": f"{host}.local", "where": "local"}]
    names += [{"name": f"{host}.{domain}", "where": "box"} for domain in _domains(runner)]
    if local_ips is None:
        try:
            import psutil
            local_ips = [a.address for addrs in psutil.net_if_addrs().values() for a in addrs if a.family == socket.AF_INET]
        except Exception:
            local_ips = []
    if _tailscale(local_ips):
        names.append({"name": host, "where": "tailscale"})
    return names
