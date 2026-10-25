"""
Météo et marées du diaporama : prévisions (OpenWeatherMap), marées, icônes (avec leurs caches).
"""
import collections
import json
import logging
import os
import traceback
from datetime import datetime, timedelta
from pathlib import Path

import pygame
import requests


logger = logging.getLogger("pimmich.slideshow")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREPARED_BASE_DIR = Path(BASE_DIR) / "static" / "prepared"


ICONS_DIR = Path(BASE_DIR) / 'static' / 'icons'


TIDES_CACHE_FILE = Path(BASE_DIR) / 'cache' / 'tides.json'


_icon_cache = {} # Cache pour les icônes météo chargées


# --- Gestion de la météo ---
_weather_and_forecast_data = None


_last_weather_and_forecast_fetch = None


_weather_warning_printed = False


def get_weather_and_forecast(config):
    """Récupère la météo actuelle et les prévisions sur 3 jours."""
    global _weather_and_forecast_data, _last_weather_and_forecast_fetch, _weather_warning_printed
    
    api_key = config.get("weather_api_key")
    city = config.get("weather_city")
    units = config.get("weather_units", "metric")
    try:
        interval_minutes = int(config.get("weather_update_interval_minutes", 30))
    except (ValueError, TypeError):
        interval_minutes = 30

    if not api_key or not city:
        if not _weather_warning_printed:
            logger.info(f"[Weather] Clé API ou ville manquante. La météo est désactivée.")
            _weather_warning_printed = True
        return None

    now = datetime.now()
    if _last_weather_and_forecast_fetch and (now - _last_weather_and_forecast_fetch).total_seconds() < interval_minutes * 60:
        return _weather_and_forecast_data

    logger.info(f"[Weather] Récupération des prévisions météo...")
    _last_weather_and_forecast_fetch = now # Mettre à jour pour éviter les appels répétés en cas d'échec

    try:
        # Utilise l'API de prévision 5 jours / 3 heures (disponible en offre gratuite)
        url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={api_key}&units={units}&lang=fr"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        api_data = response.json()

        # --- Traitement des données pour obtenir une prévision par jour ---
        current_weather = api_data['list'][0]
        
        daily_forecasts = collections.defaultdict(lambda: {'temps': [], 'icons': []})
        
        # Grouper les données par jour
        for forecast in api_data['list']:
            day = datetime.fromtimestamp(forecast['dt']).strftime('%Y-%m-%d')
            daily_forecasts[day]['temps'].append(forecast['main']['temp'])
            daily_forecasts[day]['icons'].append((forecast['weather'][0]['icon'], forecast['dt_txt'], forecast['weather'][0]['description']))

        processed_forecast = []
        # Trier les jours et prendre les 3 prochains jours (en excluant aujourd'hui)
        today_str = datetime.now().strftime('%Y-%m-%d')
        sorted_days = sorted([day for day in daily_forecasts.keys() if day > today_str])[:3]

        day_map_fr = {'Mon':'Lun', 'Tue':'Mar', 'Wed':'Mer', 'Thu':'Jeu', 'Fri':'Ven', 'Sat':'Sam', 'Sun':'Dim'}

        for i, day_str in enumerate(sorted_days):
            day_data = daily_forecasts[day_str]
            
            if i == 0:
                day_name_fr = "Demain"
            else:
                day_name_en = datetime.strptime(day_str, '%Y-%m-%d').strftime('%a')
                day_name_fr = day_map_fr.get(day_name_en, day_name_en.upper())

            min_temp = round(min(day_data['temps']))
            max_temp = round(max(day_data['temps']))
            
            # Choisir une icône représentative (celle la plus proche de 13h)
            midday_icon = day_data['icons'][0][0] # icon
            midday_desc = day_data['icons'][0][2] # description
            min_hour_diff = 24
            for icon, dt_txt, desc in day_data['icons']:
                hour = int(dt_txt.split(' ')[1].split(':')[0])
                if abs(hour - 13) < min_hour_diff:
                    min_hour_diff = abs(hour - 13)
                    midday_icon = icon
                    midday_desc = desc

            processed_forecast.append({
                'day': day_name_fr,
                'min_temp': min_temp,
                'max_temp': max_temp,
                'icon': midday_icon,
                'description': midday_desc.capitalize()
            })
        
        _weather_and_forecast_data = {'current': current_weather, 'forecast': processed_forecast}
        try:
            from utils import sky
            coord = (api_data.get('city') or {}).get('coord') or {}
            sky.remember_location(coord.get('lat'), coord.get('lon'))  # lever / coucher du soleil, lune
        except Exception:
            pass
        logger.info(f"[Weather] Météo et prévisions mises à jour pour {city}.")
        return _weather_and_forecast_data

    except requests.exceptions.RequestException as e:
        logger.info(f"[Weather] Erreur réseau lors de la récupération des prévisions : {e}")
        return None
    except Exception as e:
        logger.info(f"[Weather] Erreur générale lors de la récupération des prévisions : {e}")
        traceback.print_exc()
        return None


