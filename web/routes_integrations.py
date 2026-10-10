"""Services externes : météo, marées, prise connectée, Telegram (tests et état)."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _


@app.route('/test-weather-api', methods=['POST'])
@login_required
def test_weather_api():
    """Teste la validité d'une clé API OpenWeatherMap et d'une ville."""
    data = request.get_json()
    api_key = data.get("api_key")
    city = data.get("city")

    if not api_key or not city:
        return jsonify({"success": False, "message": "La clé API et la ville sont requises."})

    # Utilise l'URL de l'API OpenWeatherMap pour le test
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"

    try:
        response = requests.get(url, timeout=5) # type: ignore
        if response.status_code == 200:
            return jsonify({"success": True, "message": "Clé API et ville valides !"})
        elif response.status_code == 401:
            # 401 Unauthorized est la réponse typique pour une clé invalide
            return jsonify({"success": False, "message": "Clé API invalide ou non activée."})
        elif response.status_code == 404:
            # 404 Not Found pour une ville invalide
            return jsonify({"success": False, "message": "Ville non trouvée."})
        else:
            return jsonify({"success": False, "message": f"Erreur de l'API: {response.status_code} - {response.text}"})
    except requests.exceptions.RequestException as e:
        # Gère les erreurs de connexion (timeout, pas d'internet, etc.)
        return jsonify({"success": False, "message": f"Erreur de connexion : {e}"})


@app.route('/test-stormglass-api', methods=['POST'])
@login_required
def test_stormglass_api():
    """Teste la connexion à l'API StormGlass."""
    data = request.get_json()
    api_key = data.get("api_key")
    lat = data.get("lat")
    lon = data.get("lon")

    if not all([api_key, lat, lon]):
        return jsonify({"success": False, "message": "La clé API, la latitude et la longitude sont requises."})

    try:
        # Test avec une très courte fenêtre de temps pour minimiser l'utilisation des données
        start_time_utc = datetime.utcnow()
        end_time_utc = start_time_utc + timedelta(hours=1)

        headers = {'Authorization': api_key}
        params = { 'lat': lat, 'lng': lon, 'start': start_time_utc.isoformat(), 'end': end_time_utc.isoformat() }
        
        response = requests.get('https://api.stormglass.io/v2/tide/extremes/point', params=params, headers=headers, timeout=10)

        if response.status_code == 200:
            return jsonify({"success": True, "message": "Connexion à StormGlass réussie !"})
        elif response.status_code == 401:
            return jsonify({"success": False, "message": "Clé API invalide."})
        elif response.status_code == 402:
            return jsonify({"success": False, "message": "Crédits API épuisés ou plan inadapté."})
        elif response.status_code == 429:
            return jsonify({"success": False, "message": "Trop de requêtes. Veuillez réessayer plus tard."})
        else:
            try:
                error_details = response.json().get('errors', {})
                message = f"Erreur de l'API ({response.status_code}): {error_details}"
            except json.JSONDecodeError:
                message = f"Erreur de l'API ({response.status_code})"
            return jsonify({"success": False, "message": message})
    except requests.exceptions.RequestException as e:
        return jsonify({"success": False, "message": f"Erreur de connexion : {e}"})


@app.route('/api/test_smart_plug', methods=['POST'])
@login_required
def test_smart_plug():
    """Teste une URL de prise connectée."""
    data = request.get_json()
    url = data.get("url")

    if not url:
        return jsonify({"success": False, "message": "L'URL est requise."})

    try:
        # Utiliser un timeout court pour ne pas bloquer l'interface
        response = requests.post(url, timeout=5)
        if 200 <= response.status_code < 300:
            return jsonify({"success": True, "message": f"Succès ! La prise a répondu avec le code {response.status_code}."})
        else:
            return jsonify({"success": False, "message": f"Échec. La prise a répondu avec une erreur : {response.status_code}."})
    except requests.exceptions.Timeout:
        return jsonify({"success": False, "message": "Échec. La requête a expiré (timeout). Vérifiez l'adresse IP de la prise."})
    except requests.exceptions.RequestException as e:
        return jsonify({"success": False, "message": f"Échec. Erreur de connexion : {e}"})


