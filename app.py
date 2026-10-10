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
from web import routes_voice  # noqa: F401 (enregistre les routes)
from web import routes_system  # noqa: F401 (enregistre les routes)
from web import routes_messages  # noqa: F401 (enregistre les routes)
from web import routes_home  # noqa: F401 (enregistre les routes)
from web import routes_music  # noqa: F401 (enregistre les routes)
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
    from web.workers import presence_worker, cloud_update_worker
    threading.Thread(target=presence_worker, daemon=True).start()
    threading.Thread(target=cloud_update_worker, daemon=True).start()
    # Préchauffer le cache des remotes rclone (lent sur Pi 3) pour que la page de configuration s'ouvre vite
    from utils.import_gdrive import list_rclone_remotes
    threading.Thread(target=list_rclone_remotes, daemon=True).start()
    
    # Démarrer le worker de planification du diaporama
    scheduler_thread = threading.Thread(target=schedule_worker, daemon=True)
    scheduler_thread.start()

    # --- NOUVEAU: Démarrage du contrôle vocal si activé ---
    config = load_config()
    if config.get('voice_control_enabled'):
        print("Le contrôle vocal est activé, démarrage du service...")
        start_voice_control()

    # Après une mise à jour : version validée une fois l'application stable (sinon start_pimmich.sh revient en arrière)
    def confirm_update():
        import time
        import urllib.request
        from utils import updater
        time.sleep(120)
        try:
            with urllib.request.urlopen("http://127.0.0.1:5000/login", timeout=10) as resp:
                if resp.status == 200 and updater.mark_healthy():
                    print("[Mise à jour] Nouvelle version validée.")
        except OSError:
            pass
    threading.Thread(target=confirm_update, daemon=True).start()

    # Écoute uniquement en local : l'accès réseau passe par nginx (port 80)
    app.run(host='127.0.0.1', port=5000)

