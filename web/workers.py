"""Tâches de fond : planification du diaporama, mises à jour automatiques des sources, bot Telegram."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from utils import import_progress
from utils import messages_manager, disk_monitor, drive_backup
from web.core import _


# --- Worker de mise à jour automatique ---

_immich_first_run_skipped = False


_samba_first_run_skipped = False


_gdrive_first_run_skipped = False


def schedule_worker():
    """
    Thread en arrière-plan qui gère le démarrage et l'arrêt du diaporama
    en fonction des heures d'activité configurées.
    """
    logger.debug("📅️🔄 Démarrage du worker de planification du diaporama")
    from utils.slideshow_manager import desktop_mode
    if desktop_mode():
        logger.info("📅 Mode bureau Raspberry Pi OS : pas de planification du diaporama (administration seule).")
        return
    
    # --- Séquence de démarrage unique ---
    # Cette partie ne s'exécute qu'une seule fois au lancement de l'application.
    try:
        logger.info("📅 Séquence de démarrage initiale.")
        # Attendre que le système soit stable avant de manipuler l'affichage
        time.sleep(5)
        config = load_config()
        output_name = get_display_output_name()
        if output_name:
            width = config.get('display_width', 1920)
            height = config.get('display_height', 1080)
            logger.info(f"📅 Forçage de la résolution {width}x{height} sur l'écran '{output_name}' au démarrage.")
            try:
                # ⭐ NOUVEAU FIX : Forcer la résolution via swaymsg au démarrage
                subprocess.run(
                    ['swaymsg', 'output', output_name, 'mode', f'{width}x{height}'],
                    check=True,
                    timeout=10,
                    env=os.environ  # Important pour SWAYSOCK
                )
                time.sleep(2)  # Laisser le temps à l'écran de se stabiliser
                logger.info(f"📅 Résolution {width}x{height} appliquée avec succès sur {output_name}")
            except Exception as e:
                logger.error(f"❌ Échec du forçage de la résolution au démarrage : {e}")
        
        # Calcul des heures actives selon le jour (Semaine vs Weekend)
        now = datetime.now()
        is_weekend = now.weekday() >= 5 # 5=Samedi, 6=Dimanche
        
        if is_weekend:
            start_str = config.get("active_start_weekend", config.get("active_start", "07:00"))
            end_str = config.get("active_end_weekend", config.get("active_end", "23:00"))
        else:
            start_str = config.get("active_start_weekday", config.get("active_start", "07:00"))
            end_str = config.get("active_end_weekday", config.get("active_end", "22:00"))

        now_time = now.time()
        start_time = datetime.strptime(start_str, "%H:%M").time()
        end_time = datetime.strptime(end_str, "%H:%M").time()
        in_schedule_at_boot = (start_time <= end_time and start_time <= now_time <= end_time) or \
                              (start_time > end_time and (now_time >= start_time or now_time <= end_time))
        
        from utils import clock_sync
        if not clock_sync.trusted():  # démarrage sans Internet : l'heure peut dater du dernier arrêt
            logger.info("📅 Heure pas encore synchronisée (pas d'Internet ?) : le diaporama démarre quand même.")
            in_schedule_at_boot = True
        if in_schedule_at_boot:
            logger.info(f"📅 Entre {start_str} et {end_str} = Heures actives au démarrage, lancement du diaporama.")
            start_slideshow()
    except Exception as e:
        logger.error(f"❌ Erreur critique dans la séquence de démarrage : {e}", exc_info=True)

    last_schedule_state = None
    while True:
        try:
            config = load_config()
            
            now = datetime.now()
            is_weekend = now.weekday() >= 5
            
            if is_weekend:
                start_str = config.get("active_start_weekend", config.get("active_start", "07:00"))
                end_str = config.get("active_end_weekend", config.get("active_end", "23:00"))
            else:
                start_str = config.get("active_start_weekday", config.get("active_start", "07:00"))
                end_str = config.get("active_end_weekday", config.get("active_end", "22:00"))

            now_time = now.time()
            start_time = datetime.strptime(start_str, "%H:%M").time()
            end_time = datetime.strptime(end_str, "%H:%M").time()

            if start_time <= end_time:
                in_schedule = start_time <= now_time <= end_time
            else:
                in_schedule = now_time >= start_time or now_time <= end_time
            from utils import clock_sync
            if not clock_sync.trusted():
                in_schedule = True  # heure pas encore synchronisée : on affiche plutôt que de rester éteint par erreur

            # Réinitialiser l'override manuel si on change de plage horaire (ex: passage de nuit à jour)
            if last_schedule_state is not None and last_schedule_state != in_schedule:
                logger.info(f"📅 Changement de planning détecté, réinitialisation de l'override manuel.")
                config['manual_override'] = None
                save_config(config)
            
            last_schedule_state = in_schedule
            restart_after_imports()  # filet de sécurité : redémarrage reporté pendant un import terminé sans préparation
            manual_override = config.get('manual_override')
            slideshow_is_running = is_slideshow_running()

            from utils import night
            night_clock = night.clock_at_night(config)  # la nuit, le diaporama affiche une horloge au lieu de s'arrêter
            # Arrêt auto : uniquement si pas d'override "start"
            if not in_schedule and slideshow_is_running and manual_override != "start" and not night_clock:
                logger.info("📅 Heure inactive détectée et diaporama en cours. Arrêt...")
                stop_slideshow()
            # Démarrage auto : uniquement si pas d'override "stop"
            elif (in_schedule or night_clock) and not slideshow_is_running and manual_override != "stop":
                logger.info("📅 Heure active mais le diaporama est arrêté. Séquence de démarrage...")
                # 1. On s'assure que l'écran est allumé (via DPMS si pas de prise)
                set_display_power(on=True)
                # 2. On attend un court instant pour laisser l'environnement d'affichage se stabiliser
                time.sleep(5)
                
                # --- FIX: Forcer la résolution au réveil comme au démarrage ---
                output_name = get_display_output_name()
                if output_name:
                    # Mode de l'écran toujours en largeur × hauteur « paysage » (le pivotement est appliqué à part)
                    width = max(config.get('display_width', 1920), config.get('display_height', 1080))
                    height = min(config.get('display_width', 1920), config.get('display_height', 1080))
                    logger.info(f"📅 Forçage de la résolution {width}x{height} sur l'écran '{output_name}' au réveil.")
                    try:
                        subprocess.run(
                            ['swaymsg', 'output', output_name, 'mode', f'{width}x{height}'],
                            check=True, timeout=10, env=os.environ
                        )
                        time.sleep(2) # Laisser le temps à l'écran de se stabiliser
                    except Exception as e:
                        logger.error(f"❌ Échec du forçage de la résolution au réveil : {e}")

                # 3. On lance explicitement le diaporama
                start_slideshow()

        except Exception as e:
            logger.error(f"📅❌ Erreur dans le worker de planification : {e}", exc_info=True)

        # Attendre 60 secondes avant la prochaine vérification
        time.sleep(60)


def immich_update_worker():
    """
    Thread en arrière-plan qui vérifie et met à jour l'album Immich périodiquement.
    """
    logger.debug("🖼️🔄 Démarrage du worker de mise à jour automatique Immich")
    while True:
        config = load_config()
        is_enabled = config.get("immich_auto_update", False)
        interval_hours = config.get("immich_update_interval_hours", 24)
        skip_initial = config.get("skip_initial_auto_import", False) # New config option

        global _immich_first_run_skipped
        if not _immich_first_run_skipped and skip_initial:
            logger.debug("🖼️🔄 Import initial skipped as per configuration.")
            with app.app_context():
                immich_status_manager.update_status(message=_("Import initial ignoré."))
            _immich_first_run_skipped = True
            # Calculate next run and sleep, then continue to next iteration
            sleep_seconds = (interval_hours * 3600) if is_enabled else (15 * 60)
            next_run_time = datetime.now() + timedelta(seconds=sleep_seconds)
            immich_status_manager.update_status(next_run=next_run_time)
            if is_enabled:
                immich_status_manager.update_status(message="En attente...")
            time.sleep(sleep_seconds)
            continue # Skip the rest of this iteration
        
        if is_enabled:
            with app.app_context():
                status_msg = _("Mise à jour auto. activée. Intervalle : %(hours)sh.", hours=interval_hours)
                logger.info(f"🖼️🔄  {status_msg}")
                immich_status_manager.update_status(message=status_msg)
            
            try:
                with app.app_context():
                    immich_status_manager.update_status(message=_("Lancement du téléchargement..."))
                logger.info("🖼️🔄 Lancement du téléchargement et de la préparation...")
                
                # Étape 1: Téléchargement
                download_success = False
                description_map = {} # Initialiser un mappage vide
                for update in import_progress.tracked("immich", "download", download_and_extract_album(config)):
                    # NOUVEAU: Afficher les messages de progression du worker dans les logs pour le débogage
                    if update.get("message"):
                        logger.info(f"🖼️🔄  {update.get('message')}")

                    if update.get("type") == "error":
                        notify_sync_error("Immich", update.get("message", ""))
                        logger.error(f"🖼️🔄❌ Erreur lors du téléchargement : {update.get('message')}")
                        immich_status_manager.update_status(message=f"Erreur téléchargement: {update.get('message')}")
                    immich_status_manager.update_status(message=update.get('message', '')) # Update status with download message
                    if update.get("type") == "done":
                        download_success = True
                        description_map = update.get("description_map", {}) # Récupérer le mappage

                # Étape 2: Préparation et redémarrage du diaporama
                if download_success:
                    # Fusionner les descriptions d'Immich et celles de l'interface Pimmich
                    manual_captions = load_text_states()
                    final_description_map = description_map.copy()
                    # Les légendes manuelles (clés "source/fichier.jpg") écrasent celles d'Immich (clés "fichier.jpg")
                    for path, caption in manual_captions.items():
                        path_obj = Path(path)
                        if path_obj.parts and path_obj.parts[0] == "immich":
                            filename = path_obj.name
                            final_description_map[filename] = caption

                    with app.app_context():
                        immich_status_manager.update_status(message=_("Préparation des photos..."))
                    screen_width = config.get("display_width", 1920) # Utiliser la résolution configurée
                    screen_height = config.get("display_height", 1080) # Utiliser la résolution configurée
                    prep_successful = False
                    for update in import_progress.tracked("immich", "prepare", prepare_all_photos_with_progress(screen_width=screen_width, screen_height=screen_height, source_type="immich", description_map=final_description_map)):
                        immich_status_manager.update_status(message=update.get('message', '')) # Update status with preparation message
                        if update.get("type") == "error":
                            notify_sync_error("Immich", update.get("message", ""))
                            logger.error(f"🖼️🔄❌ Erreur lors de la préparation : {update.get('message')}")
                            immich_status_manager.update_status(message=f"Erreur préparation: {update.get('message')}")
                            break # Sortir de la boucle de préparation
                        if update.get("type") == "done":
                            prep_successful = True
                    
                    if prep_successful:
                        with app.app_context():
                            immich_status_manager.update_status(message=_("Mise à jour terminée. Redémarrage du diaporama..."))
                        print("🖼️🔄✅ Mise à jour terminée avec succès. Redémarrage du diaporama.")
                        if is_slideshow_running():
                            restart_slideshow_for_update()
                        with app.app_context():
                            immich_status_manager.update_status(last_run=datetime.now(), message=_("Dernière mise à jour réussie."))
                    else:
                        with app.app_context():
                            immich_status_manager.update_status(message=_("Mise à jour terminée avec avertissements/erreurs."))

            except Exception as e:
                logger.error(f"🖼️🔄❌ Erreur critique dans le worker : {e}", exc_info=True)
                immich_status_manager.update_status(message=f"Erreur critique : {e}")

        else:
            status_msg = _("Mise à jour automatique désactivée.")
            logger.info(f"🖼️🔄❌ {status_msg}")
            immich_status_manager.update_status(message=status_msg)
        
        # Attendre avant la prochaine vérification
        sleep_seconds = (interval_hours * 3600) if is_enabled else (15 * 60)
        next_run_time = datetime.now() + timedelta(seconds=sleep_seconds)
        immich_status_manager.update_status(next_run=next_run_time) # Update next_run regardless of enabled state
        if is_enabled: # Only set message to "En attente..." if it's enabled
            immich_status_manager.update_status(message="En attente...")
        time.sleep(sleep_seconds)


def samba_update_worker():
    """
    Thread en arrière-plan qui vérifie et met à jour le partage Samba périodiquement.
    """
    print("Démarrage du worker de mise à jour automatique Samba")
    while True:
        config = load_config()
        is_enabled = config.get("smb_auto_update", False)
        interval_hours = config.get("smb_update_interval_hours", 24)
        skip_initial = config.get("skip_initial_auto_import", False) # New config option

        global _samba_first_run_skipped
        if not _samba_first_run_skipped and skip_initial:
            print("[Auto-Update Samba] Import initial skipped as per configuration.")
            with app.app_context():
                samba_status_manager.update_status(message=_("Import initial ignoré."))
            _samba_first_run_skipped = True
            # Calculate next run and sleep, then continue to next iteration
            sleep_seconds = (interval_hours * 3600) if is_enabled else (15 * 60)
            next_run_time = datetime.now() + timedelta(seconds=sleep_seconds)
            samba_status_manager.update_status(next_run=next_run_time)
            if is_enabled:
                samba_status_manager.update_status(message="En attente...")
            time.sleep(sleep_seconds)
            continue # Skip the rest of this iteration
        
        if is_enabled:
            with app.app_context():
                status_msg = _("Mise à jour auto. activée. Intervalle : %(hours)sh.", hours=interval_hours)
                logger.info(f"[Auto-Update Samba] {status_msg}")
                samba_status_manager.update_status(message=status_msg)
            
            try:
                with app.app_context():
                    samba_status_manager.update_status(message=_("Lancement de l'import..."))
                print("[Auto-Update Samba] Lancement de l'import et de la préparation...")
                
                import_success = False
                for update in import_progress.tracked("samba", "download", import_samba_photos(config)):
                    if update.get("type") == "error":
                        notify_sync_error("Samba", update.get("message", ""))
                        logger.info(f"[Auto-Update Samba] Erreur lors de l'import : {update.get('message')}")
                        samba_status_manager.update_status(message=f"Erreur import: {update.get('message')}")
                    samba_status_manager.update_status(message=update.get('message', '')) # Update status with import message
                    if update.get("type") == "done":
                        import_success = True

                if import_success:
                    with app.app_context():
                        samba_status_manager.update_status(message=_("Préparation des photos..."))
                    # Charger les légendes manuelles pour Samba
                    manual_captions = load_text_states()
                    final_description_map = {}
                    for path, caption in manual_captions.items():
                        path_obj = Path(path)
                        if path_obj.parts and path_obj.parts[0] == "samba":
                            filename = path_obj.name
                            final_description_map[filename] = caption

                    screen_width = config.get("display_width", 1920) # Utiliser la résolution configurée
                    screen_height = config.get("display_height", 1080) # Utiliser la résolution configurée
                    prep_successful = False
                    for update in import_progress.tracked("samba", "prepare", prepare_all_photos_with_progress(screen_width, screen_height, "samba", description_map=final_description_map)):
                        samba_status_manager.update_status(message=update.get('message', '')) # Update status with preparation message
                        if update.get("type") == "error":
                            notify_sync_error("Samba", update.get("message", ""))
                            samba_status_manager.update_status(message=f"Erreur préparation: {update.get('message')}")
                            break
                        if update.get("type") == "done":
                            prep_successful = True
                    
                    if prep_successful:
                        with app.app_context():
                            samba_status_manager.update_status(message=_("Mise à jour terminée. Redémarrage du diaporama..."))
                        print("[Auto-Update Samba] Mise à jour terminée. Redémarrage du diaporama.")
                        if is_slideshow_running():
                            restart_slideshow_for_update()
                        with app.app_context():
                            samba_status_manager.update_status(last_run=datetime.now(), message=_("Dernière mise à jour réussie."))
                    else:
                        with app.app_context():
                            samba_status_manager.update_status(message=_("Mise à jour terminée avec avertissements/erreurs."))
            except Exception as e:
                logger.error(f"[Auto-Update Samba] Erreur critique dans le worker : {e}", exc_info=True)
                samba_status_manager.update_status(message=f"Erreur critique : {e}")
        else:
            with app.app_context():
                samba_status_manager.update_status(message=_("Mise à jour automatique Samba désactivée."))
        
        sleep_seconds = (interval_hours * 3600) if is_enabled else (15 * 60)
        next_run_time = datetime.now() + timedelta(seconds=sleep_seconds)
        samba_status_manager.update_status(next_run=next_run_time) # Update next_run regardless of enabled state
        if is_enabled: # Only set message to "En attente..." if it's enabled
            samba_status_manager.update_status(message="En attente...")
        time.sleep(sleep_seconds)


def gdrive_update_worker():
    """
    Thread en arrière-plan qui synchronise périodiquement les dossiers Google Drive sélectionnés.
    La préparation et le redémarrage du diaporama n'ont lieu que si quelque chose a changé.
    """
    print("Démarrage du worker de mise à jour automatique Google Drive")
    first_run = True
    while True:
        config = load_config()
        is_enabled = config.get("gdrive_auto_update", False)

        if first_run and config.get("skip_initial_auto_import", False):
            with app.app_context():
                gdrive_status_manager.update_status(message=_("Import initial ignoré."))
        elif is_enabled:
            try:
                with app.app_context():
                    gdrive_status_manager.update_status(message=_("Recherche de nouveautés..."))
                changes = None
                for update in import_progress.tracked("gdrive", "download", import_gdrive_photos(config)):
                    if update.get("type") == "error":
                        notify_sync_error("Google Drive", update.get("message", ""))
                        logger.info(f"[Auto-Update Google Drive] Erreur lors de l'import : {update.get('message')}")
                    gdrive_status_manager.update_status(message=update.get('message', ''))
                    if update.get("type") == "done":
                        changes = update.get("changes", 1)

                # Au premier passage, on prépare quand même pour rattraper un import interrompu
                if changes or (changes == 0 and first_run):
                    with app.app_context():
                        gdrive_status_manager.update_status(message=_("Préparation des photos..."))
                    # Charger les légendes manuelles pour Google Drive
                    description_map = {Path(path).name: caption for path, caption in load_text_states().items()
                                       if Path(path).parts and Path(path).parts[0] == "gdrive"}
                    screen_width = config.get("display_width", 1920)
                    screen_height = config.get("display_height", 1080)
                    prep_successful = False
                    for update in import_progress.tracked("gdrive", "prepare", prepare_all_photos_with_progress(screen_width, screen_height, "gdrive", description_map=description_map)):
                        gdrive_status_manager.update_status(message=update.get('message', ''))
                        if update.get("type") == "error":
                            notify_sync_error("Google Drive", update.get("message", ""))
                            break
                        if update.get("type") == "done":
                            prep_successful = True

                    with app.app_context():
                        if prep_successful:
                            if changes and is_slideshow_running():
                                restart_slideshow_for_update()
                            gdrive_status_manager.update_status(last_run=datetime.now(), message=_("Dernière mise à jour réussie."))
                        else:
                            gdrive_status_manager.update_status(message=_("Mise à jour terminée avec avertissements/erreurs."))
                elif changes == 0:
                    with app.app_context():
                        gdrive_status_manager.update_status(last_run=datetime.now(), message=_("Aucune nouveauté."))
            except Exception as e:
                logger.error(f"[Auto-Update Google Drive] Erreur critique dans le worker : {e}", exc_info=True)
                gdrive_status_manager.update_status(message=f"Erreur critique : {e}")
        else:
            with app.app_context():
                gdrive_status_manager.update_status(message=_("Mise à jour automatique Google Drive désactivée."))
        first_run = False

        # Attente jusqu'à la prochaine vérification, en relisant la config toutes les 30 s
        # pour prendre en compte immédiatement un changement d'intervalle ou une activation.
        cycle_start = datetime.now()
        while True:
            config = load_config()
            enabled_now = config.get("gdrive_auto_update", False)
            interval_minutes = max(1, int(config.get("gdrive_update_interval_minutes", 60) or 60))
            next_run = cycle_start + timedelta(minutes=interval_minutes)
            gdrive_status_manager.update_status(next_run=next_run if enabled_now else None)
            if enabled_now and not is_enabled:
                break  # Vient d'être activée : lancer tout de suite
            if enabled_now and datetime.now() >= next_run:
                break
            is_enabled = enabled_now
            time.sleep(30)


def telegram_bot_worker():
    """
    Thread en arrière-plan qui lance et maintient le bot Telegram actif.
    """
    print("Démarrage du worker du bot Telegram")
    while True: # Boucle pour relancer le bot en cas de crash
        config = load_config()
        is_enabled = config.get("telegram_bot_enabled", False)
        token = config.get("telegram_bot_token")
        users = config.get("telegram_authorized_users")
        # Charger les invités autorisés depuis leur propre fichier
        guest_users = load_telegram_guest_users()

        if is_enabled and token and users:
            try:
                # Créer et définir une nouvelle boucle d'événements pour ce thread.
                # C'est nécessaire car le bot Telegram est asynchrone et a besoin
                # d'une boucle pour fonctionner correctement en arrière-plan.
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                telegram_status_manager.update_status(message="Bot actif.")
                bot = PimmichBot(token, users, guest_users, handle_new_telegram_photo, validate_telegram_invitation)
                bot.run() # Cette fonction est bloquante (polling)
            except Exception as e:
                # Tentative de capture d'erreurs spécifiques pour un meilleur feedback
                error_str = str(e).lower()
                if 'invalid token' in error_str:
                    error_msg = "Erreur : Token du bot Telegram invalide."
                elif 'conflict' in error_str:
                    error_msg = "Erreur : Conflit, une autre instance du bot est peut-être déjà lancée."
                else:
                    error_msg = f"Erreur critique du bot : {str(e)[:100]}..."
                
                final_error_msg = f"{error_msg} Redémarrage dans 60s."
                logger.info(f"[Telegram Worker] {final_error_msg}")
                telegram_status_manager.update_status(message=error_msg) # On affiche le message concis dans l'UI
        else:
            telegram_status_manager.update_status(message="Bot désactivé ou non configuré.")
        time.sleep(60) # Attendre avant de vérifier à nouveau la config ou de relancer


def migrate_guest_folders():
    """Migre les anciens dossiers 'guests' et 'invites' vers 'invités'."""
    base_photos = BASE_DIR / "static" / "photos"
    base_prepared = BASE_DIR / "static" / "prepared"
    target_name = "invités"
    legacy_names = ["guests", "invites"]

    # Créer les dossiers cibles s'ils n'existent pas
    (base_photos / target_name).mkdir(parents=True, exist_ok=True)
    (base_prepared / target_name).mkdir(parents=True, exist_ok=True)

    for legacy in legacy_names:
        # Migration des photos sources
        legacy_photos_dir = base_photos / legacy
        if legacy_photos_dir.exists() and legacy_photos_dir.is_dir():
            logger.info(f"[Migration] Déplacement des photos de '{legacy}' vers '{target_name}'...")
            for item in legacy_photos_dir.iterdir():
                dest = base_photos / target_name / item.name
                if not dest.exists():
                    shutil.move(str(item), str(dest))
            # Supprimer le dossier source s'il est vide
            try:
                legacy_photos_dir.rmdir()
            except OSError:
                pass # Le dossier n'est pas vide, on le laisse

        # Migration des photos préparées
        legacy_prepared_dir = base_prepared / legacy
        if legacy_prepared_dir.exists() and legacy_prepared_dir.is_dir():
            logger.info(f"[Migration] Déplacement des fichiers préparés de '{legacy}' vers '{target_name}'...")
            for item in legacy_prepared_dir.iterdir():
                dest = base_prepared / target_name / item.name
                if not dest.exists():
                    shutil.move(str(item), str(dest))
            try:
                legacy_prepared_dir.rmdir()
            except OSError:
                pass

    # Mise à jour de la configuration pour remplacer les anciennes sources par la nouvelle
    config = load_config()
    sources = config.get('display_sources', [])
    new_sources = set(sources)
    modified = False
    for legacy in legacy_names:
        if legacy in new_sources:
            new_sources.remove(legacy)
            new_sources.add(target_name)
            modified = True
    
    if modified:
        config['display_sources'] = list(new_sources)
        save_config(config)
        logger.info(f"[Migration] Configuration mise à jour : sources {sources} -> {list(new_sources)}")


MAINTENANCE_INTERVAL = 10 * 60  # secondes


def run_maintenance_once():
    """
    Tâches périodiques : messages expirés, images des messages à la taille de l'écran,
    espace disque (alerte et nettoyage optionnel) et sauvegarde automatique sur Google Drive.
    """
    config = load_config()
    refresh_slideshow = False

    if messages_manager.purge_expired():
        refresh_slideshow = True
    if messages_manager.ensure_images(int(config.get("display_width", 1920)), int(config.get("display_height", 1080))):
        refresh_slideshow = True

    status = disk_monitor.disk_status(config)
    if status["low"]:
        logger.warning(f"[Disque] Espace libre faible : {status['free_gb']} Go (seuil {status['threshold_gb']} Go)")
        if config.get("disk_auto_cleanup") and disk_monitor.free_space(config):
            refresh_slideshow = True

    if drive_backup.is_due(config):
        try:
            drive_backup.backup_now(config)
        except Exception:
            pass  # l'échec est enregistré dans l'état de la sauvegarde et affiché dans l'interface

    if refresh_slideshow and is_slideshow_running():
        restart_slideshow_for_update()


def maintenance_worker():
    print("Démarrage du worker de maintenance (messages, espace disque, sauvegarde)")
    while True:
        try:
            run_maintenance_once()
        except Exception as e:
            logger.error(f"[Maintenance] Erreur : {e}", exc_info=True)
        try:
            with app.app_context():
                notify_frame_problems()
        except Exception as e:
            logger.warning(f"[Notifications] {e}")
        time.sleep(MAINTENANCE_INTERVAL)


# --- Présence : accueil des membres de la famille qui rentrent à la maison ---

PRESENCE_WAKE_MINUTES = 30


def handle_arrival(device, config):
    """Un téléphone de la famille revient : réveil du cadre, mot d'accueil, playlist de la personne."""
    from utils import presence
    name = (device.get("name") or "").strip() or _("vous")
    logger.info(f"🏠 Présence : arrivée de {name}")
    try:
        state = presence.load_state()
        entry = state.setdefault(device["mac"].lower(), {})
        if entry.get("welcome_id"):  # un seul mot d'accueil par personne
            try:
                messages_manager.delete_message(entry["welcome_id"])
            except ValueError:
                pass
        tomorrow = (datetime.now() + timedelta(days=1)).date().isoformat()
        message = messages_manager.create_message("", _("Bienvenue à la maison, %(name)s !", name=name), "", "festif", tomorrow, "Pimmich",
                                                  config.get("display_width", 1920), config.get("display_height", 1080))
        entry["welcome_id"] = message["id"]
        presence.save_state(state)
    except Exception as e:
        logger.warning(f"🏠 Mot d'accueil impossible : {e}")
    if not is_slideshow_running():  # en dehors des heures : réveil pour un moment
        config = dict(load_config())
        config["manual_override"] = "start"
        config["presence_wake_until"] = time.time() + PRESENCE_WAKE_MINUTES * 60
        save_config(config)
        set_display_power(on=True)
        time.sleep(3)
        start_slideshow()
    if device.get("playlist"):
        try:
            from web.routes_slideshow import start_photo_playlist
            start_photo_playlist(device["playlist"])
        except Exception as e:
            logger.warning(f"🏠 Playlist de {name} non lancée : {e}")


