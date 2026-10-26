"""
Point d'entrée de l'application web Pimmich (lancé par start_pimmich.sh).

Le code est réparti dans le paquet web/ :
  - web/core.py : application Flask, sécurité, constantes et utilitaires partagés
  - web/routes_*.py : routes, regroupées par domaine
  - web/workers.py : tâches de fond (mises à jour automatiques, bot Telegram, planification)
"""
from web.core import *  # noqa: F401,F403
from web import routes_auth  # noqa: F401 (enregistre les routes)
from web import routes_config  # noqa: F401 (enregistre les routes)
from web import routes_imports  # noqa: F401 (enregistre les routes)
from web import routes_integrations  # noqa: F401 (enregistre les routes)
from web import routes_guests  # noqa: F401 (enregistre les routes)
from web import routes_slideshow  # noqa: F401 (enregistre les routes)
from web import routes_playlists  # noqa: F401 (enregistre les routes)
from web import routes_photos  # noqa: F401 (enregistre les routes)
from web import routes_captions  # noqa: F401 (enregistre les routes)
from web import routes_people  # noqa: F401 (enregistre les routes)
from web import routes_smart_albums  # noqa: F401 (enregistre les routes)
from web import routes_storage  # noqa: F401 (enregistre les routes)
from web import routes_quotes  # noqa: F401 (enregistre les routes)
from web import routes_trips  # noqa: F401 (enregistre les routes)
from web import routes_app  # noqa: F401 (enregistre les routes)
from web import routes_settings  # noqa: F401 (enregistre les routes)
from web import routes_family  # noqa: F401 (enregistre les routes)
from web import routes_homeassistant  # noqa: F401 (enregistre les routes)
from web import routes_frames  # noqa: F401 (enregistre les routes)
from web import routes_history  # noqa: F401 (enregistre les routes)
from web import routes_voice  # noqa: F401 (enregistre les routes)
from web import routes_system  # noqa: F401 (enregistre les routes)
from web import routes_messages  # noqa: F401 (enregistre les routes)
from web import routes_home  # noqa: F401 (enregistre les routes)
from web import routes_music  # noqa: F401 (enregistre les routes)
from web import routes_media  # noqa: F401 (enregistre les routes)
from web import routes_party  # noqa: F401 (enregistre les routes)
from web import routes_photobook  # noqa: F401 (enregistre les routes)
from web import routes_daily_photo  # noqa: F401 (enregistre les routes)
from web import routes_scan  # noqa: F401 (enregistre les routes)
from web import routes_simple  # noqa: F401 (enregistre les routes)
from web import routes_game  # noqa: F401 (enregistre les routes)
from web.workers import *  # noqa: F401,F403


