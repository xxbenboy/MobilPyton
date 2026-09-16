"""
IMAGES DU DECOR (arbres, plantes, fleurs, pierres...).

Le dossier assets/Landscapes_Foliages/ etait jusqu'ici RESERVE : y deposer une
image ne faisait rien. Ce module le branche.

Regle : chaque element du decor a un NOM (voir la table du LISEZMOI). Si une
image porte ce nom, elle est dessinee a la place de la forme geometrique ;
sinon le dessin procedural d'origine est conserve. Le jeu reste donc identique
tant qu'aucune image n'est fournie, et s'embellit image par image.

VARIANTES : plusieurs versions d'un meme element evitent la foret de clones.
    fern.png  fern_2.png  fern_3.png ...
Le jeu les repere tout seul et en choisit une par element, de facon STABLE
(tiree du hasard de la scene) : une fougere ne change pas d'aspect entre deux
redessins de la meme case.

Les images gardent leurs PROPORTIONS : c'est la HAUTEUR demandee par la scene
qui commande, la largeur suit. Une image portrait donne donc un arbre elance,
une image carree un buisson trapu, sans deformation.
"""
import os

from kivy.core.image import Image as CoreImage
from kivy.graphics.texture import Texture

_HERE = os.path.dirname(os.path.abspath(__file__))
FOLIAGE_DIR = os.path.abspath(os.path.join(_HERE, "..", "..", "assets",
                                           "Landscapes_Foliages"))

_EXTS = (".png", ".jpg", ".jpeg")

# Nombre maximum de variantes cherchees par nom (nom, nom_2 ... nom_8).
MAX_VARIANTS = 8

_CACHE = {}          # nom -> [textures] (liste vide si aucune image)
_OMBRES = {}         # nom -> [silhouettes] (voir silhouette())


def _load(path):
    try:
        tex = CoreImage(path).texture
    except Exception:
        return None
    # Les images du decor sont DETOUREES et posees une par une : elles ne se
    # repetent jamais. Un bord "clamp" evite qu'un pixel du bord oppose vienne
    # baver sur la silhouette.
    tex.wrap = "clamp_to_edge"
    return tex


def _find_one(stem):
    for ext in _EXTS:
        path = os.path.join(FOLIAGE_DIR, stem + ext)
        if os.path.isfile(path):
            return _load(path)
    return None


def variants(name):
    """Toutes les images disponibles pour cet element (liste, parfois vide)."""
    if name not in _CACHE:
        found = []
        first = _find_one(name)
        if first is not None:
            found.append(first)
        for i in range(2, MAX_VARIANTS + 1):
            tex = _find_one("%s_%d" % (name, i))
            if tex is not None:
                found.append(tex)
        _CACHE[name] = found
    return _CACHE[name]


def sprite(name, pick=None):
    """Une image pour cet element, ou None si aucune n'a ete fournie.

    `pick` est un ENTIER qui choisit la variante. On prend volontairement un
    entier plutot qu'un tirage au sort : l'appelant le derive de la POSITION de
    l'element, donc une fougere garde son aspect meme quand la scene est
    redessinee avec un objet en moins (une recolte, par exemple). Avec un
    hasard partage, retirer un element decalait le tirage de tous les
    suivants et la case entiere changeait de visage a chaque ramassage."""
    found = variants(name)
    if not found:
        return None
    if pick is None:
        return found[0]
    return found[int(pick) % len(found)]


def _silhouette_de(path):
    """Construit la SILHOUETTE d'une image : sa forme, en blanc.

    Meme taille, meme canal alpha, mais le rouge, le vert et le bleu mis a
    fond. Dessinee avec une Color, elle pose donc un APLAT de cette couleur
    exactement sur la forme de l'element -- ce qu'un Rectangle ne sait pas
    faire, lui qui teinterait aussi le vide autour.

    C'est l'outil qui manquait pour ETALONNER une photo : la multiplier par
    une teinte ne change que sa couleur, jamais son contraste, et une photo de
    studio garde donc dans une scene stylisee des noirs et des blancs que rien
    d'autre n'a. Un aplat pose par-dessus, lui, rapproche la photo de la
    couleur du decor -- c'est ce que fait l'air entre l'oeil et la pierre.

    On relit les octets bruts (image._data[0]) plutot que pixel par pixel :
    une pepite fait 256 px de large, et read_pixel aurait coute une demi-
    seconde par variante au premier affichage (mesure faite sur les buches).
    """
    try:
        img = CoreImage(path)
        brut = img.image._data[0]
        donnees = bytearray(brut.data)
        if (brut.fmt or "rgba") != "rgba" or len(donnees) < 4:
            return None
    except Exception:
        return None
    # R, G, B a fond ; l'alpha, lui, ne bouge pas : c'est lui la forme.
    for c in range(3):
        donnees[c::4] = b"\xff" * (len(donnees) // 4)
    tex = Texture.create(size=(brut.width, brut.height), colorfmt="rgba")
    tex.blit_buffer(bytes(donnees), colorfmt="rgba", bufferfmt="ubyte")
    tex.wrap = "clamp_to_edge"
    return tex


def _chemin(stem):
    for ext in _EXTS:
        path = os.path.join(FOLIAGE_DIR, stem + ext)
        if os.path.isfile(path):
            return path
    return None


def silhouette(name, pick=None):
    """La silhouette de la variante choisie, ou None. Voir _silhouette_de.

    ATTENTION AU SENS : cette texture est televersee dans l'ordre du PNG,
    comme celle de sprite(), mais ses tex_coords par defaut ne sont pas
    retournees comme celles d'une image chargee. Il faut donc TOUJOURS lui
    fournir ses tex_coords -- ce que fait de toute facon l'appelant, qui s'en
    sert pour couper la part enterree."""
    if name not in _OMBRES:
        faites = []
        stems = [name] + ["%s_%d" % (name, i)
                          for i in range(2, MAX_VARIANTS + 1)]
        for stem in stems:
            path = _chemin(stem)
            if path is None:
                continue
            # On ecarte les echecs comme le fait variants(), sans quoi les
            # deux listes ne seraient plus dans le meme ordre et la
            # silhouette ne serait pas celle de l'image.
            sil = _silhouette_de(path)
            if sil is not None:
                faites.append(sil)
        _OMBRES[name] = faites
    faites = _OMBRES[name]
    if not faites:
        return None
    if pick is None:
        return faites[0]
    return faites[int(pick) % len(faites)]


def size_for(tex, height):
    """(largeur, hauteur) d'une image posee a cette HAUTEUR, sans deformation."""
    tw, th = tex.size
    if not th:
        return height, height
    return height * (float(tw) / float(th)), height


def has_any():
    """Vrai si AU MOINS une image de decor a ete fournie."""
    try:
        names = os.listdir(FOLIAGE_DIR)
    except OSError:
        return False
    return any(n.lower().endswith(_EXTS) for n in names)
