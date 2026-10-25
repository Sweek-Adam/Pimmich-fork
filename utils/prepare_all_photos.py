import os
import shutil
from PIL import Image, ImageFilter, ImageDraw, ImageFont
import json
try:
    import pillow_heif
    HEIF_SUPPORT = True
except ImportError:
    HEIF_SUPPORT = False
import subprocess, sys
import threading
import time
from utils.config import load_config
import piexif
from utils.image_filters import create_polaroid_effect, create_postcard_effect
from utils.message_renderer import soft_blur
from utils.exif import get_rotation_angle
import logging
import re
from pathlib import Path
from logging.handlers import RotatingFileHandler

from .config_manager import load_config

# Configuration
SOURCE_DIR = "static/photos"

# Default target output resolution for prepared images
DEFAULT_OUTPUT_WIDTH = 1920
DEFAULT_OUTPUT_HEIGHT = 1080
VIDEO_EXTENSIONS = ('.mp4', '.mov', '.avi', '.mkv')

# Chemin vers le cache du mappage des métadonnées Immich
DESCRIPTION_MAP_CACHE_FILE = Path("cache") / "immich_description_map.json"

# Chemin vers le cache des textes saisis par l'utilisateur
USER_TEXT_MAP_CACHE_FILE = Path("cache") / "user_texts.json"

CANCEL_FLAG = Path('/tmp/pimmich_cancel_import.flag')


# ============================================================
# Configuration du logging avec émojis
# ============================================================
LOGSDIR = Path(__file__).resolve().parent.parent / "logs"
LOGSDIR.mkdir(exist_ok=True)

class EmojiFormatter(logging.Formatter):
    """Formatter personnalisé avec émojis selon le niveau."""
    EMOJI_MAP = {
        "DEBUG": "🔍",
        "INFO": "ℹ️",
        "WARNING": "😒",
        "ERROR": "❌",
        "CRITICAL": "🔥"
    }

    def format(self, record):
        emoji = self.EMOJI_MAP.get(record.levelname, "")
        record.emoji = emoji
        return super().format(record)

# Charger la configuration
config = load_config()

# Créer un logger spécifique pour ce module
logger = logging.getLogger("pimmich.prepare_all_photos")

# Récupérer le niveau de log depuis la configuration
level_name = config.get("level_log", "INFO")
level = getattr(logging, level_name.upper(), logging.INFO)
logger.setLevel(level)
logger.propagate = False

# Handler fichier avec rotation (10 Mo max, 3 backups)
file_handler = RotatingFileHandler(
    LOGSDIR / "pimmich.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8"
)
file_handler.setLevel(level)

# Format modernisé avec emoji en début de ligne
file_formatter = EmojiFormatter(
    '%(emoji)s🔄%(asctime)s %(message)s',
    datefmt='%d-%m %H:%M:%S'
)
file_handler.setFormatter(file_formatter)

# Ajouter les handlers (éviter doublons si module réimporté)
if not logger.handlers:
    logger.addHandler(file_handler)

# Messages de démarrage
logger.debug("----------------Initialisation Prepare All Photos----------------")
# Mappage des types de messages vers les niveaux de log
TYPE_TO_LOGGER = {
    "progress": logger.info,
    "info": logger.info,
    "warning": logger.warning,
    "error": logger.error,
    "done": logger.info,
    "stats": logger.info,
}

def yield_and_log(msg_type: str, message: str, stage=None, percent=None, extra=None):
    """
    Fonction utilitaire qui construit un dict pour yield ET envoie le log correspondant.
    
    Args:
        msg_type: Type de message ("progress", "info", "warning", "error", "done", "stats")
        message: Le message à afficher
        stage: Étape optionnelle (ex: "CLEANING", "PREPARING_PHOTO")
        percent: Pourcentage optionnel de progression
        extra: Dictionnaire optionnel de champs supplémentaires
    
    Returns:
        Dict prêt pour yield contenant tous les champs nécessaires
    """
    result = {"type": msg_type, "message": message}
    
    if stage is not None:
        result["stage"] = stage
    if percent is not None:
        result["percent"] = percent
    if extra:
        result.update(extra)
    
    # Log avec le bon niveau selon le type
    log_func = TYPE_TO_LOGGER.get(msg_type, logger.info)
    log_func(f"🔄{message}")
    
    return result



