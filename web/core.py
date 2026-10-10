"""
Cœur de l'application web : création de l'application Flask, journalisation, sécurité,
constantes et fonctions utilitaires partagées par les routes et les workers.
"""
from flask import Flask, render_template, request, redirect, url_for, session, flash, stream_with_context, Response, jsonify, send_from_directory


import os


import json


import sys


import re


from flask_babel import Babel, _


import subprocess


import psutil


import glob


import time


import requests


import threading


import logging


from logging.handlers import RotatingFileHandler


import asyncio


import collections


import shutil


from datetime import datetime, timedelta


from werkzeug.utils import secure_filename


from pathlib import Path


from werkzeug.security import check_password_hash


import secrets


import signal


import traceback


from utils.download_album import download_and_extract_album


from utils.auth import login_required, admin_required, is_admin, login_or_internal_required # type: ignore




from utils.security import load_secret_key, ensure_internal_token, csrf_violation, is_internal_request


from utils import user_manager


from utils.slideshow_manager import is_slideshow_running, start_slideshow, stop_slideshow, restart_slideshow_process, restart_slideshow_for_update


from utils.config_manager import load_config, save_config


from utils.playlist_manager import load_playlists, save_playlists


from utils.auth_manager import change_password


from utils.network_manager import get_interface_status, set_interface_state


from utils.wifi_manager import set_wifi_config # Import the new utility


from utils.display_manager import get_display_output_name, set_display_power


from utils.prepare_all_photos import prepare_all_photos_with_progress


from utils.import_usb_photos import import_usb_photos  # Déplacé dans utils


from utils.metadata_utils import get_photo_metadata # Import get_photo_metadata


from utils.import_samba import import_samba_photos


from utils.import_gdrive import import_gdrive_photos, remove_local_media as remove_local_gdrive_media, list_folders as list_gdrive_folders, list_rclone_remotes, resolve_backend_name, parse_service_account_key, save_service_account_key, get_service_account_email


from utils.image_filters import apply_filter_to_image, add_text_to_polaroid, add_text_to_image, create_polaroid_effect


from utils.voice_control_manager import start_voice_control, stop_voice_control, is_voice_control_running


from utils.telegram_bot import PimmichBot


import secrets


import smbclient


from smbprotocol.exceptions import SMBException


APP_INSTANCE_ID = secrets.token_hex(8)


# ============================================================
# Configuration du logging avec émojis
# ============================================================
# Chargement config
config = load_config()


# Créer le dossier de logs
LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"


LOGS_DIR.mkdir(exist_ok=True)


class StripAnsiFormatter(logging.Formatter):
    """Formatter qui retire les codes ANSI (couleurs) des logs."""
    ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*m')
    
    def format(self, record):
        formatted = super().format(record)
        return self.ANSI_ESCAPE.sub('', formatted)


class EmojiFormatter(StripAnsiFormatter):
    """Formatter personnalisé avec émojis selon le niveau, sans codes ANSI."""
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


class CleanWerkzeugFormatter(EmojiFormatter):
    """Formatter spécial pour Werkzeug qui nettoie les logs HTTP."""
    
    def format(self, record):
        # Si c'est un log Werkzeug avec le format HTTP standard
        if record.name == 'werkzeug' and ' - - [' in record.getMessage():
            message = record.getMessage()
            match = re.search(r'"([^"]+)"\s+(\d+)\s+(.*)$', message)
            if match:
                record.msg = f'🌐 "{match.group(1)}" {match.group(2)}'
                record.args = ()
                emoji = self.EMOJI_MAP.get(record.levelname, "")
                record.emoji = emoji
                return StripAnsiFormatter.format(self, record)
        
        return super().format(record)


# >>> NOUVEAU : récupérer le niveau depuis la config
level_name = config.get("level_log", "INFO")


level = getattr(logging, level_name.upper(), logging.INFO)


# Créer un logger racine pour toute l'application
root_logger = logging.getLogger()


root_logger.setLevel(level)


