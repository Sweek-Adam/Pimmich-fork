"""Imports de photos (USB, Immich, Samba, Google Drive, smartphone) et préparation."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from utils import import_progress
from web.core import _


@app.route("/import-usb")
@login_required
def import_usb():
    # Nettoyer le drapeau d'annulation avant de commencer
    cancel_flag = Path('/tmp/pimmich_cancel_import.flag')
    if cancel_flag.exists(): cancel_flag.unlink()

    @stream_with_context
    def generate():
        def stream_event(data):
            """Formate les données en événement Server-Sent Event (SSE)."""
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        try:
            for update in import_progress.tracked("usb", "download", import_usb_photos()):
                yield stream_event(update)
        except Exception as e:
            yield stream_event({"type": "error", "message": f"Erreur critique : {str(e)}"})

    return Response(generate(), mimetype='text/event-stream', headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})


@app.route("/import-immich")
@login_required
def import_immich():
    # Nettoyer le drapeau d'annulation avant de commencer
    cancel_flag = Path('/tmp/pimmich_cancel_import.flag')
    if cancel_flag.exists(): cancel_flag.unlink()

    config = load_config()
    @stream_with_context
    def generate():
        import queue
        import threading
        
        q = queue.Queue()
        
        def run_import():
            try:
                for update in import_progress.tracked("immich", "download", download_and_extract_album(config)):
                    q.put(update)
                q.put(None)
            except Exception as e:
                q.put({"type": "error", "message": f"Erreur critique : {str(e)}"})
                q.put(None)

        t = threading.Thread(target=run_import)
        t.daemon = True
        t.start()

        while True:
            try:
                update = q.get(timeout=10)
                if update is None:
                    break
                yield f"data: {json.dumps(update, ensure_ascii=False)}\n\n"
                if update.get("type") == "error":
                    break
            except queue.Empty:
                yield ": keep-alive\n\n"

    return Response(generate(), mimetype='text/event-stream', headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})


@app.route("/import-samba")
@login_required
def import_samba():
    # Nettoyer le drapeau d'annulation avant de commencer
    cancel_flag = Path('/tmp/pimmich_cancel_import.flag')
    if cancel_flag.exists(): cancel_flag.unlink()

    config = load_config()
    @stream_with_context
    def generate():
        import queue
        import threading
        
        q = queue.Queue()
        
        def run_import():
            try:
                for update in import_progress.tracked("samba", "download", import_samba_photos(config)):
                    q.put(update)
                q.put(None)
            except Exception as e:
                q.put({"type": "error", "message": f"Erreur critique : {str(e)}"})
                q.put(None)

        t = threading.Thread(target=run_import)
        t.daemon = True
        t.start()

        while True:
            try:
                update = q.get(timeout=10)
                if update is None:
                    break
                yield f"data: {json.dumps(update, ensure_ascii=False)}\n\n"
                if update.get("type") == "error":
                    break
            except queue.Empty:
                yield ": keep-alive\n\n"

    return Response(generate(), mimetype='text/event-stream', headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})


@app.route("/import-gdrive")
@login_required
def import_gdrive():
    # Nettoyer le drapeau d'annulation avant de commencer
    cancel_flag = Path('/tmp/pimmich_cancel_import.flag')
    if cancel_flag.exists(): cancel_flag.unlink()

    config = load_config()
    @stream_with_context
    def generate():
        import queue
        import threading

        q = queue.Queue()

        def run_import():
            try:
                for update in import_progress.tracked("gdrive", "download", import_gdrive_photos(config)):
                    q.put(update)
                q.put(None)
            except Exception as e:
                q.put({"type": "error", "message": f"Erreur critique : {str(e)}"})
                q.put(None)

        t = threading.Thread(target=run_import)
        t.daemon = True
        t.start()

        while True:
            try:
                update = q.get(timeout=10)
                if update is None:
                    break
                yield f"data: {json.dumps(update, ensure_ascii=False)}\n\n"
                if update.get("type") == "error":
                    break
            except queue.Empty:
                yield ": keep-alive\n\n"

    return Response(generate(), mimetype='text/event-stream', headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})


@app.route('/api/gdrive/folders', methods=['POST'])
@login_required
def gdrive_folders():
    """Liste les dossiers Google Drive accessibles au compte de service.
    Utilise la clé fournie dans la requête (pas encore enregistrée) ou, à défaut, la clé enregistrée."""
    data = request.get_json(silent=True) or {}
    # Utiliser les choix du formulaire (pas forcément encore enregistrés)
    gdrive_config = {"gdrive_backend": data.get("backend", "auto"), "gdrive_rclone_remote": data.get("remote", "")}
    try:
        key_info = parse_service_account_key(data["key"]) if data.get("key", "").strip() else None
        folders = list_gdrive_folders(gdrive_config, key_info)
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Erreur Google Drive : {e}"}), 500
    return jsonify({"success": True, "folders": folders})


@app.route("/import-smartphone", methods=['POST'])
@login_required
def import_smartphone():
    # Nettoyer le drapeau d'annulation avant de commencer
    cancel_flag = Path('/tmp/pimmich_cancel_import.flag')
    if cancel_flag.exists(): cancel_flag.unlink()

    """
    Gère l'upload de photos depuis un smartphone via un formulaire web.
    """
    @stream_with_context
    def generate():
        def stream_event(data):
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        config = load_config()
        screen_width, screen_height = config.get("display_width", 1920), config.get("display_height", 1080)
        source_dir = BASE_DIR / "static" / "photos" / "smartphone"

        try:
            # --- Étape 1: Réception et sauvegarde des fichiers ---
            yield stream_event({"type": "progress", "stage": "UPLOADING", "percent": 5, "message": "Réception des fichiers..."})

            # Vider le dossier de destination pour éviter les mélanges
            if source_dir.exists():
                shutil.rmtree(source_dir)
            source_dir.mkdir(parents=True, exist_ok=True)

            uploaded_files = request.files.getlist('photos')
            if not uploaded_files or not uploaded_files[0].filename:
                yield stream_event({"type": "error", "message": "Aucun fichier sélectionné."})
                return

            for file in uploaded_files:
                file.save(source_dir / file.filename)

            yield stream_event({"type": "progress", "stage": "PREPARING", "percent": 80, "message": f"{len(uploaded_files)} photos reçues, préparation en cours..."})

            # --- Étape 2: Préparation des photos ---
            for update in import_progress.tracked("smartphone", "prepare", prepare_all_photos_with_progress(screen_width, screen_height, source_type="smartphone")):
                # Ajouter l'URL d'aperçu
                if update.get("current_photo_path"):
                    update["current_photo_url"] = url_for('static', filename=f"prepared/smartphone/{update['current_photo_path']}")
                yield stream_event(update)

        except Exception as e:
            logger.info(f"[Import Smartphone] Erreur : {e}")
            yield stream_event({"type": "error", "message": f"Erreur critique lors de l'import : {str(e)}"})

    return Response(generate(), mimetype='text/event-stream', headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})


@app.route('/test-samba', methods=['POST'])
@login_required
def test_samba_connection():
    """Teste la connexion à un partage Samba sans importer de fichiers."""

    data = request.get_json()
    server = data.get("smb_host")
    share = data.get("smb_share")
    path_in_share = data.get("smb_path", "").strip("/")
    user = data.get("smb_user")
    password = data.get("smb_password")
    
    if not all([server, share]):
        return jsonify({"success": False, "message": "Le serveur et le nom du partage sont requis."})
    
    # Construction robuste du chemin UNC pour éviter les problèmes de slashs finaux.
    if path_in_share:
        full_samba_path = f"//{server}/{share}/{path_in_share}"
    else:
        full_samba_path = f"//{server}/{share}"
    
    try:
        # Utiliser listdir en passant les identifiants directement.
        # Cela évite d'utiliser register/unregister_session qui peuvent manquer dans d'anciennes versions.
        files = smbclient.listdir(
            full_samba_path,
            username=user,
            password=password,
            connection_timeout=15
        )
        return jsonify({"success": True, "message": f"Connexion réussie ! {len(files)} élément(s) trouvé(s) dans le dossier."})

    except SMBException as e:
        # Fournir un message plus utile pour les erreurs communes
        if "STATUS_LOGON_FAILURE" in str(e):
            return jsonify({"success": False, "message": "Échec de l'authentification. Vérifiez l'utilisateur et le mot de passe."})
        elif "STATUS_BAD_NETWORK_NAME" in str(e):
            return jsonify({"success": False, "message": f"Le nom du partage '{share}' est introuvable sur le serveur."})
        elif "STATUS_OBJECT_NAME_NOT_FOUND" in str(e) or "STATUS_OBJECT_PATH_NOT_FOUND" in str(e):
            # Erreur spécifique si le sous-dossier n'existe pas
            return jsonify({"success": False, "message": f"Le chemin '{path_in_share}' est introuvable dans le partage."})
        elif "STATUS_HOST_UNREACHABLE" in str(e) or "timed out" in str(e):
             return jsonify({"success": False, "message": f"Impossible de joindre le serveur '{server}'. Vérifiez l'adresse et le pare-feu."})
        return jsonify({"success": False, "message": f"Erreur Samba : {e}"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Erreur inattendue : {e}"})


@app.route('/prepare-photos')
@login_required
def prepare_photos():
    # Nettoyer le drapeau d'annulation avant de commencer
    cancel_flag = Path('/tmp/pimmich_cancel_import.flag')
    if cancel_flag.exists(): cancel_flag.unlink()

    """
    Route pour lancer la préparation des photos pour une source donnée.
    Utilise Server-Sent Events (SSE) pour streamer le progrès.
    """
    source = request.args.get('source')
    if not source:
        def error_stream():
            error_update = {"type": "error", "message": "Le paramètre 'source' est manquant."}
            yield f"data: {json.dumps(error_update)}\n\n"
        return Response(stream_with_context(error_stream()), mimetype='text/event-stream')

    def generate_preparation_stream():
        """Générateur qui produit les événements de progression avec pings de maintien de connexion (keep-alive)."""
        import queue
        import threading
        
        q = queue.Queue()
        
        def run_preparation():
            try:
                config = load_config()
                screen_width = config.get('display_width')
                screen_height = config.get('display_height')

                # 1. Charger les descriptions de base (ex: depuis le cache Immich)
                base_description_map = {}
                if source == "immich":
                    immich_cache_path = Path("cache") / "immich_description_map.json"
                    if immich_cache_path.exists():
                        try:
                            with open(immich_cache_path, 'r', encoding='utf-8') as f:
                                base_description_map = json.load(f)
                        except Exception as e:
                            logger.info(f"[App] Avertissement: Impossible de charger le cache de description Immich: {e}")

                # 2. Charger les légendes manuelles de Pimmich
                manual_captions = load_text_states()

                # 3. Fusionner, en donnant la priorité aux légendes manuelles
                final_caption_map = base_description_map.copy()
                for path, caption in manual_captions.items():
                    filename = Path(path).name
                    final_caption_map[filename] = caption

                # Lancer la préparation et envoyer les mises à jour dans la queue.
                for update in import_progress.tracked(source, "prepare", prepare_all_photos_with_progress(screen_width, screen_height, source_type=source, description_map=final_caption_map)):
                    q.put(update)
                q.put(None) # Marqueur de fin
            except Exception as e:
                q.put({"type": "error", "message": f"Erreur serveur lors de la préparation : {str(e)}"})
                q.put(None)

        # Démarrer le traitement dans un thread d'arrière-plan
        t = threading.Thread(target=run_preparation)
        t.daemon = True
        t.start()

        # Lire la queue et streamer au client avec keep-alive
        while True:
            try:
                # Timeout de 10 secondes pour forcer un keep-alive
                update = q.get(timeout=10)
                if update is None:
                    break
                
                # Ajouter l'URL de l'image préparée dans le thread principal (qui dispose du contexte de requêtes Flask actif)
                if update.get("current_photo_path"):
                    update["current_photo_url"] = url_for('static', filename=f"prepared/{source}/{update['current_photo_path']}")
                
                yield f"data: {json.dumps(update, ensure_ascii=False)}\n\n"
                
                if update.get("type") == "error":
                    break
            except queue.Empty:
                # Nginx/Proxy et le navigateur ferment les SSE en cas d'inactivité.
                # On envoie un ping keep-alive (ignoré par l'API EventSource du navigateur)
                yield ": keep-alive\n\n"

    return Response(stream_with_context(generate_preparation_stream()), mimetype='text/event-stream', headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})


@app.route('/immich_update_status')
@login_required
def immich_update_status():
    """Retourne l'état actuel du worker de mise à jour Immich."""
    return jsonify(immich_status_manager.get_status())


