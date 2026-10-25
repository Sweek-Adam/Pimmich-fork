"""
Compositions du diaporama préparées en arrière-plan (et d'avance), file « À suivre », médias prioritaires.
"""
import logging
import os
import random
import threading
import time
from pathlib import Path

from utils import animated, compositions, layout_engine, play_queue
from utils.messages_manager import list_messages

logger = logging.getLogger("pimmich.slideshow")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREPARED_BASE_DIR = Path(BASE_DIR) / "static" / "prepared"


_composition = {"thread": None, "ready": None, "target": None, "counter": 0, "slot": 0, "style": None}


_queue_lock = threading.Lock()


_queue_context = {}  # dernier état publié pour l'onglet « À suivre » (republié quand une composition est prête)


_ahead = {}  # compositions préparées d'avance : {(playlist, indice): (chemin, diapositives utilisées, format)}


AHEAD_MAX = 2


def _render_composition(plan, snapshot, start, messages, include_messages, width, height):
    """Compose la composition qui commence à `start` : (image, diapositives utilisées, format, GIF animés) ou None."""
    rng = random.Random()
    if not snapshot or not layout_engine.is_message(snapshot[start % len(snapshot)]):
        plan = layout_engine.without_message_only(plan)  # pas de message à afficher : pas de disposition construite autour
    for _attempt in range(4):  # un autre format si celui-ci ne peut pas accueillir les photos suivantes
        style = layout_engine.pick_format(plan, rng)
        count = layout_engine.photo_count(style, rng)
        if include_messages and layout_engine.accepts_messages(style) and style not in compositions.LIMITS:
            # les messages (dans la limite de la disposition) ne prennent pas la place des photos
            chunk = layout_engine.take_slides(snapshot, start, count, layout_engine.MESSAGE_SLOTS.get(style, 1))
        else:
            chunk = layout_engine.take_chunk(snapshot, start, count)
        state = rng.getstate()
        image, used = layout_engine.render_chunk(style, chunk, messages, width, height, include_messages, rng)
        if image is not None:
            try:  # GIF animés : rejoués par-dessus pendant l'affichage
                moving = layout_engine.animations_for(style, chunk, messages, width, height, include_messages, state, image, used)
            except Exception as e:
                logger.warning(f"[Dispositions] GIF animés non repérés : {e}")
                moving = []
            return image, used, style, moving
    return None


def _save_composition(image, moving=None):
    """Fichiers en rotation : jamais réécrire celui affiché ni ceux préparés d'avance."""
    compositions.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _composition["slot"] = (_composition["slot"] + 1) % (AHEAD_MAX + 2)
    path = compositions.OUTPUT_DIR / f"composition_{_composition['slot']}.jpg"
    image.save(path, "JPEG", quality=88)
    animated.write(path, moving)  # toujours réécrit : pas d'animation d'une ancienne composition
    return str(path)


def prepare_composition(config, plan, playlist, start, width, height, force=False, base_plan=None):
    """
    Prépare en arrière-plan la composition qui commencera à l'indice `start` de cette playlist,
    puis, dans la foulée, la suivante (préparée d'avance : le diaporama n'attend plus une composition lente).
    """
    target = (id(playlist), start)
    for key in [k for k in _ahead if k[0] != id(playlist)]:
        _ahead.pop(key, None)  # playlist reconstruite ou réordonnée : réserves périmées
    if not force and _composition["target"] == target and (_composition["ready"] or (_composition["thread"] and _composition["thread"].is_alive())):
        return  # déjà prête ou en cours pour cet emplacement
    if _composition["thread"] and _composition["thread"].is_alive():
        if not force:
            return  # une autre préparation est en cours : on ne surcharge pas le processeur
        _composition["thread"].join(30)  # disposition forcée : on attend la fin de la préparation en cours
    reserved = None if force else _ahead.pop(target, None)
    _composition.update(target=target, ready=None)
    compositions.set_full_photos(config.get("compositions_full_photos", True))
    layout_engine.set_video_clips(config.get("short_videos_in_layouts", True))
    from utils import hardware_profile
    animated.set_limits(hardware_profile.value(config, "gif_items"))
    compositions.faces.set_enabled(config.get("smart_crop", True))
    include_messages = config.get("compositions_include_messages", True)
    snapshot = list(playlist)
    base_plan = base_plan or plan

    def work():
        try:
            messages = {m["id"]: m for m in list_messages() if not m.get("hidden")} if include_messages else {}
            if reserved:  # déjà préparée d'avance
                path, used, style = reserved
                if _composition["target"] == target:
                    _composition["ready"], _composition["style"] = (path, used), style
                    publish_queue()
            else:
                started = time.time()
                result = _render_composition(plan, snapshot, start, messages, include_messages, width, height)
                if result is None:
                    logger.info(f"[Dispositions] Aucune composition possible à partir de la diapositive {start} : affichage seul")
                    return
                image, used, style, moving = result
                path = _save_composition(image, moving)
                if _composition["target"] == target:
                    _composition["ready"], _composition["style"] = (path, used), style
                    publish_queue()  # la composition apparaît dans « À suivre »
                logger.info(f"[Dispositions] « {style} » ({used} photos) prête en {time.time() - started:.1f}s")
            # La suivante, d'avance
            nxt = layout_engine.next_composition_start(base_plan, snapshot, start + used, include_messages)
            if nxt is None or len(_ahead) >= AHEAD_MAX or (target[0], nxt[0] % len(snapshot)) in _ahead:
                return
            started = time.time()
            result = _render_composition(nxt[1], snapshot, nxt[0] % len(snapshot), messages, include_messages, width, height)
            if result:
                image, used2, style2, moving2 = result
                _ahead[(target[0], nxt[0] % len(snapshot))] = (_save_composition(image, moving2), used2, style2)
                logger.info(f"[Dispositions] « {style2} » préparée d'avance en {time.time() - started:.1f}s")
        except Exception as e:
            logger.warning(f"[Dispositions] Préparation impossible : {e}")

    _composition["thread"] = threading.Thread(target=work, daemon=True)
    _composition["thread"].start()