# --- Gestion des marées ---
_tides_data = None


_last_tides_fetch = None


_tides_warning_printed = False


def get_tides(config):
    """Récupère les prochaines marées haute et basse, avec un cache en mémoire et un cache fichier persistant."""
    global _tides_data, _last_tides_fetch, _tides_warning_printed
    api_key = config.get("stormglass_api_key")
    lat = config.get("tide_latitude")
    lon = config.get("tide_longitude")
    # Intervalle de cache de 12 heures pour limiter les appels API à 2 par jour max.
    cache_duration_seconds = 12 * 3600

    if not all([api_key, lat, lon]):
        if not _tides_warning_printed:
            logger.info(f"[Tides] Clé API StormGlass, latitude ou longitude manquante. Les marées sont désactivées.")
            _tides_warning_printed = True
        return None

    # 1. Vérifier le cache en mémoire d'abord
    now = datetime.now()
    if _last_tides_fetch and (now - _last_tides_fetch).total_seconds() < cache_duration_seconds:
        return _tides_data

    # 2. Le cache mémoire est expiré, on vérifie le cache fichier
    TIDES_CACHE_FILE.parent.mkdir(exist_ok=True)
    if TIDES_CACHE_FILE.exists():
        try:
            with open(TIDES_CACHE_FILE, 'r') as f:
                cache_content = json.load(f)
            
            last_file_fetch_dt = datetime.fromisoformat(cache_content['timestamp'])
            
            if (now - last_file_fetch_dt).total_seconds() < cache_duration_seconds:
                # Si c'est une entrée de cooldown, on ne fait rien et on attend.
                if cache_content.get('cooldown'):
                    logger.info(f"[Tides] Cooldown API actif depuis le cache fichier.")
                    _last_tides_fetch = now # Mettre à jour le timer en mémoire pour respecter le cooldown
                    _tides_data = None
                    return None

                tide_data_from_cache = cache_content.get('data')

                # --- NOUVEAU: Vérification du format du cache pour la compatibilité ascendante ---
                if isinstance(tide_data_from_cache, list):
                    logger.info(f"[Tides] Données de marée valides (format liste) trouvées dans le cache fichier.")
                    _tides_data = tide_data_from_cache
                    _last_tides_fetch = now
                    return tide_data_from_cache
                else:
                    logger.info(f"[Tides] Ancien format de cache détecté (dictionnaire). Le cache sera invalidé et recréé.")
                    # On laisse l'exécution continuer pour appeler l'API
        except Exception as e:
            logger.info(f"[Tides] Erreur lecture du cache fichier, récupération depuis l'API. Erreur: {e}")

    # 3. Les deux caches sont invalides, appeler l'API
    logger.info(f"[Tides] Récupération des données de marée depuis l'API StormGlass...")
    _last_tides_fetch = now # Mettre à jour pour éviter les appels répétés en cas d'échec

    try:
        start_time_utc = datetime.utcnow()
        end_time_utc = start_time_utc + timedelta(days=7) # --- MODIFICATION: Récupérer 7 jours de données ---

        headers = {'Authorization': api_key}
        params = {'lat': lat, 'lng': lon, 'start': start_time_utc.isoformat(), 'end': end_time_utc.isoformat()}
        
        response = requests.get('https://api.stormglass.io/v2/tide/extremes/point', params=params, headers=headers, timeout=15)
        response.raise_for_status()
        extremes_data = response.json().get('data', [])

        # Filtrer pour ne garder que les marées futures
        now_utc = datetime.utcnow().replace(tzinfo=None)
        future_extremes = [e for e in extremes_data if datetime.fromisoformat(e['time'].replace('Z', '+00:00')).replace(tzinfo=None) > now_utc]

        if not future_extremes:
            logger.info(f"[Tides] Aucune marée future trouvée dans les données de l'API pour les prochaines 24h.")
            return None

        # Sauvegarder la liste complète des marées futures dans le cache
        data_to_cache = {'data': future_extremes, 'timestamp': datetime.now().isoformat()}
        
        with open(TIDES_CACHE_FILE, 'w') as f:
            json.dump(data_to_cache, f, indent=2)
        
        logger.info(f"[Tides] Données de marée mises à jour et cache sauvegardé.")
        # --- CORRECTION: Mettre à jour le cache en mémoire avant de retourner ---
        _tides_data = future_extremes
        return _tides_data
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 402:
            logger.info(f"[Tides] ERREUR: Quota API StormGlass dépassé. Prochaine tentative dans 12h.")
            # Écrire un timestamp de cooldown dans le cache pour éviter les re-tentatives si le script redémarre
            cooldown_data = {'data': {}, 'timestamp': datetime.now().isoformat(), 'cooldown': True}
            try:
                with open(TIDES_CACHE_FILE, 'w') as f:
                    json.dump(cooldown_data, f, indent=2)
                logger.info(f"[Tides] Timestamp de cooldown écrit dans le cache fichier.")
            except Exception as write_e:
                logger.info(f"[Tides] Impossible d'écrire le cooldown dans le cache fichier: {write_e}")
        else:
            logger.info(f"[Tides] Erreur HTTP lors de la récupération des marées : {e}")
        _tides_data = None
        return None
    except Exception as e:
        logger.info(f"[Tides] Erreur générale lors de la récupération des marées : {e}")
        traceback.print_exc()
        _tides_data = None # Mettre le cache en mémoire à None pour forcer une nouvelle tentative
        return None


