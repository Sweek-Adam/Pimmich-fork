"""Photos des invités : page d'envoi publique, validation, invitations Telegram."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from utils import import_progress
import io
from flask import send_file
from utils import messages_manager, rate_limit
from web.core import _


@app.route('/api/telegram/invitations/<code>/revoke', methods=['POST'])
@login_required
def revoke_telegram_invitation(code):
    """Révoque l'accès d'un utilisateur en dissociant son ID de l'invitation."""
    invitations = load_invitations()
    if code not in invitations:
        return jsonify({"success": False, "message": "Invitation non trouvée."}), 404

    # Récupérer le nom de l'utilisateur avant de le supprimer pour le message de confirmation
    guest_name = invitations[code].get('used_by_user_name', 'Utilisateur inconnu')

    # Révoquer l'accès en remettant les champs 'used_by' à null
    invitations[code]['used_by_user_id'] = None
    invitations[code]['used_by_user_name'] = None
    invitations[code]['used_at'] = None

    # --- IMPORTANT ---
    # L'invitation redevient "utilisable" mais conserve sa date d'expiration d'origine.
    # Si vous souhaitez que la révocation soit définitive, vous pouvez supprimer l'invitation :
    # del invitations[code]
    # Ou la marquer comme révoquée :
    # invitations[code]['status'] = 'revoked'
    # Pour l'instant, nous la rendons simplement réutilisable.

    save_invitations(invitations)
    
    flash(_("L'accès pour l'invité '%(name)s' a été révoqué.", name=guest_name), "success")
    return jsonify({"success": True, "message": "Accès révoqué."})


@app.route('/api/telegram/bot_info')
@login_required
def get_telegram_bot_info():
    """Récupère le nom d'utilisateur du bot Telegram configuré."""
    config = load_config()
    token = config.get("telegram_bot_token")

    if not token:
        return jsonify({"success": False, "message": "Le token du bot Telegram n'est pas configuré."})

    url = f"https://api.telegram.org/bot{token}/getMe"

    try:
        response = requests.get(url, timeout=10)
        response_data = response.json()

        if response.status_code == 200 and response_data.get("ok"):
            bot_username = response_data.get("result", {}).get("username")
            if bot_username:
                return jsonify({"success": True, "username": bot_username})
            else:
                return jsonify({"success": False, "message": "Le bot n'a pas de nom d'utilisateur ou le token est incorrect."})
        else:
            error_description = response_data.get('description', 'Réponse invalide de Telegram.')
            return jsonify({"success": False, "message": f"Échec de la récupération des infos du bot : {error_description}"})
    except requests.exceptions.RequestException as e:
        return jsonify({"success": False, "message": f"Erreur de connexion à l'API Telegram : {e}"})


# --- Routes principales ---

@app.route('/upload', methods=['GET'])
def upload_page():
    """Affiche la page publique pour envoyer des photos."""
    from utils import trusted_guests
    config = load_config()
    response = app.make_response(render_template('upload.html.jinja', guest_messages_enabled=config.get("guest_messages_enabled", True),
                                                 frame_width=int(config.get("display_width", 1920)), frame_height=int(config.get("display_height", 1080))))
    if not trusted_guests.valid(request.cookies.get(trusted_guests.COOKIE)):  # identifiant de l'appareil (invités de confiance)
        response.set_cookie(trusted_guests.COOKIE, trusted_guests.new_device(), max_age=5 * 365 * 86400, httponly=True, samesite="Lax")
    return response