def presence_worker():
    """Surveille toutes les 30 s les téléphones de la famille sur le Wi-Fi."""
    from utils import presence
    while True:
        try:
            config = load_config()
            devices = config.get("presence_devices") or []
            if config.get("presence_enabled") and devices:
                for device in presence.tick(devices):
                    with app.app_context():
                        handle_arrival(device, config)
            # Fin du réveil « arrivée » : le cadre reprend ses heures normales
            until = config.get("presence_wake_until")
            if until and time.time() > until:
                config = dict(load_config())
                config.pop("presence_wake_until", None)
                if config.get("manual_override") == "start" and not is_active_hours(config):
                    config["manual_override"] = None
                save_config(config)
        except Exception as e:
            logger.warning(f"🏠 Présence : {e}")
        time.sleep(30)



# --- Notifications sur le téléphone ---

def notify_sync_error(source, message):
    from utils import notify
    notify.send(load_config(), "sync", _("Problème de synchronisation"), f"{source} : {message}"[:300], key=f"sync:{source}", repeat_after=3600)


def notify_frame_problems():
    """Problèmes graves du cadre (alimentation, chaleur, disque...) : une alerte par problème et par jour."""
    from utils import health, notify
    config = load_config()
    if not notify.wants(config, "health"):
        return
    items = health.checks(dict(config, _active_hours=is_active_hours(config)), is_slideshow_running(), True)
    today = datetime.now().strftime("%Y-%m-%d")
    for item in items:
        if item.get("level") != "error":
            continue
        translate = _  # appel indirect : l'extracteur ne doit pas prendre les clés « title » / « detail » pour des textes
        title = translate(item["title"])
        notify.send(config, "health", title, translate(item["detail"], **(item.get("params") or {})), key=f"health:{item['title']}:{today}", repeat_after=24 * 3600)


