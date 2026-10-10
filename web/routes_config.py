"""Page de configuration principale (affichage et enregistrement des réglages)."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from utils.compositions import FORMATS as COMPOSITION_FORMATS

_restart_timer = {"timer": None}
AUTOSAVE_RESTART_DELAY = 4  # secondes après la dernière modification


def schedule_slideshow_restart():
    """Relance le diaporama quelques secondes après la dernière modification (regroupe les changements)."""
    if _restart_timer["timer"]:
        _restart_timer["timer"].cancel()
    _restart_timer["timer"] = threading.Timer(AUTOSAVE_RESTART_DELAY, restart_slideshow_process)
    _restart_timer["timer"].daemon = True
    _restart_timer["timer"].start()
from web.core import _


# --- Configuration & gestion diaporama ---

@app.route('/configure', methods=['GET', 'POST'])
@login_required
def configure():
    # --- DEBUG: Vérifier les fichiers en attente au chargement de la page ---
    try:
        if PENDING_UPLOADS_DIR.exists():
            pending_files = [f.name for f in PENDING_UPLOADS_DIR.iterdir() if f.is_file() and not f.name.startswith('.')]
            logger.info(f"🔳 {len(pending_files)} photo(s) des invités en attente dans {PENDING_UPLOADS_DIR}: {pending_files}")
        else:
            logger.warning(f"🔳️ Le dossier {PENDING_UPLOADS_DIR} n'existe pas encore.")
    except Exception as e:
        logger.error(f"🔳️ Erreur lors du listage des fichiers en attente : {e}")

    config = load_config()
    saved_secrets = {key: config.get(key) for key in SECRET_CONFIG_KEYS}
    invitations = load_invitations()

    # Récupérer la liste des photos en attente pour le template
    pending_photos_list = []
    if PENDING_UPLOADS_DIR.exists():
        pending_photos_list = sorted(
            [f.name for f in PENDING_UPLOADS_DIR.iterdir() if f.is_file() and not f.name.startswith('.')],
            key=lambda p: os.path.getmtime(PENDING_UPLOADS_DIR / p),
            reverse=True
        )

    if request.method == 'POST':
        # Gérer le champ 'source' qui correspond à 'photo_source' dans le config
        if 'source' in request.form:
            config['photo_source'] = request.form.get('source')

        # --- NOUVEAU: Gérer la limite de photos pour Immich ---
        if 'max_photos_to_download_immich' in request.form:
            try:
                # S'assurer que le dictionnaire imbriqué existe
                if 'max_photos_to_download' not in config or not isinstance(config['max_photos_to_download'], dict):
                    config['max_photos_to_download'] = {}
                
                value = request.form.get('max_photos_to_download_immich')
                
                # On stocke un entier. 0, -1 ou vide signifie "illimité" pour le script de téléchargement.
                if value is None or value.strip() in ("", "0", "-1"):
                    config['max_photos_to_download']['immich'] = 0
                else:
                    config['max_photos_to_download']['immich'] = int(value)
            except (ValueError, TypeError):
                flash(_("La valeur pour la limite de photos Immich est invalide. La valeur précédente est conservée."), "warning")

        for key in [
            'immich_url', 'immich_token', 'album_name',
            'display_duration', 
            'active_start_weekday', 'active_end_weekday',
            'active_start_weekend', 'active_end_weekend',
            'screen_height_percent', 'clock_font_size', 'clock_color',
            'clock_format', 'clock_offset_x', 'clock_offset_y',
            'clock_background_color',
            'clock_outline_color', 'clock_font_path', 'clock_position', 'guest_qr_position', 'compositions_every',
            'display_width', 'display_height', # Ajout des nouvelles clés
            'transition_enabled', # Added transition_enabled
            'transition_type', 'home_assistant_token',
            'transition_duration', # Added transition_duration
            'transition_fps', # Added transition_fps
            'pan_zoom_factor', 'favorite_boost_factor',
            'immich_update_interval_hours', 'date_format', 
            'weather_api_key', 'weather_city', 'weather_units', 'weather_update_interval_minutes', 'anniversary_boost_factor',
            'smart_plug_on_url', 'smart_plug_off_url', 'smart_plug_on_delay', 'smart_plug_status_url',
            'smb_host', 'smb_share', 'smb_path', 'smb_user', 'smb_password', 'video_audio_output', 'video_audio_volume', 'telegram_boost_duration_days',
            'telegram_boost_factor', 'screen_orientation',
            'smb_update_interval_hours', 'gdrive_update_interval_minutes', 'gdrive_backend', 'gdrive_rclone_remote'
            # New fields
            , 'wifi_ssid', 'wifi_password', 'info_display_duration', 'telegram_bot_token',
            'telegram_authorized_users', 'voice_control_language',
            'voice_control_engine', 'skip_initial_auto_import',
            'tide_latitude', 'tide_longitude', 'stormglass_api_key', 'tide_offset_x', 'tide_offset_y', 'notification_sound_volume'
            , 'button_pin',
            'timezone'
        ]:
            if key in request.form:
                value = request.form.get(key)
                if key == 'compositions_every' and not (value or "").strip():
                    continue  # champ vidé pendant la saisie : 0 a un sens (compositions enchaînées), on attend un nombre
                # Gérer les champs numériques
                if key in ['display_duration', 'compositions_every', 'clock_offset_x', 'clock_offset_y', 'clock_font_size', 'weather_update_interval_minutes', 'immich_update_interval_hours', 'smb_update_interval_hours', 'gdrive_update_interval_minutes', 'display_width', 'display_height', 'info_display_duration', 'tide_offset_x', 'tide_offset_y', 'video_audio_volume', 'favorite_boost_factor', 'telegram_boost_duration_days', 'telegram_boost_factor', 'button_pin', 'smart_plug_on_delay', 'anniversary_boost_factor']: # Integer fields
                    try:
                        config[key] = int(value)
                    except (ValueError, TypeError):
                        config[key] = 0 # Mettre une valeur par défaut en cas d'erreur
                elif key in ['pan_zoom_factor']: # Float fields
                    try:
                        config[key] = float(value)
                    except (ValueError, TypeError): # type: ignore
                        config[key] = 1.0 # Default to no zoom
                elif key in ['transition_duration']: # Float fields
                    try:
                        config[key] = float(value)
                    except (ValueError, TypeError):
                        config[key] = 0.0 # Default to no transition
                else: # Gérer les champs texte
                    config[key] = value
        
        # Appliquer le fuseau horaire au système si modifié
        if 'timezone' in request.form:
            new_tz = request.form.get('timezone')
            if new_tz and new_tz != config.get('timezone', 'Europe/Paris'):
                try:
                    subprocess.run(['sudo', '-n', 'timedatectl', 'set-timezone', new_tz], check=True)
                    logger.info(f"📅 Fuseau horaire système mis à jour : {new_tz}")
                except Exception as e:
                    logger.error(f"❌ Erreur lors du réglage du fuseau horaire : {e}")

        # Traiter les clés de métadonnées (Style et Positionnement)
        # Champs texte / select
        for key in ['photo_date_format', 'country_flag_size', 'photo_location_format', 'photo_metadata_color', 'photo_metadata_outline_color', 'photo_metadata_font_path', 'photo_metadata_position', 'photo_metadata_background_color', 'country_flag_position']:
            if key in request.form:
                config[key] = request.form.get(key)
        
        # Champs numériques (int) pour les métadonnées
        for key in ['photo_metadata_font_size', 'photo_metadata_offset_x', 'photo_metadata_offset_y', 'country_flag_offset_x', 'country_flag_offset_y']:
            if key in request.form:
                try:
                    config[key] = int(request.form.get(key))
                except (ValueError, TypeError):
                    config[key] = 0

        # Champs numériques (float) pour les métadonnées
        if 'country_flag_opacity' in request.form:
            try:
                config['country_flag_opacity'] = float(request.form.get('country_flag_opacity'))
            except (ValueError, TypeError):
                config['country_flag_opacity'] = 1.0
        
        # Priorité à la résolution soumise manuellement dans le formulaire, sinon détection auto
        form_width = request.form.get('display_width')
        form_height = request.form.get('display_height')
        if form_width and form_height:
            try:
                config['display_width'] = int(form_width)
                config['display_height'] = int(form_height)
            except (ValueError, TypeError):
                detected_width, detected_height = get_screen_resolution()
                config['display_width'] = detected_width
                config['display_height'] = detected_height
        else:
            detected_width, detected_height = get_screen_resolution()
            config['display_width'] = detected_width
            config['display_height'] = detected_height

        # --- Gestion de l'orientation ---
        # Si l'utilisateur force une orientation, on s'assure que width/height correspondent
        target_orientation = config.get('screen_orientation', 'landscape')
        if target_orientation == 'portrait':
            # Si on est en portrait mais que la largeur est plus grande que la hauteur, on inverse
            if config['display_width'] > config['display_height']:
                config['display_width'], config['display_height'] = config['display_height'], config['display_width']
                logger.info(f"Orientation Portrait forcée : dimensions inversées à {config['display_width']}x{config['display_height']}")
        else: # landscape
            # Si on est en paysage mais que la hauteur est plus grande que la largeur, on inverse
            if config['display_height'] > config['display_width']:
                config['display_width'], config['display_height'] = config['display_height'], config['display_width']
                logger.info(f"Orientation Paysage forcée : dimensions inversées à {config['display_width']}x{config['display_height']}")

        logger.info(f"Résolution d'écran configurée : {config['display_width']}x{config['display_height']}. Sauvegarde dans la configuration.")
        # Gérer la clé display_sources (checkboxes)
        # request.form.getlist() retourne une liste vide si aucune checkbox avec ce nom n'est cochée.
        config['display_sources'] = request.form.getlist('display_sources')
        config["pan_zoom_enabled"] = 'pan_zoom_enabled' in request.form # New checkbox handling
        config["button_enabled"] = 'button_enabled' in request.form
        config["smart_plug_enabled"] = 'smart_plug_enabled' in request.form
        config["cec_enabled"] = 'cec_enabled' in request.form
        config["transition_enabled"] = 'transition_enabled' in request.form # New checkbox handling
        config["clock_background_enabled"] = 'clock_background_enabled' in request.form
        config["slideshow_video_enabled"] = 'slideshow_video_enabled' in request.form
        config["video_audio_enabled"] = 'video_audio_enabled' in request.form
        config["video_hwdec_enabled"] = 'video_hwdec_enabled' in request.form

        config["telegram_boost_enabled"] = 'telegram_boost_enabled' in request.form
        config["anniversary_boost_enabled"] = 'anniversary_boost_enabled' in request.form
        config["memories_banner"] = 'memories_banner' in request.form
        config["memories_composition"] = 'memories_composition' in request.form
        config["display_telegram_notification_overlay"] = "display_telegram_notification_overlay" in request.form
        # Traitement des checkboxes
        config["show_clock"] = 'show_clock' in request.form
        config["show_guest_qr"] = 'show_guest_qr' in request.form
        config["guest_messages_enabled"] = 'guest_messages_enabled' in request.form
        config["compositions_include_messages"] = 'compositions_include_messages' in request.form
        if 'compositions_form' in request.form:  # on enregistre les formats décochés : un nouveau format sera actif par défaut
            checked = set(request.form.getlist('compositions_styles'))
            config["compositions_disabled"] = [k for k in COMPOSITION_FORMATS if k not in checked]
            config.pop("compositions_styles", None)
            config["compositions_seasonal"] = 'compositions_seasonal' in request.form
            config["compositions_full_photos"] = 'compositions_full_photos' in request.form
            config["unique_enabled"] = 'unique' in checked
            config["compositions_enabled"] = True  # les formats utilisés sont ceux cochés
        config["immich_auto_update"] = 'immich_auto_update' in request.form
        config["random_content_in_album"] = "random_content_in_album" in request.form
        config["smb_auto_update"] = 'smb_auto_update' in request.form
        config["gdrive_auto_update"] = 'gdrive_auto_update' in request.form
        config["gdrive_recursive"] = 'gdrive_recursive' in request.form
        config["gdrive_trash_after_import"] = 'gdrive_trash_after_import' in request.form
        config["hide_duplicates"] = 'hide_duplicates' in request.form
        # Dossiers Google Drive sélectionnés (valeurs "id|chemin"), liés à la méthode de connexion utilisée
        gdrive_backend = resolve_backend_name({"gdrive_backend": request.form.get('gdrive_backend', config.get('gdrive_backend', 'auto'))})
        config["gdrive_folders"] = [
            {"id": v.split('|', 1)[0], "name": v.split('|', 1)[1] if '|' in v else v, "backend": gdrive_backend}
            for v in request.form.getlist('gdrive_folders')
        ]
        gdrive_key = request.form.get('gdrive_service_account_json', '').strip()
        if gdrive_key and is_admin():
            try:
                save_service_account_key(parse_service_account_key(gdrive_key))
            except ValueError as e:
                flash(_("Clé Google Drive non enregistrée : %(error)s", error=str(e)), "error")

        config["telegram_bot_enabled"] = 'telegram_bot_enabled' in request.form # 'telegram_enabled' is removed
        config["show_date"] = 'show_date' in request.form
        config["show_weather"] = 'show_weather' in request.form
        config["show_tides"] = 'show_tides' in request.form
        # Metadata checkboxes
        config["show_photo_date"] = 'show_photo_date' in request.form
        config["show_photo_location"] = 'show_photo_location' in request.form
        config["geocode_enabled"] = 'geocode_enabled' in request.form
        config["show_country_flag"] = 'show_country_flag' in request.form
        config["photo_metadata_background_enabled"] = 'photo_metadata_background_enabled' in request.form
        # La gestion de l'activation/désactivation du contrôle vocal se fait maintenant via une API dédiée
        # mais il faut aussi sauvegarder son état ici pour la persistance au redémarrage.
        config['voice_control_enabled'] = 'voice_control_enabled' in request.form
        # pour éviter les conflits avec le bouton "Enregistrer".
        if 'porcupine_access_key' in request.form:
            config['porcupine_access_key'] = request.form['porcupine_access_key']
        if 'voice_control_device_index' in request.form:
            config['voice_control_device_index'] = request.form['voice_control_device_index']

        if not is_admin():
            # Les comptes non administrateurs ne voient pas les secrets et ne peuvent pas les modifier
            config.update(saved_secrets)
        save_config(config)
        if request.headers.get("X-Autosave"):
            # Enregistrement automatique : le diaporama est relancé une seule fois après une série de modifications
            schedule_slideshow_restart()
            return jsonify({"success": True, "message": _("Enregistré")})
        restart_slideshow_process() # Redémarre uniquement le processus du diaporama
        flash(_("Configuration enregistrée. Le diaporama a été relancé pour appliquer les changements."), "success")
        return redirect(url_for('configure'))

    slideshow_running = any(
        'local_slideshow.py' in (p.info['cmdline'] or []) for p in psutil.process_iter(attrs=['cmdline'])
    )

    # Test de la connexion Wi-Fi au chargement de la page
    wifi_status = "Inconnu"
    try:
        # Ceci est une vérification très basique, vous pouvez l'améliorer
        # en vérifiant l'interface wlan0 ou en pingant une adresse externe.
        # Pour l'instant, nous allons juste vérifier si les champs sont remplis.
        if config.get("wifi_ssid"):
            wifi_status = "Configuré (état non vérifié)"
        else:
            wifi_status = "Non configuré"
    except Exception as e:
        wifi_status = f"Erreur de vérification : {e}"

    prepared_media_by_source = get_prepared_photos_by_source()

    # --- NOUVEAU: Créer une liste plate des favoris pour le nouvel onglet ---
    favorite_photos = []
    for source, media_list in prepared_media_by_source.items():
        for media in media_list:
            if media.get('is_favorite'):
                favorite_photos.append(media)

    if not is_admin():
        config = {**config, **{key: '' for key in SECRET_CONFIG_KEYS}}

    return render_template(
        'configure.html.jinja',
        config=config,
        users=user_manager.list_users() if is_admin() else [],
        main_admin_username=load_credentials().get('username', 'admin'),
        prepared_photos_by_source=prepared_media_by_source, # Le template utilise ce nom de variable
        favorite_photos=favorite_photos, # Nouvelle variable pour l'onglet des favoris
        slideshow_running=slideshow_running,
        gdrive_service_email=get_service_account_email(),
        gdrive_rclone_remotes=list_rclone_remotes(),
        invitations=invitations,
        pending_photos=pending_photos_list
    )
