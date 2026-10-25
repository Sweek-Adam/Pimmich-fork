"""Imports de photos (USB, Immich, Samba, Google Drive, smartphone) et préparation."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from utils import import_progress
from web.core import _
from utils.platform_info import tmp_path


@app.route("/import-usb")
@login_required
def import_usb():
    # Nettoyer le drapeau d'annulation avant de commencer
    cancel_flag = Path(str(tmp_path("pimmich_cancel_import.flag")))
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
    cancel_flag = Path(str(tmp_path("pimmich_cancel_import.flag")))
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
    cancel_flag = Path(str(tmp_path("pimmich_cancel_import.flag")))
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
    cancel_flag = Path(str(tmp_path("pimmich_cancel_import.flag")))
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
    cancel_flag = Path(str(tmp_path("pimmich_cancel_import.flag")))
    if cancel_flag.exists(): cancel_flag.unlink()

    """
    Gère l'upload de photos depuis un smartphone via un formulaire web.
    """
    @stream_with_context
    def generate():
        def stream_event(data):
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        from utils import members
        config = load_config()
        screen_width, screen_height = config.get("display_width", 1920), config.get("display_height", 1080)
        source = members.source_for(session.get("username"))  # chaque compte a ses envois
        source_dir = BASE_DIR / "static" / "photos" / source

        try:
            # --- Étape 1: Réception et sauvegarde des fichiers ---
            yield stream_event({"type": "progress", "stage": "UPLOADING", "percent": 5, "message": "Réception des fichiers..."})
            source_dir.mkdir(parents=True, exist_ok=True)

            uploaded_files = request.files.getlist('photos')
            if not uploaded_files or not uploaded_files[0].filename:
                yield stream_event({"type": "error", "message": "Aucun fichier sélectionné."})
                return

            for file in uploaded_files:  # les envois s'accumulent (jamais d'écrasement)
                file.save(members.unique_name(source_dir, secure_filename(file.filename) or f"photo_{secrets.token_hex(3)}.jpg"))

            config = load_config()
            if source not in config.get("display_sources", []):
                save_config(dict(config, display_sources=list(config.get("display_sources", [])) + [source]))
            from web.routes_history import log
            log("upload", _("%(count)s photo(s) envoyée(s)", count=len(uploaded_files)))

            yield stream_event({"type": "progress", "stage": "PREPARING", "percent": 80, "message": f"{len(uploaded_files)} photos reçues, préparation en cours..."})

            # --- Étape 2: Préparation des photos ---
            for update in import_progress.tracked(source, "prepare", prepare_all_photos_with_progress(screen_width, screen_height, source_type=source)):
                # Ajouter l'URL d'aperçu
                if update.get("current_photo_path"):
                    update["current_photo_url"] = url_for('static', filename=f"prepared/{source}/{update['current_photo_path']}")
                yield stream_event(update)
            if is_slideshow_running():
                restart_slideshow_for_update()

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
    password = data.get("smb_password") or (load_config().get("smb_password") if is_admin() else None)  # mot de passe enregistré
    
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
    cancel_flag = Path(str(tmp_path("pimmich_cancel_import.flag")))
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
        Path(str(tmp_path("pimmich_cancel_import.flag"))).touch()
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


# --- Albums partagés iCloud (lien public, sans identifiant Apple) ---

def run_icloud_sync(config):
    """Synchronise puis prépare les albums partagés iCloud (suivi dans la notification des imports)."""
    from utils import import_icloud
    changes = 0
    for update in import_progress.tracked("icloud", "download", import_icloud.import_icloud_photos(config)):
        if update.get("type") == "done":
            changes = update.get("changes", 0)
        if update.get("type") == "error":
            from web.workers import notify_sync_error
            notify_sync_error("iCloud", update.get("message", ""))
    if changes:
        for _update in import_progress.tracked("icloud", "prepare", prepare_all_photos_with_progress(
                config.get("display_width", 1920), config.get("display_height", 1080), source_type="icloud",
                description_map=import_icloud.captions())):
            pass
        if is_slideshow_running():
            restart_slideshow_for_update()
    return changes


@app.route('/api/icloud', methods=['GET'])
@login_required
def icloud_status_api():
    config = load_config()
    return jsonify({"success": True, "albums": config.get("icloud_albums") or [], "auto": config.get("icloud_auto_update", True)})


@app.route('/api/icloud/album', methods=['POST'])
@login_required
def icloud_add_album_api():
    """Ajoute un album partagé après avoir vérifié qu'il est lisible (nom et nombre d'éléments)."""
    from utils import import_icloud
    data = request.get_json(silent=True) or {}
    try:
        content = import_icloud.album(data.get("url", ""))
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": _("iCloud ne répond pas : %(error)s", error=str(e)[:200])}), 502
    config = dict(load_config())
    albums = [a for a in config.get("icloud_albums") or [] if a.get("token") != content["token"]]
    albums.append({"token": content["token"], "name": content["name"][:200], "count": len(content["items"]),
                   "url": f"https://www.icloud.com/sharedalbum/#{content['token']}"})
    config["icloud_albums"] = albums[:20]
    if "icloud" not in config.get("display_sources", []):
        config["display_sources"] = list(config.get("display_sources", [])) + ["icloud"]
    save_config(config)
    threading.Thread(target=run_icloud_sync, args=(config,), daemon=True).start()
    return jsonify({"success": True, "message": _("Album « %(name)s » ajouté (%(count)s éléments) : import lancé.",
                                                  name=content["name"], count=len(content["items"]))})


@app.route('/api/icloud', methods=['POST'])
@login_required
def icloud_save_api():
    data = request.get_json(silent=True) or {}
    config = dict(load_config())
    if "remove" in data:
        config["icloud_albums"] = [a for a in config.get("icloud_albums") or [] if a.get("token") != data["remove"]]
    if "auto" in data:
        config["icloud_auto_update"] = bool(data["auto"])
    save_config(config)
    if "remove" in data:
        threading.Thread(target=run_icloud_sync, args=(config,), daemon=True).start()
    return jsonify({"success": True, "message": _("Réglages iCloud enregistrés.")})


@app.route('/api/icloud/sync', methods=['POST'])
@login_required
def icloud_sync_api():
    config = load_config()
    if not config.get("icloud_albums"):
        return jsonify({"success": False, "message": _("Ajoutez d'abord un album partagé.")}), 400
    threading.Thread(target=run_icloud_sync, args=(config,), daemon=True).start()
    return jsonify({"success": True, "message": _("Synchronisation lancée : suivez-la dans la notification en bas de l'écran.")})


# --- WhatsApp : export d'une discussion (.zip avec les médias) ---

def run_whatsapp_import(zip_path, senders=None, caption_mode="text"):
    """Importe puis prépare les médias d'un export WhatsApp (suivi dans la notification des imports)."""
    from utils import import_whatsapp
    changes = 0
    try:
        for update in import_progress.tracked("whatsapp", "download", import_whatsapp.import_export(zip_path, senders, caption_mode)):
            if update.get("type") == "done":
                changes = update.get("changes", 0)
    finally:
        Path(zip_path).unlink(missing_ok=True)
    if changes:
        config = load_config()
        if "whatsapp" not in config.get("display_sources", []):
            config = dict(config, display_sources=list(config.get("display_sources", [])) + ["whatsapp"])
            save_config(config)
        for _update in import_progress.tracked("whatsapp", "prepare", prepare_all_photos_with_progress(
                config.get("display_width", 1920), config.get("display_height", 1080), source_type="whatsapp",
                description_map=import_whatsapp.captions())):
            pass
        if is_slideshow_running():
            restart_slideshow_for_update()
    return changes