@app.route('/test-telegram', methods=['POST'])
@login_required
def test_telegram():
    """Teste si le token du bot Telegram est valide en appelant la méthode getMe."""
    data = request.get_json()
    token = data.get("token")

    if not token:
        return jsonify({"success": False, "message": _("Le token du bot est requis.")})

    url = f"https://api.telegram.org/bot{token}/getMe"

    try:
        response = requests.get(url, timeout=10)
        response_data = response.json()

        if response.status_code == 200 and response_data.get("ok"):
            bot_name = response_data.get("result", {}).get("first_name", "Inconnu")
            return jsonify({"success": True, "message": _("Token valide ! Le bot s'appelle '%(bot_name)s'.", bot_name=bot_name)})
        else:
            error_description = response_data.get('description', 'Réponse invalide de Telegram.')
            return jsonify({"success": False, "message": _("Échec de l'envoi : %(error)s", error=error_description)})
    except requests.exceptions.RequestException as e:
        return jsonify({"success": False, "message": _("Erreur de connexion : %(error)s", error=str(e))})


@app.route('/api/force_tide_update', methods=['POST'])
@login_required
def force_tide_update():
    """Force la mise à jour des données de marée en appelant l'API et en écrivant dans le cache."""
    config = load_config()
    api_key = config.get("stormglass_api_key")
    lat = config.get("tide_latitude")
    lon = config.get("tide_longitude")
    tide_cache_path = Path('cache/tides.json')

    if not all([api_key, lat, lon]):
        return jsonify({"success": False, "message": "Configuration StormGlass incomplète."})

    try:
        start_time_utc = datetime.utcnow()
        # --- MODIFICATION: Récupérer 7 jours de données pour être cohérent avec le slideshow ---
        end_time_utc = start_time_utc + timedelta(days=7)

        headers = {'Authorization': api_key}
        params = {'lat': lat, 'lng': lon, 'start': start_time_utc.isoformat(), 'end': end_time_utc.isoformat()}
        
        response = requests.get('https://api.stormglass.io/v2/tide/extremes/point', params=params, headers=headers, timeout=15)
        response.raise_for_status()
        
        extremes_data = response.json().get('data', [])
        now_utc = datetime.utcnow().replace(tzinfo=None)
        future_extremes = [e for e in extremes_data if datetime.fromisoformat(e['time'].replace('Z', '+00:00')).replace(tzinfo=None) > now_utc]

        if not future_extremes:
            return jsonify({"success": False, "message": "Aucune marée future trouvée par l'API."})

        # --- CORRECTION: Sauvegarder la liste complète des marées futures, pas juste les deux prochaines ---
        data_to_cache = {'data': future_extremes, 'timestamp': datetime.now().isoformat()}
        
        tide_cache_path.parent.mkdir(exist_ok=True)
        with open(tide_cache_path, 'w') as f:
            json.dump(data_to_cache, f, indent=2)

        return jsonify({"success": True, "message": "Données de marée mises à jour avec succès !"})

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 402:
            # --- AMÉLIORATION: Écrire un état de cooldown dans le cache ---
            cooldown_data = {'data': [], 'timestamp': datetime.now().isoformat(), 'cooldown': True}
            try:
                with open(tide_cache_path, 'w') as f: json.dump(cooldown_data, f, indent=2)
            except Exception: pass
            return jsonify({"success": False, "message": "Quota API StormGlass dépassé."})
        return jsonify({"success": False, "message": f"Erreur API ({e.response.status_code})."})
    except Exception as e:
        return jsonify({"success": False, "message": f"Erreur inattendue : {e}"})


@app.route('/telegram_update_status')
@login_required
def telegram_update_status():
    """Retourne l'état actuel du worker du bot Telegram."""
    return jsonify(telegram_status_manager.get_status())


@app.route('/telegram_bot_status')
@login_required
def telegram_bot_status():
    """Retourne un état simplifié du bot Telegram pour l'interface, avec un statut pour la couleur."""
    status_data = telegram_status_manager.get_status()
    message = status_data.get("status_message", "Inconnu")
    
    status = "unknown" # Statut par défaut
    msg_lower = message.lower()

    if "actif" in msg_lower:
        status = "running"
    elif "désactivé" in msg_lower or "non configuré" in msg_lower:
        status = "stopped"
    elif "erreur" in msg_lower:
        status = "error"
        
    return jsonify({
        "status": status,
        "status_message": message
    })


