"""Photos des invités : page d'envoi publique, validation, invitations Telegram."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
import io
from flask import send_file
from utils import messages_manager, rate_limit
from web.core import _


@app.route('/api/telegram/invitations/<code>/revoke', methods=['POST'])
@login_required
def revoke_telegram_invitation(code):
    """Révoque l'accès d'un utilisateur en dissociant son ID de l'invitation."""
    invitations = load_invitations()
    if code not in invitations:
        return jsonify({"success": False, "message": "Invitation non trouvée."}), 404

    # Récupérer le nom de l'utilisateur avant de le supprimer pour le message de confirmation
    guest_name = invitations[code].get('used_by_user_name', 'Utilisateur inconnu')

    # Révoquer l'accès en remettant les champs 'used_by' à null
    invitations[code]['used_by_user_id'] = None
    invitations[code]['used_by_user_name'] = None
    invitations[code]['used_at'] = None

    # --- IMPORTANT ---
    # L'invitation redevient "utilisable" mais conserve sa date d'expiration d'origine.
    # Si vous souhaitez que la révocation soit définitive, vous pouvez supprimer l'invitation :
    # del invitations[code]
    # Ou la marquer comme révoquée :
    # invitations[code]['status'] = 'revoked'
    # Pour l'instant, nous la rendons simplement réutilisable.

    save_invitations(invitations)
    
    flash(_("L'accès pour l'invité '%(name)s' a été révoqué.", name=guest_name), "success")
    return jsonify({"success": True, "message": "Accès révoqué."})


@app.route('/api/telegram/bot_info')
@login_required
def get_telegram_bot_info():
    """Récupère le nom d'utilisateur du bot Telegram configuré."""
    config = load_config()
    token = config.get("telegram_bot_token")

    if not token:
        return jsonify({"success": False, "message": "Le token du bot Telegram n'est pas configuré."})

    url = f"https://api.telegram.org/bot{token}/getMe"

    try:
        response = requests.get(url, timeout=10)
        response_data = response.json()

        if response.status_code == 200 and response_data.get("ok"):
            bot_username = response_data.get("result", {}).get("username")
            if bot_username:
                return jsonify({"success": True, "username": bot_username})
            else:
                return jsonify({"success": False, "message": "Le bot n'a pas de nom d'utilisateur ou le token est incorrect."})
        else:
            error_description = response_data.get('description', 'Réponse invalide de Telegram.')
            return jsonify({"success": False, "message": f"Échec de la récupération des infos du bot : {error_description}"})
    except requests.exceptions.RequestException as e:
        return jsonify({"success": False, "message": f"Erreur de connexion à l'API Telegram : {e}"})


# --- Routes principales ---

@app.route('/upload', methods=['GET'])
def upload_page():
    """Affiche la page publique pour envoyer des photos."""
    return render_template('upload.html.jinja', guest_messages_enabled=load_config().get("guest_messages_enabled", True))


@app.route('/handle_upload', methods=['POST'])
def handle_upload():
    """Gère la réception des fichiers depuis la page publique."""
    if 'photos' not in request.files:
        flash(_("Aucun fichier sélectionné."), "error")
        return redirect(url_for('upload_page'))

    files = request.files.getlist('photos')
    if not files or files[0].filename == '':
        flash(_("Aucun fichier sélectionné."), "error")
        return redirect(url_for('upload_page'))

    PENDING_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    
    count = 0
    for file in files:
        if file:
            # Sécuriser le nom du fichier
            filename = secure_filename(file.filename)
            # Gérer les collisions de noms en ajoutant un timestamp et une chaîne aléatoire
            base, ext = os.path.splitext(filename)
            unique_suffix = f"{int(time.time())}_{secrets.token_hex(2)}"
            final_path = PENDING_UPLOADS_DIR / f"{base}_{unique_suffix}{ext}"
            file.save(final_path)
            logger.info(f"[Upload] Nouveau fichier reçu de l'invité et en attente : {final_path.name}")
            count += 1

    flash(_('%(count)s photo(s) envoyée(s) pour validation avec succès !', count=count), "success")
    return redirect(url_for('upload_page'))