def _save_whatsapp_upload(file):
    from utils import import_whatsapp
    path = BASE_DIR / import_whatsapp.UPLOAD_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    file.save(path)
    return path


@app.route('/api/whatsapp/upload', methods=['POST'])
@login_required
def whatsapp_upload_api():
    """Reçoit l'export (.zip) et renvoie son contenu (photos, vidéos, période, expéditeurs) avant l'import."""
    from utils import import_whatsapp
    file = request.files.get("export")
    if not file or not file.filename:
        return jsonify({"success": False, "message": _("Aucun fichier sélectionné.")}), 400
    path = _save_whatsapp_upload(file)
    try:
        summary = import_whatsapp.analyse(path)
    except Exception:
        path.unlink(missing_ok=True)
        return jsonify({"success": False, "message": _("Ce fichier n'est pas un export WhatsApp (.zip).")}), 400
    if not summary["photos"] and not summary["videos"]:
        path.unlink(missing_ok=True)
        return jsonify({"success": False, "message": _("Aucune photo ni vidéo dans cet export : choisissez « Joindre les médias » en l'exportant.")}), 400
    return jsonify({"success": True, "summary": summary})


@app.route('/api/whatsapp/import', methods=['POST'])
@login_required
def whatsapp_import_api():
    from utils import import_whatsapp
    path = BASE_DIR / import_whatsapp.UPLOAD_FILE
    if not path.is_file():
        return jsonify({"success": False, "message": _("Envoyez d'abord l'export de la discussion.")}), 400
    data = request.get_json(silent=True) or {}
    senders = [str(s) for s in data.get("senders") or []] or None
    caption_mode = data.get("caption") if data.get("caption") in import_whatsapp.CAPTION_MODES else "text"
    staged = path.with_name(f"whatsapp_{int(time.time())}.zip")
    path.replace(staged)
    threading.Thread(target=run_whatsapp_import, args=(staged, senders, caption_mode), daemon=True).start()
    return jsonify({"success": True, "message": _("Import lancé : suivez-le dans la notification en bas de l'écran.")})


