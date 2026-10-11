"""
Invités de confiance : le téléphone d'un invité reçoit un identifiant (cookie) ; une fois « toujours accepter cet
appareil » choisi lors d'une validation, ses photos suivantes s'affichent sans attendre.
"""
import json
import re
import secrets
import threading
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
META_FILE = BASE_DIR / "cache" / "pending_meta.json"
COOKIE = "pimmich_guest"
DEVICE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
_lock = threading.Lock()


def new_device():
    return secrets.token_urlsafe(18)


def valid(device):
    return bool(device and DEVICE.match(device))


def _load():
    try:
        return json.loads(META_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def remember(filename, device, name=""):
    """Note l'appareil (et le prénom) à l'origine d'une photo en attente."""
    with _lock:
        meta = _load()
        meta[filename] = {"device": device if valid(device) else "", "name": (name or "").strip()[:60]}
        META_FILE.parent.mkdir(parents=True, exist_ok=True)
        META_FILE.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


def info(filename):
    return _load().get(filename, {})


def forget(filename):
    with _lock:
        meta = _load()
        if meta.pop(filename, None) is not None:
            META_FILE.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


def is_trusted(config, device):
    return valid(device) and any(t.get("device") == device for t in config.get("trusted_guests") or [])


def trust(config, device, label):
    """Ajoute un appareil de confiance ; renvoie la nouvelle liste."""
    trusted = [t for t in config.get("trusted_guests") or [] if t.get("device") != device]
    trusted.append({"device": device, "label": (label or "").strip()[:60] or f"Appareil du {date.today().strftime('%d/%m/%Y')}",
                    "since": date.today().isoformat()})
    return trusted[-100:]