@app.route('/samba_update_status')
@login_required
def samba_update_status():
    """Retourne l'état actuel du worker de mise à jour Samba."""
    return jsonify(samba_status_manager.get_status())


@app.route('/gdrive_update_status')
@login_required
def gdrive_update_status():
    """Retourne l'état actuel du worker de mise à jour Google Drive."""
    return jsonify(gdrive_status_manager.get_status())


# --- Téléchargement Immich et Préparation photos ---


@app.route("/download", methods=["POST"])
@login_required
def download_photos():
    try:
        config = load_config()
        # Note: download_and_extract_album is now a generator. This call will do nothing.
        # This route seems to be a simple POST fallback and might need to be updated or removed. (Translated comment)
        flash("Photos téléchargées avec succès", "success")
        logger.info(f"Photos téléchargées avec succès.")

    except Exception as e:
        flash(f"Erreur téléchargement : {e}", "danger")
    return redirect(url_for("configure"))


@app.route('/api/cancel_import', methods=['POST'])
@login_required
def cancel_import():
    """Crée un fichier drapeau pour signaler l'annulation aux processus d'import/préparation."""
    try:
        Path('/tmp/pimmich_cancel_import.flag').touch()
        return jsonify({"success": True, "message": "Signal d'annulation envoyé."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# --- Google Drive : photos que le cadre ne peut pas mettre à la corbeille ---

@app.route('/api/gdrive/denied', methods=['GET'])
@login_required
def gdrive_denied_api():
    from utils.import_gdrive import trash_denied_files
    return jsonify({"success": True, "files": trash_denied_files()})


@app.route('/api/gdrive/denied/retry', methods=['POST'])
@login_required
def gdrive_denied_retry_api():
    from utils.import_gdrive import retry_trash_denied
    count = retry_trash_denied()
    return jsonify({"success": True, "message": _("%(count)s photo(s) seront de nouveau proposées à la corbeille à la prochaine synchronisation.", count=count)})


@app.route('/api/imports/progress', methods=['GET'])
@login_required
def imports_progress_api():
    """Imports en cours (téléchargement et préparation) : notification persistante de l'interface."""
    items = import_progress.snapshot()
    translate = _  # appel indirect : l'extracteur ne doit pas prendre la clé « label » pour un texte
    for item in items:
        item["label"] = translate(item["label"])
    return jsonify({"success": True, "imports": items})


# --- Autres clouds (Dropbox, OneDrive, pCloud...) via rclone ---

def run_cloud_sync(config):
    """Synchronise puis prépare les photos du cloud (suivi dans la notification des imports)."""
    from utils import import_cloud
    changes = 0
    for update in import_progress.tracked("cloud", "download", import_cloud.import_cloud_photos(config)):
        if update.get("type") == "done":
            changes = update.get("changes", 0)
        if update.get("type") == "error":
            from web.workers import notify_sync_error
            notify_sync_error("Cloud", update.get("message", ""))
    if changes:
        for _update in import_progress.tracked("cloud", "prepare", prepare_all_photos_with_progress(
                config.get("display_width", 1920), config.get("display_height", 1080), source_type="cloud")):
            pass
        if is_slideshow_running():
            restart_slideshow_for_update()
    return changes


@app.route('/api/cloud', methods=['GET'])
@login_required
def cloud_status_api():
    from utils import import_cloud
    config = load_config()
    return jsonify({"success": True, "remotes": import_cloud.remotes(), "providers": import_cloud.PROVIDERS,
                    "remote": config.get("cloud_rclone_remote", ""), "folders": config.get("cloud_folders") or [],
                    "recursive": config.get("cloud_recursive", True), "trash": config.get("cloud_trash_after_import", False),
                    "auto": config.get("cloud_auto_update", False)})


@app.route('/api/cloud/remote', methods=['POST'])
@admin_required
def cloud_add_remote_api():
    from utils import import_cloud
    data = request.get_json(silent=True) or {}
    try:
        import_cloud.add_remote(data.get("name", ""), data.get("provider", ""), data.get("token", ""))
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    config = dict(load_config())
    config["cloud_rclone_remote"] = data["name"]
    save_config(config)
    return jsonify({"success": True, "message": _("Compte ajouté : choisissez maintenant les dossiers.")})


@app.route('/api/cloud/folders', methods=['GET'])
@login_required
def cloud_folders_api():
    from utils import import_cloud
    try:
        return jsonify({"success": True, "folders": import_cloud.list_folders(load_config())})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)[:300]}), 502