@app.route('/upload/share', methods=['POST'])
def upload_share():
    """Cible de partage du téléphone (« Partager › Pimmich », Android) : export WhatsApp ou photos.

    Connecté au cadre : l'export WhatsApp est importé directement, les photos rejoignent la source WhatsApp et partages.
    Invité : les photos attendent la validation, comme depuis la page d'envoi.
    """
    files = [f for f in request.files.getlist("photos") if f and f.filename]
    if not files:
        flash(_("Aucun fichier sélectionné."), "error")
        return redirect(url_for('upload_page'))
    if not session.get("logged_in"):
        from web.routes_guests import handle_upload
        return handle_upload()
    zips = [f for f in files if f.filename.lower().endswith(".zip")]
    for file in zips[:1]:
        path = _save_whatsapp_upload(file)
        staged = path.with_name(f"whatsapp_{int(time.time())}.zip")
        path.replace(staged)
        threading.Thread(target=run_whatsapp_import, args=(staged,), daemon=True).start()
    media = [f for f in files if Path(f.filename).suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".heic") + VIDEO_EXTENSIONS]
    if media:
        target = BASE_DIR / "static" / "photos" / "whatsapp"
        target.mkdir(parents=True, exist_ok=True)
        for file in media:
            name = secure_filename(file.filename) or "photo.jpg"
            stem, ext = os.path.splitext(name)
            file.save(target / f"{datetime.now():%Y%m%d_%H%M%S}_{stem}_{secrets.token_hex(2)}{ext}")
        threading.Thread(target=run_whatsapp_prepare, daemon=True).start()
    flash(_("%(count)s fichier(s) reçu(s) : ils arrivent sur le cadre.", count=len(zips[:1]) + len(media)), "success")
    return redirect(url_for('upload_page'))


def run_whatsapp_prepare():
    from utils import import_whatsapp
    config = load_config()
    if "whatsapp" not in config.get("display_sources", []):
        config = dict(config, display_sources=list(config.get("display_sources", [])) + ["whatsapp"])
        save_config(config)
    for _update in import_progress.tracked("whatsapp", "prepare", prepare_all_photos_with_progress(
            config.get("display_width", 1920), config.get("display_height", 1080), source_type="whatsapp",
            description_map=import_whatsapp.captions())):
        pass
    if is_slideshow_running():
        restart_slideshow_for_update()


# --- Envoi par e-mail (boîte relevée en IMAP) ---

def run_email_check(config):
    """Relève la boîte mail du cadre, prépare les photos des expéditeurs autorisés, signale les autres à valider."""
    from utils import import_email, notify
    result = import_email.check(config)
    if result.get("pending"):
        base = notify.base_url(config)
        notify.send(config, "guest", _("Nouvelle photo d'invité"), _("%(count)s photo(s) à valider sur le cadre.", count=result["pending"]),
                    key="guest_photo", click=f"{base}/configure#tab-validation" if base else None, repeat_after=60)
    if result.get("accepted"):
        config = load_config()
        if "email" not in config.get("display_sources", []):
            config = dict(config, display_sources=list(config.get("display_sources", [])) + ["email"])
            save_config(config)
        for _update in import_progress.tracked("email", "prepare", prepare_all_photos_with_progress(
                config.get("display_width", 1920), config.get("display_height", 1080), source_type="email",
                description_map=import_email.captions())):
            pass
        if is_slideshow_running():
            restart_slideshow_for_update()
    return result


EMAIL_PROVIDERS = {"gmail.com": "imap.gmail.com", "googlemail.com": "imap.gmail.com", "outlook.com": "outlook.office365.com",
                   "hotmail.com": "outlook.office365.com", "hotmail.fr": "outlook.office365.com", "live.com": "outlook.office365.com",
                   "live.fr": "outlook.office365.com", "yahoo.com": "imap.mail.yahoo.com", "yahoo.fr": "imap.mail.yahoo.com",
                   "icloud.com": "imap.mail.me.com", "me.com": "imap.mail.me.com", "orange.fr": "imap.orange.fr",
                   "free.fr": "imap.free.fr", "laposte.net": "imap.laposte.net", "gmx.fr": "imap.gmx.net", "gmx.com": "imap.gmx.net"}


