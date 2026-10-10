"""
Dispositions du diaporama : « Photo unique » et les compositions (liège, mosaïque, Hokusai...).

Un même choix de disposition s'utilise partout :
  - « auto »          : selon les réglages (dispositions cochées, une composition toutes les N photos) ;
  - « unique »        : photo unique uniquement (diaporama classique) ;
  - « compositions »  : uniquement des compositions, format tiré au hasard parmi ceux cochés ;
  - <clé de format>   : uniquement ce format (ex. « liege », « hokusai »).
Il s'applique au diaporama (réglages ou choix rapide) et à chaque playlist (par défaut : comme le diaporama).

Les compositions prennent les photos suivantes de la playlist, dans l'ordre : une composition de 4 photos
« consomme » 4 diapositives. L'onglet « À suivre » et l'ordre des playlists restent ainsi cohérents.
"""
import random
from dataclasses import dataclass, field
from pathlib import Path

from utils import compositions
from utils.message_renderer import N_

AUTO, UNIQUE, COMPOSITIONS = "auto", "unique", "compositions"
VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv")


@dataclass
class LayoutPlan:
    unique: bool                       # la photo unique fait partie des dispositions
    formats: list = field(default_factory=list)  # formats de composition possibles
    every: int = 5                     # avec la photo unique : une composition toutes les `every` photos
    seasonal: bool = True              # pondération des thèmes de saison


def choice_options():
    """Valeurs proposées dans les sélecteurs (valeur, libellé à traduire, groupe)."""
    options = [(AUTO, N_("Selon les réglages"), None), (UNIQUE, N_("Photo unique"), None),
               (COMPOSITIONS, N_("Compositions uniquement (au hasard)"), None)]
    for key, (label, *_rest) in compositions.FORMATS.items():
        options.append((key, label, "theme" if key in compositions.THEME_KEYS else "format"))
    return options


def is_valid_choice(choice):
    return choice in (AUTO, UNIQUE, COMPOSITIONS) or choice in compositions.FORMATS


def resolve(config, choice=None, today=None):
    """
    Plan d'affichage pour un choix donné (None : choix rapide des réglages, `layout_override`).
    Un format choisi explicitement est utilisé même hors de sa saison.
    """
    choice = choice if choice not in (None, AUTO) else config.get("layout_override", AUTO)
    every = max(1, int(config.get("compositions_every", 5) or 5))
    seasonal = config.get("compositions_seasonal", True)
    enabled = compositions.enabled_formats(config)
    if seasonal:
        in_season = [k for k in enabled if k not in compositions.SEASONAL or compositions.in_season(k, today)]
    else:
        in_season = enabled

    if choice == UNIQUE:
        return LayoutPlan(True, [], every, seasonal)
    if choice == COMPOSITIONS:
        return LayoutPlan(False, in_season or [k for k in compositions.BASIC_FORMATS], every, seasonal)
    if choice in compositions.FORMATS:
        return LayoutPlan(False, [choice], every, seasonal)

    unique = config.get("unique_enabled", True)
    formats = in_season if config.get("compositions_enabled", True) else []
    if not unique and not formats:
        unique = True
    return LayoutPlan(unique, formats, every, seasonal)


def wants_composition(plan, photos_since_composition):
    return bool(plan.formats) and (not plan.unique or photos_since_composition >= plan.every)


def pick_format(plan, rng=None, today=None):
    """Format tiré au hasard ; les thèmes de saison sont trois fois plus fréquents pendant leur période."""
    rng = rng or random.Random()
    weighted = []
    for key in plan.formats:
        weight = 3 if plan.seasonal and key in compositions.SEASONAL and compositions.in_season(key, today) and len(plan.formats) > 1 else 1
        weighted += [key] * weight
    return rng.choice(weighted) if weighted else None


def photo_count(style, rng):
    """Nombre de diapositives qu'une composition de ce format va regrouper."""
    _label, min_n, max_n, _accepts, _render = compositions.FORMATS[style]
    if style in compositions.LIMITS:
        return rng.choice(sorted(compositions.LIMITS[style]))
    if style == "photomaton":
        return rng.choice([8, 12])
    return rng.randint(min_n, max_n)


def is_video(path):
    return str(path).lower().endswith(VIDEO_EXTENSIONS)


def take_chunk(playlist, start, count):
    """
    Les `count` diapositives suivantes à partir de `start` (la playlist boucle), en s'arrêtant avant une vidéo :
    les vidéos restent toujours en photo unique.
    """
    chunk = []
    if not playlist:
        return chunk
    for offset in range(min(count, len(playlist))):
        path = playlist[(start + offset) % len(playlist)]
        if is_video(path):
            break
        chunk.append(path)
    return chunk


def message_for_path(path, messages_by_id):
    """Message correspondant à une image de la source « messages », sinon None."""
    p = Path(path)
    if p.parent.name == "messages":
        return messages_by_id.get(p.stem)
    return None


def render_chunk(style, chunk, messages_by_id, width, height, include_messages=True, rng=None):
    """
    Compose les diapositives `chunk` (dans l'ordre) avec le format `style`.
    Retourne (image, nombre de diapositives utilisées) ou (None, 0) si le format ne peut pas les accueillir.
    Un message de la file devient une note dans la composition (au plus un par composition).
    """
    rng = rng or random.Random()
    _label, min_n, _max_n, accepts_message, render = compositions.FORMATS[style]
    message, photos, used = None, [], 0
    for path in chunk:
        note = message_for_path(path, messages_by_id) if include_messages and accepts_message else None
        if note is not None and message is None:
            message = note
            used += 1
            continue
        photo = compositions.load_photo(path, max_side=max(width, height) // (1 if len(chunk) <= 3 else 2))
        if photo is not None:
            photos.append(photo)
        used += 1
    # Ajuster au nombre d'éléments accepté par la mise en page (les diapositives en trop restent pour la suite)
    takes_slot = 1 if (message is not None and style in compositions.LIMITS) else 0
    if style in compositions.LIMITS:
        while photos and len(photos) + takes_slot not in compositions.LIMITS[style]:
            photos.pop()
            used -= 1
    if style == "photomaton":
        keep = (len(photos) // 4) * 4
        used -= len(photos) - keep
        photos = photos[:keep]
    if len(photos) < max(1, min_n - takes_slot):
        return None, 0
    return render(photos, message, width, height, rng), max(1, used)