def notify_import_done(entry):
    from utils import notify
    count = entry.get("prepare", {}).get("total") or entry.get("download", {}).get("total") or 0
    if count:
        with app.app_context():
            notify.send(load_config(), "imports", _("Import terminé"), _("%(count)s photo(s) ajoutée(s) depuis %(source)s.", count=count, source=_(entry.get("label", ""))),
                        key=f"import:{entry.get('source')}:{entry.get('started')}")


import_progress.ON_IMPORT_DONE.append(notify_import_done)


def cloud_update_worker():
    """Synchronisation automatique des autres clouds (Dropbox, OneDrive...)."""
    from web.routes_imports import run_cloud_sync
    time.sleep(120)  # laisser le cadre démarrer
    while True:
        config = load_config()
        try:
            if config.get("cloud_auto_update") and config.get("cloud_rclone_remote") and config.get("cloud_folders"):
                run_cloud_sync(config)
        except Exception as e:
            logger.warning(f"[Cloud] Synchronisation automatique : {e}")
        time.sleep(max(15, int(config.get("cloud_update_interval_minutes", 60))) * 60)


def icloud_update_worker():
    """Synchronisation automatique des albums partagés iCloud."""
    from web.routes_imports import run_icloud_sync
    time.sleep(180)  # laisser le cadre démarrer
    while True:
        config = load_config()
        try:
            if config.get("icloud_auto_update", True) and config.get("icloud_albums"):
                run_icloud_sync(config)
        except Exception as e:
            logger.warning(f"[iCloud] Synchronisation automatique : {e}")
        time.sleep(max(15, int(config.get("icloud_update_interval_minutes", 60))) * 60)