# Handler 1 : Fichier avec rotation (10 Mo max, 5 backups)
file_handler = RotatingFileHandler(
    LOGS_DIR / "pimmich.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8"
)


file_handler.setLevel(level)


file_formatter = CleanWerkzeugFormatter(
    '%(emoji)s🟨%(asctime)s %(message)s',
    datefmt='%d-%m %H:%M:%S'
)


file_handler.setFormatter(file_formatter)


# Handler 2 : Console (stdout/stderr) - pour la compatibilité avec start_pimmich.sh [Pourra etre supprimé dans quelques temps]
console_handler = logging.StreamHandler()


console_handler.setLevel(level)


console_formatter = CleanWerkzeugFormatter(
    '%(asctime)s %(emoji)s %(message)s',
    datefmt='%d-%m %H:%M:%S'
)


console_handler.setFormatter(console_formatter)


# Ajouter les handlers au logger racine
root_logger.addHandler(file_handler)


root_logger.addHandler(console_handler)


# Logger spécifique pour app.py
logger = logging.getLogger("pimmich.app")


# Configuration spécifique pour Werkzeug
werkzeug_logger = logging.getLogger('werkzeug')


werkzeug_logger.setLevel(logging.WARNING)


# ============================================================
# Création de l'application Flask
# ============================================================

# root_path : les templates, fichiers statiques et traductions sont à la racine du projet
app = Flask("app", root_path=str(Path(__file__).resolve().parent.parent))


# Fichier d'identification du compte administrateur principal (créé par setup.sh).
# PIMMICH_CREDENTIALS_PATH permet de le remplacer (tests automatisés).
CREDENTIALS_PATH = os.environ.get('PIMMICH_CREDENTIALS_PATH', '/boot/firmware/credentials.json')


# --- Clé secrète ---
# Jamais de clé par défaut connue : elle permettrait de fabriquer une session administrateur.
app.secret_key = load_secret_key(CREDENTIALS_PATH)


# Cookie de session non envoyé par les requêtes provenant d'autres sites (protection CSRF)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'


app.config['SESSION_COOKIE_HTTPONLY'] = True


# Jeton partagé avec les processus locaux (commande vocale, bouton physique)
ensure_internal_token()


# --- Limiter la taille des uploads ---
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # même limite que nginx (client_max_body_size)


def get_locale():
    # Vérifier si nous sommes dans un contexte de requête (HTTP)
    # Si appelé depuis un thread en arrière-plan (worker), on retourne la langue par défaut
    from flask import has_request_context
    if not has_request_context():
        return app.config.get('BABEL_DEFAULT_LOCALE', 'fr')

    # 1. Si un argument 'lang' est passé dans l'URL
    lang = request.args.get('lang')
    if lang and lang in app.config['LANGUAGES']:
        session['lang'] = lang
        return lang
    # 2. Si l'utilisateur a une langue définie dans sa session
    if 'lang' in session and session['lang'] in app.config['LANGUAGES']:
        return session['lang']
    # 3. Depuis l'en-tête 'Accept-Language' du navigateur
    return request.accept_languages.best_match(list(app.config['LANGUAGES'].keys()))


# --- Configuration de Babel (i18n) ---
app.config['LANGUAGES'] = {'fr': 'Français', 'en': 'English', 'es': 'Español', 'de': 'Deutsch', 'ja': '日本語'}


app.config['BABEL_DEFAULT_LOCALE'] = 'fr'


babel = Babel(app, locale_selector=get_locale)


# --- Fin de la configuration de Babel ---

@app.context_processor
def inject_locale():
    """Injecte la fonction get_locale dans le contexte des templates."""
    return dict(get_locale=get_locale)


@app.context_processor
def inject_instance_id():
    """Injecte l'ID d'instance pour le suivi du redémarrage."""
    return dict(APP_INSTANCE_ID=APP_INSTANCE_ID)


@app.context_processor
def inject_current_user():
    """Injecte le compte connecté et son rôle dans les templates."""
    return dict(current_username=session.get('username'), is_admin=is_admin())