def upcoming_compositions(plan, playlist, start, counter, include_messages=True):
    """
    Où tomberont les prochaines compositions parmi les médias suivants (onglet « À suivre »).
    Exact pour celle déjà préparée ; la suivante n'est connue que par la photo où elle commencera.
    """
    found, offset, index = [], 0, start
    limit = min(play_queue.UPCOMING_COUNT, len(playlist))
    while offset < limit and playlist:
        index %= len(playlist)
        wanted, slot_plan = layout_engine.plan_for_slide(plan, playlist[index], counter, include_messages)
        if wanted and slot_plan.formats:
            ready = _composition["ready"] if _composition["target"] == (id(playlist), index) else None
            style = _composition["style"]
            if not ready and (id(playlist), index) in _ahead:  # préparée d'avance
                path, used, style = _ahead[(id(playlist), index)]
                ready = (path, used)
            if not ready:
                found.append({"at": offset, "count": None, "style": None, "image": None})
                break
            path, used = ready
            found.append({"at": offset, "count": used, "style": style, "image": path})
            offset, index, counter = offset + used, index + used, 0
        else:
            offset, index, counter = offset + 1, index + 1, counter + 1
    return found


def publish_queue(**context):
    """Publie l'état de la file « À suivre » (le contexte est mémorisé pour être republié plus tard)."""
    with _queue_lock:  # appelée par la boucle principale et par la préparation en arrière-plan
        _queue_context.update(context)
        ctx = _queue_context
        if not ctx.get("playlist"):
            return
        try:
            planned = upcoming_compositions(ctx["plan"], ctx["playlist"], ctx["next_index"], ctx["next_counter"], ctx.get("include_messages", True))
        except Exception as e:
            logger.debug(f"[À suivre] Compositions non calculées : {e}")
            planned = []
        play_queue.publish_state(ctx["playlist"], ctx["index"], ctx["override"], ctx["consumed"], planned)


def take_composition(playlist, start, wait_seconds=0):
    """Composition prête pour cet emplacement : (chemin, nombre de diapositives utilisées), sinon (None, 0)."""
    if _composition["target"] != (id(playlist), start):
        return None, 0
    thread = _composition["thread"]
    if wait_seconds and not _composition["ready"] and thread and thread.is_alive():
        thread.join(wait_seconds)  # l'écran garde la diapositive précédente pendant ce temps
    ready, _composition["ready"], _composition["target"] = _composition["ready"], None, None
    return ready if ready else (None, 0)


def apply_priority(playlist, all_media, queue):
    """
    Place en tête de la playlist les médias de la file prioritaire (déjà dans l'ordre « dernier arrivé,
    premier affiché ») qui font partie des médias affichables, sans les répéter ensuite.
    """
    available = {os.path.realpath(p): p for p in all_media}
    priority = []
    for p in queue:
        real = os.path.realpath(p)
        if real in available and available[real] not in priority:
            priority.append(available[real])
    if not priority:
        return playlist
    first = {os.path.realpath(p) for p in priority}
    logger.info(f"[Diaporama] {len(priority)} nouveau(x) message(s) affiché(s) en premier")
    return priority + [p for p in playlist if os.path.realpath(p) not in first]