def get_pi_model():
    """Détecte le modèle du Raspberry Pi."""
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model_str = f.read()
            if 'Raspberry Pi 4' in model_str:
                return 4
            if 'Raspberry Pi 5' in model_str:
                return 5
            if 'Raspberry Pi 3' in model_str:
                return 3
            if 'Raspberry Pi 2' in model_str:
                return 2
            if 'Zero' in model_str:
                return 1
            if 'Raspberry Pi' in model_str:
                return 1
    except (FileNotFoundError, Exception):
        return None
    return None

def open_for_screen(source_path, output_height):
    """
    Ouvre une photo pour la préparer. Les très grandes photos JPEG (panoramas, appareils de 100 mégapixels et plus)
    sont décodées directement à 1/2, 1/4 ou 1/8 de leur taille, sans descendre sous la hauteur de l'écran : bien
    moins de mémoire (le Raspberry Pi 3 n'a que 1 Go) et de temps. Pillow signale ces photos comme de possibles
    « bombes de décompression » : c'est sans objet pour un JPEG décodé réduit ; les autres formats gardent la limite.
    """
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        img = Image.open(source_path)
    if img.format == "JPEG":
        side = max(1, int(output_height))  # les deux côtés : la photo peut encore être tournée (EXIF)
        img.draft("RGB", (side, side))
    elif img.width * img.height > (Image.MAX_IMAGE_PIXELS or float("inf")):
        img.close()
        raise ValueError(f"image trop grande ({img.width}×{img.height}) pour être préparée")
    return img


