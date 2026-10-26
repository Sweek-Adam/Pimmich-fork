"""
Diffusion sur une télé Chromecast (ou un écran Google TV) : le diaporama ou le film de l'année, sans câble.

Le Chromecast télécharge lui-même les photos sur le cadre, en HTTP sur le réseau de la maison (/static/ : pas de
certificat à accepter). Le cadre envoie une photo à la fois, au rythme du diaporama, depuis un fil d'arrière-plan
qu'on arrête d'un bouton (la télé revient alors à son écran d'accueil).
"""
import random
import threading
import time
import uuid

STATE = {"device": None, "name": None, "mode": None, "started": None, "shown": 0, "error": None}
_stop = threading.Event()
_thread = [None]


def _pychromecast():
    import pychromecast  # paquet facultatif : seulement pour cette fonction
    return pychromecast


def available():
    try:
        _pychromecast()
        return True
    except ImportError:
        return False


def discover(timeout=6):
    """Télés Chromecast du réseau : [{uuid, name, model}]."""
    pychromecast = _pychromecast()
    casts, browser = pychromecast.get_chromecasts(timeout=timeout)
    try:
        return sorted(({"uuid": str(c.uuid), "name": c.cast_info.friendly_name, "model": c.cast_info.model_name} for c in casts),
                      key=lambda d: d["name"].lower())
    finally:
        pychromecast.discovery.stop_discovery(browser)


def _connect(device_uuid, timeout=10):
    pychromecast = _pychromecast()
    casts, browser = pychromecast.get_listed_chromecasts(uuids=[uuid.UUID(device_uuid)], discovery_timeout=timeout)
    pychromecast.discovery.stop_discovery(browser)
    if not casts:
        raise LookupError("Télé introuvable : est-elle allumée, sur le même Wi-Fi ?")
    cast = casts[0]
    cast.wait(timeout=timeout)
    return cast


def running():
    return bool(_thread[0] and _thread[0].is_alive())


def start(device_uuid, items, seconds=10, mode="photos", connect=None):
    """Lance la diffusion : `items` = [(url, type MIME, titre)], montrés à la suite (en boucle pour des photos)."""
    stop()
    _stop.clear()
    STATE.update(device=device_uuid, name=None, mode=mode, started=time.time(), shown=0, error=None)

    def work():
        cast = None
        try:
            cast = (connect or _connect)(device_uuid)
            STATE["name"] = cast.cast_info.friendly_name
            controller = cast.media_controller
            while not _stop.is_set():
                for url, mime, title in items:
                    if _stop.is_set():
                        break
                    controller.play_media(url, mime, title=title, stream_type="BUFFERED")
                    controller.block_until_active(timeout=15)
                    STATE["shown"] += 1
                    if mime.startswith("video/"):
                        return  # un film : il se lit jusqu'au bout sur la télé
                    _stop.wait(seconds)
                if mode != "photos":
                    return
        except Exception as e:
            STATE["error"] = str(e)[:200]
        finally:
            if cast is not None and _stop.is_set():
                try:
                    cast.quit_app()
                except Exception:
                    pass

    _thread[0] = threading.Thread(target=work, daemon=True, name="chromecast")
    _thread[0].start()


def stop():
    _stop.set()
    if _thread[0] is not None:
        _thread[0].join(timeout=5)
    _thread[0] = None
    STATE.update(mode=None)


def photo_items(base_url, prepared_keys, rng=None, limit=200):
    """Photos du diaporama à diffuser (mélangées) : [(url, type MIME, titre)]."""
    keys = [k for k in prepared_keys if k.lower().endswith((".jpg", ".jpeg", ".png"))]
    (rng or random).shuffle(keys)
    from urllib.parse import quote
    return [(f"{base_url}/static/prepared/{quote(k)}", "image/jpeg", "") for k in keys[:limit]]