@app.route('/api/smart_plug/status', methods=['GET'])
@login_required
def get_smart_plug_status():
    """
    Interroge l'URL de statut de la prise connectée et retourne son état.
    """
    config = load_config()
    if not config.get("smart_plug_enabled") or not config.get("smart_plug_status_url"):
        return jsonify({"status": "disabled", "message": "Le statut de la prise n'est pas configuré."})

    status_url = config.get("smart_plug_status_url")
    token = config.get("home_assistant_token") # Le nom de la clé dans la config est 'home_assistant_token'

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = requests.get(status_url, headers=headers, timeout=5)
        response.raise_for_status() # Lève une exception pour les codes d'erreur HTTP (4xx ou 5xx)
        
        data = response.json()
        # Pour Home Assistant, l'état est dans la clé 'state'
        plug_state = data.get('state', 'unknown').lower()

        return jsonify({"status": plug_state, "message": f"État de la prise : {plug_state}"})

    except requests.exceptions.Timeout:
        return jsonify({"status": "unreachable", "message": "Timeout lors de la connexion à la prise."})
    except requests.exceptions.HTTPError as e:
        # Gérer spécifiquement les erreurs d'authentification pour un meilleur feedback
        if e.response.status_code == 401:
            return jsonify({"status": "error", "message": "Erreur 401: Non autorisé. Vérifiez votre token d'accès Home Assistant."})
        return jsonify({"status": "error", "message": f"Erreur HTTP: {str(e)}"})
    except requests.exceptions.RequestException as e:
        # Renvoyer une erreur plus explicite
        return jsonify({"status": "error", "message": f"Erreur de connexion: {str(e)}"})


@app.route('/api/tide_info')
@login_required
def get_tide_info_api():
    """Retourne les informations de marée depuis le fichier cache."""
    tide_cache_path = Path('cache/tides.json')
    if not tide_cache_path.exists():
        return jsonify({"success": False, "message": "Cache des marées non trouvé. Le diaporama doit tourner au moins une fois."})

    try:
        with open(tide_cache_path, 'r') as f:
            cache_data = json.load(f)
        
        last_update_iso = cache_data.get('timestamp')
        last_update_dt = datetime.fromisoformat(last_update_iso)
        last_update_str = last_update_dt.strftime('%d/%m/%Y à %H:%M:%S')
        api_status = "OK"
        formatted_tides = []

        if cache_data.get('cooldown'):
            api_status = f"En cooldown (quota API probablement atteint). Prochaine tentative après { (last_update_dt + timedelta(hours=12)).strftime('%H:%M') }."
        
        tides_data = cache_data.get('data', [])
        
        # --- CORRECTION: Gérer l'ancien format de cache (dictionnaire) ---
        if not tides_data or not isinstance(tides_data, list):
            api_status = "Aucune donnée de marée valide dans le cache. Forcez une mise à jour."
            if isinstance(tides_data, dict):
                api_status = "Ancien format de cache détecté. Forcez une mise à jour."
        else:
            today = datetime.now().date()
            tomorrow = today + timedelta(days=1)
            day_map = {'Mon':'Lun', 'Tue':'Mar', 'Wed':'Mer', 'Thu':'Jeu', 'Fri':'Ven', 'Sat':'Sam', 'Sun':'Dim'}

            # On ne prend que les 5 prochaines marées pour l'affichage web
            for tide in tides_data[:5]:
                tide_dt = datetime.fromisoformat(tide['time']).astimezone()
                tide_date = tide_dt.date()

                if tide_date == today: day_str = "Aujourd'hui"
                elif tide_date == tomorrow: day_str = "Demain"
                else: day_str = day_map.get(tide_dt.strftime('%a'), tide_dt.strftime('%a'))

                formatted_tides.append({
                    "type": "Pleine Mer" if tide['type'] == 'high' else "Basse Mer",
                    "time": f"{day_str} à {tide_dt.strftime('%H:%M')}",
                    "height": f"{tide['height']:.2f}m"
                })

        return jsonify({"success": True, "last_update": last_update_str, "tides": formatted_tides, "api_status": api_status})
    except (json.JSONDecodeError, KeyError, Exception) as e:
        return jsonify({"success": False, "message": f"Erreur lecture du cache: {str(e)}"})
