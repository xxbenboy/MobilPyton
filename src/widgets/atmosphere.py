"""
IMAGES DU CIEL (soleil, lune, degrade de la journee).

Le dossier assets/Atmospheres/ etait RESERVE : y deposer une image ne faisait
rien. Ce module le branche.

Comme pour le decor, les images sont FACULTATIVES : sans elles, le ciel garde
ses disques dessines au canvas. Avec elles, le soleil et la lune prennent leur
vrai visage.

La LUNE est un cas a part. Elle n'est pas dessinee comme un disque mais comme
un maillage limite a sa portion ECLAIREE (c'est ce qui donne les croissants et
les quartiers). L'image n'est donc pas posee par-dessus : elle est plaquee SUR
ce maillage, et se trouve donc decoupee par la phase. Un croissant montre le
bon morceau de la vraie lune, pas une image entiere rognee au hasard.
"""
import os

from kivy.core.image import Image as CoreImage

_HERE = os.path.dirname(os.path.abspath(__file__))
ATMOSPHERE_DIR = os.path.abspath(os.path.join(_HERE, "..", "..", "assets",
                                              "Atmospheres"))

_EXTS = (".png", ".jpg", ".jpeg")
_CACHE = {}


def _chemin(name):
    """Chemin du fichier portant ce nom, quelle que soit son extension."""
    for ext in _EXTS:
        path = os.path.join(ATMOSPHERE_DIR, name + ext)
        if os.path.isfile(path):
            return path
    return None


def sprite(name):
    """Image du ciel portant ce nom (sun, moon...), ou None si absente."""
    if name not in _CACHE:
        tex = None
        path = _chemin(name)
        if path is not None:
            try:
                tex = CoreImage(path).texture
                tex.wrap = "clamp_to_edge"
            except Exception:
                tex = None
        _CACHE[name] = tex
    return _CACHE[name]


# --------------------------------------------------------------------- #
# LA LUT DU CIEL : une image = une journee entiere
# --------------------------------------------------------------------- #
# Le degrade du ciel etait calcule : une couleur par heure, et le haut du cadre
# etait cette meme couleur multipliee par 0,4. Le haut ne pouvait donc jamais
# avoir une TEINTE differente du bas -- or c'est precisement ce que fait un
# vrai ciel au crepuscule : l'horizon flambe orange pendant que le zenith est
# deja bleu-violet. Multiplier l'orange par 0,4 donne du brun, pas du violet.
#
# sky_lut.png porte donc la journee entiere :
#
#     une COLONNE = un instant (0 h a gauche, 24 h a droite, cyclique)
#     dans la colonne, le BAS de l'image est le BAS du cadre
#
# L'image EST le ciel : aucune transformation cachee, ce qui est peint est ce
# qui s'affiche. Sans le fichier, le jeu revient a son degrade calcule.
#
# L'ORIENTATION EST TOUT LE CONTRAT de cette image : lue a l'envers, elle
# donnerait un ciel noir au ras du sol et clair au zenith. Or le SENS des
# octets bruts d'une image depend du chargeur qui l'a decodee (c'est le piege
# deja documente dans textures.py, "SENS DE L'IMAGE"), tandis qu'il est
# documente pour read_pixel : origine en HAUT a GAUCHE. On lit donc pixel par
# pixel, et le sens est juste par construction.
#
# Et cela ne coute rien : 6 000 read_pixel se mesurent a 5 ms, une fois pour
# tout le processus. (Le chargement complet en affiche 45, mais ce sont les 40
# ms de mise en route du decodeur d'images, qui seraient payees de toute facon
# -- le decodage de la LUT elle-meme prend 0,3 ms. Passer par les octets bruts
# ferait gagner 2 ms au prix d'un controle du sens a chaque chargement.)

LUT_NAME = "sky_lut"

# Finesse maximale RETENUE. La LUT recommandee fait 96 x 64 ; on la lit telle
# quelle. Mais rien n'empeche d'y deposer un panorama de 4096 x 2048, et huit
# millions de pixels tiendraient de la place pour rien : une LUT plus fine que
# le quart d'heure et que 128 etages n'apporte aucun detail visible, le degrade
# etant de toute facon etire et lisse par la carte graphique.
LUT_MAX_W = 192
LUT_MAX_H = 128

_lut = None
_lut_lue = False


def sky_lut():
    """(largeur, hauteur, colonnes) de la LUT du ciel, ou None si absente.

    `colonnes[i][j]` est le triplet (r, v, b) de la colonne i a la hauteur j,
    avec j = 0 au BAS du cadre. C'est l'ordre dont le degrade a besoin : il se
    remplit du bas vers le haut. Le retournement est fait UNE FOIS ici, au
    chargement, plutot qu'a chaque image."""
    global _lut, _lut_lue
    if _lut_lue:
        return _lut
    _lut_lue = True
    path = _chemin(LUT_NAME)
    if path is None:
        return None
    try:
        # keep_data : sans lui, Kivy jette les pixels apres les avoir
        # televerses et read_pixel leve une exception.
        img = CoreImage(path, keep_data=True)
        pw, ph = int(img.width), int(img.height)
        pas_x = max(1, -(-pw // LUT_MAX_W))
        pas_y = max(1, -(-ph // LUT_MAX_H))
        xs = range(0, pw, pas_x)
        # ph - 1 est la DERNIERE ligne du PNG, donc le BAS du cadre : on part
        # de la et on remonte, pour obtenir j = 0 en bas.
        ys = range(ph - 1, -1, -pas_y)
        cols = [[tuple(img.read_pixel(x, y)[:3]) for y in ys] for x in xs]
        _lut = (len(cols), len(cols[0]), cols)
    except Exception:
        _lut = None
    return _lut
