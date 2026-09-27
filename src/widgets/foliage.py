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
    compte si et seulement si son image se charge."""
    if name not in _STEMS:
        gardes = []
        for stem in [name] + ["%s_%d" % (name, i)
                              for i in range(2, MAX_VARIANTS + 1)]:
            if _find_one(stem) is not None:
                gardes.append(stem)
        _STEMS[name] = gardes
    return _STEMS[name]


def variants(name):
    """Toutes les images disponibles pour cet element (liste, parfois vide)."""
    if name not in _CACHE:
        _CACHE[name] = [_find_one(s) for s in _stems_charges(name)]
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
    c'est le jeu qui eclaire (meme regle que assets/textures/LISEZMOI.txt)."""
    if name not in _RELIEF:
        _RELIEF[name] = [(_find_one(stem + SUFFIXE_NORMAL),
                          _find_one(stem + SUFFIXE_PACKED))
                         for stem in _stems_charges(name)]
    faites = _RELIEF[name]
    if not faites:
        return None, None
    return faites[0 if pick is None else int(pick) % len(faites)]


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
    sert pour couper la part enterree."""
    if name not in _OMBRES:
        # LA MEME LISTE DE VARIANTES QUE L'IMAGE (voir _stems_charges) : une
        # silhouette qui ne serait pas celle du sprite pose par-dessus
        # dessinerait un aplat a cote de la pierre.
        _OMBRES[name] = [_silhouette_de(_chemin(stem))
                         for stem in _stems_charges(name)]
    faites = _OMBRES[name]
    if not faites:
        return None
    if pick is None:
        return faites[0]
    return faites[int(pick) % len(faites)]


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
