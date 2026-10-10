"""Gestion des photos préparées : suppression, filtres, favoris, textes."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from utils import messages_manager


    
# --- Suppression photo ---
@app.route('/delete_photo/<path:photo>', methods=['DELETE'])
@login_required
def delete_photo(photo):
    try:
        # Le chemin relatif est de la forme 'source/nom_photo.jpg'
        photo_path_obj = Path('static/prepared') / photo
        
        # Déterminer les chemins des versions alternatives et de la sauvegarde
        polaroid_path = photo_path_obj.with_name(f"{photo_path_obj.stem}_polaroid.jpg")
        postcard_path = photo_path_obj.with_name(f"{photo_path_obj.stem}_postcard.jpg")
        backup_path = Path('static/.backups') / photo

        # Supprimer tous les fichiers associés
        if photo_path_obj.is_file():
            photo_path_obj.unlink()
        if polaroid_path.is_file():
            polaroid_path.unlink()
        if postcard_path.is_file():
            postcard_path.unlink()
        if backup_path.is_file():
            backup_path.unlink()
        
        # Google Drive : retirer aussi le fichier téléchargé, sinon il serait préparé à nouveau
        if photo_path_obj.parts[2:3] == ('gdrive',):
            remove_local_gdrive_media(photo_path_obj.stem)
        # Messages : oublier aussi le message correspondant
        if photo_path_obj.parts[2:3] == ('messages',):
            messages_manager.delete_message(photo_path_obj.stem)

        # Supprimer l'état du filtre pour cette photo
        states = load_filter_states()
        if states.pop(photo, None):
            save_filter_states(states)

        # Supprimer des favoris si la photo y était
        favorites = load_favorites()
        if photo in favorites:
            favorites.remove(photo)
            save_favorites(favorites)

        return '', 204
    except Exception as e:
        return str(e), 500


# --- Contrôle système ---

@app.route('/delete_source_photos/<source_name>', methods=['DELETE'])
@login_required
def delete_source_photos(source_name):
    """Supprime toutes les photos préparées pour une source donnée, y compris les sauvegardes."""
    if not re.match(r'^[a-zA-Z0-9_-]+$', source_name):
        return jsonify({"success": False, "message": "Nom de source invalide."}), 400

    prepared_dir = PREPARED_DIR / source_name
    backup_dir = BASE_DIR / 'static' / '.backups' / source_name

    try:
        if prepared_dir.is_dir():
            shutil.rmtree(prepared_dir)
            logger.info(f"Dossier préparé supprimé : {prepared_dir}")
        
        if backup_dir.is_dir():
            shutil.rmtree(backup_dir)
            logger.info(f"Dossier de sauvegarde supprimé : {backup_dir}")

        if source_name == 'gdrive':
            remove_local_gdrive_media()
        if source_name == 'messages':
            messages_manager.delete_all_messages()

        # Supprimer les états de filtre pour cette source
        states = load_filter_states()
        keys_to_delete = [key for key in states if key.startswith(f"{source_name}/")]
        if keys_to_delete:
            for key in keys_to_delete:
                del states[key]
            save_filter_states(states)
        return jsonify({"success": True, "message": "Photos supprimées."}), 200
    except Exception as e:
        logger.info(f"Erreur lors de la suppression des photos de la source {source_name}: {e}")
        return jsonify({"success": False, "message": f"Erreur serveur : {e}"}), 500


@app.route('/api/apply_filter', methods=['POST'])
@login_required
def apply_filter_api():
    """Applique un filtre à une photo préparée."""
    data = request.get_json()
    photo_relative_path = data.get('photo')
    filter_name = data.get('filter')

    if not photo_relative_path or not filter_name:
        return jsonify({"success": False, "message": "Chemin de la photo ou nom du filtre manquant."}), 400

    # Le chemin relatif est de la forme 'source/nom_photo.jpg'
    photo_full_path = PREPARED_DIR / photo_relative_path

    if not photo_full_path.is_file():
        return jsonify({"success": False, "message": f"Photo non trouvée : {photo_full_path}"}), 404

    try:
        apply_filter_to_image(str(photo_full_path), filter_name)
        # Le chemin ne change pas, mais on le renvoie pour forcer le rafraîchissement du cache du navigateur
        new_url = url_for('static', filename=f'prepared/{photo_relative_path}')
        return jsonify({"success": True, "message": "Filtre appliqué !", "new_path": new_url})
    except ValueError as e: # Pour les noms de filtres invalides
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        logger.info(f"Erreur lors de l'application du filtre : {e}")
        return jsonify({"success": False, "message": f"Erreur interne du serveur : {e}"}), 500


@app.route('/api/set_photo_filter', methods=['POST'])
@login_required
def set_photo_filter():
    """Enregistre la préférence de filtre pour une photo donnée."""
    data = request.get_json()
    photo_relative_path = data.get('photo')
    filter_name = data.get('filter')

    if not photo_relative_path or not filter_name:
        return jsonify({"success": False, "message": "Données manquantes."}), 400

    states = load_filter_states()
    
    if filter_name in ['none', 'original']:
        # Si le filtre est 'none' ou 'original', on le retire du fichier d'état
        states.pop(photo_relative_path, None)
    else:
        states[photo_relative_path] = filter_name
    
    save_filter_states(states)
    return jsonify({"success": True, "message": "Préférence de filtre enregistrée."})


@app.route('/api/toggle_favorite', methods=['POST'])
@login_required
def toggle_favorite():
    """Ajoute ou retire une photo de la liste des favoris."""
    data = request.get_json()
    photo_relative_path = data.get('photo')

    if not photo_relative_path:
        return jsonify({"success": False, "message": "Chemin de la photo manquant."}), 400

    favorites = load_favorites()
    is_currently_favorite = photo_relative_path in favorites

    if is_currently_favorite:
        favorites.remove(photo_relative_path)
    else:
        favorites.append(photo_relative_path)
    
    save_favorites(favorites)
    
    return jsonify({"success": True, "is_favorite": not is_currently_favorite})


@app.route('/api/set_polaroid_text', methods=['POST'])
@login_required
def set_polaroid_text():
    """Applique un texte à une image Polaroid."""
    data = request.get_json()
    photo_relative_path = data.get('photo')
    text = data.get('text', '')

    if not photo_relative_path:
        return jsonify({"success": False, "message": "Chemin de la photo manquant."}), 400

    try:
        # Construire le chemin vers la version polaroid de l'image
        path_obj = Path(photo_relative_path)
        polaroid_filename = f"{path_obj.stem}_polaroid.jpg"
        polaroid_relative_path = path_obj.with_name(polaroid_filename)
        polaroid_full_path = PREPARED_DIR / polaroid_relative_path

        if not polaroid_full_path.exists():
             return jsonify({"success": False, "message": "La version Polaroid de cette photo n'existe pas."}), 404

        # Appeler la fonction pour ajouter le texte
        add_text_to_polaroid(str(polaroid_full_path), text)

        # Sauvegarder le texte dans le fichier de config
        texts = load_polaroid_texts()
        if text and text.strip():
            texts[photo_relative_path] = text
        else:
            texts.pop(photo_relative_path, None) # Supprimer la clé si le texte est vide
        save_polaroid_texts(texts)

        return jsonify({"success": True, "message": "Texte mis à jour."})
    except Exception as e:
        return jsonify({"success": False, "message": f"Erreur interne du serveur : {e}"}), 500


@app.route('/api/set_image_text', methods=['POST'])
@login_required
def set_image_text():
    """Applique un texte à une image générique."""
    data = request.get_json()
    photo_relative_path = data.get('photo')
    text = data.get('text', '')

    if not photo_relative_path:
        return jsonify({"success": False, "message": "Chemin de la photo manquant."}), 400

    try:
        # Le chemin relatif est de la forme 'source/nom_photo.jpg'
        photo_full_path = PREPARED_DIR / photo_relative_path

        if not photo_full_path.is_file():
            return jsonify({"success": False, "message": f"Photo non trouvée : {photo_full_path}"}), 404

        # Photos : le texte est dessiné sur l'image ; vidéos : il est affiché en sous-titre pendant la lecture
        if photo_full_path.suffix.lower() not in VIDEO_EXTENSIONS:
            add_text_to_image(str(photo_full_path), text)

        # Sauvegarder le texte dans le fichier de config
        texts = load_text_states()
        if text and text.strip():
            texts[photo_relative_path] = text
        else:
            texts.pop(photo_relative_path, None) # Supprimer la clé si le texte est vide
        save_text_states(texts)

        return jsonify({"success": True, "message": "Texte mis à jour."})
    except Exception as e:
        return jsonify({"success": False, "message": f"Erreur interne du serveur : {e}"}), 500


# --- Tri automatique (photos floues, sombres, captures d'écran, rafales) ---

QUALITY_SWITCHES = ("auto_filter_enabled", "filter_blurry", "filter_dark", "filter_screenshots", "filter_bursts")


@app.route('/api/quality', methods=['GET'])
@login_required
def quality_api():
    from utils import photo_index, photo_quality
    from utils.dedup import hashes_for
    config = load_config()
    index = photo_index.load()
    hashes = None
    if config.get("filter_bursts", True):
        paths = [str(PREPARED_DIR / key) for key in index]
        hashes = {photo_index.key_for(p): h for p, h in hashes_for(paths).items() if h is not None}
    rejected = photo_quality.excluded(index, dict(config, auto_filter_enabled=True), hashes)  # liste même si le tri est en pause
    items = [{"path": key, "thumb": url_for("static", filename=f"prepared/{key}"), "reasons": reasons}
             for key, reasons in sorted(rejected.items()) if (PREPARED_DIR / key).is_file()]
    return jsonify({"success": True, "settings": {k: bool(config.get(k, True)) for k in QUALITY_SWITCHES},
                    "excluded": items, "kept": len(config.get("quality_keep") or [])})


@app.route('/api/quality', methods=['POST'])
@login_required
def quality_save_api():
    data = request.get_json(silent=True) or {}
    config = dict(load_config())
    for key in QUALITY_SWITCHES:
        if key in data:
            config[key] = bool(data[key])
    save_config(config)
    return jsonify({"success": True, "message": _("Tri automatique enregistré : appliqué au prochain tour du diaporama.")})


@app.route('/api/quality/keep', methods=['POST'])
@login_required
def quality_keep_api():
    """Remet une photo écartée dans le diaporama (ou annule)."""
    data = request.get_json(silent=True) or {}
    path = str(data.get("path", ""))
    base = PREPARED_DIR.resolve()
    if not (base / path).resolve().is_file() or base not in (base / path).resolve().parents:
        return jsonify({"success": False, "message": _("Photo introuvable.")}), 404
    config = dict(load_config())
    keep = set(config.get("quality_keep") or [])
    keep.add(path) if data.get("keep", True) else keep.discard(path)
    config["quality_keep"] = sorted(keep)
    save_config(config)
    return jsonify({"success": True, "message": _("Photo remise dans le diaporama.") if data.get("keep", True) else _("Photo de nouveau écartée.")})
