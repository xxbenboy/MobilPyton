"""
Polices personnalisees (optionnelles).

But : pouvoir utiliser une police speciale pour le TITRE (et, si voulu, pour
le reste de l'interface) SANS faire planter l'app si le fichier de police
n'est pas encore present.

Fonctionnement :
- On cherche un fichier dans `assets/fonts/` :
    * title.ttf (ou .otf)  -> police du TITRE
    * ui.ttf    (ou .otf)  -> police du reste du texte (optionnel)
- Si le fichier existe, on l'enregistre et on renvoie son nom.
- Sinon, on renvoie "Roboto" (la police par defaut de Kivy).

=> Tant que tu n'as pas mis de fichier, tout marche avec la police par defaut.
   Des que tu deposes `assets/fonts/title.ttf`, le titre l'utilise au prochain
   lancement (voir assets/fonts/LISEZMOI.txt).
"""
import os

from kivy.core.text import LabelBase

# Dossier des polices, calcule par rapport a ce fichier (marche sur PC et
# une fois empaquete dans l'APK).
_HERE = os.path.dirname(os.path.abspath(__file__))
_FONTS_DIR = os.path.abspath(os.path.join(_HERE, "..", "..", "assets", "fonts"))

_cache = {}


def _find(*names):
    for name in names:
        path = os.path.join(_FONTS_DIR, name)
        if os.path.isfile(path):
            return path
    return None


def _resolve(cache_key, registered_name, *filenames):
    """Enregistre la police si le fichier existe, sinon renvoie Roboto."""
    if cache_key in _cache:
        return _cache[cache_key]
    path = _find(*filenames)
    if path:
        LabelBase.register(name=registered_name, fn_regular=path)
        result = registered_name
    else:
        result = "Roboto"        # police par defaut de Kivy
    _cache[cache_key] = result
    return result


def title_font():
    """Police du titre.

    Cherche assets/fonts/title.ttf (regulier) et, en option,
    assets/fonts/title-bold.ttf (gras). Repli sur Roboto si absent.
    """
    if "title" in _cache:
        return _cache["title"]
    regular = _find("title.ttf", "title.otf")
    bold = _find("title-bold.ttf", "title-bold.otf")
    if regular:
        kwargs = {"name": "WildTitle", "fn_regular": regular}
        if bold:
            kwargs["fn_bold"] = bold
        LabelBase.register(**kwargs)
        result = "WildTitle"
    else:
        result = "Roboto"
    _cache["title"] = result
    return result


def ui_font():
    """Police du reste du texte (assets/fonts/ui.ttf si present)."""
    return _resolve("ui", "WildUI", "ui.ttf", "ui.otf")
