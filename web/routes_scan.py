"""Scanner de vieilles photos papier (voir utils/photo_scan.py) : aperçu redressé, puis ajout au cadre (source « scans »)."""
import secrets
import time

from flask import send_file

from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from utils import import_progress, photo_scan

SOURCE = "scans"
PENDING = BASE_DIR / "cache" / "scans"
MAX_BYTES = 30 * 1024 * 1024


def _pending(scan_id):
    if not re.fullmatch(r"[0-9a-f]{12}", str(scan_id or "")):
        return None
    path = PENDING / f"{scan_id}.jpg"
    return path if path.is_file() else None


@app.route('/api/scan', methods=['POST'])
@login_required
def scan_api():
    file = request.files.get("photo")
    data = file.read(MAX_BYTES + 1) if file else b""
    if not data or len(data) > MAX_BYTES:
        return jsonify({"success": False, "message": _("Photo manquante ou trop lourde.")}), 400
    try:
        out, found = photo_scan.scan(data)
    except Exception as e:
        logger.warning(f"[Scanner] {e}")
        return jsonify({"success": False, "message": _("Cette image n'est pas lisible.")}), 400
    PENDING.mkdir(parents=True, exist_ok=True)
    for old in PENDING.glob("*.jpg"):  # aperçus abandonnés
        if old.stat().st_mtime < time.time() - 86400:
            old.unlink(missing_ok=True)
    scan_id = secrets.token_hex(6)
    (PENDING / f"{scan_id}.jpg").write_bytes(out)
    return jsonify({"success": True, "id": scan_id, "found": found,
                    "message": _("Tirage détecté et redressé.") if found else _("Bords du tirage non trouvés : la photo est seulement ravivée.")})


@app.route('/api/scan/<scan_id>.jpg')
@login_required
def scan_preview_api(scan_id):
    path = _pending(scan_id)
    if not path:
        abort(404)
    return send_file(path, mimetype="image/jpeg", max_age=0)


@app.route('/api/scan/<scan_id>', methods=['POST', 'DELETE'])
@login_required
def scan_keep_api(scan_id):
    path = _pending(scan_id)
    if not path:
        return jsonify({"success": False, "message": _("Aperçu introuvable : recommencez.")}), 404
    if request.method == 'DELETE':
        path.unlink(missing_ok=True)
        return jsonify({"success": True})
    rotate = int((request.get_json(silent=True) or {}).get("rotate") or 0) % 360
    target = BASE_DIR / "static" / "photos" / SOURCE
    target.mkdir(parents=True, exist_ok=True)
    final = target / f"scan_{datetime.now():%Y%m%d_%H%M%S}_{scan_id[:4]}.jpg"
    from PIL import Image
    with Image.open(path) as image:
        (image.rotate(-rotate, expand=True) if rotate in (90, 180, 270) else image.copy()).save(final, "JPEG", quality=92)
    path.unlink(missing_ok=True)
    config = load_config()
    from utils import colorize
    if config.get("scan_colorize", True) and colorize.installed():
        try:  # tirage noir et blanc : colorisé, l'original gardé à part (dossier caché)
            from web.routes_colorize import colorize_file
            keep = final.parent / ".noir_et_blanc" / final.name
            keep.parent.mkdir(exist_ok=True)
            shutil.copy2(final, keep)
            if not colorize_file(keep, final):
                keep.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"[Scanner] Colorisation impossible : {e}")
    if SOURCE not in config.get("display_sources", []):
        save_config(dict(config, display_sources=list(config.get("display_sources", [])) + [SOURCE]))

    def prepare():
        cfg = load_config()
        for _update in import_progress.tracked(SOURCE, "prepare", prepare_all_photos_with_progress(
                cfg.get("display_width", 1920), cfg.get("display_height", 1080), source_type=SOURCE)):
            pass
        if is_slideshow_running():
            restart_slideshow_for_update()
    threading.Thread(target=prepare, daemon=True, name="scan-prepare").start()
    return jsonify({"success": True, "message": _("Photo ajoutée au cadre.")})