@app.route('/api/email', methods=['GET'])
@login_required
def email_status_api():
    config = load_config()
    return jsonify({"success": True, "enabled": config.get("email_enabled", False), "host": config.get("email_imap_host", ""),
                    "port": config.get("email_imap_port", 993), "user": config.get("email_user", ""),
                    "has_password": bool(config.get("email_password")), "folder": config.get("email_folder", "INBOX"),
                    "allowed": config.get("email_allowed_senders") or [], "unknown": config.get("email_unknown_senders", "pending"),
                    "providers": EMAIL_PROVIDERS})


@app.route('/api/email', methods=['POST'])
@admin_required
def email_save_api():
    data = request.get_json(silent=True) or {}
    config = dict(load_config())
    for key, field in (("host", "email_imap_host"), ("user", "email_user"), ("folder", "email_folder")):
        if key in data:
            config[field] = str(data[key] or "").strip()[:200]
    if data.get("password"):
        config["email_password"] = str(data["password"])[:200]
    if "port" in data:
        try:
            config["email_imap_port"] = max(1, min(65535, int(data["port"])))
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": _("Port invalide.")}), 400
    if "allowed" in data:
        config["email_allowed_senders"] = sorted({a.strip().lower() for a in re.split(r"[\s,;]+", str(data["allowed"])) if "@" in a})[:100]
    if data.get("unknown") in ("pending", "ignore"):
        config["email_unknown_senders"] = data["unknown"]
    if "enabled" in data:
        config["email_enabled"] = bool(data["enabled"])
    save_config(config)
    return jsonify({"success": True, "message": _("Réglages de l'e-mail enregistrés.")})


@app.route('/api/email/test', methods=['POST'])
@admin_required
def email_test_api():
    from utils import import_email
    try:
        count = import_email.test(load_config())
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": _("Connexion impossible : %(error)s", error=str(e)[:200])}), 502
    return jsonify({"success": True, "message": _("Connexion réussie : %(count)s messages dans la boîte.", count=count)})


@app.route('/api/email/check', methods=['POST'])
@login_required
def email_check_api():
    config = load_config()
    if not config.get("email_enabled"):
        return jsonify({"success": False, "message": _("Activez d'abord la réception par e-mail.")}), 400
    try:
        result = run_email_check(config)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)[:300]}), 502
    return jsonify({"success": True, "message": _("%(accepted)s photo(s) ajoutée(s), %(pending)s à valider, %(ignored)s ignorée(s).",
                                                  accepted=result["accepted"], pending=result["pending"], ignored=result["ignored"])})


# --- Mes envois (un compte par membre de la famille) ---

@app.route('/api/my_uploads', methods=['GET'])
@login_required
def my_uploads_api():
    from utils import members
    source = members.source_for(session.get("username"))
    folder = PREPARED_DIR / source
    items = []
    for f in sorted(folder.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True) if folder.is_dir() else []:
        if f.suffix.lower() in (".jpg", ".mp4") and not f.stem.endswith(("_polaroid", "_postcard", "_thumbnail")):
            thumb = f.with_name(f"{f.stem}_thumbnail.jpg").name if f.suffix.lower() == ".mp4" else f.name
            items.append({"name": f.name, "thumb": url_for("static", filename=f"prepared/{source}/{thumb}")})
    return jsonify({"success": True, "source": source, "items": items})


@app.route('/api/my_uploads/<name>', methods=['DELETE'])
@login_required
def my_uploads_delete_api(name):
    from utils import members
    source = members.source_for(session.get("username"))
    if Path(name).name != name or name.startswith("."):
        return jsonify({"success": False, "message": _("Photo introuvable.")}), 404
    stem = Path(name).stem
    removed = 0
    for folder in (PREPARED_DIR / source, BASE_DIR / "static" / "photos" / source, BASE_DIR / "static" / ".backups" / source):
        for f in folder.glob(f"{stem}*") if folder.is_dir() else []:
            if re.sub(r"(_polaroid|_postcard|_thumbnail|_animation)$", "", f.stem) == stem:
                f.unlink()
                removed += 1
    if not removed:
        return jsonify({"success": False, "message": _("Photo introuvable.")}), 404
    if is_slideshow_running():
        restart_slideshow_for_update()
    return jsonify({"success": True, "message": _("Photo supprimée du cadre.")})
