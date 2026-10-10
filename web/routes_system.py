"""Système : arrêt, redémarrage, mises à jour, réseau, sauvegarde, logs et informations."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _


@app.route('/shutdown', methods=['POST'])
@admin_required
def shutdown():
    subprocess.run(['sudo', '-n', 'shutdown', 'now'], check=False)
    return redirect(url_for('configure'))


@app.route('/reboot', methods=['POST'])
@admin_required
def reboot():
    subprocess.run(['sudo', '-n', 'reboot'], check=False)
    return redirect(url_for('configure'))


@app.route('/system_reboot', methods=['POST'])
@admin_required
def system_reboot():
    """Affiche la page de redémarrage et lance le reboot après 1 seconde."""
    # Supprimer le fichier log si coché
    if request.form.get('delete_logs'):
        log_file = BASE_DIR / 'logs' / 'pimmich.log'
        if os.path.exists(log_file):
            try:
                os.remove(log_file)
                print("pimmich.log supprimé")
            except Exception as e:
                print(f"Erreur suppression log: {e}")    
    
    
    
    
    return render_template('rebooting.html.jinja')


@app.route('/update', methods=['GET'])
@admin_required
def update_view():
    """Affiche la page dédiée au processus de mise à jour."""
    return render_template('update.html.jinja')


@app.route('/rebooting', methods=['GET'])
def rebooting():
    """Affiche la page de redémarrage (accessible en GET pour les redirections)."""
    return render_template('rebooting.html.jinja')


@app.route('/api/trigger_reboot', methods=['POST'])
@admin_required
def trigger_reboot():
    """Lance la commande de redémarrage système."""
    try:
        # Lancer le reboot en arrière-plan pour que la réponse HTTP puisse être envoyée
        import threading
        def delayed_reboot():
            time.sleep(1)  # Attendre 1 seconde pour que la page se charge
            subprocess.run(['sudo', '-n', 'reboot'], check=False)
        
        reboot_thread = threading.Thread(target=delayed_reboot)
        reboot_thread.daemon = True
        reboot_thread.start()
        
        return jsonify({"success": True, "message": "Redémarrage initié"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/switch_to_desktop', methods=['POST'])
@admin_required
def switch_to_desktop():
    """Quitte le mode cadre photo et repasse sur le bureau Raspberry Pi OS au prochain démarrage.

    Annule les étapes 9 et 10 de setup.sh : démarrage en mode bureau (auto-login)
    au lieu de la console, et suppression du lancement automatique de Sway.
    """
    # Le bureau n'existe que sur Raspberry Pi OS "with desktop" (pas sur la version Lite)
    if not (shutil.which('lightdm') or os.path.exists('/usr/sbin/lightdm')):
        return jsonify({"success": False, "message": _("Aucun environnement de bureau détecté (Raspberry Pi OS Lite ?). Opération annulée.")}), 400

    bash_profile = os.path.join(os.path.expanduser('~'), '.bash_profile')
    original_profile = None
    try:
        # 1. Retirer le lancement automatique de Sway du .bash_profile
        if os.path.exists(bash_profile):
            with open(bash_profile, 'r') as f:
                original_profile = f.read()
            new_profile = re.sub(
                r'if \[\[ -z \$DISPLAY \]\] && \[\[ \$\(tty\) = /dev/tty1 \]\]; then\s*\n\s*exec sway\s*\n\s*fi\s*\n?',
                '', original_profile)
            if new_profile != original_profile:
                shutil.copy2(bash_profile, bash_profile + '.pimmich.bak')
                with open(bash_profile, 'w') as f:
                    f.write(new_profile)

        # 2. Démarrage en mode bureau avec auto-login (B4)
        result = subprocess.run(['sudo', '-n', 'raspi-config', 'nonint', 'do_boot_behaviour', 'B4'],
                                capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "raspi-config a échoué")
    except Exception as e:
        # Restaurer le .bash_profile pour ne pas laisser le système dans un état intermédiaire
        if original_profile is not None:
            with open(bash_profile, 'w') as f:
                f.write(original_profile)
        logger.error(f"Erreur lors du passage au bureau Raspberry Pi OS : {e}")
        return jsonify({"success": False, "message": str(e)}), 500

    # 3. Redémarrer en arrière-plan pour que la réponse HTTP puisse être envoyée
    def delayed_reboot():
        time.sleep(2)
        subprocess.run(['sudo', '-n', 'reboot'], check=False)
    threading.Thread(target=delayed_reboot, daemon=True).start()

    return jsonify({"success": True, "message": _("Le système redémarre sur le bureau Raspberry Pi OS. Pimmich ne se lancera plus automatiquement.")})


@app.route('/api/ping', methods=['GET'])
def ping():
    """Endpoint simple pour vérifier que le serveur est disponible."""
    # Calcul de la plage d'activité pour informer la page d'update
    config = load_config()
    now = datetime.now()
    is_weekend = now.weekday() >= 5
    if is_weekend:
        start_str = config.get("active_start_weekend", config.get("active_start", "07:00"))
        end_str = config.get("active_end_weekend", config.get("active_end", "23:00"))
    else:
        start_str = config.get("active_start_weekday", config.get("active_start", "07:00"))
        end_str = config.get("active_end_weekday", config.get("active_end", "22:00"))
    
    is_active = True
    try:
        start_t = datetime.strptime(start_str, "%H:%M").time()
        end_t = datetime.strptime(end_str, "%H:%M").time()
        now_t = now.time()
        is_active = (start_t <= now_t <= end_t) if start_t <= end_t else (now_t >= start_t or now_t <= end_t)
    except: pass

    return jsonify({
        "status": "ok",
        "instance": APP_INSTANCE_ID,
        "slideshow_running": is_slideshow_running(),
        "is_active_hours": is_active
    })


@app.route('/restart_app', methods=['POST'])
@admin_required
def restart_app():
    """Redémarre uniquement l'application web Flask."""
    # Code de sortie spécial pour indiquer au script shell de redémarrer l'application
    RESTART_EXIT_CODE = 42
    def do_restart():
        # Laisser le temps au navigateur de recevoir la réponse avant de tuer le processus
        time.sleep(2)
        print("[Restart] Redémarrage de l'application web demandé par l'utilisateur.")
        sys.exit(RESTART_EXIT_CODE)
        os._exit(RESTART_EXIT_CODE)

    # Lancer le redémarrage dans un thread pour ne pas bloquer la réponse HTTP
    restart_thread = threading.Thread(target=do_restart)
    restart_thread.start()
    
    flash(_("L'application web redémarre... La page sera inaccessible pendant quelques instants."), "success")
    return redirect(url_for('configure'))