@app.route('/handle_upload', methods=['POST'])
def handle_upload():
    """Gère la réception des fichiers depuis la page publique."""
    if 'photos' not in request.files:
        flash(_("Aucun fichier sélectionné."), "error")
        return redirect(url_for('upload_page'))

    files = request.files.getlist('photos')
    if not files or files[0].filename == '':
        flash(_("Aucun fichier sélectionné."), "error")
        return redirect(url_for('upload_page'))

    PENDING_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    from utils import trusted_guests
    device = request.cookies.get(trusted_guests.COOKIE, "")
    guest_name = (request.form.get("name") or "").strip()
    saved = []

    count = 0
    for file in files:
        if file:
            # Sécuriser le nom du fichier
            filename = secure_filename(file.filename)
            # Gérer les collisions de noms en ajoutant un timestamp et une chaîne aléatoire
            base, ext = os.path.splitext(filename)
            unique_suffix = f"{int(time.time())}_{secrets.token_hex(2)}"
            final_path = PENDING_UPLOADS_DIR / f"{base}_{unique_suffix}{ext}"
            file.save(final_path)
            trusted_guests.remember(final_path.name, device, guest_name)
            saved.append(final_path)
            logger.info(f"[Upload] Nouveau fichier reçu de l'invité et en attente : {final_path.name}")
            count += 1

    if count and trusted_guests.is_trusted(load_config(), device):
        # Invité de confiance : ses photos sont validées d'office (préparées en arrière-plan)
        threading.Thread(target=lambda: [approve_pending(p) for p in saved], daemon=True, name="guest-trusted").start()
        flash(_('Merci ! %(count)s photo(s) envoyée(s) : elles arrivent sur le cadre.', count=count), "success")
        return redirect(url_for('upload_page'))

    if count:
        from web.routes_history import log
        log("guest", _("%(count)s photo(s) d'invité", count=count), who=guest_name or _("Invité"))
        from utils import notify
        config = load_config()
        base = notify.base_url(config)
        notify.send(config, "guest", _("Nouvelle photo d'invité"), _("%(count)s photo(s) à valider sur le cadre.", count=count),
                    key="guest_photo", click=f"{base}/configure#tab-validation" if base else None, repeat_after=60)
    flash(_('%(count)s photo(s) envoyée(s) pour validation avec succès !', count=count), "success")
    return redirect(url_for('upload_page'))


def approve_pending(pending_path):
    """Valide une photo d'invité : préparée dans la source « invités », puis retirée de l'attente. Renvoie (succès, message)."""
    from utils import trusted_guests
    pending_path = Path(pending_path)
    target_source = "invités"
    source_dir = BASE_DIR / "static" / "photos" / target_source
    source_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(str(pending_path), str(source_dir / pending_path.name))  # copie : l'original reste en attente en cas d'échec
    config = load_config()
    screen_width, screen_height = config.get("display_width", 1920), config.get("display_height", 1080)
    try:
        preparation_successful = False
        for update in import_progress.tracked(target_source, "prepare", prepare_all_photos_with_progress(screen_width, screen_height, source_type=target_source)):
            if update.get("type") == "done":
                preparation_successful = True
        if not preparation_successful:
            return False, _("La préparation de la photo a échoué. La photo reste en attente.")
        pending_path.unlink(missing_ok=True)
        trusted_guests.forget(pending_path.name)
        config = load_config()
        if 'invités' not in config.get('display_sources', []):  # la photo validée doit être diffusée
            config = dict(config, display_sources=list(config.get('display_sources', [])) + ['invités'])
            save_config(config)
        if is_slideshow_running():
            restart_slideshow_for_update()
        return True, _("Photo approuvée et préparée. Le diaporama a été mis à jour.")
    except Exception as e:
        return False, f"Erreur lors de la préparation: {e}"


@app.route('/api/trusted_guests', methods=['GET'])
@login_required
def trusted_guests_api():
    return jsonify({"success": True, "trusted": [{"device": t["device"][:6] + "…", "id": t["device"], "label": t.get("label", ""), "since": t.get("since", "")}
                                                 for t in load_config().get("trusted_guests") or []]})


@app.route('/api/trusted_guests/<device>', methods=['DELETE'])
@login_required
def trusted_guests_remove_api(device):
    config = dict(load_config())
    before = config.get("trusted_guests") or []
    config["trusted_guests"] = [t for t in before if t.get("device") != device]
    save_config(config)
    return jsonify({"success": len(before) != len(config["trusted_guests"]), "message": _("Cet appareil devra de nouveau être validé.")})


