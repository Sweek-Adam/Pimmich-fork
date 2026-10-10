"""
Santé du cadre et assistant de démarrage : vérifications simples, chacune avec une explication claire
et l'endroit de l'interface où régler le problème.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

from utils.message_renderer import N_

PROJECT_DIR = Path(__file__).resolve().parent.parent
HTTPS_CERT = Path("/etc/ssl/pimmich/pimmich.crt")
SOURCES_WITH_SETTINGS = ("immich", "samba", "gdrive")


def _prepared_count():
    prepared = PROJECT_DIR / "static" / "prepared"
    if not prepared.exists():
        return 0
    return sum(1 for d in prepared.iterdir() if d.is_dir() for f in d.iterdir()
               if f.is_file() and not f.name.endswith(("_polaroid.jpg", "_postcard.jpg", "_thumbnail.jpg")))


def _gdrive_denied_count():
    manifest = PROJECT_DIR / "static" / "photos" / "gdrive" / ".gdrive_manifest.json"
    try:
        return sum(1 for e in json.loads(manifest.read_text()).values() if e.get("trash_denied"))
    except (OSError, json.JSONDecodeError):
        return 0


def _pending_guest_photos():
    pending = PROJECT_DIR / "static" / "pending_uploads"
    return sum(1 for f in pending.iterdir() if f.is_file() and not f.name.startswith(".")) if pending.exists() else 0


def guests_invited(config):
    """La famille est invitée : Telegram configuré, envoi reçu d'un invité, ou lien partagé depuis l'interface."""
    if config.get("telegram_bot_token") or "guests" in (config.get("setup_marks") or []):
        return True
    if _pending_guest_photos():
        return True
    validated = PROJECT_DIR / "static" / "prepared" / "invités"
    if validated.exists() and any(f.is_file() for f in validated.iterdir()):
        return True
    try:
        from utils.messages_manager import list_messages
        return any(m.get("guest") for m in list_messages())
    except Exception:
        return False


def source_configured(config):
    return bool(config.get("immich_url") and config.get("immich_token")) or bool(config.get("smb_host")) or bool(config.get("gdrive_folders"))


def checks(config, slideshow_running, is_admin, proxy_host_ok=True, worker_messages=None, now=None):
    """
    Liste des problèmes et conseils : {level: error|warning|info, title, detail, tab (onglet où agir)}.
    Seuls les problèmes réels sont retournés : une liste vide signifie que tout va bien.
    """
    now = now or datetime.now()
    items = []

    def add(level, title, detail, tab=None, **params):
        items.append({"level": level, "title": title, "detail": detail, "tab": tab, "params": params})

    photos = _prepared_count()
    if photos == 0:
        add("warning", N_("Aucune photo à afficher"),
            N_("Ajoutez une source de photos (Google Drive, Immich, partage réseau, clé USB) puis lancez un import."), "tab-sources")
    if not slideshow_running and config.get("_active_hours", True):
        add("warning", N_("Le diaporama est arrêté"), N_("Il devrait tourner à cette heure-ci. Relancez-le depuis l'accueil."), "tab-accueil")
    for worker, message in (worker_messages or {}).items():
        if message and ("erreur" in message.lower() or "error" in message.lower()):
            add("error", N_("Problème de synchronisation"), f"{worker} : {message}", "tab-sources")
    pending = _pending_guest_photos()
    if pending:
        add("info", N_("Photos d'invités à valider"), N_("%(count)s photo(s) attendent votre validation.") , "tab-validation", count=pending)
    denied = _gdrive_denied_count()
    if denied:
        add("info", N_("Photos laissées sur Google Drive"),
            N_("%(count)s photo(s) déposée(s) par un autre compte ne peuvent pas être mises à la corbeille du Drive : elles restent affichées sur le cadre."),
            "tab-sources", count=denied)  # liste détaillée : Sources > Photos que le cadre ne peut pas retirer du Drive
    if not is_admin:
        return items

    try:
        from utils.disk_monitor import disk_status
        disk = disk_status(config)
        if disk["low"]:
            add("error", N_("Espace disque faible"), N_("%(free)s Go libres. Supprimez des photos ou activez le nettoyage automatique."),
                "tab-maintenance", free=disk["free_gb"])
    except OSError:
        pass
    try:
        from utils.drive_backup import load_status
        backup = load_status()
        if config.get("backup_drive_enabled"):
            if backup.get("last_error"):
                add("error", N_("La sauvegarde a échoué"), backup["last_error"], "tab-maintenance")
            elif not backup.get("last_success") or now - datetime.fromisoformat(backup["last_success"]) > timedelta(days=7):
                add("warning", N_("Sauvegarde ancienne"), N_("Aucune sauvegarde réussie depuis plus de 7 jours."), "tab-maintenance")
    except (OSError, ValueError):
        pass
    if not HTTPS_CERT.exists() or not proxy_host_ok:
        add("info", N_("Connexion non chiffrée"),
            N_("Sur le Raspberry Pi, lancez une fois : sudo ~/pimmich/utils/enable_https.sh (active le HTTPS et corrige la configuration nginx)."),
            "tab-maintenance")
    return items


def setup_steps(config, is_admin):
    """Étapes de l'assistant de démarrage, avec leur état."""
    from utils.drive_backup import load_status
    steps = [
        {"key": "source", "title": N_("Choisir une source de photos"), "done": source_configured(config) or _prepared_count() > 0, "tab": "tab-sources"},
        {"key": "photos", "title": N_("Importer des photos"), "done": _prepared_count() > 0, "tab": "tab-actions"},
        {"key": "hours", "title": N_("Régler les heures d'affichage"), "done": bool(config.get("active_start_weekday")), "tab": "tab-affichage"},
        {"key": "ambiance", "title": N_("Choisir une ambiance"), "done": bool(config.get("ambiance")), "tab": "tab-accueil"},
        {"key": "guests", "title": N_("Inviter la famille (QR code, Telegram)"), "done": guests_invited(config), "tab": "tab-invites"},
    ]
    if is_admin:
        steps += [
            {"key": "https", "title": N_("Sécuriser la connexion (HTTPS)"), "done": HTTPS_CERT.exists(), "tab": "tab-maintenance"},
            {"key": "backup", "title": N_("Activer la sauvegarde automatique"), "done": bool(config.get("backup_drive_enabled") and load_status().get("last_success")), "tab": "tab-maintenance"},
        ]
    return steps