@app.route('/api/cloud', methods=['POST'])
@login_required
def cloud_save_api():
    from utils import import_cloud
    data = request.get_json(silent=True) or {}
    config = dict(load_config())
    if "remote" in data:
        if data["remote"] and data["remote"] not in [r["name"] for r in import_cloud.remotes()]:
            return jsonify({"success": False, "message": _("Compte inconnu.")}), 400
        config["cloud_rclone_remote"] = data["remote"]
    if "folders" in data:
        config["cloud_folders"] = [{"id": str(f.get("id", ""))[:300], "name": str(f.get("name", ""))[:300]}
                                   for f in data["folders"] if isinstance(f, dict) and f.get("id")][:50]
    for key, field in (("recursive", "cloud_recursive"), ("trash", "cloud_trash_after_import"), ("auto", "cloud_auto_update")):
        if key in data:
            config[field] = bool(data[key])
    if config.get("cloud_folders") and "cloud" not in config.get("display_sources", []):
        config["display_sources"] = list(config.get("display_sources", [])) + ["cloud"]
    save_config(config)
    return jsonify({"success": True, "message": _("Réglages du cloud enregistrés.")})


@app.route('/api/cloud/sync', methods=['POST'])
@login_required
def cloud_sync_api():
    config = load_config()
    if not config.get("cloud_rclone_remote") or not config.get("cloud_folders"):
        return jsonify({"success": False, "message": _("Choisissez d'abord un compte et des dossiers.")}), 400
    threading.Thread(target=run_cloud_sync, args=(config,), daemon=True).start()
    return jsonify({"success": True, "message": _("Synchronisation lancée : suivez-la dans la notification en bas de l'écran.")})