@app.route('/api/get_pending_photos')
@login_required
def get_pending_photos():
    """Retourne la liste des photos en attente de validation."""
    try:
        # S'assurer que le dossier existe pour éviter les erreurs.
        if not PENDING_UPLOADS_DIR.exists():
            PENDING_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

        logger.debug(f"Listing pending photos in: {PENDING_UPLOADS_DIR}")

        # Lister les fichiers dans le dossier des uploads en attente.
        files_with_mtime = []
        for f in PENDING_UPLOADS_DIR.iterdir():
            if f.is_file() and not f.name.startswith('.'): # Ignorer les fichiers cachés
                try:
                    files_with_mtime.append((f.name, f.stat().st_mtime))
                except OSError as e:
                    logger.debug(f"Error reading file {f.name}: {e}")

        # Trier par date de modification (le plus récent en premier)
        files_with_mtime.sort(key=lambda x: x[1], reverse=True)
        pending_files = [f[0] for f in files_with_mtime]
        
        logger.debug(f"Found {len(pending_files)} pending photos.")

        # Retourner une réponse structurée et ajouter des en-têtes anti-cache.
        from utils import trusted_guests
        response = jsonify({"success": True, "photos": pending_files,
                            "meta": {f: {"name": trusted_guests.info(f).get("name", ""), "device": bool(trusted_guests.info(f).get("device"))} for f in pending_files}})
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    except Exception as e:
        logger.info(f"[ERROR] get_pending_photos failed: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/manage_pending_photo', methods=['POST'])
@login_required
def manage_pending_photo():
    """Approuve ou rejette une photo en attente."""
    data = request.get_json()
    filename = data.get('filename')
    action = data.get('action')

    if not filename or action not in ['approve', 'reject', 'trust']:
        return jsonify({"success": False, "message": "Données invalides."}), 400

    pending_path = PENDING_UPLOADS_DIR / secure_filename(filename)

    if not pending_path.is_file():
        return jsonify({"success": False, "message": "Fichier non trouvé."}), 404

    if action == 'reject':
        try:
            pending_path.unlink()
            from utils import trusted_guests
            trusted_guests.forget(pending_path.name)
            return jsonify({"success": True, "message": _("Photo rejetée.")})
        except Exception as e:
            return jsonify({"success": False, "message": f"Erreur: {e}"}), 500

    if action in ('approve', 'trust'):
        if action == 'trust':
            from utils import trusted_guests
            meta = trusted_guests.info(pending_path.name)
            if not trusted_guests.valid(meta.get("device")):
                return jsonify({"success": False, "message": _("Appareil inconnu pour cette photo (envoyée avant cette fonction).")}), 400
            config = dict(load_config())
            config["trusted_guests"] = trusted_guests.trust(config, meta["device"], meta.get("name"))
            save_config(config)
        ok, message = approve_pending(pending_path)
        if ok:
            return jsonify({"success": True, "message": _("Photo approuvée : cet appareil est désormais de confiance.") if action == 'trust' else message})
        return jsonify({"success": False, "message": message}), 500

    return jsonify({"success": False, "message": _("Action inconnue.")}), 400


@app.route('/debug/pending')
@admin_required
def debug_pending():
    """Route de diagnostic pour voir les fichiers bruts."""
    if not PENDING_UPLOADS_DIR.exists():
        return f"Le dossier {PENDING_UPLOADS_DIR} n'existe pas."
    files = [f.name for f in PENDING_UPLOADS_DIR.iterdir()]
    return f"Fichiers dans le dossier d'attente : {files}"


@app.route('/api/telegram/invitations', methods=['GET', 'POST'])
@login_required
def manage_telegram_invitations():
    if request.method == 'GET':
        invitations = load_invitations()
        # Filtrer pour ne garder que les invitations valides et non expirées
        active_invitations = {
            code: data for code, data in invitations.items()
            if datetime.fromisoformat(data['expires_at']) > datetime.now()
        }
        return jsonify(list(active_invitations.values()))

    if request.method == 'POST':
        data = request.get_json()
        guest_name = data.get('name')
        duration_days = int(data.get('duration', 7))

        if not guest_name:
            return jsonify({"success": False, "message": "Le nom de l'invité est requis."}), 400

        invitations = load_invitations()
        code = secrets.token_urlsafe(6) # Génère un code court et sécurisé
        
        invitations[code] = {
            "code": code,
            "guest_name": guest_name,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=duration_days)).isoformat(),
            "used_by_user_id": None
        }
        save_invitations(invitations)
        return jsonify({"success": True, "message": "Invitation créée.", "invitation": invitations[code]})


