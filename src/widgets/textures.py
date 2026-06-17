"""
Systeme de TEXTURES seamless (qui se repetent sans coupure visible).

Depose tes images dans  assets/textures/<nom>.png  (voir LISEZMOI.txt). Si une
texture existe pour une surface, elle l'habille ; sinon on utilise une COULEUR
PLANE de repli -> le jeu reste joli meme sans aucune texture, et s'embellit au
fur et a mesure que tu ajoutes des images.

Pour une repetition propre, utilise des PNG CARRES en puissance de 2
(256x256 ou 512x512) concus "seamless" (les bords se raccordent).
"""
import os

from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Rectangle, Quad, Mesh

_HERE = os.path.dirname(os.path.abspath(__file__))
TEXTURES_DIR = os.path.abspath(os.path.join(_HERE, "..", "..", "assets",
                                            "textures"))

# Couleur de repli par texture (utilisee tant que l'image n'existe pas).
# Choisies pour coller au rendu actuel : sans aucune texture, rien ne change.
FALLBACKS = {
    "grass":            (0.26, 0.42, 0.19, 1),   # herbe proche (plaine)
    "grass_far":        (0.36, 0.50, 0.26, 1),   # herbe lointaine (crete)
    "forest_floor":     (0.12, 0.15, 0.09, 1),   # sol de foret proche
    "forest_floor_far": (0.18, 0.22, 0.13, 1),   # sol de foret lointain
    "rock":             (0.42, 0.41, 0.46, 1),   # roche (montagne)
    "rock_dark":        (0.33, 0.32, 0.37, 1),   # roche en bas (ombre)
    "water":            (0.15, 0.38, 0.58, 1),   # eau (lac)
    "sand":             (0.32, 0.30, 0.22, 1),   # rive / terre
    "bark":             (0.28, 0.19, 0.11, 1),   # ecorce (troncs)
    "foliage":          (0.09, 0.18, 0.11, 1),   # feuillage (arbres/buissons)
    "skin":             (0.84, 0.66, 0.50, 1),   # peau (mains)
}

_CACHE = {}


def texture(name):
    """Texture Kivy (repetable) pour `name`, ou None si l'image n'existe pas."""
    if name not in _CACHE:
        tex = None
        for ext in (".png", ".jpg", ".jpeg"):
            p = os.path.join(TEXTURES_DIR, name + ext)
            if os.path.isfile(p):
                try:
                    tex = CoreImage(p).texture
                    tex.wrap = "repeat"          # repetition seamless
                except Exception:
                    tex = None
                break
        _CACHE[name] = tex
    return _CACHE[name]


def fallback(name):
    return FALLBACKS.get(name, (0.5, 0.5, 0.5, 1))


def paint(name, alpha=1.0):
    """A appeler DANS un bloc `with canvas`. Pose la bonne couleur de dessin et
    renvoie la texture a passer a la forme (ou None s'il n'y a pas de texture).

    - Texture presente -> Color(1,1,1,alpha) (la texture fournit la couleur).
    - Sinon            -> Color(couleur de repli) (avec alpha applique).
    """
    tex = texture(name)
    if tex is None:
        r, g, b, a = fallback(name)
        Color(r, g, b, a * alpha)
    else:
        Color(1, 1, 1, alpha)
    return tex


def paint_color(name, color):
    """Comme paint(), mais la couleur de repli est CELLE fournie (`color`),
    pas la couleur generique du dico. Utile pour les formes dont la teinte
    varie selon le contexte (arbres proches/lointains, buissons...)."""
    tex = texture(name)
    if tex is None:
        Color(*color)
    else:
        Color(1, 1, 1, color[3] if len(color) > 3 else 1)
    return tex


def tiled_coords(w, h, tile_px):
    """tex_coords pour repeter une texture tous les ~`tile_px` pixels."""
    u = max(1.0, float(w) / tile_px)
    v = max(1.0, float(h) / tile_px)
    return (0, 0, u, 0, u, v, 0, v)
