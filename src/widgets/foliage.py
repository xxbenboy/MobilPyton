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
import math
import os
import random

from kivy.core.image import Image as CoreImage

from src.widgets.gl_textures import texture_depuis_octets

_HERE = os.path.dirname(os.path.abspath(__file__))
FOLIAGE_DIR = os.path.abspath(os.path.join(_HERE, "..", "..", "assets",
                                           "Landscapes_Foliages"))

_EXTS = (".png", ".jpg", ".jpeg")

# Nombre maximum de variantes cherchees par nom (nom, nom_2 ... nom_10).
# Dix : la planche de branches livree en porte dix, toutes differentes.
MAX_VARIANTS = 10

_CACHE = {}          # nom -> [textures] (liste vide si aucune image)
_OMBRES = {}         # nom -> [silhouettes] (voir silhouette())
_STEMS = {}          # nom -> [noms de fichier retenus], voir _stems_charges


def _taille_png(path):
    """(largeur, hauteur) lues dans l'en-tete d'un PNG, sans le decoder ; ou
    None pour tout autre fichier."""
    try:
        with open(path, "rb") as f:
            tete = f.read(24)
    except OSError:
        return None
    if len(tete) < 24 or tete[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return (int.from_bytes(tete[16:20], "big"),
            int.from_bytes(tete[20:24], "big"))


def _puissance_de_2(n):
    return n > 0 and n & (n - 1) == 0


def _load(path):
    # UNE IMAGE EN PUISSANCE DE 2 RECOIT DES MIPMAPS. Un petit element du
    # decor -- un baton, une touffe de trefle -- est dessine dix fois plus
    # petit que son image : sans version reduite, la carte graphique y
    # pioche un pixel au hasard, et un baton brun devenait un trait de lichen
    # gris clair. Les mipmaps lui rendent sa couleur moyenne.
    #
    # SEULEMENT en puissance de 2 : un telephone en OpenGL ES 2 refuse les
    # mipmaps sur une autre taille, et l'image s'afficherait NOIRE. Les
    # images plus anciennes (arbres, pepites, herbe) ne le sont pas : elles
    # restent dessinees exactement comme avant. Une image deposee en
    # puissance de 2 doit avoir ses pixels transparents de la couleur de
    # l'objet (et non noirs), sinon ses versions reduites s'assombrissent.
    taille = _taille_png(path)
    mip = bool(taille) and all(_puissance_de_2(v) for v in taille)
    try:
        tex = CoreImage(path, mipmap=mip).texture
    except Exception:
        return None
    # Les images du decor sont DETOUREES et posees une par une : elles ne se
    # repetent jamais. Un bord "clamp" evite qu'un pixel du bord oppose vienne
    # baver sur la silhouette.
    tex.wrap = "clamp_to_edge"
    if mip:
        try:
            tex.min_filter = "linear_mipmap_linear"
        except Exception:
            pass
    return tex


def _find_one(stem):
    for ext in _EXTS:
        path = os.path.join(FOLIAGE_DIR, stem + ext)
        if os.path.isfile(path):
            return _load(path)
    return None


def _stems_charges(name):
    """Les noms de fichier des variantes RETENUES, dans l'ordre.

    UNE SEULE LISTE POUR TOUT LE MONDE, et c'est la raison d'etre de cette
    fonction. L'image, la silhouette et les cartes de relief d'un element sont
    trois lectures separees du meme dossier ; si chacune decidait pour son
    compte quelles variantes existent, il suffirait d'un fichier present mais
    illisible pour que les listes se decalent -- et une pierre porterait alors
    la silhouette ou la carte de normales d'une AUTRE. Ici, une variante
    compte si et seulement si son image se charge.

    ET ON GARDE CE QU'ON VIENT DE CHARGER. C'etait la le gros gaspillage :
    cette fonction chargeait chaque image POUR VOIR si elle se chargeait, la
    jetait, et `variants` la rechargeait aussitot derriere. Deux decodages et
    deux televersements vers la carte graphique par image, dont la moitie
    partait a la poubelle sans avoir jamais servi.

    Sur les douze arbres du jeu -- cinq feuillus et sept sapins, chacun
    d'environ 1,8 Mo une fois decode -- cela faisait 44 Mo charges pour rien,
    en pointe, au moment meme ou la scene se construit. Sur un telephone,
    c'est le genre de pointe qui fait tuer l'application."""
    if name not in _STEMS:
        gardes, images = [], []
        for stem in [name] + ["%s_%d" % (name, i)
                              for i in range(2, MAX_VARIANTS + 1)]:
            tex = _find_one(stem)
            if tex is not None:
                gardes.append(stem)
                images.append(tex)
        _STEMS[name] = gardes
        _CACHE[name] = images
    return _STEMS[name]


def variants(name):
    """Toutes les images disponibles pour cet element (liste, parfois vide)."""
    _stems_charges(name)          # c'est lui qui les charge, une seule fois
    return _CACHE.get(name, [])


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


# SUFFIXES DES CARTES DE RELIEF, les memes que pour les sols (voir
# textures.py) : _R pour les normales, _P pour la carte packed dont le canal
# rouge porte l'occlusion. L'image de base, elle, n'a pas de suffixe.
#
# AUCUN RISQUE DE COLLISION AVEC LES VARIANTES : celles-ci se nomment par un
# CHIFFRE (nom_2 ... nom_8), jamais par une lettre. La carte de normales de la
# deuxieme variante s'appelle donc nom_2_R.
SUFFIXE_NORMAL = "_R"
SUFFIXE_PACKED = "_P"

_RELIEF = {}         # nom -> [(normal, packed), ...], un par variante


def relief(name, pick=None):
    """(normales, packed) de cette variante -- (None, None) si non fournies.

    Deposer nom_R.png a cote de nom.png suffit : l'element est alors ECLAIRE
    par le soleil de la scene, et son cote clair change avec l'heure, au lieu
    de porter un relief peint une fois pour toutes. Les deux cartes sont
    independantes ; l'une sans l'autre marche.

    Dessine tes cartes de base en lumiere NEUTRE, sans ombre peinte dedans :
    c'est le jeu qui eclaire (meme regle que assets/textures/LISEZMOI.txt).

    UNE VARIANTE A LA FOIS. Cette fonction chargeait les cartes de TOUTES les
    variantes des qu'on lui en demandait une : le premier arbre dessine
    faisait entrer les dix cartes des cinq feuillus, puis le premier sapin
    les quatorze des sept siens. Une scene n'en montre pourtant que trois ou
    quatre. On ne charge donc plus que celle qu'on demande, et la liste garde
    sa place pour les autres -- l'alignement avec les variantes de l'image
    reste donc exact, ce qui est tout ce qui comptait."""
    stems = _stems_charges(name)
    if not stems:
        return None, None
    if name not in _RELIEF:
        _RELIEF[name] = [None] * len(stems)
    i = 0 if pick is None else int(pick) % len(stems)
    if _RELIEF[name][i] is None:
        _RELIEF[name][i] = (_find_one(stems[i] + SUFFIXE_NORMAL),
                            _find_one(stems[i] + SUFFIXE_PACKED))
    return _RELIEF[name][i]


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

    /!\ KEEP_DATA. Kivy libere les pixels apres les avoir televerses vers la
    carte graphique : sans ce mot-cle, `brut.data` vaut None, bytearray(None)
    leve, et cette fonction rend None -- SANS BRUIT. Les silhouettes
    n'existaient donc pas du tout sur telephone, et rien ne le disait : les
    pepites y perdaient leurs voiles d'etalonnage depuis toujours. Sur PC les
    pixels restaient la, et tous les apercus etaient justes.
    """
    try:
        img = CoreImage(path, keep_data=True)
        brut = img.image._data[0]
        donnees = bytearray(brut.data)
        if (brut.fmt or "rgba") != "rgba" or len(donnees) < 4:
            return None
    except Exception:
        return None
    # R, G, B a fond ; l'alpha, lui, ne bouge pas : c'est lui la forme.
    for c in range(3):
        donnees[c::4] = b"\xff" * (len(donnees) // 4)
    return texture_depuis_octets((brut.width, brut.height), bytes(donnees),
                                 wrap="clamp_to_edge")


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
    sert pour couper la part enterree.

    UNE VARIANTE A LA FOIS, comme pour les cartes de relief : construire les
    dix silhouettes d'un element pour n'en poser qu'une redecode dix images
    au moment ou la scene se monte. La liste garde leur place, donc
    l'alignement avec les variantes reste exact."""
    # LA MEME LISTE DE VARIANTES QUE L'IMAGE (voir _stems_charges) : une
    # silhouette qui ne serait pas celle du sprite pose par-dessus
    # dessinerait un aplat a cote de la pierre.
    stems = _stems_charges(name)
    if not stems:
        return None
    if name not in _OMBRES:
        _OMBRES[name] = [False] * len(stems)
    i = 0 if pick is None else int(pick) % len(stems)
    if _OMBRES[name][i] is False:
        _OMBRES[name][i] = _silhouette_de(_chemin(stems[i]))
    return _OMBRES[name][i]


# --------------------------------------------------------------------- #
# L'HERBE OMBREE, EN UNE SEULE PLANCHE
# --------------------------------------------------------------------- #
# Une touffe d'herbe n'est pas un aplat : ses brins se font de l'ombre les uns
# aux autres, et le COEUR de la touffe, au ras du sol, ne voit presque pas le
# ciel. Il est donc sombre, et seules les pointes prennent la lumiere. C'est
# ce contraste qui donne du VOLUME a une touffe ; sans lui elle se lit comme
# une decoupe collee sur le sol -- ce qui etait precisement le reproche.
#
# L'image livree n'en porte qu'un soupcon (son pied est 1,6 fois plus sombre
# que ses pointes). On le creuse ici, une fois, au chargement : chaque rangee
# de pixels est multipliee par un facteur qui monte du pied vers le haut.
#
# LA PLANCHE REUNIT TOUTES LES VARIANTES dans une seule texture, pour une
# raison de cout : une scene de plaine pose plus de deux mille touffes, et une
# touffe par dessin ferait deux mille dessins par image. Sur une meme texture,
# des touffes voisines en profondeur se dessinent D'UN SEUL COUP (voir
# ZoneScenery._lot_herbe).
#
# ELLE EST EN PUISSANCE DE 2, avec des MIPMAPS. Une touffe du fond fait une
# vingtaine de pixels pour une image de 448 : sans version reduite, la carte
# graphique y pioche un pixel au hasard, et le fond fourmille de points
# vert vif. Avec, la touffe lointaine se fond en une tache douce -- ce que
# l'oeil voit vraiment a cette distance.
#
# Tout se fait sur les OCTETS, sans bibliotheque d'image : l'APK n'embarque
# que Kivy. Les operations sont des traductions d'octets et des operations
# sur de grands entiers, faites en C par Python : quelques millisecondes.

# Clarte au ras du sol, en part de la couleur de l'image.
OMBRE_PIED = 0.40
# Part de la hauteur (depuis le pied) ou la touffe atteint sa pleine lumiere.
OMBRE_HAUTEUR = 0.62
# Plus grande planche admise (cote, en pixels) : 2048 passe partout.
PLANCHE_MAX = 2048

_PLANCHES = {}


def _pow2(n):
    p = 1
    while p < n:
        p *= 2
    return p


def _clarte_rangee(s):
    """Facteur de clarte a la hauteur s (0 au pied, 1 en haut de l'image)."""
    x = max(0.0, min(1.0, s / OMBRE_HAUTEUR))
    lisse = x * x * (3.0 - 2.0 * x)
    return OMBRE_PIED + (1.0 - OMBRE_PIED) * lisse


def _octets_rgba(path):
    """(largeur, hauteur, octets RGBA serres) de l'image, ou None."""
    try:
        img = CoreImage(path, keep_data=True)
        brut = img.image._data[0]
        if (brut.fmt or "rgba") != "rgba":
            return None
        w, h = int(brut.width), int(brut.height)
        donnees = bytes(brut.data)
    except Exception:
        return None
    # LE PAS D'UNE LIGNE SE DEDUIT DES DONNEES, pas de `rowlength` : selon le
    # chargeur, celui-ci est compte en pixels, en octets, ou laisse a zero
    # (SDL2, celui du telephone, y met 1 792 pour une image de 448 pixels --
    # des octets). La taille reelle, elle, ne ment pas.
    pas = len(donnees) // h if h else 0
    if pas < w * 4:
        return None
    if pas != w * 4:                   # lignes rembourrees : on les resserre
        donnees = b"".join(donnees[r * pas:r * pas + w * 4] for r in range(h))
    return w, h, donnees


def _ombre_la(w, h, donnees):
    """Assombrit les rangees vers le PIED de la touffe.

    LE PIED EST LA DERNIERE RANGEE DES OCTETS, quel que soit le chargeur :
    c'est elle que le maillage de la touffe pose au sol (voir
    ZoneScenery._sprite_plie, ou le bas de la touffe lit v = 1). L'ombre suit
    donc toujours le dessin, meme si un chargeur rangeait l'image a l'envers."""
    out = bytearray(donnees)
    tables = {}
    ligne = w * 4
    for r in range(h):
        s = (h - 1 - r) / float(max(1, h - 1))
        f = round(_clarte_rangee(s) * 128.0) / 128.0
        if f >= 0.999:
            continue
        tab = tables.get(f)
        if tab is None:
            tab = bytes(min(255, int(v * f + 0.5)) for v in range(256))
            tables[f] = tab
        a = r * ligne
        rangee = out[a:a + ligne]
        for c in range(3):
            rangee[c::4] = rangee[c::4].translate(tab)
        out[a:a + ligne] = rangee
    return out


def _moyenne_opaque(donnees):
    """Couleur moyenne (0..255) des pixels franchement opaques."""
    n = len(donnees) // 4
    pas = max(1, n // 6000) * 4
    total = [0, 0, 0]
    k = 0
    for i in range(0, len(donnees) - 3, pas):
        if donnees[i + 3] >= 200:
            total[0] += donnees[i]
            total[1] += donnees[i + 1]
            total[2] += donnees[i + 2]
            k += 1
    if not k:
        return (0, 0, 0)
    return tuple(int(t / k) for t in total)


def _borde(atlas, couleur):
    """Donne aux pixels TRANSPARENTS la couleur moyenne de l'herbe.

    Ils sont noirs dans l'image livree, et cela ne se voyait pas : leur alpha
    est nul. Mais une version reduite (mipmap) MOYENNE les pixels voisins,
    transparents compris -- leur noir se melangeait alors au vert, et chaque
    touffe lointaine s'entourait d'un halo sombre. Avec la couleur de l'herbe
    dessous, la moyenne reste verte.

    Fait sur tout le canal d'un coup, en grands entiers : un masque ou
    l'alpha est nul, puis un choix bit a bit entre l'ancien octet et le
    nouveau."""
    n = len(atlas) // 4
    tout = (1 << (8 * n)) - 1
    alpha = bytes(atlas[3::4])
    masque = int.from_bytes(alpha.translate(bytes([255] + [0] * 255)), "big")
    garde = masque ^ tout
    for c in range(3):
        canal = int.from_bytes(bytes(atlas[c::4]), "big")
        fond = int.from_bytes(bytes([couleur[c]]) * n, "big")
        atlas[c::4] = ((canal & garde) | (fond & masque)).to_bytes(n, "big")


class Planche(object):
    """Toutes les variantes d'une herbe, ombrees, dans une seule texture.

    `cases[i]` = (u0, u1, v_haut, v_pied, largeur_px, hauteur_px) de la
    variante i : ou la lire dans la planche, et sa taille d'origine (pour
    garder ses proportions a l'ecran)."""

    def __init__(self, tex, cases, moyenne):
        self.tex = tex
        self.cases = cases
        self.moyenne = moyenne          # couleur moyenne (0..1) apres ombrage

    def case(self, pick):
        return self.cases[int(pick) % len(self.cases)]


def planche_ombree(name):
    """La planche ombree de cette herbe (voir plus haut), ou None.

    None si aucune image n'a ete fournie, ou si l'une d'elles ne se lit pas en
    RGBA : l'appelant garde alors son dessin d'origine, image par image."""
    if name in _PLANCHES:
        return _PLANCHES[name]
    _PLANCHES[name] = None
    images = []
    for stem in _stems_charges(name):
        chemin = _chemin(stem)
        lu = _octets_rgba(chemin) if chemin else None
        if lu is None:
            return None
        images.append(lu)
    if not images:
        return None
    n = len(images)
    colonnes = min(n, 4)
    lignes = -(-n // colonnes)
    cw = max(w for w, _h, _d in images)
    ch = max(h for _w, h, _d in images)
    pw, ph = _pow2(colonnes * cw), _pow2(lignes * ch)
    if pw > PLANCHE_MAX or ph > PLANCHE_MAX:
        return None
    atlas = bytearray(pw * ph * 4)
    cases = []
    for i, (w, h, donnees) in enumerate(images):
        ombree = _ombre_la(w, h, donnees)
        x0 = (i % colonnes) * cw
        y0 = (i // colonnes) * ch
        for r in range(h):
            a = ((y0 + r) * pw + x0) * 4
            atlas[a:a + w * 4] = ombree[r * w * 4:(r + 1) * w * 4]
        # v = 0 est la PREMIERE rangee des octets : le HAUT de la touffe.
        cases.append((x0 / float(pw), (x0 + w) / float(pw),
                      y0 / float(ph), (y0 + h) / float(ph), w, h))
    moyenne = _moyenne_opaque(bytes(atlas))
    _borde(atlas, moyenne)
    try:
        tex = texture_depuis_octets((pw, ph), atlas, wrap="clamp_to_edge",
                                    mipmap=True,
                                    min_filter="linear_mipmap_linear")
    except Exception:
        return None
    planche = Planche(tex, cases, tuple(c / 255.0 for c in moyenne))
    _PLANCHES[name] = planche
    return planche


# --------------------------------------------------------------------- #
# LES PETITES PIERRES : LES PEPITES, EN PETIT
# --------------------------------------------------------------------- #
# Les petites pierres prennent les photos de la pepite ET ses cartes de relief
# (normales, occlusion) : c'est le meme granit, il doit prendre le meme jour.
#
# PAS LES IMAGES TELLES QUELLES, pourtant. Une pepite est dessinee a peu pres
# a la taille de son image ; une petite pierre, trois a six fois plus petite.
# Sans version reduite (mipmaps), la carte graphique pioche alors un pixel sur
# cinq : le granit fourmille, et le relief scintille de points clairs. Or les
# images de pepite ne sont pas en puissance de 2, et un telephone refuse les
# mipmaps sur une autre taille (voir _load).
#
# On en fait donc une PLANCHE, une fois, au chargement :
#   - chaque image REDUITE DE MOITIE (128 pixels de large : la plus grosse
#     petite pierre en fait une centaine a l'ecran) ;
#   - chacune aussi EN MIROIR, ce qui double les formes : cinq pierres en
#     font dix. Le miroir d'une carte de normales n'est pas un simple miroir
#     -- ce qui penchait vers la droite penche desormais vers la gauche, donc
#     son canal rouge s'inverse (voir plant_leafy_2 dans le LISEZMOI) ;
#   - la SILHOUETTE de chacune, en blanc, sur la meme texture que les
#     couleurs : les voiles qui etalonnent la pierre (voir
#     ZoneScenery._etalonne_pepite) se lisent la, sans texture de plus ;
#   - trois textures de meme plan -- couleurs, normales, occlusion -- en
#     puissance de 2, avec mipmaps. Une case a la meme place dans les trois :
#     le shader lit les trois aux memes coordonnees.
#
# CHAQUE CASE FAIT 128 x 128, et la pierre y est posee EN BAS : il reste un
# vide transparent au-dessus d'elle. Une version reduite melange les pixels
# voisins ; ce vide garde le haut de la pierre a l'ecart de la case du
# dessus. Les silhouettes, blanches, sont rangees a part des couleurs, une
# case vide les en separe : un lisere blanc au flanc d'une pierre grise se
# serait vu.

CASE_PIERRE = 128
COLONNES_PIERRE = 4

_PIERRES = {}
_INVERSE = bytes(255 - i for i in range(256))


def _moyenne_octets(a, b):
    """La moyenne, octet par octet, de deux suites d'octets de meme longueur.

    En un seul calcul sur de grands entiers : (a ET b) + ((a OU-X b) / 2) est
    la moyenne entiere de deux nombres, et le masque 0xFE empeche le decalage
    de faire deborder un bit d'un octet dans son voisin."""
    n = len(a)
    x = int.from_bytes(a, "big")
    y = int.from_bytes(b, "big")
    masque = int.from_bytes(b"\xfe" * n, "big")
    return ((x & y) + (((x ^ y) & masque) >> 1)).to_bytes(n, "big")


def _moitie(w, h, donnees):
    """(w/2, h/2, octets) : l'image reduite de moitie, chaque carre de 2 x 2
    pixels remplace par sa moyenne.

    Une hauteur impaire recoit une rangee de plus EN HAUT (la premiere des
    octets), copie de celle-ci : le bas de la pierre, celui qui touche le sol,
    reste exactement a sa place."""
    ligne = w * 4
    if h % 2:
        donnees = donnees[:ligne] + donnees
        h += 1
    rangees = [donnees[r * ligne:(r + 1) * ligne] for r in range(h)]
    v = _moyenne_octets(b"".join(rangees[0::2]), b"".join(rangees[1::2]))
    px = memoryview(v).cast("I")
    return w // 2, h // 2, _moyenne_octets(px[0::2].tobytes(),
                                           px[1::2].tobytes())


def _miroir(w, h, donnees):
    """L'image retournee de gauche a droite (pixel par pixel, pas octet par
    octet : chaque pixel garde l'ordre de ses canaux)."""
    px = memoryview(donnees).cast("I")
    return b"".join(px[r * w:(r + 1) * w][::-1].tobytes() for r in range(h))


def _inverse_rouge(donnees):
    """Carte de normales retournee : sa pente gauche-droite change de sens."""
    out = bytearray(donnees)
    out[0::4] = out[0::4].translate(_INVERSE)
    return bytes(out)


class PlanchePierres(object):
    """Les pierres reduites, en miroir et en silhouette (voir plus haut).

    `cases[i]` = (uv de la pierre, uv de sa silhouette, largeur, hauteur),
    chaque uv valant (u gauche, u droite, v du haut, v du pied). La
    silhouette d'une pierre en miroir est celle de l'original, lue a
    l'envers : son u gauche est plus grand que son u droit."""

    def __init__(self, tex, normales, packed, cases):
        self.tex = tex
        self.normales = normales
        self.packed = packed
        self.cases = cases

    def case(self, pick):
        return self.cases[int(pick) % len(self.cases)]


def _lit_carte(stem, suffixe, w, h):
    """Les octets d'une carte de relief, ou None si absente ou d'une autre
    taille que l'image (elle ne tomberait pas sur la pierre)."""
    chemin = _chemin(stem + suffixe)
    lu = _octets_rgba(chemin) if chemin else None
    if lu is None or lu[0] != w or lu[1] != h:
        return None
    return lu[2]


def planche_pierres(name):
    """La planche des petites pierres tiree des images `name`, ou None.

    None si aucune image n'a ete fournie ou si l'une ne se lit pas : les
    petites pierres gardent alors leur dessin d'origine."""
    if name in _PIERRES:
        return _PIERRES[name]
    _PIERRES[name] = None
    if memoryview(b"\0\0\0\0").cast("I").itemsize != 4:
        return None
    lues = []
    for stem in _stems_charges(name):
        chemin = _chemin(stem)
        lu = _octets_rgba(chemin) if chemin else None
        if lu is None or lu[0] % 2:
            return None
        w, h, couleur = lu
        couleur = bytearray(couleur)
        _borde(couleur, _moyenne_opaque(couleur))
        w2, h2, c = _moitie(w, h, bytes(couleur))
        if w2 > CASE_PIERRE or h2 > CASE_PIERRE:
            return None
        cartes = []
        for suffixe in (SUFFIXE_NORMAL, SUFFIXE_PACKED):
            brut = _lit_carte(stem, suffixe, w, h)
            cartes.append(_moitie(w, h, brut)[2] if brut else None)
        lues.append((w2, h2, c, cartes[0], cartes[1]))
    if not lues:
        return None

    n = len(lues)
    debut_sil = 2 * n + 1              # une case vide entre couleurs et blanc
    nb = debut_sil + n
    cote = CASE_PIERRE
    pw = _pow2(COLONNES_PIERRE * cote)
    ph = _pow2(-(-nb // COLONNES_PIERRE) * cote)
    if pw > PLANCHE_MAX or ph > PLANCHE_MAX:
        return None
    fond = _moyenne_opaque(b"".join(c for _w, _h, c, _n, _p in lues))
    couleurs = bytearray(bytes(fond) + b"\0") * (pw * ph)
    normales = bytearray(b"\x80\x80\xff\xff") * (pw * ph)
    packed = bytearray(b"\xff") * (pw * ph * 4)

    def coin(k):
        return (k % COLONNES_PIERRE) * cote, (k // COLONNES_PIERRE) * cote

    def pose(atlas, k, w, h, donnees):
        """Copie une image dans la case k, posee en bas et centree."""
        x0, y0 = coin(k)
        x0 += (cote - w) // 2
        y0 += cote - h
        for r in range(h):
            a = ((y0 + r) * pw + x0) * 4
            atlas[a:a + w * 4] = donnees[r * w * 4:(r + 1) * w * 4]

    def uv(k, w, h, miroir=False):
        x0, y0 = coin(k)
        x0 += (cote - w) // 2
        u0, u1 = x0 / float(pw), (x0 + w) / float(pw)
        if miroir:
            u0, u1 = u1, u0
        return (u0, u1, (y0 + cote - h) / float(ph), (y0 + cote) / float(ph))

    blanc = bytearray(b"\xff\xff\xff\0") * cote
    cases_miroir = []
    cases = []
    for i, (w, h, c, nor, pak) in enumerate(lues):
        # La case de la silhouette est BLANCHE jusque dans son vide : c'est
        # du blanc que ses versions reduites y melangent, pas du gris.
        x0, y0 = coin(debut_sil + i)
        for r in range(cote):
            a = ((y0 + r) * pw + x0) * 4
            couleurs[a:a + cote * 4] = blanc
        sil = bytearray(c)
        for k in range(3):
            sil[k::4] = b"\xff" * (len(sil) // 4)
        pose(couleurs, debut_sil + i, w, h, sil)
        pose(couleurs, i, w, h, c)
        pose(couleurs, n + i, w, h, _miroir(w, h, c))
        if nor is not None:
            pose(normales, i, w, h, nor)
            pose(normales, n + i, w, h, _inverse_rouge(_miroir(w, h, nor)))
        if pak is not None:
            pose(packed, i, w, h, pak)
            pose(packed, n + i, w, h, _miroir(w, h, pak))
        cases.append((uv(i, w, h), uv(debut_sil + i, w, h), w, h))
        cases_miroir.append((uv(n + i, w, h),
                             uv(debut_sil + i, w, h, miroir=True), w, h))
    try:
        textures = [texture_depuis_octets((pw, ph), bytes(atlas),
                                          wrap="clamp_to_edge", mipmap=True,
                                          min_filter="linear_mipmap_linear")
                    for atlas in (couleurs, normales, packed)]
    except Exception:
        return None
    planche = PlanchePierres(textures[0], textures[1], textures[2],
                             cases + cases_miroir)
    _PIERRES[name] = planche
    return planche


# --------------------------------------------------------------------- #
# OU COMMENCE LE FEUILLAGE D'UN ARBRE
# --------------------------------------------------------------------- #
# Le vent ne remue que les feuilles : sous cette ligne, le tronc ne bouge pas
# (voir zone_scenery, _tick_feuillage). La ligne etait une CONSTANTE, mesuree
# a la main sur le premier arbre livre -- 0,26 de la hauteur.
#
# Cela a tenu tant qu'il n'y avait qu'un arbre. Mesure sur les cinq :
#
#     forest_tree    0,256      forest_tree_4  0,409
#     forest_tree_3  0,277      forest_tree_5  0,344
#
# L'arbre 4 est un grand elance dont le fut monte jusqu'a 41 % : avec 0,26,
# quinze pour cent de tronc NU se seraient balances. Sur un arbre mince, cela
# se voit tout de suite.
#
# ON LA MESURE DONC, une fois par image, au chargement. C'est ce qui garde la
# promesse du dossier : deposer une image suffit, sans rien regler dans le
# code. Un sapin livre plus tard aura la sienne sans qu'on y pense.
_BASES = {}

# Une colonne sur huit suffit : on cherche une LIGNE, pas un contour, et huit
# fois moins d'octets a lire au chargement.
_PAS_FEUILLAGE = 8
# La part de pixels verts qui fait dire "ici, c'est du feuillage".
_PART_FEUILLES = 0.15
# De combien le vert doit depasser le rouge et le bleu. L'ecorce est brune
# (rouge devant), les feuilles sont vertes : huit niveaux suffisent a les
# separer sans prendre les mousses du tronc.
_MARGE_VERTE = 8
# Bornes de securite. En dessous, le tronc bougerait ; au-dessus, l'arbre
# serait presque entierement fige. Une image qui sort de la (un arbre
# d'automne, dont les feuilles ne sont pas vertes) retombe sur le defaut.
BASE_FEUILLAGE_MIN, BASE_FEUILLAGE_MAX = 0.05, 0.55


def _inclinaison_de(octets, w, h):
    """De combien l'arbre PENCHE, en degres (positif = vers la droite).

    On compare l'abscisse de son PIED a celle de son HOUPPIER. Mesure sur les
    douze arbres livres : onze sont entre -1 et +1 degre, deux penchent
    franchement (+5,5 et +7,2). Ces deux-la penchaient donc toujours du meme
    cote et du meme angle, et deux d'entre eux cote a cote se voyaient tout
    de suite. Le jeu s'en sert pour les REDRESSER avant d'appliquer son
    propre tirage (voir zone_scenery, _sprite_feuillage)."""
    pas = _PAS_FEUILLAGE * 4

    def centre(y0, y1):
        somme = n = 0
        for y in range(y0, y1):
            ligne = octets[y * w * 4:(y + 1) * w * 4]
            for i in range(0, len(ligne) - 3, pas):
                if ligne[i + 3] >= 128:
                    somme += i // 4
                    n += 1
        return (somme / float(n) if n else None), n

    pied, n1 = centre(int(h * 0.94), h)
    houppier, n2 = centre(0, int(h * 0.55))
    if pied is None or houppier is None or n1 < 20 or n2 < 20:
        return 0.0
    # Le bras de levier : du pied au milieu du houppier, soit 0,7 h.
    return math.degrees(math.atan2(houppier - pied, 0.7 * h))


def _mesures_de(path):
    """(hauteur ou commencent les feuilles, inclinaison en degres).

    LES DEUX DANS LE MEME DECODAGE. Ouvrir l'image une fois par mesure
    doublerait le cout au demarrage, et c'est exactement ce qu'on vient de
    retirer ailleurs dans ce fichier.

    La hauteur est une fraction depuis le BAS, ou None si l'on n'a pas su la
    lire -- l'appelant garde alors son defaut.

    On remonte depuis le pied, ligne par ligne, et on s'arrete a la premiere
    ou le feuillage l'emporte. Rend None si l'image ne se laisse pas lire ou
    si le resultat sort des bornes -- l'appelant garde alors son defaut.

    Octets bruts plutot que read_pixel, pour la meme raison que les
    silhouettes : lire un arbre de 640 px pixel par pixel couterait une demi-
    seconde a son premier affichage. Mesure ici : 9 ms par image, decodage
    compris, une seule fois -- et seuls les arbres passent par la.

    /!\ KEEP_DATA, ET TOUT DANS LE MEME GARDE-FOU. Kivy LIBERE les pixels
    apres les avoir televerses vers la carte graphique, sauf si on lui
    demande de les garder : `brut.data` vaut alors None. Ce n'est pas une
    erreur, c'est le fonctionnement normal -- mais aucune exception n'est
    levee, et le None ressort tel quel.

    La premiere version demandait la taille dans un try et appelait len() sur
    les octets JUSTE APRES, hors du try. Sur un PC les pixels restaient la et
    tout marchait ; sur telephone ils etaient liberes, len(None) levait une
    TypeError que plus personne n'attrapait, et le jeu mourait au premier
    arbre dessine -- c'est-a-dire au demarrage. Les autres lecteurs de ce
    fichier (voir _silhouette_de) n'ont jamais eu le probleme parce qu'ils
    touchent les octets DANS leur try.
    """
    if path is None:
        return None
    try:
        brut = CoreImage(path, keep_data=True).image._data[0]
        octets = brut.data
        w, h = int(brut.width), int(brut.height)
        if (brut.fmt or "rgba") != "rgba" or not octets:
            return None
        if w < 8 or h < 8 or len(octets) < w * h * 4:
            return None
        pas = _PAS_FEUILLAGE * 4
        for y in range(h - 1, -1, -1):
            ligne = octets[y * w * 4:(y + 1) * w * 4]
            opaques = feuilles = 0
            for i in range(0, len(ligne) - 3, pas):
                if ligne[i + 3] < 128:
                    continue
                opaques += 1
                g = ligne[i + 1]
                if (g > ligne[i] + _MARGE_VERTE
                        and g > ligne[i + 2] + _MARGE_VERTE):
                    feuilles += 1
            if opaques > 2 and feuilles > _PART_FEUILLES * opaques:
                # Les octets sont dans l'ordre du PNG, ligne 0 en HAUT.
                part = (h - y) / float(h)
                if not BASE_FEUILLAGE_MIN <= part <= BASE_FEUILLAGE_MAX:
                    part = None
                return part, _inclinaison_de(octets, w, h)
        return None, _inclinaison_de(octets, w, h)
    except Exception:
        return None, 0.0


def base_du_feuillage(name, pick=None):
    """La hauteur ou commencent les feuilles de cette variante, ou None.

    Mesuree une fois par image et gardee : le decor se redessine a chaque
    recolte, et relire les octets d'un arbre a chaque fois se verrait.

    UNE VARIANTE A LA FOIS. Mesurer les douze arbres du jeu des qu'on en
    dessine un rouvrait douze images -- 17 Mo decodes et une centaine de
    millisecondes -- pour trois ou quatre reponses utiles."""
    stems = _stems_charges(name)
    if not stems:
        return None
    return _mesures(name, pick)[0]


def inclinaison(name, pick=None):
    """De combien cette variante PENCHE, en degres (positif = a droite).

    Zero si on n'a pas su la lire : un arbre qu'on ne sait pas mesurer est
    traite comme droit, ce qui est le cas de la grande majorite."""
    return _mesures(name, pick)[1]


def _mesures(name, pick=None):
    """(base du feuillage, inclinaison) de cette variante. Une seule lecture
    par image, gardee : le decor se redessine a chaque recolte."""
    stems = _stems_charges(name)
    if not stems:
        return None, 0.0
    if name not in _BASES:
        _BASES[name] = [None] * len(stems)
    i = 0 if pick is None else int(pick) % len(stems)
    if _BASES[name][i] is None:
        _BASES[name][i] = _mesures_de(_chemin(stems[i]))
    return _BASES[name][i]


# --- LES IMAGES PENCHEES SONT PLUS RARES QUE LES AUTRES ----------------- #
# Deux sapins sur sept penchent franchement (+6,0 et +7,0 degres mesures) ;
# a tirage egal, plus d'un sapin sur quatre aurait cette silhouette-la. Le
# jeu les REDRESSE ensuite, mais un tronc courbe reste reconnaissable : le
# voir un arbre sur quatre fait doublon.
#
# On n'ecrit AUCUNE LISTE de fichiers : le seuil s'applique a ce qui est
# mesure, donc une image livree demain est traitee toute seule.
PENCHE_FRANCHE = 3.0
# Quelle part des tirages tombes sur une image penchee on garde. A 0,4 les
# deux sapins penches passent de 28 % des sapins a 11 %.
PART_PENCHEE = 0.4


def variante_droite(name, pick):
    """`pick`, ou un voisin, pour que les images penchees se fassent rares.

    On rend un NUMERO DE TIRAGE, pas un indice : l'appelant le repasse a
    sprite(), relief() et inclinaison(), qui doivent tous trois designer la
    MEME image. Rendre un indice obligerait chacun d'eux a savoir s'il a
    affaire a l'un ou a l'autre.

    Le tirage est graine par le numero d'origine : la meme position garde
    donc la meme reponse d'un redessin a l'autre.

    ON NE MESURE QUE CE QU'IL FAUT : l'image tiree d'abord, puis les
    suivantes seulement si celle-la penche -- ce qui est rare. Une image
    droite ne coute donc rien de plus qu'avant."""
    stems = _stems_charges(name)
    n = len(stems)
    if n < 2 or pick is None:
        return pick
    p = int(pick)
    if abs(_mesures(name, p)[1]) < PENCHE_FRANCHE:
        return pick
    r = random.Random("penche:%s:%d" % (name, p))
    if r.random() < PART_PENCHEE:
        return pick
    # ON DECALE D'UN NOMBRE DE CRANS TIRE, pas toujours d'un seul. Mesure :
    # avec un cran fixe, les deux sapins penches tombaient tous deux sur le
    # meme voisin, qui passait a lui seul de 14 a 32 % des sapins -- on
    # avait remplace une image trop vue par une autre.
    #
    # S'il n'y a aucune image droite ou se rabattre -- les deux buissons de
    # plaine sont un miroir l'un de l'autre, tous deux a 5,7 degres -- on
    # garde le tirage d'origine plutot que d'en imposer un aussi penche.
    crans = list(range(1, n))
    r.shuffle(crans)
    for k in crans:
        if abs(_mesures(name, p + k)[1]) < PENCHE_FRANCHE:
            return p + k
    return pick


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