@app.route('/api/telegram/invitations/<code>', methods=['DELETE'])
@login_required
def delete_telegram_invitation(code):
    invitations = load_invitations()
    if code in invitations:
        del invitations[code]
        save_invitations(invitations)
        return jsonify({"success": True, "message": "Invitation supprimée."})
    else:
        return jsonify({"success": False, "message": "Invitation non trouvée."}), 404


# --- Messages écrits par les invités (sans compte), affichés directement ---

GUEST_MESSAGES_PER_HOUR = 5     # par appareil
GUEST_MESSAGES_PER_HOUR_ALL = 20  # tous appareils confondus (si l'adresse de l'appareil est inconnue)


def _guest_key():
    from utils.login_throttle import client_ip
    import ipaddress
    ip = client_ip(request)
    if ip and not ipaddress.ip_address(ip).is_loopback:
        return ip, GUEST_MESSAGES_PER_HOUR
    return "tous", GUEST_MESSAGES_PER_HOUR_ALL  # derrière un proxy mal configuré, tous les appareils ont la même adresse


def _guest_messages_disabled():
    if not load_config().get("guest_messages_enabled", True):
        return jsonify({"success": False, "message": _("Les messages des invités sont désactivés.")}), 403
    return None


@app.route('/upload/message/preview', methods=['POST'])
def guest_message_preview():
    disabled = _guest_messages_disabled()
    if disabled:
        return disabled
    key, _limit = _guest_key()
    if not rate_limit.allow(("aperçu", key), 60, 3600):
        return jsonify({"success": False, "message": _("Trop d'aperçus, réessayez plus tard.")}), 429
    data = request.get_json(silent=True) or {}
    config = load_config()
    try:
        image = messages_manager.preview(data.get("title"), data.get("body"), data.get("signature"), data.get("style"),
                                         int(config.get("display_width", 1920)), int(config.get("display_height", 1080)))
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=75)
    buffer.seek(0)
    return send_file(buffer, mimetype="image/jpeg")


@app.route('/upload/message', methods=['POST'])
def guest_message_publish():
    disabled = _guest_messages_disabled()
    if disabled:
        return disabled
    data = request.get_json(silent=True) or {}
    key, limit = _guest_key()
    if not rate_limit.allow(("message", key), limit, 3600):
        return jsonify({"success": False, "message": _("Vous avez déjà envoyé plusieurs messages : réessayez dans une heure.")}), 429
    config = load_config()
    name = (data.get("signature") or "").strip()
    try:
        message = messages_manager.create_message(
            data.get("title"), data.get("body"), name, data.get("style"), data.get("expires"),
            f"{_('Invité')}{' : ' + name if name else ''}",
            int(config.get("display_width", 1920)), int(config.get("display_height", 1080)), guest=True)
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    if messages_manager.SOURCE_NAME not in config.get("display_sources", []):
        config = dict(config)
        config["display_sources"] = config.get("display_sources", []) + [messages_manager.SOURCE_NAME]
        save_config(config)
    from web.routes_history import log
    log("message", _("Message d'invité"), {"type": "delete_message", "data": message["id"]}, who=message.get("signature") or _("Invité"))
    logger.info(f"[Messages] Message invité {message['id']} publié ({message['author']}, jusqu'au {message['expires']})")
    from utils import notify
    text = " — ".join(t for t in (message.get("title"), message.get("body")) if t)[:160]
    notify.send(config, "guest", _("Nouveau message d'invité"), f"{name or _('Un invité')} : {text}", key=f"guest_message:{message['id']}")
    if is_slideshow_running():
        restart_slideshow_for_update()
    return jsonify({"success": True, "message": _("Merci ! Votre message va s'afficher sur le cadre (jusqu'au %(date)s).", date=message["expires"])})


