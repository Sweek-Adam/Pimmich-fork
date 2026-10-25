"""
Suivi des imports en cours (téléchargement puis préparation), pour la notification persistante de l'interface.

Chaque import (Google Drive, Immich, partage réseau, clé USB, téléphone, invités) passe ses événements par
`tracked(source, phase, générateur)` : rien ne change pour l'appelant, et l'état est consultable par
`snapshot()` (pourcentage et « n / total » de chaque phase).
"""
import threading
import time

from utils.message_renderer import N_

SOURCE_LABELS = {"gdrive": "Google Drive", "cloud": "Cloud", "icloud": "iCloud", "whatsapp": "WhatsApp", "email": N_("E-mail"), "personnes": N_("Personnes"), "immich": "Immich", "samba": N_("Partage réseau"), "usb": N_("Clé USB"),
                 "smartphone": N_("Téléphone"), "invités": N_("Invités"), "telegram": "Telegram"}
QUIET_AFTER_DOWNLOAD = 45  # sans préparation dans ce délai après le téléchargement : import considéré comme fini
FORGET_AFTER = 20          # un import terminé reste affiché quelques secondes (« terminé »)

_lock = threading.Lock()
_imports = {}
_work = {}  # source -> média en cours de préparation (détails de l'import), et derniers médias traités
RECENT = 12
ON_FINISHED = []  # fonctions appelées à la fin d'une préparation
ON_IMPORT_DONE = []  # fonctions appelées avec le bilan d'un import terminé (notifications)


def _phase():
    return {"current": 0, "total": 0, "percent": 0, "done": False}


def _entry(source):
    entry = _imports.get(source)
    if entry is None or entry.get("finished"):
        entry = {"source": source, "started": time.time(), "download": _phase(), "prepare": _phase(),
                 "phase": "download", "message": "", "finished": None, "error": None}
        _imports[source] = entry
    return entry


def update(source, phase, event, quiet=False):
    """Interprète un événement d'import ou de préparation.

    quiet : synchronisation automatique, cachée tant qu'elle n'a rien à télécharger ni à préparer."""
    with _lock:
        entry = _entry(source)
        entry.setdefault("quiet", quiet)
        step = entry[phase]
        entry["phase"], entry["updated"] = phase, time.time()
        if event.get("message"):
            entry["message"] = str(event["message"])[:200]
        if isinstance(event.get("total"), int) and event["total"] >= 0:
            step["total"] = event["total"]
        if isinstance(event.get("current"), int):
            step["current"] = event["current"]
        if step["total"]:
            entry["quiet"] = False  # des médias à traiter : l'import devient visible
            step["percent"] = min(100, int(100 * step["current"] / step["total"]))
        elif isinstance(event.get("percent"), (int, float)):
            step["percent"] = max(step["percent"], min(99, int(event["percent"])))
        if event.get("type") == "done":
            step["done"], step["percent"] = True, 100
            if step["total"]:
                step["current"] = step["total"]
        if event.get("type") == "error":
            entry["quiet"] = False
            entry["error"] = str(event.get("message", ""))[:200]


def finish(source, phase):
    with _lock:
        entry = _imports.get(source)
        if not entry or entry.get("finished"):
            return
        entry[phase]["done"] = True
        entry[phase]["percent"] = 100
        if phase == "prepare":
            entry["finished"] = time.time()
    if phase == "prepare" and entry:
        report = dict(entry, label=SOURCE_LABELS.get(source, source))
        for callback in list(ON_IMPORT_DONE):
            try:
                callback(report)
            except Exception:
                pass
    if phase == "prepare":
        for callback in list(ON_FINISHED):  # ex. redémarrage du diaporama reporté pendant l'import
            try:
                callback()
            except Exception:
                pass


def tracked(source, phase, generator, quiet=False):
    """Relaie les événements du générateur tout en mettant à jour le suivi (quiet : voir update)."""
    try:
        for event in generator:
            if isinstance(event, dict):
                update(source, phase, event, quiet=quiet)
            yield event
    finally:
        finish(source, phase)


def work_started(source, name, kind, size, index=None, total=None, step=None):
    """Un média commence à être préparé (détails : nom, type, poids, encodage...)."""
    with _lock:
        work = _work.setdefault(source, {"recent": [], "failed": []})
        work["current"] = {"name": name, "kind": kind, "size": size, "started": time.time(), "index": index, "total": total,
                           "step": step or "", "percent": None, "speed": None}


def work_progress(source, percent=None, step=None, speed=None):
    with _lock:
        current = (_work.get(source) or {}).get("current")
        if current:
            if percent is not None:
                current["percent"] = max(0, min(100, int(percent)))
            if step is not None:
                current["step"] = step
            if speed is not None:
                current["speed"] = speed


def work_done(source, name, ok=True, error=None):
    with _lock:
        work = _work.setdefault(source, {"recent": [], "failed": []})
        current = work.pop("current", None) or {}
        item = {"name": name, "kind": current.get("kind"), "size": current.get("size"), "ok": ok,
                "seconds": round(time.time() - current.get("started", time.time()), 1), "error": (error or "")[:300] if not ok else None}
        work["recent"] = ([item] + work["recent"])[:RECENT]
        if not ok:
            work["failed"] = ([item] + [f for f in work["failed"] if f["name"] != name])[:50]


def work(source):
    with _lock:
        data = _work.get(source)
        if not data:
            return None
        current = dict(data["current"]) if data.get("current") else None
        if current:
            current["elapsed"] = round(time.time() - current["started"], 1)
        return {"current": current, "recent": [dict(r) for r in data["recent"]], "failed": [dict(f) for f in data["failed"]]}


def snapshot(now=None):
    """Imports à afficher : en cours, ou terminés depuis quelques secondes."""
    now = now or time.time()
    out = []
    with _lock:
        for source, entry in list(_imports.items()):
            if not entry.get("finished") and entry["download"]["done"] and entry["phase"] == "download" \
                    and now - entry.get("updated", now) > QUIET_AFTER_DOWNLOAD:
                entry["finished"] = now  # rien à préparer ensuite : affiché « terminé » quelques secondes
            if entry.get("finished") and (now - entry["finished"] > FORGET_AFTER or entry.get("quiet")):
                _imports.pop(source, None)  # une synchronisation sans nouveauté disparaît sans s'être montrée
                continue
            if entry.get("quiet"):
                continue
            out.append(dict(entry, label=SOURCE_LABELS.get(source, source), download=dict(entry["download"]),
                            prepare=dict(entry["prepare"]), active=not entry.get("finished")))
    for item in out:
        item["work"] = work(item["source"])
    return sorted(out, key=lambda e: e["started"])


def reset():
    with _lock:
        _imports.clear()
        _work.clear()