def prepare_photo(source_path, dest_path, output_width, output_height, source_type=None, caption=None):
    """Prépare une photo pour l'affichage avec redimensionnement, rotation EXIF et fond flou."""
    config = load_config()
    screen_height_percent = int(config.get("screen_height_percent", "100"))
    effective_photo_height = int(output_height * (screen_height_percent / 100))
    
    try:
        # Gestion des fichiers HEIF/HEIC
        if source_path.lower().endswith(('.heic', '.heif')):
            if HEIF_SUPPORT:
                pillow_heif.register_heif_opener()
            else:
                logger.warning(f"Support HEIF désactivé (pillow-heif non installé). Impossible de traiter {source_path}")
                return None
        
        img = open_for_screen(source_path, output_height)
        
        # Modification Sigalou 25/01/2026 - Suppression de la lecture EXIF redondante
        # Les métadonnées sont déjà dans le JSON créé par download_album.py
        # On ne lit plus les EXIF ici pour éviter la duplication
        # Fin Modification Sigalou 25/01/2026
        
        # 1. Handle EXIF Orientation
        rotation_angle = get_rotation_angle(img)
        if rotation_angle != 0:
            img = img.rotate(rotation_angle, expand=True)
        
        # Remove EXIF data after rotation
        if "exif" in img.info:
            img.info.pop("exif")
        if "icc_profile" in img.info:
            img.info.pop("icc_profile")
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        
        # Determine if the image is portrait-like
        img_aspect_ratio = img.width / img.height
        display_area_aspect_ratio = output_width / effective_photo_height
        
        pi_model = get_pi_model()
        is_low_end = (pi_model in [1, 2, 3])
        resample_filter = Image.Resampling.BILINEAR if is_low_end else Image.Resampling.LANCZOS
        
        if img_aspect_ratio < display_area_aspect_ratio:
            # Portrait photo - add blurred background
            img_content = img.copy()
            scale = effective_photo_height / img.height
            new_width = int(img.width * scale)
            img_content = img_content.resize((new_width, effective_photo_height), resample_filter)
            
            # Create blurred background
            if is_low_end:
                # Optimized, low-memory background blur for Raspberry Pi 1, 2, 3
                bg_scale = max(160 / img.width, 90 / img.height)
                bg_new_width = int(img.width * bg_scale)
                bg_new_height = int(img.height * bg_scale)
                bg_img = img.resize((bg_new_width, bg_new_height), Image.Resampling.NEAREST)
                if bg_img.width > 160 or bg_img.height > 90:
                    left = (bg_img.width - 160) // 2
                    top = (bg_img.height - 90) // 2
                    bg_img = bg_img.crop((left, top, left + 160, top + 90))
                bg_img = soft_blur(bg_img, 3)
                bg_img = bg_img.resize((output_width, output_height), Image.Resampling.BILINEAR)
            else:
                bg_img = img.copy()
                bg_scale = max(output_width / img.width, output_height / img.height)
                bg_new_width = int(img.width * bg_scale)
                bg_new_height = int(img.height * bg_scale)
                bg_img = bg_img.resize((bg_new_width, bg_new_height), Image.Resampling.LANCZOS)
                if bg_img.width > output_width or bg_img.height > output_height:
                    left = (bg_img.width - output_width) // 2
                    top = (bg_img.height - output_height) // 2
                    bg_img = bg_img.crop((left, top, left + output_width, top + output_height))
                bg_img = soft_blur(bg_img, 50)
            
            final_img = Image.new('RGB', (output_width, output_height), (0, 0, 0))
            final_img.paste(bg_img, (0, 0))
            
            x_offset = (output_width - img_content.width) // 2
            y_offset = (output_height - img_content.height) // 2
            final_img.paste(img_content, (x_offset, y_offset))
        else:
            # Landscape or square photo
            img_content = img.copy()
            scale = effective_photo_height / img.height
            new_width = int(img.width * scale)
            img_content = img_content.resize((new_width, effective_photo_height), resample_filter)
            
            final_img = Image.new('RGB', (output_width, output_height), (0, 0, 0))
            x_offset = (output_width - img_content.width) // 2
            y_offset = (output_height - img_content.height) // 2
            if img_content.width > output_width and config.get("smart_crop", True):
                # Photo plus large que l'écran : la partie gardée contient les visages
                from utils import faces
                found = faces.for_file(source_path, img)
                if found:
                    x_offset = -faces.window(img_content.width, img_content.height, output_width, img_content.height, found)[0]
            final_img.paste(img_content, (x_offset, y_offset))
        
        # Prepare EXIF metadata with content coordinates
        exif_bytes_to_add = None
        try:
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
            bbox_str = f"pimmich_bbox:{x_offset},{y_offset},{img_content.width},{img_content.height}"
            exif_dict["Exif"][piexif.ExifIFD.UserComment] = bbox_str.encode('ascii')
            exif_bytes_to_add = piexif.dump(exif_dict)
        except Exception as exif_e:
            print(f"[EXIF] Avertissement: Impossible de créer les métadonnées pour {os.path.basename(source_path)}: {exif_e}")
        
        # Generate Polaroid version
        try:
            polaroid_content = create_polaroid_effect(img_content.copy())
            polaroid_final_img = final_img.copy()
            polaroid_final_img.paste(polaroid_content, (x_offset, y_offset))
            
            dest_path_obj = Path(dest_path)
            polaroid_dest_path = dest_path_obj.with_name(f"{dest_path_obj.stem}_polaroid.jpg")
            polaroid_final_img.save(polaroid_dest_path, 'JPEG', quality=90, optimize=True, exif=exif_bytes_to_add)
        except Exception as polaroid_e:
            print(f"[Polaroid] Avertissement: Impossible de créer la version Polaroid pour {os.path.basename(source_path)}: {polaroid_e}")
        
        # Generate Postcard version
        try:
            postcard_img_content = img_content.copy()
            scale_factor = 0.85
            postcard_img_content.thumbnail(
                (int(output_width * scale_factor), int(output_height * scale_factor)),
                resample_filter
            )
            
            from utils import captions
            caption_key = f"{source_type or Path(dest_path).parent.name}/{Path(dest_path).name}"
            postcard_content = create_postcard_effect(postcard_img_content, caption=caption,
                                                      style=captions.style_for(config, "photo", caption_key))
            postcard_final_img = final_img.copy()
            postcard_x_offset = (output_width - postcard_content.width) // 2
            postcard_y_offset = (output_height - postcard_content.height) // 2
            postcard_final_img.paste(postcard_content, (postcard_x_offset, postcard_y_offset), postcard_content)
            
            dest_path_obj = Path(dest_path)
            postcard_dest_path = dest_path_obj.with_name(f"{dest_path_obj.stem}_postcard.jpg")
            postcard_final_img.save(postcard_dest_path, 'JPEG', quality=90, optimize=True, exif=exif_bytes_to_add)
        except Exception as postcard_e:
            print(f"--- ERREUR CRÉATION CARTE POSTALE pour {os.path.basename(source_path)} ---")
            print(f"Détails de l'erreur : {postcard_e}")
            print("Vérifiez que les polices (static/fonts) et les timbres (static/stamps) sont présents et accessibles.")
            print("--------------------------------------------------------------------")
        
        # Save main prepared image
        img_to_save = final_img
        if exif_bytes_to_add:
            img_to_save.save(dest_path, 'JPEG', quality=85, optimize=True, exif=exif_bytes_to_add)
        else:
            img_to_save.save(dest_path, 'JPEG', quality=85, optimize=True)

        # GIF animé : la photo préparée montre sa première image, l'animation est rejouée par-dessus à l'affichage
        from utils import animated
        if animated.is_animated(source_path):
            animated.write(dest_path, [animated.single_item(source_path, x_offset, y_offset, img_content.width, img_content.height)])
        else:
            animated.write(dest_path, [])
    
    except Exception as e:
        raise Exception(f"Erreur lors du traitement de l'image '{os.path.basename(source_path)}': {e}")

