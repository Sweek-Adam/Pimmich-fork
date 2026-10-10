"""Contrôle vocal et périphériques audio."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _


@app.route('/api/audio_devices', methods=['GET'])
@login_required
def get_audio_devices():
    """Retourne la liste des périphériques d'entrée audio."""
    try:
        # L'importation peut échouer si les dépendances C (comme portaudio) sont manquantes
        import sounddevice as sd
        devices = sd.query_devices()
        input_devices = [
            {"index": i, "name": d['name'], "hostapi": sd.query_hostapis(d['hostapi'])['name']}
            for i, d in enumerate(devices) if d['max_input_channels'] > 0
        ]
        return jsonify({"success": True, "devices": input_devices})
    except Exception as e:
        # Renvoyer une erreur JSON claire au lieu de planter ou de renvoyer une liste vide.
        # Cela permet au frontend d'afficher un message d'erreur utile.
        error_message = f"Erreur API Audio: {type(e).__name__} - {e}"
        logger.info(f"[ERROR] in get_audio_devices: {error_message}") # Log pour le débogage côté serveur
        return jsonify({"success": False, "message": error_message, "devices": []})


@app.route('/api/voice_control/status', methods=['GET'])
@login_required
def get_voice_control_status():
    status_file = 'logs/voice_control_status.json'
    if not is_voice_control_running():
        return jsonify({"status": "stopped", "message": _("Le service est arrêté.")})
    
    if os.path.exists(status_file):
        try:
            with open(status_file, 'r') as f:
                return jsonify(json.load(f))
        except Exception as e:
            return jsonify({"status": "unknown", "message": f"Erreur lecture statut: {e}"})
    else:
        return jsonify({"status": "starting", "message": _("Démarrage du service...")})


@app.route('/api/audio_diagnostics', methods=['GET'])
@login_required
def get_audio_diagnostics():
    """Exécute des commandes de diagnostic audio et retourne le résultat."""
    diagnostics = {}
    try:
        # Commande lsusb pour lister les périphériques USB
        lsusb_result = subprocess.run(
            ['lsusb'], capture_output=True, text=True, check=False, timeout=5
        )
        diagnostics['lsusb'] = lsusb_result.stdout.strip() if lsusb_result.returncode == 0 else f"Erreur (code {lsusb_result.returncode}):\n{lsusb_result.stderr.strip()}"
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        diagnostics['lsusb'] = f"Erreur lors de l'exécution de 'lsusb': {e}"

    try:
        # Commande arecord -l pour lister les périphériques de capture audio
        arecord_result = subprocess.run(
            ['arecord', '-l'], capture_output=True, text=True, check=False, timeout=5
        )
        diagnostics['arecord'] = arecord_result.stdout.strip() if arecord_result.returncode == 0 else f"Erreur (code {arecord_result.returncode}):\n{arecord_result.stderr.strip()}"
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        diagnostics['arecord'] = f"Erreur lors de l'exécution de 'arecord -l': {e}"

    return jsonify({"success": True, "diagnostics": diagnostics})


@app.route('/api/voice_control/toggle', methods=['POST'])
@login_required
def toggle_voice_control():
    """Active ou désactive le service de contrôle vocal."""
    data = request.get_json()
    enabled = data.get('enabled')

    if enabled is None:
        return jsonify({"success": False, "message": _("Paramètre 'enabled' manquant.")}), 400

    try:
        # Mettre à jour la configuration
        config = load_config()
        config['voice_control_enabled'] = enabled
        save_config(config)

        # Démarrer ou arrêter le service
        if enabled:
            start_voice_control()
            message = _("Service de contrôle vocal activé.")
        else:
            stop_voice_control()
            message = _("Service de contrôle vocal désactivé.")
        
        return jsonify({"success": True, "message": message})
    except Exception as e:
        logger.error(f"Erreur lors du basculement du contrôle vocal : {e}", exc_info=True)
        return jsonify({"success": False, "message": _("Erreur interne du serveur : %(error)s", error=str(e))}), 500
