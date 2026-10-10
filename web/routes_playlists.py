"""Playlists et musiques de fond."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from utils import layout_engine
from web.core import _


# --- API pour la gestion des Playlists ---

@app.route('/api/playlists', methods=['GET'])
@login_or_internal_required
def get_playlists():
    """Retourne la liste de toutes les playlists."""
    playlists = load_playlists()
    return jsonify(playlists)


@app.route('/api/playlists', methods=['POST'])
@login_required
def create_playlist():
    """Crée une nouvelle playlist."""
    data = request.get_json()
    name = data.get('name')
    music_file = data.get('music_file') # Cette ligne doit être en dehors du bloc 'if'
    if not name or not name.strip():
        return jsonify({"success": False, "message": "Le nom de la playlist est requis."}), 400

    playlists = load_playlists()
    
    # Vérifier si une playlist avec le même nom existe déjà
    if any(p['name'].lower() == name.strip().lower() for p in playlists):
        return jsonify({"success": False, "message": "Une playlist avec ce nom existe déjà."}), 409

    new_playlist = {
        "id": secrets.token_hex(8),
        "name": name.strip(),
        "photos": [],
        "music_file": music_file
    }
    playlists.append(new_playlist)
    save_playlists(playlists)
    return jsonify({"success": True, "playlist": new_playlist}), 201


@app.route('/api/playlists/<playlist_id>/update_music', methods=['POST'])
@login_required
def update_playlist_music(playlist_id):
    """Met à jour le fichier musical d'une playlist existante."""
    data = request.get_json()
    music_file = data.get('music_file')

    playlists = load_playlists()
    found = False
    for playlist in playlists:
        if playlist.get('id') == playlist_id:
            playlist['music_file'] = music_file
            found = True
            break
    
    if not found:
        return jsonify({"success": False, "message": "Playlist non trouvée."}), 404

    save_playlists(playlists)
    return jsonify({"success": True, "message": "Musique de la playlist mise à jour."})


@app.route('/api/playlists/<playlist_id>/layout', methods=['POST'])
@login_or_internal_required
def update_playlist_layout(playlist_id):
    """Disposition propre à une playlist (« auto » : comme le diaporama)."""
    layout = (request.get_json(silent=True) or {}).get('layout', layout_engine.AUTO)
    if not layout_engine.is_valid_choice(layout):
        return jsonify({"success": False, "message": _("Disposition inconnue.")}), 400
    playlists = load_playlists()
    for playlist in playlists:
        if playlist.get('id') == playlist_id:
            playlist['layout'] = layout
            save_playlists(playlists)
            return jsonify({"success": True, "message": _("Disposition de la playlist enregistrée.")})
    return jsonify({"success": False, "message": "Playlist non trouvée."}), 404


@app.route('/api/music_files', methods=['GET'])
@login_required
def get_music_files():
    """Returns a list of available music files in static/music/."""
    music_dir = BASE_DIR / "static" / "music"
    music_files = []
    if music_dir.exists():
        for f in music_dir.iterdir():
            if f.is_file() and f.suffix.lower() in ['.mp3', '.wav']:
                music_files.append(f.name)
    return jsonify({"success": True, "files": sorted(music_files)})


@app.route('/api/music_files/<filename>', methods=['DELETE'])
@login_required
def delete_music_file(filename):
    """Supprime un fichier musical de static/music/."""
    # Le nom de fichier est déjà sécurisé lors de l'upload et est passé tel quel depuis la liste des fichiers.
    # secure_filename() est donc inutile ici et peut causer des problèmes si le nom de fichier
    # n'est pas exactement le même après sécurisation (ex: espaces vs underscores).
    music_path = BASE_DIR / "static" / "music" / filename
    
    if music_path.exists() and music_path.is_file():
        try:
            music_path.unlink()
            logger.info(f"🎵 Musique supprimée : {filename}")
            return jsonify({"success": True, "message": f"Fichier '{filename}' supprimé avec succès."})
        except Exception as e:
            return jsonify({"success": False, "message": f"Erreur lors de la suppression : {str(e)}"}), 500
    else:
        logger.warning(f"❌ Tentative de suppression de fichier introuvable: {music_path}")
        return jsonify({"success": False, "message": "Fichier introuvable."}), 404