def email_worker():
    """Relève régulière de la boîte mail du cadre."""
    from web.routes_imports import run_email_check
    time.sleep(90)
    while True:
        config = load_config()
        try:
            if config.get("email_enabled"):
                run_email_check(config)
        except Exception as e:
            logger.warning(f"[E-mail] Relève : {e}")
            notify_sync_error("E-mail", str(e))
        time.sleep(max(1, int(config.get("email_check_minutes", 5))) * 60)


def people_worker():
    """Personnes d'Immich : mise à jour toutes les 6 heures (nouveaux visages nommés, nouvelles photos)."""
    from web.routes_people import run_people_refresh
    time.sleep(240)
    while True:
        config = load_config()
        try:
            if config.get("immich_url") and config.get("immich_token"):
                run_people_refresh(config)
        except Exception as e:
            logger.warning(f"[Personnes] Mise à jour : {e}")
        time.sleep(6 * 3600)


_reprepare_lock = threading.Lock()


def _caption_maps():
    """Légendes des sources qui en fournissent (pour qu'une photo repréparée garde la sienne)."""
    from utils import import_email, import_icloud, import_whatsapp
    maps = {"icloud": import_icloud.captions, "whatsapp": import_whatsapp.captions, "email": import_email.captions}
    try:
        immich = json.loads((BASE_DIR / "cache" / "immich_description_map.json").read_text(encoding="utf-8"))
        maps["immich"] = lambda: immich
    except (OSError, ValueError):
        pass
    return maps