@app.context_processor
def inject_disk_alert():
    """Alerte d'espace disque faible, affichée aux administrateurs."""
    if not session.get('logged_in') or not is_admin():
        return {}
    from utils.disk_monitor import disk_status
    try:
        status = disk_status(load_config())
    except OSError:
        return {}
    return dict(disk_alert=status if status["low"] else None)


# Réglages contenant des secrets : masqués et non modifiables pour les comptes non administrateurs
SECRET_CONFIG_KEYS = ['immich_token', 'smb_password', 'weather_api_key', 'stormglass_api_key', 'telegram_bot_token',
                      'telegram_authorized_users', 'porcupine_access_key', 'home_assistant_token', 'wifi_ssid', 'wifi_password']


@app.before_request
def protect_against_csrf():
    """Refuse les requêtes d'action envoyées depuis un autre site (CSRF)."""
    if csrf_violation(request):
        logger.warning(f"[Sécurité] Requête inter-site refusée : {request.method} {request.path} "
                       f"(Sec-Fetch-Site={request.headers.get('Sec-Fetch-Site')}, Origin={request.headers.get('Origin')}, Host={request.host!r})")
        return jsonify({"success": False, "message": "Requête refusée (origine non autorisée)."}), 403


@app.before_request
def refresh_user_role():
    """Applique immédiatement la suppression d'un compte ou le changement de son rôle."""
    username = session.get('username')
    if not session.get('logged_in') or not username or username == load_credentials().get('username'):
        return
    role = user_manager.get_role(username)
    if role is None:
        session.clear()
    else:
        session['role'] = role


# Chemins de base
BASE_DIR = Path(__file__).resolve().parent.parent


# Chemins de config
VIDEO_EXTENSIONS = ('.mp4', '.mov', '.avi', '.mkv')


PENDING_UPLOADS_DIR = BASE_DIR / "static" / "pending_uploads"


CONFIG_PATH = 'config/config.json'


FILTER_STATES_PATH = 'config/filter_states.json'


FAVORITES_PATH = 'config/favorites.json'


POLAROID_TEXTS_PATH = 'config/polaroid_texts.json'


TEXT_STATES_PATH = 'config/text_states.json'


INVITATIONS_PATH = 'config/invitations.json'


TELEGRAM_GUEST_USERS_PATH = 'config/telegram_guest_users.json'


NEW_POSTCARD_FLAG_PATH = 'cache/new_postcard.flag'


CUSTOM_PLAYLIST_FILE = "/tmp/pimmich_custom_playlist.json"


CURRENT_PHOTO_FILE = "/tmp/pimmich_current_photo.txt"


PREPARED_DIR = BASE_DIR / "static" / "prepared"


# Dictionnaire central pour les fichiers de log
LOG_FILES_MAP = {
    "app": {"path": "logs/pimmich.log", "name_key": "Pimmich (Serveur Web & Supervisor)"},
    "voice_control_stdout": {"path": "logs/voice_control_stdout.log", "name_key": "voice_control.py (Contrôle Vocal - Sortie Standard)"},
    "voice_control_stderr": {"path": "logs/voice_control_stderr.log", "name_key": "voice_control.py (Contrôle Vocal - Erreurs)"},
}


class WorkerStatus:
    def __init__(self):
        self.lock = threading.Lock()
        self.last_run = None
        self.next_run = None
        self.status_message = "Initialisation..."

    def update_status(self, last_run=None, next_run=None, message=None):
        with self.lock:
            if last_run:
                self.last_run = last_run.isoformat()
            if next_run:
                self.next_run = next_run.isoformat()
            if message:
                self.status_message = message

    def get_status(self):
        with self.lock:
            return {
                "last_run": self.last_run,
                "next_run": self.next_run,
                "status_message": self.status_message
            }


immich_status_manager = WorkerStatus()


samba_status_manager = WorkerStatus()


gdrive_status_manager = WorkerStatus()


telegram_status_manager = WorkerStatus()


# Historique pour le graphique de température CPU (conserve les 60 dernières mesures)
cpu_temp_history = collections.deque(maxlen=60)