def load_icon(icon_name, size, is_weather_icon=True):
    """
    Charge une icône, la met en cache et la retourne comme une surface Pygame.
    Retourne un carré rouge en cas d'échec pour un débogage visuel.
    """
    if size <= 0:
        logger.info(f"[Display] AVERTISSEMENT: Taille d'icône invalide ({size}px) pour '{icon_name}'.")
        return None

    icon_key = f"{icon_name}_{size}"
    if icon_key in _icon_cache:
        return _icon_cache[icon_key]

    if is_weather_icon:
        icon_dir = PREPARED_BASE_DIR.parent / 'weather_icons'
    else:
        icon_dir = ICONS_DIR
    
    icon_path = icon_dir / f"{icon_name}.png"

    if icon_path.exists():
        try:
            loaded_surface = pygame.image.load(str(icon_path)).convert_alpha()
            icon_surface = pygame.transform.scale(loaded_surface, (size, size))
            _icon_cache[icon_key] = icon_surface
            return icon_surface
        except Exception as e:
            logger.info(f"[Display] Erreur chargement icône '{icon_path}': {e}")
            # Fall through to return placeholder
    else:
        warning_key = f"warn_{icon_name}"
        if warning_key not in _icon_cache:
            logger.info(f"[Display] AVERTISSEMENT: Fichier icône non trouvé : {icon_path}")
            _icon_cache[warning_key] = True
    
    # --- Retourner None en cas d'échec ---
    # Cela permet à la logique d'affichage de simplement ignorer l'icône.
    return None
