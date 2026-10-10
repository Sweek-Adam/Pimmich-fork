"""Pilotage du diaporama : lecture, veille, sources, durée, écran et résolution."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from utils import play_queue, layout_engine, compositions, spotify
from web.core import _, _send_slideshow_signal


# --- Gestion Diaporama ---

@app.route("/slideshow")
@login_required
def slideshow():
    return render_template("slideshow.html.jinja")


@app.route('/slideshow_view')
@login_required
def slideshow_view():
    all_media = [media for source_media in get_prepared_photos_by_source().values() for media in source_media]
    return render_template('slideshow_view.html.jinja', photos=all_media) # Le template s'attend probablement à une variable 'photos'


@app.route('/toggle_slideshow', methods=['POST'])
@login_required
def toggle_slideshow():
    config = load_config()

    # On lit l'état actuel du slideshow
    running = is_slideshow_running()

    # Si le slideshow est lancé, on l'arrête, sinon on le démarre
    if running:
        stop_slideshow()
        config['manual_override'] = "stop"  # L'utilisateur a demandé l'arrêt
    else:
        set_display_power(on=True)
        time.sleep(1)
        start_slideshow()
        config['manual_override'] = "start"  # L'utilisateur a demandé le démarrage

    save_config(config) # Save config after manual override

    return redirect(url_for('configure'))


@app.route('/api/slideshow/restart_for_update', methods=['POST'])
@login_required
def restart_slideshow_for_update_route():
    """Redémarre le diaporama pour une mise à jour de contenu, sans éteindre l'écran."""
    try:
        if is_slideshow_running():
            restart_slideshow_for_update()
        return jsonify({"success": True, "message": "Commande de redémarrage envoyée."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


def start_photo_playlist(playlist_id):
    """Lance une playlist de photos sur le cadre (et sa musique Spotify associée) : (succès, message, code HTTP)."""
    playlists = load_playlists()
    target_playlist = next((p for p in playlists if p.get('id') == playlist_id), None)
    if not target_playlist:
        return False, "Playlist non trouvée.", 404
    if not target_playlist.get('photos'):
        return False, "La playlist est vide.", 400
    playlist_data_to_save = {
        "name": target_playlist.get('name', 'Playlist'),
        "photos": target_playlist.get('photos', []),
        "music_file": target_playlist.get('music_file'),
        "layout": target_playlist.get('layout', layout_engine.AUTO),  # disposition propre à la playlist
    }
    # Écrire les données dans le fichier temporaire que le diaporama lira
    with open(CUSTOM_PLAYLIST_FILE, 'w') as f:
        json.dump(playlist_data_to_save, f)
    # Redémarrer le diaporama pour charger la nouvelle playlist sans éteindre l'écran
    restart_slideshow_for_update()
    links = load_config().get("spotify_links") or {}
    spotify.play_linked_in_background(links.get(f"playlist:{playlist_id}"), logger)  # musique Spotify associée
    return True, f"Lancement du diaporama pour la playlist '{target_playlist.get('name')}'.", 200


@app.route('/api/playlists/play', methods=['POST'])
@login_or_internal_required
def play_playlist():
    # Accès contrôlé par @login_or_internal_required (session ou jeton interne)
    playlist_id = (request.get_json(silent=True) or {}).get('id')
    if not playlist_id:
        return jsonify({"success": False, "message": "ID de playlist manquant."}), 400
    try:
        ok, message, status = start_photo_playlist(playlist_id)
        return jsonify({"success": ok, "message": message}), status
    except Exception as e:
        logger.info(f"Erreur lors du lancement de la playlist : {e}")
        return jsonify({"success": False, "message": "Erreur interne du serveur."}), 500


@app.route('/api/slideshow/restart_standard', methods=['POST'])
@login_or_internal_required
def restart_standard_slideshow():
    """Arrête tout diaporama en cours et en lance un nouveau en mode standard."""
    try:
        # S'assurer que le fichier de playlist personnalisée est supprimé
        if os.path.exists(CUSTOM_PLAYLIST_FILE):
            os.remove(CUSTOM_PLAYLIST_FILE)
        
        # Redémarrer le diaporama en mode standard sans éteindre l'écran
        restart_slideshow_for_update()
        return jsonify({"success": True, "message": "Diaporama standard relancé."})
    except Exception as e:
        logger.info(f"Erreur lors du redémarrage du diaporama standard : {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/slideshow/toggle_sleep', methods=['POST'])
@login_or_internal_required
def toggle_sleep_api():
    """Bascule l'état du diaporama (actif/veille). Pour utilisation avec un bouton physique."""
    # Accès contrôlé par @login_or_internal_required (session ou jeton interne)
    
    try:
        if is_slideshow_running():
            logger.info("API toggle_sleep: Diaporama en cours -> Arrêt.")
            stop_slideshow()
            message = "Diaporama mis en veille."
        else:
            logger.info("API toggle_sleep: Diaporama arrêté -> Démarrage.")
            start_slideshow()
            message = "Diaporama réveillé."
        return jsonify({"success": True, "message": message})
    except Exception as e:
        logger.error(f"Erreur lors du basculement de la veille via API : {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/display/power', methods=['POST'])
@login_or_internal_required
def display_power():
    """Allume ou éteint l'écran."""
    # Accès contrôlé par @login_or_internal_required (session ou jeton interne)
    
    data = request.get_json()
    state = data.get('state') # 'on' or 'off'

    if state not in ['on', 'off']:
        return jsonify({"success": False, "message": "État invalide. Utilisez 'on' ou 'off'."}), 400

    # La logique est maintenant dans le slideshow_manager
    if state == 'on':
        if not is_slideshow_running():
            start_slideshow()
        success, message = True, "Commande de démarrage envoyée."
    else: # off
        if is_slideshow_running():
            stop_slideshow()
        success, message = True, "Commande d'arrêt envoyée."

    return jsonify({"success": success, "message": message})


@app.route('/api/sources/play/<source_name>', methods=['POST'])
@login_or_internal_required
def play_source_as_playlist(source_name):
    """Joue toutes les photos d'une source donnée comme une playlist."""
    # Accès contrôlé par @login_or_internal_required (session ou jeton interne)

    source_dir = PREPARED_DIR / source_name
    if not source_dir.is_dir():
        return jsonify({"success": False, "message": f"La source '{source_name}' n'existe pas."}), 404

    photos = [
        f"{source_name}/{f.name}" for f in source_dir.iterdir() 
        if f.is_file() and not f.name.endswith(('_polaroid.jpg', '_thumbnail.jpg', '_postcard.jpg'))
    ]

    if not photos:
        return jsonify({"success": False, "message": f"La source '{source_name}' est vide."}), 400
    
    playlist_data = {"name": f"Source: {source_name.capitalize()}", "photos": photos}
    
    try:
        with open(CUSTOM_PLAYLIST_FILE, 'w', encoding='utf-8') as f:
            json.dump(playlist_data, f)
        
        stop_slideshow()
        time.sleep(1.5) # Donner un peu plus de temps pour l'arrêt
        start_slideshow()
        
        return jsonify({"success": True, "message": f"Lancement du diaporama pour la source '{source_name}'."})
    except Exception as e:
        return jsonify({"success": False, "message": f"Erreur lors du lancement de la playlist source: {e}"}), 500


@app.route('/api/sources/toggle', methods=['POST'])
@login_or_internal_required
def toggle_source():
    """Active ou désactive une source dans la configuration."""
    # Accès contrôlé par @login_or_internal_required (session ou jeton interne)
        
    data = request.get_json()
    source_name = data.get('source')
    state = data.get('state') # 'on' or 'off'
    app.logger.info(f"Action demandée : '{state}' pour la source '{source_name}'")

    if not source_name or state not in ['on', 'off']:
        app.logger.error(f"Paramètres invalides reçus : source='{source_name}', state='{state}'")
        return jsonify({"success": False, "message": "Paramètres 'source' ou 'state' invalides."}), 400

    try:
        config = load_config()
        original_sources = config.get('display_sources', [])
        app.logger.info(f"Sources avant modification : {original_sources}")
        display_sources = set(original_sources)

        if state == 'on':
            display_sources.add(source_name)
            action_msg = "activée"
        else: # off
            display_sources.discard(source_name)
            action_msg = "désactivée"

        new_sources_list = sorted(list(display_sources))
        config['display_sources'] = new_sources_list
        app.logger.info(f"Sources après modification (avant sauvegarde) : {new_sources_list}")
        save_config(config)
        app.logger.info("Configuration sauvegardée avec succès dans config.json.")
        
        # Le diaporama détectera le changement automatiquement au prochain cycle.
        # Il n'est plus nécessaire de le redémarrer de force, ce qui causait le timeout.
        return jsonify({"success": True, "message": f"Source '{source_name}' {action_msg}. Le changement sera appliqué sur le diaporama."})
    except Exception as e:
        app.logger.error(f"Erreur dans la fonction toggle_source : {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Erreur lors de la modification de la source : {e}"}), 500


@app.route('/api/slideshow/set_duration', methods=['POST'])
@login_or_internal_required
def set_slideshow_duration():
    """Modifie la durée d'affichage des photos et redémarre le diaporama."""
    # Accès contrôlé par @login_or_internal_required (session ou jeton interne)
    
    data = request.get_json()
    duration = data.get('duration')

    if not isinstance(duration, int) or duration <= 0:
        return jsonify({"success": False, "message": "Durée invalide. Un entier positif est requis."}), 400

    try:
        config = load_config()
        config['display_duration'] = duration
        save_config(config)
        
        # Redémarrer le diaporama pour appliquer la nouvelle durée
        if is_slideshow_running():
            stop_slideshow()
            time.sleep(1) # Laisser le temps au processus de se terminer
        
        start_slideshow()
        
        return jsonify({"success": True, "message": f"Durée d'affichage réglée à {duration} secondes."})
    except Exception as e:
        app.logger.error(f"Erreur lors du changement de la durée d'affichage : {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Erreur interne du serveur : {e}"}), 500


@app.route('/api/slideshow/next', methods=['POST'])
@login_or_internal_required
def slideshow_next():
    return _send_slideshow_signal(signal.SIGUSR1)


@app.route('/api/slideshow/previous', methods=['POST'])
@login_or_internal_required
def slideshow_previous():
    return _send_slideshow_signal(signal.SIGUSR2)


@app.route('/api/slideshow/toggle_pause', methods=['POST'])
@login_or_internal_required
def slideshow_toggle_pause():
    return _send_slideshow_signal(signal.SIGTSTP)


@app.route('/api/slideshow/toggle_notifications', methods=['POST'])
@login_or_internal_required
def toggle_notifications_api():
    """Bascule l'affichage des notifications sur le diaporama."""
    # Accès contrôlé par @login_or_internal_required (session ou jeton interne)
    
    try:
        config = load_config()
        current_state = config.get("display_telegram_notification_overlay", True)
        new_state = not current_state
        config["display_telegram_notification_overlay"] = new_state
        save_config(config)
        
        return jsonify({"success": True, "enabled": new_state})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/slideshow/status')
@login_or_internal_required
def slideshow_status():
    if not is_slideshow_running():
        return jsonify({"running": False, "paused": False})
    try:
        with open("/tmp/pimmich_slideshow_status.json", "r") as f:
            status = json.load(f)
        config = load_config()
        return jsonify({"running": True, "notifications_enabled": config.get("display_telegram_notification_overlay", True), **status})
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({"running": True, "paused": False, "notifications_enabled": True})


@app.route('/api/get_available_resolutions')
@login_required
def get_available_resolutions():
    """
    Récupère les résolutions disponibles pour la sortie d'affichage principale.
    """
    try:
        output_name = get_display_output_name()
        if not output_name:
            return jsonify({"success": False, "message": "Aucune sortie d'affichage principale trouvée."})

        result = subprocess.run(['swaymsg', '-t', 'get_outputs'], capture_output=True, text=True, check=True, env=os.environ)
        outputs = json.loads(result.stdout)

        resolutions = []
        for output in outputs:
            if output.get('name') == output_name and 'modes' in output:
                for mode in output['modes']:
                    resolutions.append({
                        "width": mode['width'],
                        "height": mode['height'],
                        "refresh": mode['refresh'] / 1000, # Convertir de mHz à Hz
                        "text": f"{mode['width']}x{mode['height']} @ {mode['refresh']/1000:.2f}Hz"
                    })
                # Inverser pour avoir les plus hautes résolutions en premier
                resolutions.reverse()
                return jsonify({"success": True, "resolutions": resolutions})

        return jsonify({"success": False, "message": "Aucun mode trouvé pour la sortie principale."})

    except Exception as e:
        return jsonify({"success": False, "message": f"Erreur lors de la récupération des résolutions : {e}"})


@app.route('/api/set_resolution', methods=['POST'])
@login_required
def set_resolution():
    """
    Applique une nouvelle résolution à l'écran et la sauvegarde dans la configuration.
    """
    data = request.get_json()
    width = data.get('width')
    height = data.get('height')

    if not width or not height:
        return jsonify({"success": False, "message": "Largeur et hauteur requises."}), 400

    try:
        output_name = get_display_output_name()
        if not output_name:
            return jsonify({"success": False, "message": "Aucune sortie d'affichage à configurer."})

        # Appliquer la résolution via swaymsg
        subprocess.run(['swaymsg', 'output', output_name, 'resolution', f'{width}x{height}'], check=True)

        # Sauvegarder dans la configuration pour la persistance
        config = load_config()
        config['display_width'] = int(width)
        config['display_height'] = int(height)
        save_config(config)

        # Redémarrer le diaporama pour qu'il prenne en compte la nouvelle résolution
        if is_slideshow_running():
            stop_slideshow()
            start_slideshow()
            message = _("Résolution appliquée : %(width)sx%(height)s. Le diaporama a été redémarré.", width=width, height=height)
        else:
            message = _("Résolution appliquée : %(width)sx%(height)s. Le diaporama n'était pas en cours.", width=width, height=height)

        return jsonify({"success": True, "message": message})
    except Exception as e:
        return jsonify({"success": False, "message": f"Erreur lors de l'application de la résolution : {e}"}), 500


@app.route('/get_current_resolution')
@login_required
def get_current_resolution_route():
    """
    Endpoint pour récupérer la résolution de l'écran si le diaporama est actif.
    """
    width, height = get_screen_resolution()
    
    if width and height:
         return jsonify({"success": True, "width": width, "height": height})
    else:
         # Ce cas ne devrait plus arriver car get_screen_resolution a un fallback, mais on le garde par sécurité.
         return jsonify({"success": False, "message": "Impossible de détecter la résolution. L'écran est-il branché ?"})


@app.route('/current_photo_status')
@login_required
def current_photo_status():
    """Retourne le chemin de la photo en cours d'affichage."""
    if not is_slideshow_running():
        return jsonify({"current_photo": None, "status": "stopped"})

    try:
        if os.path.exists(CURRENT_PHOTO_FILE):
            with open(CURRENT_PHOTO_FILE, "r") as f:
                photo_path = f.read().strip()
            if photo_path:
                # Construire l'URL complète pour l'attribut src de l'image
                return jsonify({"current_photo": url_for('static', filename=photo_path), "status": "running"})
    except Exception as e:
        logger.info(f"Erreur lecture fichier photo actuelle : {e}")
        
    return jsonify({"current_photo": None, "status": "running"})


# --- File d'attente du diaporama (onglet « À suivre ») ---

STATIC_DIR = (BASE_DIR / "static").resolve()


def _queue_item(path):
    """Média de la file -> {chemin relatif à static, URL de miniature, type}."""
    try:
        relative = Path(path).resolve().relative_to(STATIC_DIR)
    except ValueError:
        return None
    is_video = relative.suffix.lower() in VIDEO_EXTENSIONS
    thumb = relative.with_name(f"{relative.stem}_thumbnail.jpg") if is_video else relative
    source = relative.parts[1] if len(relative.parts) > 2 and relative.parts[0] == "prepared" else ""
    return {"path": relative.as_posix(), "thumb": url_for('static', filename=thumb.as_posix()),
            "video": is_video, "source": source, "name": relative.name}


@app.route('/api/slideshow/queue', methods=['GET'])
@login_required
def slideshow_queue():
    state = play_queue.read_state()
    if not state or not is_slideshow_running():
        return jsonify({"success": True, "running": False, "current": None, "upcoming": []})
    upcoming = [item for item in map(_queue_item, state.get("upcoming", [])) if item]
    return jsonify({"success": True, "running": True, "current": _queue_item(state.get("current", "")), "upcoming": upcoming,
                    "slots": _queue_slots(state.get("upcoming", []), state.get("compositions", []))})


def _queue_slots(paths, planned):
    """
    Les suivants tels qu'ils seront affichés : photo seule, ou composition regroupant plusieurs photos.
    Une composition pas encore préparée n'a qu'une photo (celle par laquelle elle commencera) et `pending`.
    """
    starts = {c.get("at"): c for c in planned if isinstance(c, dict)}
    slots, index = [], 0
    while index < len(paths):
        plan = starts.get(index)
        if not plan:
            item = _queue_item(paths[index])
            if item:
                slots.append(dict(item, type="photo"))
            index += 1
            continue
        count = plan.get("count") or 1
        items = [item for item in map(_queue_item, paths[index:index + count]) if item]
        style = compositions.FORMATS.get(plan.get("style") or "")
        image = _queue_item(plan["image"]) if plan.get("image") else None
        slots.append({"type": "composition", "pending": not plan.get("count"), "items": items,
                      "label": _(style[0]) if style else _("Composition"), "image": image["thumb"] if image else None})
        index += count
    return slots


@app.route('/api/slideshow/queue', methods=['POST'])
@login_required
def slideshow_queue_reorder():
    data = request.get_json(silent=True) or {}
    order = data.get("order")
    if not isinstance(order, list) or not order:
        return jsonify({"success": False, "message": _("Ordre invalide.")}), 400
    paths = []
    for relative in order:
        path = (STATIC_DIR / str(relative)).resolve()
        if STATIC_DIR not in path.parents or not path.is_file():  # uniquement des médias existants du dossier static
            return jsonify({"success": False, "message": _("Ordre invalide.")}), 400
        paths.append(path)
    play_queue.request_order(paths)
    if data.get("play_now"):
        _send_slideshow_signal(signal.SIGUSR1)  # passer tout de suite au premier média demandé
    return jsonify({"success": True, "message": _("Nouvel ordre enregistré.")})


# --- Disposition du diaporama (choix rapide : photo unique, un format précis, compositions...) ---

@app.route('/api/slideshow/layout', methods=['GET'])
@login_required
def get_slideshow_layout():
    return jsonify({"success": True, "layout": load_config().get("layout_override", layout_engine.AUTO)})


@app.route('/api/slideshow/layout', methods=['POST'])
@login_or_internal_required
def set_slideshow_layout():
    choice = (request.get_json(silent=True) or {}).get("layout", layout_engine.AUTO)
    if not layout_engine.is_valid_choice(choice):
        return jsonify({"success": False, "message": _("Disposition inconnue.")}), 400
    config = dict(load_config())
    config["layout_override"] = choice
    save_config(config)
    if is_slideshow_running():
        restart_slideshow_for_update()
    return jsonify({"success": True, "message": _("Disposition appliquée au diaporama.")})