def reprepare_all_sources():
    """Nouvelle taille d'écran (orientation changée) : toutes les photos sont repréparées, en arrière-plan."""
    if not _reprepare_lock.acquire(blocking=False):
        return
    try:
        config = load_config()
        maps = _caption_maps()
        photos = BASE_DIR / "static" / "photos"
        for source in sorted(photos.iterdir()) if photos.is_dir() else []:
            if not source.is_dir() or source.name.startswith("."):
                continue
            loader = maps.get(source.name)
            for _update in import_progress.tracked(source.name, "prepare", prepare_all_photos_with_progress(
                    config.get("display_width", 1920), config.get("display_height", 1080), source_type=source.name,
                    description_map=loader() if loader else None)):
                pass
        if is_slideshow_running():
            restart_slideshow_for_update()
    except Exception as e:
        logger.warning(f"[Orientation] Nouvelle préparation des photos : {e}")
    finally:
        _reprepare_lock.release()


def rotation_worker():
    """Mode « automatique » : le capteur d'orientation fait pivoter l'écran quand on tourne le cadre."""
    from utils import screen_rotation
    sensor, follower, missing_since = None, None, 0
    while True:
        config = load_config()
        if config.get("screen_orientation") != "auto":
            sensor, follower = None, None
            time.sleep(10)
            continue
        if sensor is None:
            if time.time() - missing_since < 60:
                time.sleep(5)
                continue
            sensor = screen_rotation.open_sensor()
            if sensor is None:
                missing_since = time.time()
                continue
            logger.info(f"[Orientation] Capteur {sensor.kind} trouvé.")
            follower = screen_rotation.Follower(screen_rotation.current(config))
        try:
            vector = sensor.read()
        except OSError:
            sensor = None
            continue
        screen_rotation.LIVE.update(vector=[round(v, 3) for v in vector], sensor=sensor.kind, at=time.time())  # en mémoire : pas d'écriture
        state = screen_rotation.load_state()
        changed = follower.update(screen_rotation.orientation_from(vector, state.get("calibration")))
        if changed:
            state["orientation"] = changed
            screen_rotation.save_state(state)
            config = dict(load_config())
            config["display_width"], config["display_height"] = screen_rotation.sized(
                config, config.get("display_width", 1920), config.get("display_height", 1080))
            save_config(config)
            logger.info(f"[Orientation] Cadre tourné : {changed}.")
            screen_rotation.apply(changed)
            if is_slideshow_running():
                restart_slideshow_process()
            threading.Thread(target=reprepare_all_sources, daemon=True, name="reprepare").start()
        time.sleep(1)


