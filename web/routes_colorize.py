"""Colorisation des photos noir et blanc (voir utils/colorize.py) : installation du modèle, colorisation d'une photo."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from utils import colorize, import_progress

SOURCE = "colorisees"  # copies colorisées (l'original reste dans sa source)
_working = set()


def _original_for(prepared_key):
    """Photo d'origine d'une photo de la bibliothèque (source/nom préparé), sinon la version préparée."""
    import glob
    source, name = prepared_key.split("/", 1)
    folder = BASE_DIR / "static" / "photos" / source
    for path in sorted(folder.glob(glob.escape(Path(name).stem) + ".*")) if folder.is_dir() else []:
        if path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            return path
    return PREPARED_DIR / prepared_key


def colorize_file(source_path, target_path):
    """Écrit la version colorisée d'une photo ; False si elle n'est pas en noir et blanc."""
    from PIL import Image, ImageOps
    with Image.open(source_path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
    if not colorize.is_grayscale(image):
        return False
    image.thumbnail((3000, 3000))
    Path(target_path).parent.mkdir(parents=True, exist_ok=True)
    colorize.colorize(image).save(target_path, "JPEG", quality=92)
    return True


def _publish():
    config = load_config()
    if SOURCE not in config.get("display_sources", []):
        save_config(dict(config, display_sources=list(config.get("display_sources", [])) + [SOURCE]))
    for _update in import_progress.tracked(SOURCE, "prepare", prepare_all_photos_with_progress(
            config.get("display_width", 1920), config.get("display_height", 1080), source_type=SOURCE)):
        pass
    if is_slideshow_running():
        restart_slideshow_for_update()


@app.route('/api/colorize', methods=['GET'])
@login_required
def colorize_state_api():
    return jsonify({"success": True, "installed": colorize.installed(), "install": dict(colorize.INSTALL)})


@app.route('/api/colorize/install', methods=['POST'])
@admin_required
def colorize_install_api():
    if colorize.INSTALL["running"]:
        return jsonify({"success": False, "message": _("Installation déjà en cours.")}), 409
    try:
        import onnx  # noqa: F401 (conversion du modèle)
    except ImportError:
        return jsonify({"success": False, "message": _("Lancez d'abord une fois : ~/pimmich/venv/bin/pip install onnx")}), 409

    def work():
        try:
            colorize.install()
        except Exception as e:
            logger.warning(f"[Colorisation] Installation : {e}")
    threading.Thread(target=work, daemon=True, name="colorize-install").start()
    return jsonify({"success": True, "message": _("Téléchargement du modèle de colorisation (129 Mo) : quelques minutes.")})


@app.route('/api/colorize', methods=['POST'])
@login_required
def colorize_photo_api():
    """Colorise une photo noir et blanc de la bibliothèque : une copie colorisée rejoint le diaporama."""
    key = str((request.get_json(silent=True) or {}).get("path") or "")
    if not key or ".." in Path(key).parts or not (PREPARED_DIR / key).is_file():
        return jsonify({"success": False, "message": _("Photo introuvable.")}), 404
    if not colorize.installed():
        return jsonify({"success": False, "message": _("Installez d'abord la colorisation (page Importer › Colorisation).")}), 409
    source = _original_for(key)
    target = BASE_DIR / "static" / "photos" / SOURCE / f"{Path(key).stem}_couleur.jpg"
    from PIL import Image
    with Image.open(source) as image:
        if not colorize.is_grayscale(image):
            return jsonify({"success": False, "message": _("Cette photo est déjà en couleur.")}), 400
    if key in _working:
        return jsonify({"success": False, "message": _("Colorisation déjà en cours.")}), 409
    _working.add(key)

    def work():
        try:
            from utils import busy
            with busy.working(_("Colorisation")):
                colorize_file(source, target)
            _publish()
        except Exception as e:
            logger.warning(f"[Colorisation] {key} : {e}")
        finally:
            _working.discard(key)
    threading.Thread(target=work, daemon=True, name="colorize").start()
    return jsonify({"success": True, "message": _("Colorisation en cours : la copie en couleur rejoindra le diaporama dans un instant.")})