@app.route('/upload/drawing', methods=['POST'])
def guest_drawing_publish():
    """Dessin à main levée (et autocollants) fait sur le téléphone d'un invité : affiché comme un message."""
    disabled = _guest_messages_disabled()
    if disabled:
        return disabled
    key, limit = _guest_key()
    if not rate_limit.allow(("message", key), limit, 3600):
        return jsonify({"success": False, "message": _("Vous avez déjà envoyé plusieurs messages : réessayez dans une heure.")}), 429
    file = request.files.get("drawing")
    name = (request.form.get("signature") or "").strip()
    config = load_config()
    try:
        message = messages_manager.create_drawing(file.read() if file else b"", name, f"{_('Invité')}{' : ' + name if name else ''}",
                                                  int(config.get("display_width", 1920)), int(config.get("display_height", 1080)))
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    if messages_manager.SOURCE_NAME not in config.get("display_sources", []):
        config = dict(config)
        config["display_sources"] = config.get("display_sources", []) + [messages_manager.SOURCE_NAME]
        save_config(config)
    from web.routes_history import log
    log("drawing", _("Dessin d'invité"), {"type": "delete_message", "data": message["id"]}, who=message.get("signature") or _("Invité"))
    logger.info(f"[Messages] Dessin d'invité {message['id']} publié ({message['author']})")
    from utils import notify
    notify.send(config, "guest", _("Nouveau dessin d'invité"), _("%(name)s a fait un dessin pour le cadre.", name=name or _("Un invité")),
                key=f"guest_message:{message['id']}")
    if is_slideshow_running():
        restart_slideshow_for_update()
    return jsonify({"success": True, "message": _("Merci ! Votre dessin va s'afficher sur le cadre (jusqu'au %(date)s).", date=message["expires"])})


@app.route('/upload/voice', methods=['POST'])
def guest_voice_publish():
    """Message vocal enregistré sur le téléphone : le cadre le lit quand sa carte s'affiche."""
    disabled = _guest_messages_disabled()
    if disabled:
        return disabled
    key, limit = _guest_key()
    if not rate_limit.allow(("message", key), limit, 3600):
        return jsonify({"success": False, "message": _("Vous avez déjà envoyé plusieurs messages : réessayez dans une heure.")}), 429
    file = request.files.get("voice")
    name = (request.form.get("signature") or "").strip()
    config = load_config()
    try:
        message = messages_manager.create_voice(file.read() if file else b"", name, f"{_('Invité')}{' : ' + name if name else ''}",
                                                int(config.get("display_width", 1920)), int(config.get("display_height", 1080)))
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    if messages_manager.SOURCE_NAME not in config.get("display_sources", []):
        config = dict(config, display_sources=config.get("display_sources", []) + [messages_manager.SOURCE_NAME])
        save_config(config)
    from web.routes_history import log
    log("voice", _("Message vocal d'invité"), {"type": "delete_message", "data": message["id"]}, who=name or _("Invité"))
    from utils import notify
    notify.send(config, "guest", _("Nouveau message vocal"), _("%(name)s a laissé un message vocal.", name=name or _("Un invité")),
                key=f"guest_message:{message['id']}")
    if is_slideshow_running():
        restart_slideshow_for_update()
    return jsonify({"success": True, "message": _("Merci ! Votre message vocal sera lu par le cadre (jusqu'au %(date)s).", date=message["expires"])})


# --- Réactions sur la photo affichée, et livre d'or (réseau de la maison seulement) ---

def _now_showing():
    """Photo affichée en ce moment (chemin relatif à static/), ou None."""
    try:
        path = Path(CURRENT_PHOTO_FILE).read_text().strip()
    except OSError:
        return None
    if not path.startswith(("prepared/", "compositions/")) or "/messages/" in path or not is_slideshow_running():
        return None
    return path


@app.route('/upload/now', methods=['GET'])
def guest_now_showing():
    if not load_config().get("guest_reactions_enabled", True):
        return jsonify({"success": False, "photo": None}), 403
    from utils import reactions
    photo = _now_showing()
    return jsonify({"success": True, "photo": photo, "url": url_for('static', filename=photo) if photo else None,
                    "counts": reactions.counts(photo) if photo else {}, "kinds": reactions.KINDS})