# --- NOUVELLES ROUTES POUR LE CONTRÔLE VOCAL AVANCÉ ---

@app.route('/api/system/shutdown', methods=['POST'])
@login_or_internal_required
def system_shutdown():
    """Éteint le système (commande vocale ou administrateur)."""
    # Derrière nginx, toutes les requêtes semblent venir de 127.0.0.1 : on s'appuie sur le jeton interne ou le rôle
    if not is_internal_request(request) and not is_admin():
        return jsonify({"success": False, "message": "Action réservée aux administrateurs."}), 403
    print("Arrêt du système demandé via API.")
    subprocess.run(['sudo', '-n', 'shutdown', '-h', 'now'])
    return jsonify({"success": True, "message": "Arrêt en cours."})


@app.route('/save_wifi_settings', methods=['POST'])
@admin_required
def save_wifi_settings():
    ssid = request.form.get('wifi_ssid')
    password = request.form.get('wifi_password')
    country = request.form.get('wifi_country') # Get the country code

    if not ssid or not country: # Country is now required
        flash(_("Le SSID et le pays Wi-Fi sont obligatoires."), "danger")
        return redirect(url_for('configure'))

    try:
        # Sauvegarder les paramètres dans la config.json
        config = load_config()
        config['wifi_ssid'] = ssid
        config['wifi_password'] = password
        config['wifi_country'] = country # Save country to config
        save_config(config)

        # Appliquer les paramètres Wi-Fi au système
        set_wifi_config(ssid, password, country) # Pass country to the function
        flash(_("Paramètres Wi-Fi appliqués. Le service réseau a été redémarré pour forcer la connexion. Veuillez patienter une minute et vérifier le statut."), "success")
    except Exception as e:
        flash(_("Erreur lors de l'application des paramètres Wi-Fi : %(error)s", error=e), "danger")
    return redirect(url_for('configure'))


@app.route('/api/wifi_status')
@login_required
def get_wifi_status_api():
    """Retourne l'état actuel de la connexion Wi-Fi."""
    status = get_wifi_status()
    return jsonify({"success": True, **status})


