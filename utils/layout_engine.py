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
from dataclasses import dataclass, field, replace
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
    try:
        every = max(0, int(config.get("compositions_every", 5)))  # 0 : les compositions s'enchaînent
    except (TypeError, ValueError):
        every = 5
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


SECONDS_PER_PHOTO = 2.5  # une composition reste affichée assez longtemps pour regarder chaque photo


def composition_seconds(config, photos):
    """Durée d'affichage d'une composition : au moins la durée réglée, allongée selon le nombre de photos."""
    try:
        base = float(config.get("display_duration", 10))
    except (TypeError, ValueError):
        base = 10
    return max(base, round(photos * SECONDS_PER_PHOTO))


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


def is_message(path):
    """Diapositive d'un message (source « messages »)."""
    return Path(path).parent.name == "messages"


def accepts_messages(style):
    """La disposition peut afficher un message (note, fantôme...) au milieu des photos."""
    return style in compositions.FORMATS and bool(compositions.FORMATS[style][3])


MESSAGE_SLOTS = {"halloween": 3}  # dispositions qui accueillent plusieurs messages à la fois


def plan_for_slide(plan, path, counter, include_messages=True):
    """
    (composition voulue ?, plan à utiliser) pour la diapositive `path`.
    Un message arrive : il est affiché dans une composition qui accepte les messages (plutôt que seul),
    si une telle disposition est disponible.
    """
    if is_video(path):
        return False, plan
    if include_messages and plan.formats and is_message(path):
        formats = [f for f in plan.formats if accepts_messages(f)]
        if formats:
            return True, replace(plan, formats=formats)
    return wants_composition(plan, counter), plan


def spread_messages(playlist, plan, include_messages=True):
    """
    Espace les messages dans la playlist pour que chacun (ou chaque groupe, selon la disposition) soit suivi
    d'assez de photos pour former une composition. L'ordre des photos et celui des messages ne changent pas :
    un message trop proche du précédent est simplement décalé un peu plus loin.
    """
    formats = [f for f in plan.formats if accepts_messages(f)] if include_messages else []
    if not formats or not any(map(is_message, playlist)):
        return playlist
    group_size = min(MESSAGE_SLOTS.get(f, 1) for f in formats)
    gap = max(compositions.FORMATS[f][1] for f in formats)  # photos nécessaires après un groupe de messages
    out, pending = [], []
    need, open_group = 0, 0  # photos encore nécessaires ; messages du groupe en cours (pas encore suivi d'une photo)
    for path in playlist:
        if is_message(path):
            pending.append(path)
        else:
            out.append(path)
            need, open_group = max(0, need - 1), 0
        while pending:
            if 0 < open_group < group_size:  # le groupe en cours a encore de la place
                open_group += 1
            elif need == 0:  # assez de photos depuis le groupe précédent : nouveau groupe
                open_group, need = 1, gap
            else:
                break
            out.append(pending.pop(0))
    return out + pending  # messages restants : en fin de boucle (la playlist recommence par des photos)


def next_composition_start(plan, playlist, start, include_messages=True, max_scan=40):
    """
    Après une composition qui se termine juste avant `start` (compteur remis à zéro), indice où commencera
    la composition suivante, avec le plan à utiliser : (indice, plan), sinon None.
    """
    counter = 0
    for offset in range(min(max_scan, len(playlist))):
        index = start + offset
        wanted, slot_plan = plan_for_slide(plan, playlist[index % len(playlist)], counter, include_messages)
        if wanted and slot_plan.formats:
            return index, slot_plan
        counter += 1
    return None


def take_slides(playlist, start, photos_wanted, message_slots):
    """
    Diapositives d'une composition qui affiche les messages : jusqu'à `message_slots` messages, plus
    `photos_wanted` photos (les messages ne prennent pas la place des photos). S'arrête avant une vidéo,
    et avant un message en trop (il ira dans la composition suivante).
    """
    chunk, photos, messages = [], 0, 0
    for offset in range(len(playlist)):
        path = playlist[(start + offset) % len(playlist)]
        if is_video(path):
            break
        if is_message(path):
            if messages >= message_slots:
                break
            messages += 1
        else:
            photos += 1
        chunk.append(path)
        if photos >= photos_wanted:
            break
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
    Un message de la file devient une note dans la composition (un seul, sauf MESSAGE_SLOTS : plusieurs fantômes).
    """
    rng = rng or random.Random()
    _label, min_n, max_n, accepts_message, render = compositions.FORMATS[style]
    slots = MESSAGE_SLOTS.get(style, 1)
    notes, photos, used = [], [], 0
    for path in chunk:
        note = message_for_path(path, messages_by_id) if include_messages and accepts_message else None
        if note is not None:
            if len(notes) >= slots:
                break  # message en trop : il ira dans la composition suivante
            notes.append(note)
            used += 1
            continue
        if len(photos) >= max_n:
            break  # disposition complète : les diapositives suivantes restent pour la suite
        photo = compositions.load_photo(path, max_side=max(width, height) // (1 if len(chunk) <= 3 else 2))
        if photo is not None:
            photos.append(photo)
        used += 1
    message = notes if slots > 1 else (notes[0] if notes else None)  # plusieurs messages : liste (ex. fantômes)
    # Ajuster au nombre d'éléments accepté par la mise en page (les diapositives en trop restent pour la suite)
    takes_slot = 1 if (notes and style in compositions.LIMITS) else 0
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