@app.route('/upload/react', methods=['POST'])
def guest_react():
    from utils import reactions
    if not load_config().get("guest_reactions_enabled", True):
        return jsonify({"success": False, "message": _("Les réactions sont désactivées.")}), 403
    data = request.get_json(silent=True) or {}
    key, _limit = _guest_key()
    if not rate_limit.allow(("réaction", key), 60, 3600):
        return jsonify({"success": False, "message": _("Doucement ! Réessayez dans un moment.")}), 429
    photo = str(data.get("photo") or "")
    base = (BASE_DIR / "static").resolve()
    full = (base / photo).resolve()
    if not photo.startswith(("prepared/", "compositions/")) or base not in full.parents or not full.is_file():
        return jsonify({"success": False, "message": _("Photo introuvable.")}), 404
    try:
        counts = reactions.add(photo, data.get("kind"), str(data.get("name") or ""))
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    return jsonify({"success": True, "counts": counts})


@app.route('/upload/guestbook', methods=['GET'])
def guest_book_page():
    from utils import guestbook
    return render_template('guestbook.html.jinja', entries=guestbook.entries())


@app.route('/api/guestbook/<entry_id>', methods=['DELETE'])
@login_required
def guest_book_delete(entry_id):
    from utils import guestbook
    if not re.fullmatch(r"[0-9a-f]{12}", entry_id) or not guestbook.delete(entry_id):
        return jsonify({"success": False, "message": _("Page introuvable.")}), 404
    return jsonify({"success": True, "message": _("Page retirée du livre d'or.")})


@app.route('/api/reactions', methods=['GET'])
@login_required
def reactions_api():
    from utils import reactions
    return jsonify({"success": True, "recent": reactions.recent(), "most_loved": reactions.most_loved(), "kinds": reactions.KINDS})


# --- Invités hors de la maison (Tailscale Funnel) ---

def _remote_entry_ready():
    """L'entrée nginx réservée aux invités (port local 8088) est installée."""
    import socket
    from utils import remote_guests
    with socket.socket() as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", remote_guests.REMOTE_PORT)) == 0


@app.route('/api/remote_guests', methods=['GET'])
@admin_required
def remote_guests_status_api():
    from utils import remote_guests
    config = load_config()
    status = remote_guests.tailscale_status()
    token = config.get("guest_link_token")
    link = f"https://{status['dns_name']}/upload?k={token}" if status["dns_name"] and token else None
    return jsonify({"success": True, "enabled": bool(config.get("remote_guests_enabled")), "entry_ready": _remote_entry_ready(),
                    "link": link if config.get("remote_guests_enabled") else None, **status})


@app.route('/api/remote_guests', methods=['POST'])
@admin_required
def remote_guests_toggle_api():
    from utils import remote_guests
    enabled = bool((request.get_json(silent=True) or {}).get("enabled"))
    if enabled and not _remote_entry_ready():
        return jsonify({"success": False, "message": _("Lancez d'abord une fois sur le Raspberry Pi : ~/pimmich/utils/enable_remote_guests.sh")}), 409
    ok, output = remote_guests.set_funnel(enabled)
    if not ok and enabled:
        activation = re.search(r"https://login\.tailscale\.com/\S+", output or "")
        if activation:  # Funnel pas encore autorisé sur le compte Tailscale
            return jsonify({"success": False, "activation_url": activation.group(0),
                            "message": _("Autorisez d'abord Funnel sur votre compte Tailscale (bouton « Enable » sur la page qui s'ouvre), puis réactivez « Hors de la maison ».")}), 409
        return jsonify({"success": False, "message": _("Tailscale refuse la publication : %(detail)s", detail=output[-400:])}), 502
    config = dict(load_config())
    config["remote_guests_enabled"] = enabled
    if enabled and not config.get("guest_link_token"):
        config["guest_link_token"] = remote_guests.new_token()
    save_config(config)
    return jsonify({"success": True, "message": _("Les invités peuvent maintenant envoyer depuis n'importe où, avec le lien.") if enabled
                    else _("La page invités n'est plus accessible depuis internet.")})


@app.route('/api/remote_guests/new_link', methods=['POST'])
@admin_required
def remote_guests_new_link_api():
    from utils import remote_guests
    config = dict(load_config())
    config["guest_link_token"] = remote_guests.new_token()
    save_config(config)
    return jsonify({"success": True, "message": _("Nouveau lien créé : l'ancien ne fonctionne plus.")})