@app.route('/api/get_pending_photos')
@login_required
def get_pending_photos():
    """Retourne la liste des photos en attente de validation."""
    try:
        # S'assurer que le dossier existe pour éviter les erreurs.
        if not PENDING_UPLOADS_DIR.exists():
            PENDING_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

        logger.debug(f"Listing pending photos in: {PENDING_UPLOADS_DIR}")

        # Lister les fichiers dans le dossier des uploads en attente.
        files_with_mtime = []
        for f in PENDING_UPLOADS_DIR.iterdir():
            if f.is_file() and not f.name.startswith('.'): # Ignorer les fichiers cachés
                try:
                    files_with_mtime.append((f.name, f.stat().st_mtime))
                except OSError as e:
                    logger.debug(f"Error reading file {f.name}: {e}")

        # Trier par date de modification (le plus récent en premier)
        files_with_mtime.sort(key=lambda x: x[1], reverse=True)
        pending_files = [f[0] for f in files_with_mtime]
        
        logger.debug(f"Found {len(pending_files)} pending photos.")

        # Retourner une réponse structurée et ajouter des en-têtes anti-cache.
        response = jsonify({"success": True, "photos": pending_files})
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    except Exception as e:
        logger.info(f"[ERROR] get_pending_photos failed: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/manage_pending_photo', methods=['POST'])
@login_required
def manage_pending_photo():
    """Approuve ou rejette une photo en attente."""
    data = request.get_json()
    filename = data.get('filename')
    action = data.get('action')

    if not filename or not action in ['approve', 'reject']:
        return jsonify({"success": False, "message": "Données invalides."}), 400

    pending_path = PENDING_UPLOADS_DIR / secure_filename(filename)

    if not pending_path.is_file():
        return jsonify({"success": False, "message": "Fichier non trouvé."}), 404

    if action == 'reject':
        try:
            pending_path.unlink()
            return jsonify({"success": True, "message": _("Photo rejetée.")})
        except Exception as e:
            return jsonify({"success": False, "message": f"Erreur: {e}"}), 500

    if action == 'approve':
        # Processus d'approbation rendu plus robuste :
        # 1. Copier la photo vers le dossier de transit (au lieu de la déplacer).
        # 2. Lancer la préparation.
        # 3. Si la préparation réussit, supprimer la photo du dossier d'attente.
        # Utiliser un dossier spécifique 'invités' pour éviter de mélanger ou supprimer d'autres photos
        target_source = "invités"
        source_dir = BASE_DIR / "static" / "photos" / target_source
        source_dir.mkdir(parents=True, exist_ok=True)

        # Copier la photo pour la traiter
        shutil.copy(str(pending_path), str(source_dir / pending_path.name))

        # Lancer la préparation
        config = load_config()
        screen_width, screen_height = config.get("display_width", 1920), config.get("display_height", 1080)
        try:
            preparation_successful = False
            # Utiliser la fonction importée correcte et la source 'guests'
            for update in prepare_all_photos_with_progress(screen_width, screen_height, source_type=target_source):
                # On vérifie si la préparation s'est terminée avec succès en lisant le flux d'événements
                if update.get("type") == "done":
                    preparation_successful = True
            
            if preparation_successful:
                pending_path.unlink() # Supprimer l'original seulement si tout s'est bien passé

                # --- NOUVEAU: Activer automatiquement la source 'invites' si elle ne l'est pas ---
                # Cela garantit que la photo validée sera bien diffusée par le diaporama.
                current_sources = config.get('display_sources', [])
                if 'invités' not in current_sources:
                    current_sources.append('invités')
                    config['display_sources'] = current_sources
                    save_config(config)

                # Redémarrer le diaporama pour inclure la nouvelle photo immédiatement
                if is_slideshow_running():
                    restart_slideshow_for_update()

                return jsonify({"success": True, "message": _("Photo approuvée et préparée. Le diaporama a été mis à jour.")})
            else:
                return jsonify({"success": False, "message": _("La préparation de la photo a échoué. La photo reste en attente.")}), 500
        except Exception as e:
            return jsonify({"success": False, "message": f"Erreur lors de la préparation: {e}"}), 500

    return jsonify({"success": False, "message": _("Action inconnue.")}), 400


@app.route('/debug/pending')
@admin_required
def debug_pending():
    """Route de diagnostic pour voir les fichiers bruts."""
    if not PENDING_UPLOADS_DIR.exists():
        return f"Le dossier {PENDING_UPLOADS_DIR} n'existe pas."
    files = [f.name for f in PENDING_UPLOADS_DIR.iterdir()]
    return f"Fichiers dans le dossier d'attente : {files}"


@app.route('/api/telegram/invitations', methods=['GET', 'POST'])
@login_required
def manage_telegram_invitations():
    if request.method == 'GET':
        invitations = load_invitations()
        # Filtrer pour ne garder que les invitations valides et non expirées
        active_invitations = {
            code: data for code, data in invitations.items()
            if datetime.fromisoformat(data['expires_at']) > datetime.now()
        }
        return jsonify(list(active_invitations.values()))

    if request.method == 'POST':
        data = request.get_json()
        guest_name = data.get('name')
        duration_days = int(data.get('duration', 7))

        if not guest_name:
            return jsonify({"success": False, "message": "Le nom de l'invité est requis."}), 400

        invitations = load_invitations()
        code = secrets.token_urlsafe(6) # Génère un code court et sécurisé
        
        invitations[code] = {
            "code": code,
            "guest_name": guest_name,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=duration_days)).isoformat(),
            "used_by_user_id": None
        }
        save_invitations(invitations)
        return jsonify({"success": True, "message": "Invitation créée.", "invitation": invitations[code]})


