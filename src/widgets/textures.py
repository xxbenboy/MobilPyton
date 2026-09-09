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
    # grass_far n'est pas ici : il EMPRUNTE tout a grass (voir ALIAS).
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
}


# ------------------------------------------------------------------ #
# SURFACES EMPRUNTEES
# ------------------------------------------------------------------ #
# Certaines surfaces montrent LA MEME MATIERE qu'une autre, juste plus loin.
# La crete de l'horizon en plaine, c'est de l'herbe -- la meme. Lui donner ses
# propres images reviendrait a payer deux fois le meme poids dans l'APK pour
# afficher deux fois la meme chose, et surtout a les desynchroniser : le jour
# ou l'on remplace grass_B.png, la crete garderait l'ancienne herbe.
#
# Une surface empruntee reprend donc les trois cartes de sa source, avec un
# ASSOMBRISSEMENT : c'est ce qui la detache du champ juste devant, et ce qui
# dit "ca, c'est plus loin". La valeur multiplie la couleur (1.0 = identique).
#
#    nom emprunteur : (nom source, assombrissement)
ALIAS = {
    "grass_far": ("grass", 0.82),
}


def _alias(name):
    """(surface qui fournit les images, assombrissement a appliquer)."""
    return ALIAS.get(name, (name, 1.0))


def tile_for(name):
    """Taille d'une repetition. Une surface empruntee prend celle de sa
    source : c'est la MEME image, elle doit se repeter au meme rythme."""
    if name in TILE_PX:
        return TILE_PX[name]
    return TILE_PX.get(_alias(name)[0], DEFAULT_TILE)


_CACHE = {}      # chemin -> texture (ou None)


def _load(path):
    if path not in _CACHE:
        tex = None
        try:
            # MIPMAP : le sol est vu en perspective, donc une tuile lointaine
            # peut n'occuper que quelques dizaines de pixels. Sans mipmap, la
            # carte graphique pioche alors UN pixel au hasard dans les 512 de
            # l'image : le fond se met a fourmiller, et le fourmillement bouge
            # des que la scene bouge. Le mipmap garde des versions reduites,
            # deja moyennees, et choisit la bonne selon la taille a l'ecran.
            # (Il exige des images en puissance de 2 -- ce que le LISEZMOI
            # demande deja.)
            tex = CoreImage(path, mipmap=True).texture
            tex.wrap = "repeat"
            try:
                tex.min_filter = "linear_mipmap_linear"
            except Exception:
                pass
        except Exception:
            tex = None
        if tex is None:                    # repli : sans mipmap, mais visible
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
    """BaseColor : <nom>_B, ou ancien <nom> (compat), sinon None.

    Une surface EMPRUNTEE (voir ALIAS) va chercher celle de sa source, mais
    seulement si sa source en a une : deposer un vrai grass_far_B.png reste
    possible et reprend la main."""
    src = _alias(name)[0]
    return (_find(name, SUFFIX_BASE) or _find(name, "")
            or (_find(src, SUFFIX_BASE) or _find(src, "") if src != name
                else None))


def normal_texture(name):
    """Carte de normales : <nom>_R, sinon celle de la source, sinon None."""
    src = _alias(name)[0]
    return _find(name, SUFFIX_NORMAL) or (_find(src, SUFFIX_NORMAL)
                                          if src != name else None)


def packed_texture(name):
    """Carte packed : <nom>_P, sinon celle de la source, sinon None."""
    src = _alias(name)[0]
    return _find(name, SUFFIX_PACKED) or (_find(src, SUFFIX_PACKED)
                                          if src != name else None)


def has_any_normal():
    """Vrai si AU MOINS une carte de normales existe (active l'eclairage)."""
    for name in FALLBACKS:
        if normal_texture(name) is not None:
            return True
    return False


def fallback(name):
    """Couleur de repli. Une surface empruntee derive la sienne de sa source,
    avec le meme assombrissement que sa texture : les deux chemins (avec ou
    sans images) donnent ainsi le meme rapport clair/sombre."""
    if name not in FALLBACKS:
        src, k = _alias(name)
        if src != name:
            r, g, b, a = FALLBACKS.get(src, (0.5, 0.5, 0.5, 1))
            return (r * k, g * k, b * k, a)
    return FALLBACKS.get(name, (0.5, 0.5, 0.5, 1))


def paint(name, alpha=1.0):
    """A appeler DANS un bloc `with canvas`. Pose la couleur de dessin et
    renvoie la BaseColor a passer a la forme (texture=...), ou None si absente.

    - BaseColor presente -> Color(k,k,k,alpha), ou k est l'assombrissement de
      la surface (1 = la texture fournit la couleur telle quelle).
    - Sinon              -> Color(couleur de repli) (avec alpha)."""
    tex = base_texture(name)
    if tex is None:
        r, g, b, a = fallback(name)
        Color(r, g, b, a * alpha)
    else:
        k = _alias(name)[1]
        Color(k, k, k, alpha)
    return tex


def paint_color(name, color):
    """Comme paint(), mais la couleur de repli est CELLE fournie (`color`)."""
    tex = base_texture(name)
    if tex is None:
        Color(*color)
    else:
        k = _alias(name)[1]
        Color(k, k, k, color[3] if len(color) > 3 else 1)
    return tex


# ------------------------------------------------------------------ #
# SENS DE L'IMAGE  (pourquoi tous les "v" sont NEGATIFS ici)
# ------------------------------------------------------------------ #
# Une image PNG se lit de HAUT en BAS, une texture OpenGL de BAS en HAUT.
# Kivy compense en retournant lui-meme les coordonnees d'une texture : c'est
# ce que fait `texture.tex_coords`, utilise quand on ne precise RIEN.
#
# Mais des qu'on fournit nos propres `tex_coords` (pour repeter la texture, ou
# pour un maillage), on court-circuite cette compensation et on parle
# directement a OpenGL : v = 0 tombe alors sur la PREMIERE ligne du PNG, donc
# sur le HAUT de l'image. Un v qui monte avec l'ecran descend donc dans
# l'image, et le sol s'affiche a l'envers.
#
# La regle, partout ou l'on ecrit des coordonnees a la main : v DESCEND quand
# l'ecran MONTE (v negatif vers le haut). La repetition (wrap="repeat") rend
# les valeurs negatives parfaitement legitimes.

def tiled_coords(w, h, tile_px):
    """tex_coords pour repeter une texture tous les ~`tile_px` pixels."""
    u = max(1.0, float(w) / tile_px)
    v = max(1.0, float(h) / tile_px)
    # Coins dans l'ordre de Kivy : bas-gauche, bas-droit, haut-droit,
    # haut-gauche. Le haut recoit -v (voir la note ci-dessus).
    return (0, 0, u, 0, u, -v, 0, -v)
