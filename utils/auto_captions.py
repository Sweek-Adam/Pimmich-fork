"""
Légendes proposées automatiquement : une courte description de chaque photo (« Trois enfants sur la plage au coucher du
soleil ») et des mots-clés, qui servent à la recherche de la bibliothèque et qu'on peut adopter comme légende en un clic.
Elles ne remplacent jamais une légende écrite à la main.

Deux façons, au choix :
- « immich » : mots-clés seulement, déduits de la recherche par contenu d'Immich (son analyse des images tourne sur le
  serveur Immich de la maison) ; gratuit, mais seulement pour les photos importées d'Immich ;
- « claude » : une vraie phrase et des mots-clés, écrits par Claude (Anthropic) d'après une copie réduite de la photo.
  Les photos quittent alors la maison : désactivé par défaut, avec une clé d'API à saisir, et un coût par photo.
Le travail se fait la nuit, par petits lots (utils/night_work.py n'est pas gêné : une photo à la fois).
"""
import base64
import io
import json
import threading
import time
from pathlib import Path

from PIL import Image, ImageOps

PROJECT_DIR = Path(__file__).resolve().parent.parent
STORE = PROJECT_DIR / "cache" / "auto_captions.json"
MODEL = "claude-opus-5-5"
MAX_SIDE = 1024           # copie réduite envoyée (assez pour décrire, peu de jetons)
PER_NIGHT = 150
IMMICH_TOP = 40           # pour chaque mot-clé : les photos les mieux classées par Immich
_lock = threading.Lock()

# Mots-clés cherchés dans Immich (requête en anglais, comprise par son modèle) -> mot affiché
CONCEPTS = [
    ("beach", "plage"), ("sea", "mer"), ("mountain", "montagne"), ("snow", "neige"), ("forest", "forêt"),
    ("sunset", "coucher de soleil"), ("city at night", "ville la nuit"), ("garden", "jardin"), ("lake", "lac"),
    ("birthday cake", "anniversaire"), ("christmas tree", "Noël"), ("wedding", "mariage"), ("party", "fête"),
    ("baby", "bébé"), ("children playing", "enfants qui jouent"), ("family group photo", "photo de famille"),
    ("selfie", "selfie"), ("dog", "chien"), ("cat", "chat"), ("horse", "cheval"), ("food on a table", "repas"),
    ("swimming pool", "piscine"), ("bicycle", "vélo"), ("car", "voiture"), ("boat", "bateau"), ("airplane", "avion"),
    ("flowers", "fleurs"), ("museum", "musée"), ("concert", "concert"), ("sport", "sport"), ("costume", "déguisement"),
    ("school", "école"), ("hiking", "randonnée"), ("camping tent", "camping"), ("fireworks", "feu d'artifice"),
    ("rain", "pluie"), ("castle", "château"), ("church", "église"), ("carnival", "carnaval"), ("halloween", "Halloween"),
]


def load():
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(data):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STORE)


def store(results):
    """Ajoute des résultats {clé: {caption?, tags}} (les mots-clés existants sont gardés)."""
    with _lock:
        data = load()
        for key, entry in results.items():
            old = data.get(key, {})
            tags = list(dict.fromkeys(list(old.get("tags", [])) + list(entry.get("tags", []))))[:12]
            data[key] = {**old, **{k: v for k, v in entry.items() if v}, "tags": tags, "at": time.time()}
        _save(data)


def text_for(key, data=None):
    """Texte cherchable (description et mots-clés) d'une photo."""
    entry = (data if data is not None else load()).get(key) or {}
    return " ".join([entry.get("caption", "")] + entry.get("tags", []))


# --- Immich : mots-clés ---

def immich_tags(config, keys):
    """Mots-clés des photos `keys` (source/nom) d'après la recherche par contenu d'Immich : {clé: {"tags": [...]}}."""
    from utils import immich_search
    found = {}
    for query, label in CONCEPTS:
        try:
            names = immich_search.smart_search(config, query, size=IMMICH_TOP)
        except Exception:
            continue
        for key in keys:
            if immich_search.rank(key, names) is not None:
                found.setdefault(key, {"tags": [], "how": "immich"})["tags"].append(label)
    return found


# --- Claude : une phrase et des mots-clés ---

PROMPT = ("Voici une photo de famille affichée sur un cadre photo. Écris une seule phrase courte et naturelle qui la décrit "
          "(au plus 15 mots, sans « On voit » ni « Cette photo »), puis, sur une deuxième ligne commençant par « Mots-clés : », "
          "4 à 6 mots-clés simples séparés par des virgules (lieu, saison, activité, animaux, objets). Ne devine ni les noms "
          "des personnes ni leur âge. Réponds en {language}.")
LANGUAGES = {"fr": "français", "en": "anglais", "es": "espagnol", "de": "allemand", "ja": "japonais"}


def _jpeg_b64(path):
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((MAX_SIDE, MAX_SIDE))
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=85)
    return base64.standard_b64encode(buffer.getvalue()).decode("ascii")


def parse(text):
    """« Phrase.\\nMots-clés : a, b, c » -> (phrase, [a, b, c])."""
    caption, tags = "", []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        head, sep, rest = line.partition(":")
        if sep and head.strip().lower().replace("-", "").replace(" ", "") in ("motsclés", "motscles", "keywords", "palabrasclave", "schlüsselwörter", "キーワード"):
            tags = [t.strip(" .") for t in rest.split(",") if t.strip(" .")][:8]
        elif not caption:
            caption = line.strip('"« »')[:200]
    return caption, tags


def claude_caption(config, path, client=None):
    """Description d'une photo par Claude : (phrase, mots-clés), ou None si Claude refuse de la décrire."""
    import anthropic
    client = client or anthropic.Anthropic(api_key=config.get("anthropic_api_key"))
    language = LANGUAGES.get((config.get("language") or "fr")[:2], "français")
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=1024,
        output_config={"effort": "low"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _jpeg_b64(path)}},
            {"type": "text", "text": PROMPT.format(language=language)},
        ]}],
    )
    if response.stop_reason == "refusal":
        return None
    text = "".join(block.text for block in response.content if block.type == "text")
    return parse(text)


def pending(keys, data=None, how=None):
    """Photos sans proposition (ou, pour `how`, sans proposition de cette façon-là)."""
    data = data if data is not None else load()
    return [k for k in keys if k not in data or (how and data[k].get("how") != how and not data[k].get("caption"))]
