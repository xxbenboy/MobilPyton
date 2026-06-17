"""
Systeme de TEXTURES PBR (Physically Based Rendering), seamless.

Chaque surface peut recevoir un JEU de 3 images (toutes optionnelles) :
    <nom>_B.png   BaseColor  (couleur / albedo)         -> ce qu'on voit
    <nom>_R.png   Normal     (relief / carte de normales) -> eclairage
    <nom>_P.png   Packed     (AO/Rugosite/Metallique...)   -> occlusion (canal R)

A deposer dans  assets/textures/  (voir LISEZMOI.txt).

- Si la BaseColor existe -> elle habille la surface ; sinon couleur plane de
  repli (le rendu actuel est preserve sans aucune image).
- Si des cartes Normal existent -> un eclairage par relief s'active (shader).
- Compat : un ancien fichier  <nom>.png  (sans suffixe) est pris comme BaseColor.

Pour une repetition propre : PNG CARRES en puissance de 2 (256 ou 512),
"seamless" (bords raccord).
"""
import os

from kivy.core.image import Image as CoreImage
from kivy.graphics import Color

_HERE = os.path.dirname(os.path.abspath(__file__))
TEXTURES_DIR = os.path.abspath(os.path.join(_HERE, "..", "..", "assets",
                                            "textures"))

# Suffixes des 3 cartes PBR (confirme par l'utilisateur).
SUFFIX_BASE = "_B"     # BaseColor
SUFFIX_PACKED = "_P"   # Packed (AO / Rugosite / Metallique)
SUFFIX_NORMAL = "_R"   # Normal (relief)

# Couleur de repli par surface (si pas de BaseColor). Colle au rendu actuel.
FALLBACKS = {
    "grass":            (0.26, 0.42, 0.19, 1),
    "grass_far":        (0.36, 0.50, 0.26, 1),
    "forest_floor":     (0.12, 0.15, 0.09, 1),
    "forest_floor_far": (0.18, 0.22, 0.13, 1),
    "rock":             (0.42, 0.41, 0.46, 1),
    "rock_dark":        (0.33, 0.32, 0.37, 1),
    "water":            (0.15, 0.38, 0.58, 1),
    "sand":             (0.32, 0.30, 0.22, 1),
    "bark":             (0.28, 0.19, 0.11, 1),
    "foliage":          (0.09, 0.18, 0.11, 1),
    "skin":             (0.84, 0.66, 0.50, 1),
}

# Taille (en pixels ecran) d'UNE repetition de la texture, par surface.
# Plus la valeur est GRANDE, plus la texture parait ZOOMEE (elle se repete
# moins souvent, donc ses motifs sont plus gros). 256 = defaut.
DEFAULT_TILE = 256
TILE_PX = {
    "grass": 448,        # ~1.75x la taille de base (256)
    "grass_far": 448,
}


def tile_for(name):
    return TILE_PX.get(name, DEFAULT_TILE)


_CACHE = {}      # chemin -> texture (ou None)


def _load(path):
    if path not in _CACHE:
        tex = None
        try:
            tex = CoreImage(path).texture
            tex.wrap = "repeat"
        except Exception:
            tex = None
        _CACHE[path] = tex
    return _CACHE[path]


def _find(name, suffix=""):
    """Texture pour <name><suffix> si un fichier existe, sinon None."""
    for ext in (".png", ".jpg", ".jpeg"):
        p = os.path.join(TEXTURES_DIR, name + suffix + ext)
        if os.path.isfile(p):
            return _load(p)
    return None


def base_texture(name):
    """BaseColor : <nom>_B, ou ancien <nom> (compat), sinon None."""
    return _find(name, SUFFIX_BASE) or _find(name, "")


def normal_texture(name):
    """Carte de normales : <nom>_R, sinon None."""
    return _find(name, SUFFIX_NORMAL)


def packed_texture(name):
    """Carte packed : <nom>_P, sinon None."""
    return _find(name, SUFFIX_PACKED)


def has_any_normal():
    """Vrai si AU MOINS une carte de normales existe (active l'eclairage)."""
    for name in FALLBACKS:
        if normal_texture(name) is not None:
            return True
    return False


def fallback(name):
    return FALLBACKS.get(name, (0.5, 0.5, 0.5, 1))


def paint(name, alpha=1.0):
    """A appeler DANS un bloc `with canvas`. Pose la couleur de dessin et
    renvoie la BaseColor a passer a la forme (texture=...), ou None si absente.

    - BaseColor presente -> Color(1,1,1,alpha) (la texture fournit la couleur).
    - Sinon              -> Color(couleur de repli) (avec alpha)."""
    tex = base_texture(name)
    if tex is None:
        r, g, b, a = fallback(name)
        Color(r, g, b, a * alpha)
    else:
        Color(1, 1, 1, alpha)
    return tex


def paint_color(name, color):
    """Comme paint(), mais la couleur de repli est CELLE fournie (`color`)."""
    tex = base_texture(name)
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