@app.route('/api/upload_music', methods=['POST'])
@login_required
def upload_music():
    """Télécharge un nouveau fichier musical vers static/music/."""
    if 'music_file' not in request.files:
        return jsonify({"success": False, "message": "Aucun fichier sélectionné."}), 400
    
    file = request.files['music_file']
    if file.filename == '':
        return jsonify({"success": False, "message": "Aucun fichier sélectionné."}), 400
    
    if file and file.filename.lower().endswith(('.mp3', '.wav')):
        filename = secure_filename(file.filename)
        music_dir = BASE_DIR / "static" / "music"
        music_dir.mkdir(parents=True, exist_ok=True)
        file.save(music_dir / filename)
        logger.info(f"🎵 Nouvelle musique importée : {filename}")
        return jsonify({"success": True, "message": f"Fichier '{filename}' téléchargé avec succès."})
    else:
        return jsonify({"success": False, "message": "Format de fichier non supporté. MP3 ou WAV uniquement."}), 400


@app.route('/api/playlists/<playlist_id>', methods=['DELETE'])
@login_or_internal_required
def delete_playlist(playlist_id):
    """Supprime une playlist."""
    playlists = load_playlists()
    playlists = [p for p in playlists if p.get('id') != playlist_id]
    save_playlists(playlists)
    return jsonify({"success": True})


@app.route('/api/playlists/<playlist_id>/rename', methods=['POST'])
@login_or_internal_required
def rename_playlist(playlist_id):
    """Renomme une playlist."""
    data = request.get_json()
    new_name = data.get('name')
    if not new_name or not new_name.strip():
        return jsonify({"success": False, "message": "Le nouveau nom ne peut pas être vide."}), 400

    playlists = load_playlists()
    
    if any(p['name'].lower() == new_name.strip().lower() and p.get('id') != playlist_id for p in playlists):
        return jsonify({"success": False, "message": "Une autre playlist avec ce nom existe déjà."}), 409

    found = False
    for playlist in playlists:
        if playlist.get('id') == playlist_id:
            playlist['name'] = new_name.strip()
            found = True
            break
    
    save_playlists(playlists)
    return jsonify({"success": True, "message": "Playlist renommée."})


@app.route('/api/playlists/<playlist_id>/photos', methods=['POST'])
@login_or_internal_required
def add_photo_to_playlist(playlist_id):
    """Ajoute une photo à une playlist."""
    data = request.get_json()
    photo_path = data.get('photo_path')
    if not photo_path:
        return jsonify({"success": False, "message": "Chemin de la photo manquant."}), 400

    playlists = load_playlists()
    for playlist in playlists:
        if playlist.get('id') == playlist_id:
            if photo_path not in playlist['photos']:
                playlist['photos'].append(photo_path)
            save_playlists(playlists)
            return jsonify({"success": True})
    return jsonify({"success": False, "message": "Playlist non trouvée."}), 404


@app.route('/api/playlists/<playlist_id>/photos/<path:photo_path>', methods=['DELETE'])
@login_or_internal_required
def remove_photo_from_playlist(playlist_id, photo_path):
    """Retire une photo d'une playlist."""
    playlists = load_playlists()
    for playlist in playlists:
        if playlist.get('id') == playlist_id:
            if photo_path in playlist['photos']:
                playlist['photos'].remove(photo_path)
            save_playlists(playlists)
            return jsonify({"success": True})
    return jsonify({"success": False, "message": "Playlist non trouvée."}), 404


@app.route('/api/playlists/<playlist_id>/reorder', methods=['POST'])
@login_or_internal_required
def reorder_playlist(playlist_id):
    """
    Réorganise les photos d'une playlist spécifique.
    Reçoit une liste de chemins de photos dans le nouvel ordre.
    """
    data = request.get_json()
    if not data or 'photos' not in data:
        return jsonify({"success": False, "message": "Données manquantes."}), 400

    new_photo_order = data['photos']

    try:
        playlists = load_playlists() 
        
        playlist_found = False
        for playlist in playlists:
            if playlist.get('id') == playlist_id:
                # Mesure de sécurité : on vérifie que le nouvel ordre contient
                # exactement les mêmes photos que l'ordre original, sans ajout ni suppression.
                original_photos_set = set(playlist['photos'])
                new_photos_set = set(new_photo_order)

                if original_photos_set != new_photos_set:
                     return jsonify({"success": False, "message": "Incohérence dans la liste des photos."}), 400

                playlist['photos'] = new_photo_order
                playlist_found = True
                break
        
        if not playlist_found:
            return jsonify({"success": False, "message": "Playlist non trouvée."}), 404

        save_playlists(playlists) 

        return jsonify({"success": True, "message": "Ordre de la playlist sauvegardé."})

    except Exception as e:
        logger.info(f"Erreur lors de la réorganisation de la playlist : {e}")
        return jsonify({"success": False, "message": "Erreur interne du serveur."}), 500