def storage_worker():
    """Supports de stockage : montés au démarrage, puis remontés s'ils reviennent (disque rebranché, NAS rallumé)."""
    from utils import storage
    while True:
        config = load_config()
        if config.get("storages"):
            try:
                for storage_id, (ok, message) in storage.mount_all(config).items():
                    if not ok:
                        logger.warning(f"[Stockage] Support {storage_id} indisponible : {message}")
            except Exception as e:
                logger.warning(f"[Stockage] {e}")
        time.sleep(300)


def quote_worker():
    """Citation du jour : nouvelle image chaque jour (et après un changement de réglage ou de taille d'écran)."""
    from web.routes_quotes import refresh_quote
    shown = None
    time.sleep(60)
    while True:
        config = load_config()
        key = (datetime.now().date().isoformat(), config.get("quote_enabled"), config.get("display_width"), config.get("display_height"),
               config.get("language"), config.get("quote_mode"), config.get("quote_style"), json.dumps(config.get("quotes_family") or []))
        if key != shown:
            try:
                refresh_quote(config)
                shown = key
            except Exception as e:
                logger.warning(f"[Citation] {e}")
        time.sleep(600)


def message_schedule_worker():
    """Messages programmés : ils entrent dans le diaporama à l'heure prévue (et en sortent à la fin de leur plage)."""
    while True:
        try:
            shown = messages_manager.refresh_schedule()
            if shown:
                logger.info(f"[Messages] {len(shown)} message(s) programmé(s) affiché(s).")
                if is_slideshow_running():
                    restart_slideshow_for_update()
        except Exception as e:
            logger.warning(f"[Messages] Programmation : {e}")
        time.sleep(30)