LIGHT_VIDEO_DEFAULT_MB = 150  # au-delà (réglage « video_light_above_mb »), encodage allégé : 720p, 30 images/s au plus


def _even(value):
    return max(2, int(value) // 2 * 2)


def video_duration(source_path):
    """Durée de la vidéo en secondes (None si inconnue)."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(source_path)],
                             capture_output=True, text=True, timeout=30).stdout.strip()
        return float(out) if out else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def run_ffmpeg(command, duration=None, on_progress=None):
    """Lance ffmpeg en suivant son avancement (pourcentage, vitesse). Retourne (code, fin du message d'erreur)."""
    import tempfile
    command = list(command)
    at = command.index("ffmpeg") + 1
    command[at:at] = ["-nostats", "-progress", "pipe:1"]
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as errors:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors, text=True, encoding="utf-8", errors="replace")
        speed = None
        for line in process.stdout:
            key, _sep, value = line.strip().partition("=")
            if key == "speed" and value not in ("", "N/A"):
                speed = value
            elif key == "out_time_us" and duration and on_progress and value.isdigit():
                on_progress(100 * int(value) / 1e6 / duration, speed)
        code = process.wait()
        errors.seek(0)
        return code, errors.read()[-600:]


def prepare_video(source_path, dest_path, output_width, output_height, on_progress=None, light_above_mb=None):
    """
    Prépare une vidéo pour l'affichage et génère sa vignette.
    Les vidéos lourdes (au-delà de `light_above_mb` Mo ; 0 : jamais) sont encodées en version allégée : 720p,
    30 images/s au plus, réglages économes en mémoire. Elles restent affichées en plein écran.
    """
    from utils import hardware_profile
    config = load_config()
    always_light = light_above_mb is None and hardware_profile.value(config, "videos_always_light")  # petits Pi : 720p
    if light_above_mb is None:
        light_above_mb = hardware_profile.setting(config, "video_light_above_mb")
    try:
        light_above_mb = float(light_above_mb)
    except (TypeError, ValueError):
        light_above_mb = LIGHT_VIDEO_DEFAULT_MB
    size_mb = os.path.getsize(source_path) / (1024 * 1024)
    light = always_light or (light_above_mb > 0 and size_mb >= light_above_mb)
    pi_model = get_pi_model()
    if light:
        output_width, output_height = _even(output_width * 2 / 3), _even(output_height * 2 / 3)
        print(f"[Video Prep] Vidéo lourde ({size_mb:.0f} Mo) : encodage allégé en {output_width}x{output_height}")
    # Encodage logiciel : moins de fils (et de mémoire) sur les petits Raspberry Pi et pour les vidéos lourdes
    software = ['-c:v', 'libx264', '-preset', 'superfast' if light else 'veryfast', '-crf', '26' if light else '23',
                '-profile:v', 'high', '-level', '4.0']
    if light or (pi_model and pi_model <= 3):
        software += ['-threads', '2', '-x264-params', 'rc-lookahead=10:ref=2']
    try:
        # --- MODIFICATION SIGALOU 29/01/2026 (2) ---
        # Logique d'encodage améliorée pour Pi 4/5 et meilleure gestion des erreurs.
        encoder = 'libx264'
        encoder_params = software[2:]
        bitrate = '4M' if light else '8M'
        try:
            result = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True, check=True, timeout=20)
            available_encoders = result.stdout
            
            # Priorité à l'encodeur matériel moderne v4l2m2m pour tous les modèles de Raspberry Pi (3, 4, 5)
            if pi_model and 'h264_v4l2m2m' in available_encoders:
                encoder = 'h264_v4l2m2m'
                encoder_params = ['-b:v', bitrate]
                print(f"[Video Prep] Raspberry Pi {pi_model} détecté. Utilisation de l'encodeur matériel : h264_v4l2m2m")
            elif pi_model and 'h264_omx' in available_encoders:
                encoder = 'h264_omx'
                encoder_params = ['-b:v', bitrate]
                print(f"[Video Prep] Raspberry Pi {pi_model} détecté. Utilisation de l'encodeur matériel legacy : h264_omx")
            else:
                print("[Video Prep] Aucun encodeur matériel trouvé, utilisation de l'encodeur logiciel : libx264")
        except Exception as e:
            print(f"[Video Prep] Avertissement : Impossible de détecter les encodeurs ({e}). Utilisation de l'encodeur logiciel par défaut.")
        
        # Encoder dans un fichier temporaire, hors des dossiers lus par le diaporama, puis le renommer une fois terminé :
        # une conversion interrompue (redémarrage, coupure) ne laisse jamais de vidéo tronquée considérée comme prête.
        tmp_dir = Path(dest_path).parent.parent.parent / ".prep_tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / f"{Path(dest_path).parent.name}_{Path(dest_path).name}"

        command = [
            'ffmpeg', '-i', source_path, '-vf', f"scale='min({output_width},iw)':'min({output_height},ih)':force_original_aspect_ratio=decrease,pad={output_width}:{output_height}:(ow-iw)/2:(oh-ih)/2",
            *(['-fpsmax', '30'] if light else []),
            '-c:v', encoder, *encoder_params,
            '-pix_fmt', 'yuv420p',  # Ajout pour une meilleure compatibilité
            '-c:a', 'aac', '-b:a', '128k',
            '-y', str(tmp_path)
        ]
        
        # Priorité basse : le diaporama reste fluide et le Raspberry Pi évite les pics de consommation
        if shutil.which("nice"):
            command = ["nice", "-n", "15", *command]
        duration = video_duration(source_path)
        report = (lambda percent, speed: on_progress(percent, f"{encoder}{' · ' + speed if speed else ''}")) if on_progress else None
        code, errors = run_ffmpeg(command, duration, report)

        if code != 0 and encoder != 'libx264':
            # L'encodeur matériel refuse certaines vidéos (ex. HEVC de téléphone sur Pi 3) : nouvel essai en logiciel
            print(f"[Video Prep] Encodeur matériel {encoder} en échec, nouvel essai avec libx264 (plus lent)")
            tmp_path.unlink(missing_ok=True)
            index = command.index('-c:v')
            command = command[:index] + software + command[index + 2 + len(encoder_params):]
            encoder = 'libx264'
            code, errors = run_ffmpeg(command, duration, report)

        if code != 0:
            tmp_path.unlink(missing_ok=True)
            raise Exception(f"ffmpeg a échoué avec le code {code}. Erreur: {errors.strip()}")
        os.replace(tmp_path, dest_path)
    
    except Exception as video_e:
        raise Exception(f"Erreur lors du traitement de la vidéo '{os.path.basename(source_path)}': {video_e}")
    
    # Generate thumbnail
    try:
        dest_path_obj = Path(dest_path)
        thumbnail_path = dest_path_obj.with_name(f"{dest_path_obj.stem}_thumbnail.jpg")
        thumb_command = [
            'ffmpeg', '-i', source_path, '-ss', '00:00:01.000', '-vframes', '1', '-q:v', '2', str(thumbnail_path), '-y'
        ]
        subprocess.run(thumb_command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as thumb_e:
        print(f"[Vignette] Avertissement: Impossible de créer la vignette pour {os.path.basename(source_path)}: {thumb_e}")

# --- Un média à la fois : imports, bouton « Préparer » de l'inventaire ---

PHOTO_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.heic', '.heif')
PREPARE_LOCK = threading.RLock()  # deux préparations en même temps satureraient un Raspberry Pi
ERRORS_FILE = Path("cache") / "prepare_errors.json"
_errors_lock = threading.Lock()


def is_media(filename):
    return filename.lower().endswith(PHOTO_EXTENSIONS + VIDEO_EXTENSIONS) and not filename.startswith(".")


def is_video(filename):
    return filename.lower().endswith(VIDEO_EXTENSIONS)


def prepared_name(filename):
    return os.path.splitext(filename)[0] + (".mp4" if is_video(filename) else ".jpg")


def preparation_state(prepared_dir, filename, width, height):
    """« ok » (prêt), « missing » (pas préparé), « empty » (fichier vide ou coupé) ou « stale » (autre taille d'écran)."""
    prep_path = Path(prepared_dir) / prepared_name(filename)
    try:
        if not prep_path.is_file():
            return "missing"
        if prep_path.stat().st_size == 0:
            return "empty"
        if not is_video(filename):
            with Image.open(prep_path) as prepared:
                if prepared.size != (width, height):
                    return "stale"
    except Exception:
        return "empty"
    return "ok"


def preparation_errors():
    try:
        return json.loads(ERRORS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _record_error(source_type, filename, error):
    key = f"{source_type}/{filename}"
    with _errors_lock:
        errors = preparation_errors()
        if error:
            errors[key] = {"error": str(error)[:400], "at": time.strftime("%Y-%m-%d %H:%M")}
        elif key not in errors:
            return
        else:
            errors.pop(key)
        try:
            ERRORS_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp = ERRORS_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(errors, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, ERRORS_FILE)
        except OSError:
            pass


def _load_user_texts():
    if USER_TEXT_MAP_CACHE_FILE.exists():
        try:
            with open(USER_TEXT_MAP_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            print(f"Avertissement: Impossible de charger le fichier de textes utilisateur {USER_TEXT_MAP_CACHE_FILE}")
    return {}


def prepare_media(source_type, filename, width, height, description_map=None, user_text_map=None, index=None, total=None):
    """
    Prépare un média de la source (photo ou vidéo). Retourne (type, aperçu). L'avancement est visible dans les
    détails de l'import ; un échec est noté pour l'inventaire des médias (et retiré quand le média passe).
    """
    from utils import import_progress
    description_map = description_map or {}
    user_text_map = _load_user_texts() if user_text_map is None else user_text_map
    src_path = os.path.join("static", "photos", source_type, filename)
    prepared_dir = Path("static") / "prepared" / source_type
    prepared_dir.mkdir(parents=True, exist_ok=True)
    base_name = os.path.splitext(filename)[0]
    video = is_video(filename)
    try:
        size = os.path.getsize(src_path)
    except OSError:
        size = None
    from utils import busy
    with PREPARE_LOCK, busy.working(f"préparation de {source_type}/{filename}"):
        import_progress.work_started(source_type, filename, "video" if video else "photo", size, index, total,
                                     step="encodage" if video else "photo")
        try:
            if video:
                progress = lambda percent, info: import_progress.work_progress(source_type, percent, speed=info)
                prepare_video(src_path, str(prepared_dir / f"{base_name}.mp4"), width, height, on_progress=progress)
                result = ("vidéo", f"{base_name}_thumbnail.jpg")
            else:
                dest_filename = f"{base_name}.jpg"
                # Modification Sigalou 25/01/2026 - Priorité au texte saisi, puis à la description Immich
                caption = user_text_map.get(f"{source_type}/{dest_filename}")
                if caption is None:
                    immich_data = description_map.get(filename)
                    if immich_data and isinstance(immich_data, dict):
                        caption = immich_data.get("description")
                    elif isinstance(immich_data, str):
                        caption = immich_data  # Backward compatibility
                prepare_photo(src_path, str(prepared_dir / dest_filename), width, height, source_type=source_type, caption=caption)
                result = ("photo", dest_filename)
        except Exception as e:
            import_progress.work_done(source_type, filename, ok=False, error=str(e))
            _record_error(source_type, filename, e)
            raise
        import_progress.work_done(source_type, filename, ok=True)
        _record_error(source_type, filename, None)
        return result


def media_inventory(source_type, width, height):
    """Médias d'une source et leur état de préparation (du plus récent au plus ancien)."""
    source_dir = Path("static") / "photos" / source_type
    prepared_dir = Path("static") / "prepared" / source_type
    errors = preparation_errors()
    from utils import night_work
    config = load_config()
    waits_night = not night_work.heavy_allowed(config)
    items = []
    from utils import motion_photos
    for entry in os.scandir(source_dir) if source_dir.is_dir() else []:
        if not entry.is_file() or not is_media(entry.name) or motion_photos.is_live_photo_video(entry.path):
            continue
        stat = entry.stat()
        state = preparation_state(prepared_dir, entry.name, width, height)
        error = errors.get(f"{source_type}/{entry.name}")
        items.append({"name": entry.name, "kind": "video" if is_video(entry.name) else "photo", "size": stat.st_size,
                      "modified": int(stat.st_mtime), "state": state, "prepared": prepared_name(entry.name),
                      "error": error["error"] if error and state != "ok" else None,
                      "night": state != "ok" and waits_night and night_work.is_heavy(entry.path, config)})
    return sorted(items, key=lambda i: -i["modified"])


def prepare_all_photos_with_progress(screen_width=None, screen_height=None, source_type="unknown", description_map=None):
    """Prépare les photos et retourne des objets structurés pour le suivi."""
    if description_map is None:
        description_map = {}
    # Ce fil de préparation passe après le diaporama et l'interface (Linux : priorité par fil d'exécution)
    try:
        import threading
        os.setpriority(os.PRIO_PROCESS, threading.get_native_id(), 10)
    except (AttributeError, OSError, PermissionError):
        pass
    
    # Charger les textes saisis par l'utilisateur
    user_text_map = _load_user_texts()
    
    actual_output_width = screen_width if screen_width is not None else DEFAULT_OUTPUT_WIDTH
    actual_output_height = screen_height if screen_height is not None else DEFAULT_OUTPUT_HEIGHT
    
    SOURCE_DIR_FOR_PREP = Path("static") / "photos" / source_type
    PREPARED_SOURCE_DIR = Path("static") / "prepared" / source_type
    
    if not SOURCE_DIR_FOR_PREP.is_dir():
        yield yield_and_log("error", f"Le dossier source '{SOURCE_DIR_FOR_PREP}' n'existe pas.")
        return
    
    PREPARED_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Smart synchronization logic
    from utils import motion_photos
    source_files = {f: os.path.splitext(f)[0] for f in os.listdir(SOURCE_DIR_FOR_PREP)
                    if is_media(f) and not motion_photos.is_live_photo_video(SOURCE_DIR_FOR_PREP / f)}  # Live Photo : vidéo de la photo
    for f in os.listdir(SOURCE_DIR_FOR_PREP):  # préparée autrefois comme une vidéo à part : retirée du diaporama
        if motion_photos.is_live_photo_video(SOURCE_DIR_FOR_PREP / f):
            stem = os.path.splitext(f)[0]
            for old in (PREPARED_SOURCE_DIR / f"{stem}.mp4", PREPARED_SOURCE_DIR / f"{stem}_thumbnail.jpg"):
                old.unlink(missing_ok=True)
    source_basenames = set(source_files.values())
    
    # Déjà préparés : fichier présent, non vide, à la taille de l'écran (sinon : changement d'orientation, à refaire)
    prepared_basenames = {basename for filename, basename in source_files.items()
                          if preparation_state(PREPARED_SOURCE_DIR, filename, actual_output_width, actual_output_height) == "ok"}

    # Récupérer tous les basenames actuellement présents sur le disque dans prepared/
    all_prepared_basenames_on_disk = set()
    if PREPARED_SOURCE_DIR.exists():
        for f in PREPARED_SOURCE_DIR.iterdir():
            if f.is_file():
                base = re.sub(r'(_polaroid|_postcard|_thumbnail|_animation)$', '', f.stem)
                all_prepared_basenames_on_disk.add(base)
    
    # Delete obsolete media (except for smartphone source)
    basenames_to_delete = set()
    if source_type != "smartphone":
        basenames_to_delete = all_prepared_basenames_on_disk - source_basenames
    
    if basenames_to_delete:
        yield yield_and_log(
            "progress",
            f"Suppression de {len(basenames_to_delete)} médias obsolètes...",
            stage="CLEANING",
            percent=25
        )
        
        for basename in basenames_to_delete:
            for file_to_delete in PREPARED_SOURCE_DIR.glob(f"{basename}*"):
                try:
                    if file_to_delete.is_file():
                        file_to_delete.unlink()
                except OSError as e:
                    yield yield_and_log("warning", f"Impossible de supprimer {file_to_delete.name} : {e}")
            
            backup_dir = PREPARED_SOURCE_DIR.parent.parent / '.backups' / source_type
            if backup_dir.exists():
                for backup_file_to_delete in backup_dir.glob(f"{basename}*"):
                    if backup_file_to_delete.is_file():
                        backup_file_to_delete.unlink()
    
    # Determine files to prepare (new ones)
    basenames_to_prepare = source_basenames - prepared_basenames
    files_to_prepare = [f for f, basename in source_files.items() if basename in basenames_to_prepare]
    # Les petits médias d'abord (photos, courtes vidéos) : ils arrivent vite sur le cadre, les gros vidéos à la fin
    files_to_prepare.sort(key=lambda f: (os.path.getsize(SOURCE_DIR_FOR_PREP / f) if (SOURCE_DIR_FOR_PREP / f).exists() else 0, f))
    # Grosses vidéos : la nuit seulement (diaporama éteint), pour ne pas saturer le Raspberry Pi pendant l'affichage
    from utils import night_work
    config_now = load_config()
    if not night_work.heavy_allowed(config_now):
        later = [f for f in files_to_prepare if night_work.is_heavy(SOURCE_DIR_FOR_PREP / f, config_now)]
        if later:
            files_to_prepare = [f for f in files_to_prepare if f not in later]
            yield yield_and_log("info", f"{len(later)} grosse(s) vidéo(s) préparée(s) cette nuit, quand le cadre sera éteint.")
    total = len(files_to_prepare)
    
    if total == 0:
        yield yield_and_log("info", "Aucune nouvelle photo à préparer. Le dossier est à jour.")
        yield yield_and_log(
            "done",
            "Aucune nouvelle photo à préparer.",
            stage="PREPARING_COMPLETE",
            percent=100
        )
        return
    
    yield yield_and_log(
        "stats",
        f"Début de la préparation de {total} nouvelles photos...",
        stage="PREPARING_START",
        percent=22,
        extra={"total": total}
    )
    
    for i, filename in enumerate(files_to_prepare, start=1):
        # Check for cancellation
        if CANCEL_FLAG.exists():
            yield yield_and_log("warning", "Préparation annulée par l'utilisateur.")
            return
        
        try:
            message_type, current_preview = prepare_media(source_type, filename, actual_output_width, actual_output_height,
                                                          description_map, user_text_map, index=i, total=total)
            
            if i == 1:
                percent = 25  # Modif Sigalou, Début boucle après cleaning 21%
            else:
                percent = 25 + int(((i - 1) / total) * 75)  # Modif Sigalou 25 à 100%
            
            yield yield_and_log(
                "progress",
                f"Nouveau média préparé ({message_type}) : {filename} ({i}/{total})",
                stage="PREPARING_PHOTO",
                percent=percent,
                extra={"current": i, "total": total, "current_photo_path": current_preview}
            )
        
        except Exception as e:
            yield yield_and_log("warning", f"Erreur lors de la préparation de {filename}: {e}",
                                extra={"current": i, "total": total})
    
    yield yield_and_log(
        "done",
        "Préparation des nouvelles photos terminée.",
        stage="PREPARING_COMPLETE",
        percent=100
    )

def prepare_all_photos(status_callback=None):
    """Version originale avec callback pour compatibilité"""
    for update in prepare_all_photos_with_progress():
        message = update.get("message", str(update))
        if status_callback:
            status_callback(message)
        else:
            print(message)

if __name__ == "__main__":
    print("Test de préparation des photos...")
    prepare_all_photos()
    print("Terminé !")