# NOUVEAU: Historique pour le graphique d'utilisation CPU
cpu_usage_history = collections.deque(maxlen=60)


# NOUVEAU: Historique pour le graphique d'utilisation RAM
ram_usage_history = collections.deque(maxlen=60)


# NOUVEAU: Historique pour le graphique d'utilisation Disque
disk_usage_history = collections.deque(maxlen=60)


def get_screen_resolution():
    """
    Détecte la résolution de l'écran principal via swaymsg.
    Retourne (width, height) ou (1920, 1080) en cas d'erreur.
    """
    # Charger la configuration pour avoir une résolution de secours fiable
    config = load_config()
    default_width = int(config.get('display_width', 1920))
    default_height = int(config.get('display_height', 1080))
    try:
        # Assurer que SWAYSOCK est défini
        if "SWAYSOCK" not in os.environ:
            user_id = os.getuid()
            # Utiliser glob pour trouver le socket, car le nom peut varier
            sock_path_pattern = f"/run/user/{user_id}/sway-ipc.*"
            socks = glob.glob(sock_path_pattern)
            if socks:
                os.environ["SWAYSOCK"] = socks[0]
            else:
                logger.warning("SWAYSOCK non trouvé, utilisation de la résolution de secours depuis la config.")
                return default_width, default_height

        # Utiliser HDMI_OUTPUT du slideshow_manager pour cibler la bonne sortie
        # ou chercher la sortie active si HDMI_OUTPUT n'est pas suffisant.
        # Pour l'instant, on se base sur la sortie active.
        result = subprocess.run(['swaymsg', '-t', 'get_outputs'], capture_output=True, text=True, check=True, env=os.environ)
        outputs = json.loads(result.stdout)
        
        # --- MODIFICATION ---
        # On cherche la première sortie qui a un mode configuré, qu'elle soit active ou non.
        # C'est plus robuste car l'écran peut être désactivé (en veille).
        for output in outputs:
            if output.get('current_mode'):
                mode = output['current_mode']
                logger.info(f"Résolution détectée sur la sortie '{output.get('name')}': {mode['width']}x{mode['height']} (Active: {output.get('active', False)})")
                return mode['width'], mode['height']
        
        logger.info(f"😒 Aucune sortie avec un mode configuré trouvée (écran en veille ?), utilisation de la résolution de secours depuis la config.")
        return default_width, default_height
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError, IndexError) as e:
        logger.info(f"😒 Erreur lors de la détection de la résolution de l'écran : {e}. Utilisation de la résolution de secours depuis la config.")
        return default_width, default_height
    except Exception as e:
        logger.info(f"😒 Erreur inattendue lors de la détection de la résolution : {e}. Utilisation de la résolution de secours depuis la config.")
        return default_width, default_height


def get_photo_previews():
    photo_dir = BASE_DIR / "static" / "photos"
    return sorted([f.name for f in photo_dir.glob("*") if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".gif"]])