@app.route('/api/interface_status/<interface_name>')
@login_required
def get_interface_status_api(interface_name):
    """Retourne l'état d'une interface réseau spécifique."""
    # Valider le nom de l'interface pour la sécurité
    if not re.match(r'^[a-zA-Z0-9-]+$', interface_name):
        return jsonify({"success": False, "message": "Nom d'interface invalide."}), 400
    
    status = get_interface_status(interface_name)
    return jsonify({"success": True, **status})


@app.route('/api/set_interface_state', methods=['POST'])
@admin_required
def set_interface_state_api():
    """Active ou désactive une interface réseau."""
    data = request.get_json()
    interface_name = data.get('interface')
    state = data.get('state')

    if not interface_name or not state in ['up', 'down']:
        return jsonify({"success": False, "message": "Données invalides."}), 400
    
    if not re.match(r'^[a-zA-Z0-9-]+$', interface_name):
        return jsonify({"success": False, "message": "Nom d'interface invalide."}), 400

    try:
        set_interface_state(interface_name, state)
        return jsonify({"success": True, "message": f"L'interface {interface_name} a été passée à l'état '{state}'."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# --- Lancement de l'application ---

@app.route('/api/backup_settings')
@admin_required
def backup_settings_api():
    """Permet de télécharger le fichier de configuration actuel."""
    try:
        backup_name = f'pimmich_backup_{datetime.now().strftime("%Y-%m-%d")}.json'
        return send_from_directory('config', 'config.json', as_attachment=True, download_name=backup_name)
    except FileNotFoundError:
        flash(_("Le fichier de configuration n'a pas été trouvé."), "danger")
        return redirect(url_for('configure'))


@app.route('/api/restore_settings', methods=['POST'])
@admin_required
def restore_settings_api():
    """Restaure la configuration à partir d'un fichier de sauvegarde."""
    if 'backup_file' not in request.files:
        flash(_("Aucun fichier de sauvegarde sélectionné."), "warning")
        return redirect(url_for('configure'))

    file = request.files['backup_file']
    if file.filename == '':
        flash(_("Aucun fichier de sauvegarde sélectionné."), "warning")
        return redirect(url_for('configure'))

    try:
        # Lire et valider le contenu JSON
        content = file.stream.read().decode("utf-8")
        new_config_data = json.loads(content)

        # Sauvegarder la nouvelle configuration
        save_config(new_config_data)
        flash(_("Configuration restaurée avec succès ! Le diaporama va redémarrer pour appliquer les changements."), "success")
    except (json.JSONDecodeError, UnicodeDecodeError):
        flash(_("Fichier de sauvegarde invalide ou corrompu. Ce n'est pas un fichier JSON valide."), "danger")
    except Exception as e:
        flash(_("Erreur lors de la restauration : %(error)s", error=e), "danger")
    
    return redirect(url_for('configure'))


@app.route('/api/system_info')
@login_required
def get_system_info_api():
    """Retourne les informations système (température, CPU, RAM, stockage) en JSON."""
    try:
        # Obtenir l'heure une seule fois pour les deux mesures
        current_time_str = datetime.now().strftime("%H:%M:%S")

        # Température CPU
        current_temp_float = get_cpu_temperature()
        
        # Ajouter la mesure à l'historique si elle est valide
        if current_temp_float is not None:
            cpu_temp_history.append({
                "time": current_time_str,
                "temp": current_temp_float
            })
            cpu_temp_str = f"{current_temp_float:.1f}°C"
        else:
            cpu_temp_str = "N/A"

        # Utilisation CPU
        # interval=None le rend non-bloquant et compare à l'appel précédent. Idéal pour le polling.
        current_cpu_usage_float = psutil.cpu_percent(interval=None)
        cpu_usage_history.append({
            "time": current_time_str,
            "usage": current_cpu_usage_float
        })
        cpu_usage_str = f"{current_cpu_usage_float}%"

        # Utilisation RAM
        ram = psutil.virtual_memory()
        ram_usage_percent_float = ram.percent
        ram_usage_history.append({
            "time": current_time_str,
            "usage": ram_usage_percent_float
        })
        ram_usage_str = f"{ram.percent}% ({ram.used / (1024**3):.1f}GB / {ram.total / (1024**3):.1f}GB)"

        # Utilisation Disque
        disk = psutil.disk_usage('/')
        disk_usage_percent_float = disk.percent
        disk_usage_history.append({
            "time": current_time_str,
            "usage": disk_usage_percent_float
        })
        disk_usage_str = f"{disk.percent}% ({disk.used / (1024**3):.1f}GB / {disk.total / (1024**3):.1f}GB)"

        return jsonify({
            "success": True,
            "cpu_temp": cpu_temp_str,
            "cpu_usage": cpu_usage_str,
            "ram_usage": ram_usage_str,
            "disk_usage": disk_usage_str,
            "cpu_temp_history": list(cpu_temp_history),
            "cpu_usage_history": list(cpu_usage_history),
            "ram_usage_history": list(ram_usage_history),
            "disk_usage_history": list(disk_usage_history) # Ajouter l'historique pour le graphique
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route('/api/list_logs', methods=['GET'])
@admin_required
def list_logs():
    """Retourne la liste des fichiers de log qui existent réellement."""
    available_logs = []
    # Itérer dans un ordre défini pour une interface utilisateur cohérente
    log_order = ["app", "voice_control_stdout", "voice_control_stderr"]
    for key in log_order:
        info = LOG_FILES_MAP.get(key)
        if info and os.path.exists(info["path"]):
            # Traduire la clé du nom pendant la requête
            available_logs.append({"key": key, "name": _(info["name_key"])})
    return jsonify({"success": True, "logs": available_logs})


@app.route('/api/logs')
@admin_required
def get_logs_api():
    """Retourne le contenu d'un fichier de log spécifié."""
    log_type = request.args.get('type', 'app')
    
    log_info = LOG_FILES_MAP.get(log_type)
    if not log_info:
        return jsonify({"success": False, "message": "Type de log invalide."})

    log_file_path = log_info['path']

    try:
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            # Lire seulement les 500 dernières lignes pour améliorer les performances
            # sur les fichiers de log volumineux, ce qui rend l'interface plus réactive.
            lines = f.readlines()
            content = "".join(lines[-500:])
        return jsonify({"success": True, "content": content})
    except FileNotFoundError:
        # C'est un cas normal si le log n'a pas encore été créé. On retourne un contenu vide.
        return jsonify({"success": True, "content": ""})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route('/api/clear_logs', methods=['POST'])
@admin_required
def clear_logs_api():
    """Efface le contenu d'un fichier de log spécifié."""
    data = request.get_json()
    log_type = data.get('type')

    log_info = LOG_FILES_MAP.get(log_type)
    if not log_info:
        return jsonify({"success": False, "message": "Type de log invalide."}), 400
    log_file_path = log_info['path']

    try:
        if os.path.exists(log_file_path):
            with open(log_file_path, 'w') as f:
                f.truncate(0) # Efface le contenu du fichier
            return jsonify({"success": True, "message": f"Le log '{log_type}' a été effacé."})
        else:
            return jsonify({"success": False, "message": f"Fichier de log '{log_file_path}' non trouvé."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/upstream_status', methods=['GET'])
@admin_required
def upstream_status():
    """Indique les nouveautés disponibles sur le dépôt d'origine de Pimmich et sur le dépôt suivi."""
    try:
        return jsonify({"success": True, **check_upstream()})
    except Exception as e:
        logger.warning(f"[Upstream] Vérification impossible : {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/update_app', methods=['GET'])
@admin_required
def update_app():
    """
    Met à jour l'application depuis GitHub et la redémarre.
    Utilise Server-Sent Events pour donner un feedback en direct.
    """
    @stream_with_context
    def generate():
        def stream_event(data):
            """Formate les données en événement Server-Sent Event (SSE)."""
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        update_script_path = Path(app.root_path) / 'update_script.sh'

        if not update_script_path.exists():
            yield stream_event({"type": "error", "message": "Le script de mise à jour 'update_script.sh' est introuvable."})
            return

        try:
            os.chmod(update_script_path, 0o755)
        except OSError as e:
            yield stream_event({"type": "error", "message": f"Impossible de rendre le script de mise à jour exécutable : {e}"})
            return

        yield stream_event({"type": "info", "percent": 5, "message": "Lancement du script de mise à jour..."})

        process = subprocess.Popen(
            ['/bin/bash', str(update_script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            encoding='utf-8'
        )

        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if not line: continue

            if line.startswith("STEP:PULL:"):
                yield stream_event({"type": "info", "percent": 25, "message": line.replace("STEP:PULL:", "").strip()})
            elif line.startswith("STEP:PIP:"):
                yield stream_event({"type": "info", "percent": 75, "message": line.replace("STEP:PIP:", "").strip()})
            elif line.startswith("STEP:RESTART:"):
                yield stream_event({"type": "info", "percent": 95, "message": line.replace("STEP:RESTART:", "").strip()})
            else:
                yield stream_event({"type": "info", "message": line})

        process.stdout.close()
        return_code = process.wait()

        if return_code == 0:
            yield stream_event({"stage": "RESTART", "percent": 100, "message": "Mise à jour terminée. Redémarrage du système en cours..."})
            def restart_server():
                time.sleep(10)
                print("[Update] Redémarrage du système suite à la mise à jour...")
                subprocess.run(['sudo', '-n', 'reboot'], check=False)
            
            restart_thread = threading.Thread(target=restart_server)
            restart_thread.start()
        else:
            yield stream_event({"type": "error", "message": f"La mise à jour a échoué. Le script a retourné le code d'erreur {return_code}."})

    return Response(generate(), mimetype='text/event-stream', headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})


@app.route('/api/expand_filesystem', methods=['POST'])
@admin_required
def expand_filesystem():
    """
    Lance le script qui étend le système de fichiers racine.
    """
    @stream_with_context
    def generate():
        def stream_event(data):
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        script_path = Path(app.root_path) / 'utils' / 'expand_filesystem.sh'

        if not script_path.exists():
            yield stream_event({"type": "error", "message": "Le script 'utils/expand_filesystem.sh' est introuvable."})
            return

        try:
            os.chmod(script_path, 0o755)
        except OSError as e:
            yield stream_event({"type": "error", "message": f"Impossible de rendre le script exécutable : {e}"})
            return

        command = ['/bin/bash', str(script_path)]

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            encoding='utf-8'
        )

        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if not line: continue

            parts = line.split(':', 2)
            if len(parts) == 3:
                yield stream_event({"type": parts[0], "stage": parts[1], "message": parts[2]})
            else:
                yield stream_event({"type": "raw", "message": line})

        process.stdout.close()
        process.wait()

    return Response(generate(), mimetype='text/event-stream', headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})


@app.route('/api/scan_wifi', methods=['GET'])
@admin_required
def scan_wifi():
    """Scanne les réseaux Wi-Fi disponibles et les retourne en JSON."""
    try:
        # --- AMÉLIORATION POUR PI ZERO 2W ---
        # Étape 1: Forcer un nouveau scan de manière plus robuste.
        # Cette commande ne retourne rien mais déclenche le scan en arrière-plan.
        # On ignore les erreurs au cas où un scan serait déjà en cours.
        # C'est plus fiable sur du matériel moins performant comme le Pi Zero 2W.
        subprocess.run(['sudo', '-n', 'nmcli', 'device', 'wifi', 'rescan'], timeout=15, check=False)
        
        # Attendre un peu que le scan se termine. 5 secondes est un bon compromis.
        time.sleep(5)

        # Étape 2: Lister les résultats du scan qui vient d'être fait.
        cmd = ['sudo', '-n', 'nmcli', '--terse', '--fields', 'SSID,SIGNAL,SECURITY', 'dev', 'wifi', 'list']
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
        
        output = result.stdout.strip()
        
        # Éviter les doublons de SSID, ne garder que le plus fort signal
        seen_ssids = {}

        for line in output.split('\n'):
            if not line:
                continue
            
            # Gérer les SSID qui peuvent contenir des ':' en les échappant.
            # nmcli --terse échappe les ':' avec '\:'. On ne peut pas juste splitter.
            # La méthode la plus simple est de joindre toutes les parties sauf les deux dernières.
            parts = line.split(':')
            if len(parts) < 3:
                continue
            
            security = parts[-1]
            signal = int(parts[-2])
            ssid = ":".join(parts[:-2]).replace('\\:', ':')

            if not ssid: # Ignorer les SSID vides (réseaux cachés)
                continue

            # Si on a déjà vu ce SSID, on garde seulement celui avec le meilleur signal
            if ssid not in seen_ssids or signal > seen_ssids[ssid]['signal']:
                seen_ssids[ssid] = {
                    "ssid": ssid,
                    "signal": signal,
                    "security": security if security else "Open"
                }
        
        networks = sorted(seen_ssids.values(), key=lambda x: x['signal'], reverse=True)

        return jsonify({"success": True, "networks": networks})

    except FileNotFoundError:
        return jsonify({"success": False, "message": "La commande 'nmcli' est introuvable. NetworkManager est-il installé et actif ?"}), 500
    except subprocess.CalledProcessError as e:
        return jsonify({"success": False, "message": f"Erreur lors du scan Wi-Fi : {e.stderr}"}), 500
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "message": "Le scan Wi-Fi a pris trop de temps (timeout)."}), 500
    except Exception as e:
        return jsonify({"success": False, "message": f"Erreur inattendue : {str(e)}"}), 500