if __name__ == '__main__':
    # Lancer la migration des dossiers invités au démarrage
    migrate_guest_folders()

    # Démarrer les workers de mise à jour dans des threads séparés
    immich_thread = threading.Thread(target=immich_update_worker, daemon=True)
    immich_thread.start()
    samba_thread = threading.Thread(target=samba_update_worker, daemon=True)
    samba_thread.start()
    gdrive_thread = threading.Thread(target=gdrive_update_worker, daemon=True)
    gdrive_thread.start()
    telegram_thread = threading.Thread(target=telegram_bot_worker, daemon=True)
    telegram_thread.start()
    maintenance_thread = threading.Thread(target=maintenance_worker, daemon=True)
    maintenance_thread.start()
    from web.workers import presence_worker, cloud_update_worker, icloud_update_worker, email_worker, people_worker, rotation_worker, storage_worker, quote_worker, message_schedule_worker, hdmi_audio_worker, music_schedule_worker, stats_worker, reliability_worker, trips_worker, button_worker, hotspot_worker, tv_remote_worker, motion_worker
    from utils.platform_info import desktop, web_port
    on_pi = not desktop()  # édition ordinateur : pas de matériel du Raspberry Pi (GPIO, capteur, disques, Wi-Fi de secours)
    if on_pi:
        threading.Thread(target=presence_worker, daemon=True).start()
    threading.Thread(target=cloud_update_worker, daemon=True).start()
    threading.Thread(target=icloud_update_worker, daemon=True).start()
    threading.Thread(target=email_worker, daemon=True).start()
    threading.Thread(target=people_worker, daemon=True).start()
    if on_pi:
        threading.Thread(target=rotation_worker, daemon=True).start()
    if on_pi:
        threading.Thread(target=storage_worker, daemon=True).start()
    threading.Thread(target=quote_worker, daemon=True).start()
    threading.Thread(target=trips_worker, daemon=True).start()
    threading.Thread(target=message_schedule_worker, daemon=True).start()
    if on_pi:
        threading.Thread(target=hdmi_audio_worker, daemon=True).start()
    threading.Thread(target=music_schedule_worker, daemon=True).start()
    threading.Thread(target=stats_worker, daemon=True).start()
    threading.Thread(target=reliability_worker, daemon=True).start()
    from web.workers import night_work_worker
    threading.Thread(target=night_work_worker, daemon=True, name="night-work").start()
    threading.Thread(target=routes_party.party_worker, daemon=True, name="party").start()
    from web.workers import daily_summary_worker, frame_share_worker, auto_backup_worker, daily_photo_worker
    from web.workers import occasion_reminder_worker
    threading.Thread(target=occasion_reminder_worker, daemon=True, name="occasion-reminders").start()  # rappels d'anniversaire
    threading.Thread(target=daily_photo_worker, daemon=True, name="daily-photo").start()  # photo du jour par e-mail
    threading.Thread(target=auto_backup_worker, daemon=True, name="auto-backup").start()  # sauvegarde de la semaine
    threading.Thread(target=frame_share_worker, daemon=True, name="frame-share").start()  # cadres jumelés
    from web.workers import frame_wall_worker
    threading.Thread(target=frame_wall_worker, daemon=True, name="frame-wall").start()  # mur de cadres
    threading.Thread(target=daily_summary_worker, daemon=True, name="daily-summary").start()
    if on_pi:
        threading.Thread(target=button_worker, daemon=True, name="button").start()  # bouton physique (GPIO)
        threading.Thread(target=hotspot_worker, daemon=True, name="hotspot").start()  # Wi-Fi de secours
        threading.Thread(target=tv_remote_worker, daemon=True, name="tv-remote").start()  # télécommande de la TV (CEC)
        threading.Thread(target=motion_worker, daemon=True, name="motion").start()  # détecteur de mouvement (GPIO)
    routes_homeassistant.restart_bridge()  # Home Assistant (MQTT), s'il est configuré
    # Préchauffer le cache des remotes rclone (lent sur Pi 3) pour que la page de configuration s'ouvre vite
    from utils.import_gdrive import list_rclone_remotes
    threading.Thread(target=list_rclone_remotes, daemon=True).start()
    
    # Démarrer le worker de planification du diaporama
    scheduler_thread = threading.Thread(target=schedule_worker, daemon=True)
    scheduler_thread.start()

    # --- NOUVEAU: Démarrage du contrôle vocal si activé ---
    config = load_config()
    if config.get('voice_control_enabled') and on_pi:
        print("Le contrôle vocal est activé, démarrage du service...")
        start_voice_control()

    # Après une mise à jour : version validée une fois l'application stable (sinon start_pimmich.sh revient en arrière)
    def confirm_update():
        import time
        import urllib.request
        from utils import updater
        time.sleep(120)
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{5000 if on_pi else web_port()}/login", timeout=10) as resp:
                if resp.status == 200 and updater.mark_healthy():
                    print("[Mise à jour] Nouvelle version validée.")
        except OSError:
            pass
    threading.Thread(target=confirm_update, daemon=True).start()

    if on_pi:
        # Écoute uniquement en local : l'accès réseau passe par nginx (port 80)
        app.run(host='127.0.0.1', port=5000)
    else:
        # Ordinateur (édition événement) : pas de nginx, les invités arrivent directement sur ce port
        app.run(host=os.environ.get("PIMMICH_HOST", "0.0.0.0"), port=web_port(), threaded=True)

