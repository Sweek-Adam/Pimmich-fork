"""
File d'attente du diaporama, partagée entre le processus du diaporama et l'interface web.

- Le diaporama publie à chaque photo les prochains médias à afficher (STATE_FILE).
- L'interface peut demander un nouvel ordre pour ces médias (ORDER_FILE) ; le diaporama l'applique
  juste avant de passer au média suivant.
"""
import os
import json
import time
from pathlib import Path

STATE_FILE = Path("/tmp/pimmich_queue.json")
ORDER_FILE = Path("/tmp/pimmich_queue_order.json")
UPCOMING_COUNT = 30


def _write_json(path, data):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False))
    tmp.replace(path)


def _cycle(playlist, start):
    """La playlist parcourue en boucle à partir de l'indice `start`."""
    return playlist[start:] + playlist[:start] if playlist else []


def publish_state(playlist, current_index, current_override=None):
    """
    Publie le média affiché et les suivants (dans l'ordre où ils seront affichés).
    `current_override` : média affiché hors playlist (composition) ; playlist[current_index] est alors le suivant.
    """
    if not playlist:
        return
    if current_override:
        current, upcoming = current_override, _cycle(playlist, current_index)[:min(UPCOMING_COUNT, len(playlist))]
    else:
        current, upcoming = playlist[current_index], _cycle(playlist, current_index + 1)[:min(UPCOMING_COUNT, len(playlist) - 1)]
    try:
        _write_json(STATE_FILE, {"current": current, "upcoming": upcoming, "updated": time.time()})
    except OSError:
        pass


def read_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def request_order(paths):
    """Demande au diaporama d'afficher ces médias dans cet ordre, avant les autres."""
    _write_json(ORDER_FILE, {"order": [str(p) for p in paths], "requested": time.time()})


def apply_requested_order(playlist, next_index):
    """
    Si un nouvel ordre a été demandé, retourne (playlist réordonnée, 0) : les médias demandés d'abord,
    puis le reste de la boucle. Sinon retourne (playlist, next_index) inchangés.
    Les médias inconnus de la playlist sont ignorés ; chaque média demandé n'est déplacé qu'une fois.
    """
    try:
        order = json.loads(ORDER_FILE.read_text()).get("order", [])
    except (OSError, json.JSONDecodeError):
        return playlist, next_index
    ORDER_FILE.unlink(missing_ok=True)
    if not playlist:
        return playlist, next_index

    rest = _cycle(playlist, next_index % len(playlist))
    by_real = {}
    for i, p in enumerate(rest):
        by_real.setdefault(os.path.realpath(p), []).append(i)
    first, taken = [], set()
    for p in order:
        positions = by_real.get(os.path.realpath(p))
        if positions:
            i = positions.pop(0)  # une occurrence (une photo favorite peut apparaître plusieurs fois)
            first.append(rest[i])
            taken.add(i)
    if not first:
        return playlist, next_index
    return first + [p for i, p in enumerate(rest) if i not in taken], 0