@app.route('/api/telegram/invitations/<code>', methods=['DELETE'])
@login_required
def delete_telegram_invitation(code):
    invitations = load_invitations()
    if code in invitations:
        del invitations[code]
        save_invitations(invitations)
        return jsonify({"success": True, "message": "Invitation supprimée."})
    else:
        return jsonify({"success": False, "message": "Invitation non trouvée."}), 404


# --- Messages écrits par les invités (sans compte), affichés directement ---

GUEST_MESSAGES_PER_HOUR = 5     # par appareil
GUEST_MESSAGES_PER_HOUR_ALL = 20  # tous appareils confondus (si l'adresse de l'appareil est inconnue)


def _guest_key():
    from utils.login_throttle import client_ip
    import ipaddress
    ip = client_ip(request)
    if ip and not ipaddress.ip_address(ip).is_loopback:
        return ip, GUEST_MESSAGES_PER_HOUR
    return "tous", GUEST_MESSAGES_PER_HOUR_ALL  # derrière un proxy mal configuré, tous les appareils ont la même adresse


def _guest_messages_disabled():
    if not load_config().get("guest_messages_enabled", True):
        return jsonify({"success": False, "message": _("Les messages des invités sont désactivés.")}), 403
    return None


@app.route('/upload/message/preview', methods=['POST'])
def guest_message_preview():
    disabled = _guest_messages_disabled()
    if disabled:
        return disabled
    key, _limit = _guest_key()
    if not rate_limit.allow(("aperçu", key), 60, 3600):
        return jsonify({"success": False, "message": _("Trop d'aperçus, réessayez plus tard.")}), 429
    data = request.get_json(silent=True) or {}
    config = load_config()
    try:
        image = messages_manager.preview(data.get("title"), data.get("body"), data.get("signature"), data.get("style"),
                                         int(config.get("display_width", 1920)), int(config.get("display_height", 1080)))
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=75)
    buffer.seek(0)
    return send_file(buffer, mimetype="image/jpeg")


@app.route('/upload/message', methods=['POST'])
def guest_message_publish():
    disabled = _guest_messages_disabled()
    if disabled:
        return disabled
    data = request.get_json(silent=True) or {}
    key, limit = _guest_key()
    if not rate_limit.allow(("message", key), limit, 3600):
        return jsonify({"success": False, "message": _("Vous avez déjà envoyé plusieurs messages : réessayez dans une heure.")}), 429
    config = load_config()
    name = (data.get("signature") or "").strip()
    try:
        message = messages_manager.create_message(
            data.get("title"), data.get("body"), name, data.get("style"), data.get("expires"),
            f"{_('Invité')}{' : ' + name if name else ''}",
            int(config.get("display_width", 1920)), int(config.get("display_height", 1080)), guest=True)
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    if messages_manager.SOURCE_NAME not in config.get("display_sources", []):
        config = dict(config)
        config["display_sources"] = config.get("display_sources", []) + [messages_manager.SOURCE_NAME]
        save_config(config)
    logger.info(f"[Messages] Message invité {message['id']} publié ({message['author']}, jusqu'au {message['expires']})")
    if is_slideshow_running():
        restart_slideshow_for_update()
    return jsonify({"success": True, "message": _("Merci ! Votre message va s'afficher sur le cadre (jusqu'au %(date)s).", date=message["expires"])})