def hdmi_audio_worker():
    """Son HDMI disparu (écran éteint au démarrage du Pi) : réparé automatiquement dès que l'écran répond."""
    from utils import audio_output
    time.sleep(60)
    while True:
        config = load_config()
        try:
            if config.get("video_audio_output", "auto") in ("hdmi", "auto") and audio_output.hdmi_audio_missing():
                if audio_output.repair_hdmi_audio() and config.get("video_audio_output") == "hdmi":
                    audio_output.apply_audio_output("hdmi")
        except Exception as e:
            logger.warning(f"[Son] Réparation HDMI : {e}")
        time.sleep(300)


def button_worker():
    """Bouton physique (GPIO) : un appui met le cadre en veille ou le réveille. Réglages relus toutes les 5 s."""
    from utils import gpio_button
    gpio = gpio_button.load_gpio()
    gpio_button.STATE["available"] = gpio is not None
    if gpio is None:
        return

    def pressed():
        from web.routes_slideshow import toggle_sleep
        gpio_button.STATE["last_press"] = time.time()
        logger.info("[Bouton] Appui détecté : bascule de la veille.")
        threading.Thread(target=toggle_sleep, daemon=True, name="button-sleep").start()

    watcher = gpio_button.Watcher(gpio, pressed)
    reload_at = 0
    while True:
        if time.monotonic() >= reload_at:
            config = load_config()
            wanted = (bool(config.get("button_enabled")), int(config.get("button_pin", 23) or 23))
            try:
                watcher.configure(*wanted)
                gpio_button.STATE.update(pin=watcher.pin, error=None)
            except Exception as e:
                if gpio_button.STATE.get("error") != str(e):
                    logger.warning(f"[Bouton] GPIO {wanted[1]} : {e}")
                gpio_button.STATE.update(pin=None, error=str(e))
                watcher.pin = None
            reload_at = time.monotonic() + 5
        try:
            watcher.poll()
        except Exception as e:
            logger.warning(f"[Bouton] Lecture : {e}")
            watcher.pin = None
        time.sleep(gpio_button.POLL if watcher.pin is not None else 1)


def hotspot_worker():
    """Point d'accès de secours « Cadre-Pimmich » quand aucun réseau connu n'est trouvé (réglage wifi_hotspot_fallback)."""
    from utils import hotspot, wifi_networks
    hotspot.STATE_FILE.unlink(missing_ok=True)
    if not shutil.which("nmcli"):
        return
    fallback = hotspot.Fallback()
    actions = {"start": hotspot.start, "stop": hotspot.stop, "clients": hotspot.clients, "wait": time.sleep,
               "online": wifi_networks.online}
    time.sleep(30)
    while True:
        try:
            config = load_config()
            enabled = bool(config.get("wifi_hotspot_fallback"))
            key = hotspot.password(config, save_config) if enabled else ""
            result = fallback.step(enabled, wifi_networks.online(), key, actions)
            if result in ("started", "restarted", "back_online", "stopped", "failed"):
                logger.info(f"[Wi-Fi] Point d'accès de secours : {result}")
        except Exception as e:
            logger.warning(f"[Wi-Fi] Point d'accès de secours : {e}")
        time.sleep(30)