def load_credentials():
    try:
        with open(CREDENTIALS_PATH, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Pas de compte par défaut au mot de passe connu : setup.sh (utils/create_initial_user.py) crée ce fichier.
        logger.error(f"Fichier d'identification {CREDENTIALS_PATH} absent ou illisible : connexion admin impossible. "
                     f"Recréez-le avec : sudo venv/bin/python utils/create_initial_user.py --output {CREDENTIALS_PATH}")
        return {}


def check_credentials(username, password):
    credentials = load_credentials()
    stored_username = credentials.get("username")
    stored_hash = credentials.get("password_hash")

    if not stored_username or not stored_hash:
        # Handle legacy plaintext password for backward compatibility
        stored_password = credentials.get("password")
        if stored_password and username == stored_username and password == stored_password:
            print("AVERTISSEMENT: Le mot de passe est stocké en clair. Veuillez le changer pour le sécuriser.")
            return True
        return False

    return username == stored_username and check_password_hash(stored_hash, password)


def load_filter_states():
    """Charge les états des filtres depuis un fichier JSON."""
    if not os.path.exists(FILTER_STATES_PATH):
        return {}
    try:
        with open(FILTER_STATES_PATH, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_filter_states(states):
    """Sauvegarde les états des filtres dans un fichier JSON."""
    try:
        with open(FILTER_STATES_PATH, 'w') as f:
            json.dump(states, f, indent=4)
    except Exception as e:
        logger.info(f"Erreur lors de la sauvegarde des états de filtre : {e}")


def load_favorites():
    """Charge la liste des photos favorites depuis un fichier JSON."""
    if not os.path.exists(FAVORITES_PATH):
        return []
    try:
        with open(FAVORITES_PATH, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_favorites(favorites_list):
    """Sauvegarde la liste des photos favorites dans un fichier JSON."""
    try:
        with open(FAVORITES_PATH, 'w') as f:
            json.dump(favorites_list, f, indent=2)
    except Exception as e:
        logger.info(f"😒 Erreur lors de la sauvegarde des favoris : {e}")


def load_polaroid_texts():
    """Charge les textes des polaroids depuis un fichier JSON."""
    if not os.path.exists(POLAROID_TEXTS_PATH):
        return {}
    try:
        with open(POLAROID_TEXTS_PATH, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_polaroid_texts(texts_dict):
    """Sauvegarde les textes des polaroids dans un fichier JSON."""
    try:
        with open(POLAROID_TEXTS_PATH, 'w') as f:
            json.dump(texts_dict, f, indent=2)
    except Exception as e:
        logger.info(f"😒 Erreur lors de la sauvegarde des textes polaroid : {e}")


def load_text_states():
    """Charge les textes des photos depuis un fichier JSON."""
    if not os.path.exists(TEXT_STATES_PATH):
        return {}
    try:
        with open(TEXT_STATES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_text_states(states):
    """Sauvegarde les textes des photos dans un fichier JSON."""
    try:
        with open(TEXT_STATES_PATH, 'w', encoding='utf-8') as f:
            json.dump(states, f, indent=4)
    except IOError as e:
        logger.info(f"😒 Erreur lors de la sauvegarde des états de texte : {e}")


def load_telegram_guest_users():
    """Charge les utilisateurs invités de Telegram depuis un fichier JSON."""
    if not os.path.exists(TELEGRAM_GUEST_USERS_PATH):
        return {}
    try:
        with open(TELEGRAM_GUEST_USERS_PATH, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_telegram_guest_users(guest_users_dict):
    """Sauvegarde les utilisateurs invités de Telegram dans un fichier JSON."""
    try:
        with open(TELEGRAM_GUEST_USERS_PATH, 'w') as f:
            json.dump(guest_users_dict, f, indent=4)
    except Exception as e:
        logger.info(f"😒 Erreur lors de la sauvegarde des invités Telegram : {e}")


def add_telegram_guest_user(user_id, guest_name):
    """Ajoute un nouvel invité Telegram et sauvegarde le fichier."""
    guest_users = load_telegram_guest_users()
    guest_users[str(user_id)] = guest_name
    save_telegram_guest_users(guest_users)


def load_invitations():
    """Charge les invitations Telegram depuis un fichier JSON."""
    if not os.path.exists(INVITATIONS_PATH):
        return {}
    try:
        with open(INVITATIONS_PATH, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_invitations(invitations_dict):
    """Sauvegarde les invitations Telegram dans un fichier JSON."""
    try:
        with open(INVITATIONS_PATH, 'w') as f:
            json.dump(invitations_dict, f, indent=4)
    except Exception as e:
        logger.info(f"😒 Erreur lors de la sauvegarde des invitations : {e}")


def get_prepared_photos_by_source():
    """
    Récupère les médias préparés (photos et vidéos), organisés par leur source.
    Retourne un dictionnaire où les clés sont les noms des sources et les valeurs sont des listes de dictionnaires.
    Ex: {'immich': [{'path': 'immich/media.jpg', 'type': 'image', 'has_polaroid': True}, ...]}
    """
    # Charger la configuration pour obtenir les noms des invités
    config = load_config()
    guest_users = config.get('telegram_guest_users', {})

    base_prepared_dir = PREPARED_DIR
    media_by_source = {}
    filter_states = load_filter_states()
    favorites = load_favorites()
    polaroid_texts = load_polaroid_texts()
    text_states = load_text_states()
    
    # Charger la config pour le boost anniversaire
    app_config = load_config()
    anniversary_boost_enabled = app_config.get("anniversary_boost_enabled", False)
    if base_prepared_dir.exists():
        for source_dir in base_prepared_dir.iterdir():
            if source_dir.is_dir():
                source_name = source_dir.name
                
                # Lister tous les fichiers (images et vidéos)
                all_files_in_dir = list(source_dir.iterdir())
                all_filenames = {f.name for f in all_files_in_dir}
                
                # Identifier les médias de base (non-polaroid, non-vignette, non-postcard)
                base_media = sorted(
                    [f for f in all_files_in_dir if f.is_file() and not f.name.endswith(('_polaroid.jpg', '_thumbnail.jpg', '_postcard.jpg'))]
                )

                media_data_list = []
                for media_path_obj in base_media:
                    media_name = media_path_obj.name
                    media_relative_path = f"{source_name}/{media_name}"
                    media_type = 'video' if media_path_obj.suffix.lower() in VIDEO_EXTENSIONS else 'image'
                    
                    media_item = {
                        "path": media_relative_path,
                        "type": media_type,
                        "is_favorite": media_relative_path in favorites,
                        "is_anniversary": False # Default to False
                    }

                    # Vérifier si c'est une photo anniversaire
                    if anniversary_boost_enabled and media_type == 'image':
                        photo_metadata = get_photo_metadata(media_path_obj)
                        if photo_metadata:
                            date_priority = [
                                "subSecDateTimeOriginal", "dateTimeOriginal", "SubSecDateTimeOriginal", "DateTimeOriginal",
                                "subSecCreateDate", "createDate", "SubSecCreateDate", "CreateDate",
                                "subSecModifyDate", "modifyDate", "SubSecModifyDate",
                                "mediaCreateDate", "dateTimeCreated", "MediaCreateDate", "DateTimeCreated",
                                "fileModifiedAt", "fileCreatedAt"
                            ]
                            date_taken_str = next((photo_metadata.get(field) for field in date_priority if photo_metadata.get(field)), None)
                            
                            if date_taken_str:
                                try:
                                    photo_date = datetime.fromisoformat(date_taken_str.replace('Z', '+00:00'))
                                    if photo_date.month == datetime.now().month and photo_date.day == datetime.now().day:
                                        media_item["is_anniversary"] = True
                                except Exception as e:
                                    logger.debug(f"Erreur lors de la lecture de la date pour l'icône anniversaire: {e}")

                    # Les options de filtre ne s'appliquent qu'aux images
                    if media_type == 'image':
                        base_name = media_path_obj.stem
                        has_polaroid = f"{base_name}_polaroid.jpg" in all_filenames
                        has_postcard = f"{base_name}_postcard.jpg" in all_filenames
                        media_item["has_polaroid"] = has_polaroid
                        media_item["has_postcard"] = has_postcard
                        media_item["polaroid_text"] = polaroid_texts.get(media_relative_path, "")
                        media_item["text"] = text_states.get(media_relative_path, "")
                        media_item["active_filter"] = filter_states.get(media_relative_path, "none")
                    elif media_type == 'video':
                        # Chercher la vignette correspondante pour la vidéo
                        thumbnail_name = f"{media_path_obj.stem}_thumbnail.jpg"
                        if thumbnail_name in all_filenames:
                            media_item["thumbnail_path"] = f"{source_name}/{thumbnail_name}"
                    
                    media_data_list.append(media_item)
                
                if media_data_list:
                    media_by_source[source_name] = media_data_list
                    
    return media_by_source


def handle_new_telegram_photo(temp_photo_path_str, caption, user_name=None):
    """
    Fonction de rappel pour traiter une nouvelle photo reçue via Telegram.
    Cette fonction est synchrone et peut maintenant inclure le nom de l'expéditeur.
    """
    with app.app_context():
        logger.info(f"[Telegram] Traitement de la nouvelle photo : {temp_photo_path_str}")
        try:
            # Construire la légende finale en ajoutant le nom de l'expéditeur
            final_caption = caption
            if user_name:
                # Si une légende existe déjà, ajouter le nom avant. Sinon, utiliser juste le nom.
                if caption:
                    final_caption = f"De {user_name} : {caption}"
                else:
                    final_caption = f"De {user_name}"

            temp_photo_path = Path(temp_photo_path_str)
            
            # 1. Définir les chemins
            source_dir = BASE_DIR / "static" / "photos" / "telegram"
            prepared_dir = BASE_DIR / "static" / "prepared" / "telegram"
            source_dir.mkdir(parents=True, exist_ok=True)
            prepared_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = int(time.time())
            # Ajouter quelques caractères aléatoires pour éviter les collisions si plusieurs photos arrivent dans la même seconde
            new_filename_base = f"telegram_{timestamp}_{secrets.token_hex(4)}"
            
            # 2. Copier la photo temporaire vers le dossier source permanent
            source_photo_path = source_dir / f"{new_filename_base}.jpg"
            shutil.copy(temp_photo_path, source_photo_path)
            
            # 3. Préparer la photo
            from utils.prepare_all_photos import prepare_photo # Import local pour éviter dépendance circulaire
            prepared_photo_path = prepared_dir / f"{new_filename_base}.jpg"
            config = load_config()
            screen_width, screen_height = config.get("display_width", 1920), config.get("display_height", 1080)
            prepare_photo(str(source_photo_path), str(prepared_photo_path), screen_width, screen_height, source_type='telegram', caption=final_caption)
            
            # 4. Gérer la légende
            if final_caption:
                relative_path = f"telegram/{new_filename_base}.jpg"
                text_states = load_text_states()
                text_states[relative_path] = final_caption
                save_text_states(text_states)
                add_text_to_image(str(prepared_photo_path), final_caption)

            # Créer un fichier "drapeau" pour notifier le diaporama et y écrire le chemin de la nouvelle carte postale
            postcard_path = prepared_dir / f"{new_filename_base}_postcard.jpg"
            path_to_write = str(postcard_path) if postcard_path.exists() else str(prepared_photo_path)

            try:
                with open(NEW_POSTCARD_FLAG_PATH, 'w') as f:
                    f.write(path_to_write)
                logger.info(f"[Telegram] Fichier de notification sonore créé avec le chemin : {path_to_write}")
            except Exception as e:
                logger.info(f"[Telegram] ERREUR lors de la création du fichier de notification : {e}")

            logger.info(f"[Telegram] Photo {new_filename_base}.jpg traitée avec succès.")
        except Exception as e:
            error_message = f"[Telegram] ERREUR lors du traitement de la photo : {e}\n{traceback.format_exc()}"
            print(error_message)
            # Renvoyer l'exception pour que le bot puisse notifier l'utilisateur de l'échec.
            raise Exception(f"Le traitement de la photo a échoué côté serveur. {e}")
        finally:
            # Nettoyer le fichier temporaire créé par le bot
            if Path(temp_photo_path_str).exists():
                Path(temp_photo_path_str).unlink()


def validate_telegram_invitation(code, user_id, user_name):
    """Valide un code d'invitation, et si valide, ajoute l'utilisateur à la config."""
    invitations = load_invitations()
    
    if code not in invitations:
        return {"success": False, "message": _("Code d'invitation invalide.")}

    invitation = invitations[code]
    
    # Vérifier si le code est expiré
    if datetime.fromisoformat(invitation['expires_at']) < datetime.now():
        return {"success": False, "message": _("Ce code d'invitation a expiré.")}

    # Vérifier si le code a déjà été utilisé
    if invitation.get('used_by_user_id'):
        # Si c'est le même utilisateur qui réutilise le code, on l'autorise
        if invitation['used_by_user_id'] == user_id:
            return {"success": True, "message": _("Vous êtes déjà autorisé. Envoyez-moi une photo !")}
        else:
            return {"success": False, "message": _("Ce code d'invitation a déjà été utilisé.")}

    # Si le code est valide et non utilisé, on ajoute l'utilisateur à la liste des invités
    add_telegram_guest_user(user_id, invitation['guest_name'])

    # Marquer l'invitation comme utilisée
    invitation['used_by_user_id'] = user_id
    invitation['used_by_user_name'] = user_name
    invitation['used_at'] = datetime.now().isoformat()
    save_invitations(invitations)

    return {"success": True, "message": _("Félicitations %(name)s ! Vous pouvez maintenant envoyer des cartes postales au cadre.", name=invitation['guest_name'])}


def _send_slideshow_signal(sig):
    """Helper function to send a signal to the slideshow process."""
    if not is_slideshow_running():
        return jsonify({"success": False, "message": "Le diaporama n'est pas en cours."}), 404
    try:
        with open("/tmp/pimmich_slideshow.pid", "r") as f:
            pid = int(f.read())
        os.kill(pid, sig)
        return jsonify({"success": True})
    except (FileNotFoundError, ValueError, ProcessLookupError) as e:
        return jsonify({"success": False, "message": f"Impossible de communiquer avec le diaporama : {e}"}), 500


def get_wifi_status():
    """
    Récupère l'état de la connexion Wi-Fi de manière optimisée en un seul appel à nmcli.
    Cette fonction est plus robuste et rapide que de multiples appels à des commandes différentes.
    """
    interface = "wlan0" # On assume que wlan0 est l'interface Wi-Fi
    
    # Vérification rapide si l'interface Wi-Fi existe physiquement sur le système
    # pour éviter de lancer une commande nmcli lourde/bloquante en l'absence de Wi-Fi (ex: Pi 2)
    if not os.path.exists(f"/sys/class/net/{interface}"):
        return {"is_connected": False, "ssid": "N/A (Pas de carte Wi-Fi)", "ip_address": "N/A"}

    try:
        # Commande optimisée pour récupérer toutes les infos en une fois, de manière concise (-t)
        cmd = ['nmcli', '-t', '-f', 'GENERAL.STATE,GENERAL.CONNECTION,IP4.ADDRESS', 'dev', 'show', interface]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=5)
        
        output_map = {}
        for line in result.stdout.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                output_map[key] = value

        state_code_str = output_map.get('GENERAL.STATE', '0').split(' ')[0]
        state_code = int(state_code_str) if state_code_str.isdigit() else 0
        is_connected = (state_code == 100)
        
        if is_connected:
            ssid = output_map.get('GENERAL.CONNECTION', 'Inconnu')
            ip_address = output_map.get('IP4.ADDRESS[1]', 'N/A').split('/')[0]
            return {"is_connected": True, "ssid": ssid, "ip_address": ip_address}
        else:
            return {"is_connected": False, "ssid": "Non connecté", "ip_address": "N/A"}

    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired, IndexError, ValueError) as e:
        logger.info(f"Erreur lors de la récupération du statut Wi-Fi : {e}")
        return {"is_connected": False, "ssid": "Erreur", "ip_address": "N/A"}


def get_cpu_temperature():
    """
    Tente de récupérer la température du CPU en utilisant plusieurs méthodes.
    Retourne la température formatée ou "N/A" en cas d'échec.
    """
    # Méthode 1: vcgencmd (spécifique au Raspberry Pi)
    try:
        temp_output = subprocess.check_output(['vcgencmd', 'measure_temp']).decode('utf-8')
        match = re.search(r"temp=([\d\.]*)'C", temp_output)
        if match:
            return float(match.group(1))
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass  # Si la commande échoue, on passe à la méthode suivante

    # Méthode 2: sysfs thermal_zone0 (Linux générique)
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp_raw = int(f.read())
            return temp_raw / 1000.0
    except (FileNotFoundError, ValueError):
        pass # Si le fichier n'existe pas ou est invalide, on passe à la suite

    return None # Valeur par défaut si toutes les méthodes échouent
