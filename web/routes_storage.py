"""Stockage sur plusieurs supports : carte SD, disques USB, partages réseau ; emplacement de chaque source."""
import re
import secrets

from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from utils import storage

_move_state = {"running": False}
SHARE = re.compile(r"^//[A-Za-z0-9._-]+(/[^/\s][^\s]*)+$")


def _storage_view(item):
    mounted = storage.is_mounted(item)
    return {"id": item["id"], "label": item.get("label", item["id"]), "kind": item["kind"], "mounted": mounted,
            "usage": storage.usage(storage.mountpoint(item)) if mounted else None, "share": item.get("share")}


@app.route('/api/storage', methods=['GET'])
@login_required
def storage_api():
    config = load_config()
    configured = config.get("storages") or []
    known = {s.get("uuid") for s in configured}
    return jsonify({"success": True, "sd": storage.usage(BASE_DIR), "storages": [_storage_view(s) for s in configured],
                    "disks": [d for d in storage.disks() if d["uuid"] not in known],
                    "sources": storage.source_sizes(), "move": dict(_move_state)})


@app.route('/api/storage/add', methods=['POST'])
@admin_required
def storage_add_api():
    """Ajoute un disque (par son UUID) ou un partage réseau (//serveur/partage) et le monte."""
    data = request.get_json(silent=True) or {}
    config = dict(load_config())
    configured = list(config.get("storages") or [])
    item = {"id": f"s{secrets.token_hex(3)}", "label": str(data.get("label") or "").strip()[:60]}
    if data.get("kind") == "disk":
        disk = next((d for d in storage.disks() if d["uuid"] == data.get("uuid")), None)
        if disk is None:
            return jsonify({"success": False, "message": _("Disque introuvable : est-il bien branché ?")}), 404
        if any(s.get("uuid") == disk["uuid"] for s in configured):
            return jsonify({"success": False, "message": _("Ce disque est déjà ajouté.")}), 409
        item.update(kind="disk", uuid=disk["uuid"], label=item["label"] or disk["label"])
    elif data.get("kind") == "smb":
        share = str(data.get("share") or "").strip().replace("\\", "/")
        if not SHARE.match(share):
            return jsonify({"success": False, "message": _("Adresse du partage invalide (ex : //nas.local/photos).")}), 400
        item.update(kind="smb", share=share, label=item["label"] or share[2:])
        if data.get("username"):
            storage.save_credentials(item["id"], str(data["username"])[:100], str(data.get("password") or "")[:200], str(data.get("domain") or "")[:100])
    else:
        return jsonify({"success": False, "message": _("Type de support inconnu.")}), 400
    ok, message = storage.mount(item)
    if not ok:
        (storage.CREDENTIALS_DIR / f"{item['id']}.cred").unlink(missing_ok=True)
        return jsonify({"success": False, "message": _("Impossible d'utiliser ce support : %(error)s", error=message)}), 400
    configured.append(item)
    config["storages"] = configured
    save_config(config)
    return jsonify({"success": True, "message": _("Support « %(name)s » ajouté.", name=item["label"])})


@app.route('/api/storage/remove', methods=['POST'])
@admin_required
def storage_remove_api():
    storage_id = (request.get_json(silent=True) or {}).get("id")
    config = dict(load_config())
    if storage_id in (config.get("storage_placement") or {}).values():
        return jsonify({"success": False, "message": _("Des photos sont encore sur ce support : déplacez-les d'abord.")}), 400
    item = next((s for s in config.get("storages") or [] if s["id"] == storage_id), None)
    if item is None:
        return jsonify({"success": False, "message": _("Support inconnu.")}), 404
    storage.unmount(item)
    (storage.CREDENTIALS_DIR / f"{storage_id}.cred").unlink(missing_ok=True)
    config["storages"] = [s for s in config["storages"] if s["id"] != storage_id]
    save_config(config)
    return jsonify({"success": True, "message": _("Support retiré.")})


def _run_move(source, target):
    with app.app_context():
        _move(source, target)


def _move(source, target):
    def progress(done, total):
        _move_state.update(done=done, total=total)
    try:
        storage.move(source, target, load_config(), progress)
        config = dict(load_config())
        placement = dict(config.get("storage_placement") or {})
        if target == storage.SD:
            placement.pop(source, None)
        else:
            placement[source] = target
        config["storage_placement"] = placement
        save_config(config)
        _move_state.update(message=_("Photos de « %(source)s » déplacées.", source=source), ok=True)
        if is_slideshow_running():
            restart_slideshow_for_update()
    except Exception as e:
        _move_state.update(message=str(e)[:300], ok=False)
    finally:
        _move_state["running"] = False


@app.route('/api/storage/move', methods=['POST'])
@admin_required
def storage_move_api():
    data = request.get_json(silent=True) or {}
    source, target = str(data.get("source") or ""), str(data.get("to") or "")
    if source not in storage.sources():
        return jsonify({"success": False, "message": _("Source inconnue.")}), 404
    if target != storage.SD and not any(s["id"] == target for s in load_config().get("storages") or []):
        return jsonify({"success": False, "message": _("Support inconnu.")}), 404
    if _move_state.get("running"):
        return jsonify({"success": False, "message": _("Un déplacement est déjà en cours.")}), 409
    _move_state.clear()
    _move_state.update(running=True, source=source, to=target, done=0, total=0)
    threading.Thread(target=_run_move, args=(source, target), daemon=True, name="storage-move").start()
    return jsonify({"success": True, "message": _("Déplacement lancé : les photos restent affichées pendant la copie.")})