def music_schedule_worker():
    """Musique selon l'heure : la plage en cours lance sa musique (sans couper ce qui a été lancé à la main)."""
    from utils import music_schedule, now_playing, radio, spotify
    conductor = music_schedule.Conductor()
    time.sleep(90)
    while True:
        config = load_config()
        try:
            playing = now_playing.current(())
            playing = {"source": playing.get("source"), "title": playing.get("title")} if playing else None
            decision = conductor.tick(config, playing) if is_active_hours(config) else None
            if decision and decision[0] == "start":
                slot = decision[1]
                label = slot.get("label") or slot["value"]
                if slot["kind"] == "radio":
                    radio.play(slot["value"], label)
                    conductor.mark_started(slot, "radio", label[:80])
                elif slot["kind"] == "file":
                    radio.play_file(music_schedule.MUSIC_DIR / slot["value"], label)
                    conductor.mark_started(slot, "radio", label[:80])
                elif slot["kind"] == "spotify" and spotify.connected():
                    spotify.play_on_frame(slot["value"])
                    conductor.mark_started(slot, "spotify", None)
                logger.info(f"[Musique] Plage {slot['start']}-{slot['end']} : {label}")
            elif decision and decision[0] == "stop":
                if decision[1] == "radio":
                    radio.stop()
                elif decision[1] == "spotify":
                    spotify.control("pause")
                logger.info("[Musique] Fin de la plage horaire.")
        except Exception as e:
            logger.warning(f"[Musique] Selon l'heure : {e}")
        time.sleep(60)


def stats_worker():
    """Additionne les photos affichées (notées en mémoire vive) toutes les 30 minutes."""
    from utils import stats
    while True:
        time.sleep(1800)
        try:
            stats.collect()
        except Exception as e:
            logger.debug(f"[Stats] {e}")


def reliability_worker():
    """Surveillance : relance le diaporama s'il se fige ; fait tourner les journaux une fois par heure."""
    from utils import reliability
    restarts, last_rotation = [], 0
    time.sleep(240)
    while True:
        config = load_config()
        try:
            if is_slideshow_running() and reliability.frozen(config.get("display_duration", 10), started=reliability.slideshow_started()):
                logger.warning("[Surveillance] Le diaporama ne répond plus : relance.")
                restarts = [t for t in restarts if time.time() - t < 3600] + [time.time()]
                reliability.beat(force=True)  # nouveau délai avant la prochaine vérification
                restart_slideshow_process()
                if len(restarts) >= 3:
                    from utils import notify
                    notify.send(config, "health", _("Diaporama instable"), _("Il a dû être relancé %(count)s fois en une heure.", count=len(restarts)),
                                key="watchdog", repeat_after=3600)
            if time.time() - last_rotation > 3600:
                last_rotation = time.time()
                rotated = reliability.rotate_logs(BASE_DIR / "logs")
                if rotated:
                    logger.info(f"[Journaux] Rotation : {', '.join(rotated)}")
        except Exception as e:
            logger.warning(f"[Surveillance] {e}")
        time.sleep(60)


def trips_worker():
    """Cartes des voyages : souvenirs du jour et cartes à jour quand de nouvelles photos arrivent."""
    from utils import photo_index, trips
    from web.routes_trips import refresh_cards
    shown = None
    time.sleep(90)
    while True:
        config = load_config()
        if config.get("trip_cards", "off") != "off":
            key = (datetime.now().date().isoformat(), config.get("trip_cards"), config.get("display_width"), config.get("display_height"),
                   config.get("language"), _mtime(photo_index.INDEX_FILE), _mtime(trips.PLACES_FILE))
            if key != shown:
                try:
                    refresh_cards(config)
                    shown = key
                except Exception as e:
                    logger.warning(f"[Voyages] {e}")
        time.sleep(1800)


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0


def night_work_worker():
    """La nuit (diaporama éteint) : grosses vidéos en attente, puis une nouvelle tentative pour les médias en échec."""
    from utils import night_work, notify

    def tell(failed):
        config = load_config()
        names = ", ".join(name for _source, name in failed[:5]) + ("…" if len(failed) > 5 else "")
        base = notify.base_url(config)
        with app.app_context():
            notify.send(config, "media", _("Médias impossibles à préparer"),
                        _("%(count)s média(s) n'ont pas pu être préparés malgré un nouvel essai cette nuit : %(names)s", count=len(failed), names=names),
                        key=f"media:{night_work.night_key()}", click=f"{base}/app/#/preparation" if base else None, repeat_after=24 * 3600)

    time.sleep(300)
    while True:
        try:
            config = load_config()
            busy = any(i.get("active") for i in import_progress.snapshot())
            if not busy and not night_work.active_now(config):
                width, height = int(config.get("display_width", 1920)), int(config.get("display_height", 1080))
                done = night_work.run_once(config, width, height, notify=tell)
                if done["heavy"] or done["retried"]:
                    logger.info(f"[Nuit] {done['heavy']} grosse(s) vidéo(s), {done['retried']} nouvel(s) essai(s), "
                                f"{len(done['notified'])} échec(s) signalé(s)")
        except Exception as e:
            logger.warning(f"[Nuit] {e}")
        time.sleep(600)


def daily_summary_worker():
    """Bilan du jour, une fois par jour à l'heure choisie (si la notification « Bilan du jour » est cochée)."""
    from utils import daily_summary, notify
    time.sleep(120)
    while True:
        try:
            config = load_config()
            if notify.wants(config, "daily") and daily_summary.due(config):
                with app.app_context():
                    translate = _
                    title, text = daily_summary.build(config, translate=translate)
                    notify.send(config, "daily", title, text, key=f"daily:{datetime.now():%Y-%m-%d}", repeat_after=20 * 3600)
                daily_summary.mark_sent()
        except Exception as e:
            logger.warning(f"[Bilan] {e}")
        time.sleep(300)
