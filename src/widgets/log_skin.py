"""
LA PEAU D'UNE BUCHE, prise sur la buche du jeu.

Le plancher etait couvert de buches inventees : un galbe calcule et la couleur
de la piece. Or le jeu A DEJA une buche -- celle qu'on ramasse, celle qu'on
depense pour batir -- et c'est la meme matiere. En dessiner une seconde, c'est
promettre au joueur que ses buches deviendront ce plancher et lui en montrer
un autre.

ON DECOUPE DONC L'OBJET, en deux morceaux qui n'ont pas le meme role :

    L'ECORCE      le fut, redresse et rendu RACCORD. Elle habille la surface
                  ronde des buches, et se repete le long d'elles.
    LE BOUT       les cernes, qu'on voit a l'extremite d'un rondin scie. Il
                  habille les bouts de buche au bord du plancher -- c'est ce
                  detail-la, plus que la couleur, qui fait reconnaitre un
                  rondin.

LE FUT EST REDRESSE COLONNE PAR COLONNE. L'objet est dessine de biais : son
fut monte vers la droite et son epaisseur varie. Recadrer l'image d'un bloc
aurait donc donne une ecorce penchee, qui se serait vue des la premiere
repetition. On ramene chaque colonne de l'image sur toute la hauteur de la
tuile, ce qui redresse le fut sans rien deformer d'autre que ce qu'il faut.

LA TUILE EST MIROIR. Une bande d'ecorce mise bout a bout se raccorde rarement,
et la couture se voit d'autant mieux qu'elle revient a intervalle regulier. En
collant la bande et son reflet, le bord droit de l'une est exactement le bord
gauche de l'autre : la repetition n'a plus de couture du tout.

SI L'IMAGE MANQUE, TOUT REND None et les dessinateurs retombent sur une
couleur de bois. Un plancher sans texture reste un plancher ; une exception au
milieu d'un chantier, non.
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.abspath(os.path.join(_HERE, "..", "..", "assets", "items",
                                      "Buche.png"))

# Couleur de repli, prise sur le fut de l'objet. Elle sert quand l'image ne
# peut pas etre lue, et aussi de teinte de base sous la texture.
BOIS = (0.55, 0.36, 0.21)

# Tous les combien l'ecorce se repete le long d'une buche, en cubes. Une buche
# de huit cubes de long montre donc quatre fois le motif : assez pour qu'on
# voie du grain, pas assez pour qu'on reconnaisse la repetition. La valeur est
# ici et non dans un ecran : le chantier et la scene du jeu montrent le meme
# plancher, et deux echelles de grain se seraient vues au passage de l'un a
# l'autre.
MOTIF = 2.0

# Taille des tuiles. Puissances de deux : une texture repetee (l'ecorce, le
# long d'une buche) l'exige sur les cartes graphiques des telephones.
ECORCE_L, ECORCE_H = 64, 64        # avant le miroir -- la tuile fera 128 de
BOUT_COTE = 64                     # large

# En dessous de quelle opacite un pixel de l'objet ne compte pas.
_SEUIL_ALPHA = 0.35

# Le bout est BEAUCOUP plus clair que le fut : c'est du bois frais scie contre
# de l'ecorce. On coupe l'objet la ou la clarte fait ce saut, plutot qu'a une
# fraction fixe -- ainsi le decoupage suit l'image, et survit au jour ou elle
# sera redessinee.
_SAUT_CLARTE = 1.30

# Ou couper si le saut ne se trouve pas, en fraction de la largeur de l'objet.
_COUPE_DEFAUT = 0.64

_cache = {}


# --------------------------------------------------------------------- #
# LECTURE DE L'OBJET
# --------------------------------------------------------------------- #
# Ordre des composantes selon le format rendu par le chargeur d'images, et
# combien d'octets par pixel.
_FORMATS = {"rgba": (0, 1, 2, 3), "rgb": (0, 1, 2, None),
            "bgra": (2, 1, 0, 3), "bgr": (2, 1, 0, None)}


class _Source:
    """L'image de l'objet, avec de quoi la questionner pixel par pixel."""

    def __init__(self, img, w, h):
        self.img, self.w, self.h = img, w, h
        self._brut, self._ordre = self._octets()
        self._col = {}

    def _octets(self):
        """Les octets bruts de l'image, ou (None, None).

        ON LES PREND EN UN BLOC. Les demander pixel par pixel a Kivy revient a
        traverser trois couches de Python pour chaque point : un demi-quart de
        million de fois, cela faisait une demi-seconde ici et bien davantage
        sur un telephone -- un gel visible au moment meme ou le joueur
        confirme son plancher. Les memes octets, indexes a la main, se lisent
        en quelques millisecondes.

        On ne s'inquiete pas du SENS des lignes : les deux tuiles qu'on en
        tire sont a peu pres symetriques de haut en bas -- un fut vu de cote,
        des cernes ronds -- si bien qu'une image a l'envers donne la meme
        chose. Le sens gauche-droite, lui, compte : c'est celui qui separe le
        fut du bout, et il n'est jamais retourne."""
        try:
            donnees = self.img.image._data[0]
            octets = donnees.data
            ordre = _FORMATS.get(str(donnees.fmt).lower())
            if ordre and octets:
                n = 4 if ordre[3] is not None else 3
                if len(octets) >= self.w * self.h * n:
                    return octets, ordre
        except Exception:
            pass
        return None, None

    def pixel(self, x, y):
        x = min(self.w - 1, max(0, int(x)))
        y = min(self.h - 1, max(0, int(y)))
        if self._brut is not None:
            ir, ig, ib, ia = self._ordre
            n = 4 if ia is not None else 3
            i = (y * self.w + x) * n
            b = self._brut
            return (b[i + ir] / 255.0, b[i + ig] / 255.0, b[i + ib] / 255.0,
                    1.0 if ia is None else b[i + ia] / 255.0)
        try:
            p = self.img.read_pixel(x, y)
        except Exception:
            return (0.0, 0.0, 0.0, 0.0)
        if not p:
            return (0.0, 0.0, 0.0, 0.0)
        # Kivy rend 3 ou 4 composantes, en 0..1 ou en 0..255 selon le
        # chargeur. On ramene tout au meme etalon.
        v = [float(c) for c in p]
        if max(v) > 1.001:
            v = [c / 255.0 for c in v]
        while len(v) < 4:
            v.append(1.0)
        return tuple(v[:4])

    def colonne(self, x):
        """(haut, bas) de la matiere dans cette colonne, ou None si vide.

        C'est ce qui permet de REDRESSER le fut : on ramene chaque colonne sur
        toute la hauteur de la tuile, quelle que soit sa place dans l'image."""
        if x in self._col:
            return self._col[x]
        # ON CHERCHE GROS, PUIS ON AFFINE. Le fut est plein sur toute sa
        # hauteur : un balayage de quatre en quatre ne peut pas le manquer, et
        # les trois pixels sautes se rattrapent au bord. Ligne par ligne, c'est
        # quatre fois plus de lectures pour le meme resultat.
        pas = 4
        vus = [y for y in range(0, self.h, pas)
               if self.pixel(x, y)[3] >= _SEUIL_ALPHA]
        if not vus:
            self._col[x] = None
            return None
        haut, bas = vus[0], vus[-1]
        while haut > 0 and self.pixel(x, haut - 1)[3] >= _SEUIL_ALPHA:
            haut -= 1
        while bas < self.h - 1 and self.pixel(x, bas + 1)[3] >= _SEUIL_ALPHA:
            bas += 1
        self._col[x] = (haut, bas)
        return self._col[x]

    def clarte(self, x, echantillons=12):
        """La clarte moyenne de la matiere d'une colonne, ou None."""
        bornes = self.colonne(x)
        if bornes is None:
            return None
        haut, bas = bornes
        vals = []
        for k in range(echantillons):
            y = haut + (bas - haut) * (k + 0.5) / echantillons
            r, g, b, a = self.pixel(x, y)
            if a >= _SEUIL_ALPHA:
                vals.append(0.3 * r + 0.6 * g + 0.1 * b)
        return sum(vals) / len(vals) if vals else None


def _charge():
    """L'objet, ou None si on ne peut pas le lire."""
    if "source" in _cache:
        return _cache["source"]
    src = None
    try:
        from kivy.core.image import Image as CoreImage
        img = CoreImage(SOURCE, keep_data=True)
        w, h = int(img.width), int(img.height)
        if w > 1 and h > 1 and img.read_pixel(w // 2, h // 2):
            src = _Source(img, w, h)
    except Exception:
        src = None
    _cache["source"] = src
    return src


def _etendue(src):
    """(x0, x1) des colonnes qui portent de la matiere.

    On sonde UNE SEULE LIGNE, a mi-hauteur. Une buche est une forme pleine et
    d'un seul tenant : sa ligne du milieu la traverse d'un bord a l'autre.
    Balayer l'image entiere aurait donne exactement le meme resultat, en
    lisant deux cent mille pixels au lieu de cinq cents."""
    y = src.h // 2
    xs = [x for x in range(src.w) if src.pixel(x, y)[3] >= _SEUIL_ALPHA]
    if len(xs) >= 8:
        return xs[0], xs[-1]
    # La ligne du milieu ne traverse rien : l'objet n'est pas ou on croyait.
    # On paie alors le balayage complet plutot que de rendre n'importe quoi.
    plein = [x for x in range(src.w) if src.colonne(x) is not None]
    return (plein[0], plein[-1]) if plein else None


def _coupe(src, x0, x1):
    """L'abscisse ou le fut s'arrete et ou le bout commence."""
    pas = max(1, (x1 - x0) // 28)
    xs = list(range(x0, x1 + 1, pas))
    clartes = [(x, src.clarte(x)) for x in xs]
    clartes = [(x, c) for x, c in clartes if c is not None]
    if len(clartes) < 6:
        return x0 + int((x1 - x0) * _COUPE_DEFAUT)
    # La reference est prise sur la PREMIERE MOITIE : c'est du fut a coup sur,
    # le bout etant a une extremite. La mediane, et non la moyenne, pour que
    # quelques colonnes claires ne la tirent pas a elles.
    moitie = sorted(c for _x, c in clartes[:len(clartes) // 2])
    ref = moitie[len(moitie) // 2]
    for x, c in clartes:
        if x > x0 + (x1 - x0) * 0.25 and c > ref * _SAUT_CLARTE:
            return x
    return x0 + int((x1 - x0) * _COUPE_DEFAUT)


# --------------------------------------------------------------------- #
# LES DEUX TUILES
# --------------------------------------------------------------------- #
def _octets_ecorce(src, x0, x_fin):
    """La bande d'ecorce redressee, puis son miroir : 2*ECORCE_L de large."""
    # ON S'ECARTE DES DEUX BORDS. A gauche c'est le trait de contour de
    # l'objet, pas de l'ecorce : il ferait une barre sombre a chaque
    # repetition. A droite, le bout deborde de la coupe -- une colonne de
    # cernes clairs prise pour de l'ecorce revenait en pastille lumineuse a
    # chaque motif, et on ne voyait plus qu'elle.
    large = x_fin - x0
    debut = x0 + max(1, int(large * 0.06))
    arret = x_fin - max(1, int(large * 0.12))
    bande = []
    for i in range(ECORCE_L):
        x = debut + (arret - debut) * (i + 0.5) / ECORCE_L
        bornes = src.colonne(int(x))
        if bornes is None:
            bande.append([(0.0, 0.0, 0.0, 0.0)] * ECORCE_H)
            continue
        haut, bas = bornes
        col = []
        for j in range(ECORCE_H):
            y = haut + (bas - haut) * (j + 0.5) / ECORCE_H
            col.append(src.pixel(x, y))
        bande.append(col)
    # LE MIROIR : le bord droit de la bande devient le bord gauche de son
    # reflet, donc la repetition n'a plus de couture.
    colonnes = bande + bande[::-1]
    out = bytearray()
    for j in range(ECORCE_H):
        for col in colonnes:
            r, g, b, _a = col[j]
            out += bytes((_o(r), _o(g), _o(b), 255))
    return bytes(out), (2 * ECORCE_L, ECORCE_H)


def _cadre_bout(src, x_fin, x1):
    """Le rectangle qui serre les cernes, plus un peu d'ecorce autour.

    On ne prend pas la coupe telle quelle : a l'endroit ou le fut s'arrete, il
    en reste encore un coin dans l'image, et ce coin se serait retrouve plaque
    en travers du rondin. On cherche donc l'etendue du bois CLAIR -- la face
    sciee -- et on l'elargit juste assez pour garder le cerne d'ecorce qui en
    fait le tour."""
    clairs = []
    for x in range(x_fin, x1 + 1, max(1, (x1 - x_fin) // 40)):
        bornes = src.colonne(x)
        if bornes is None:
            continue
        haut, bas = bornes
        for k in range(20):
            y = haut + (bas - haut) * (k + 0.5) / 20
            r, g, b, a = src.pixel(x, y)
            if a >= _SEUIL_ALPHA and (0.3 * r + 0.6 * g + 0.1 * b) > 0.52:
                clairs.append((x, y))
    if len(clairs) < 8:
        cols = [src.colonne(x) for x in range(x_fin, x1 + 1)]
        cols = [c for c in cols if c is not None]
        if not cols:
            return None
        return x_fin, x1, min(h for h, _b in cols), max(b for _h, b in cols)
    cx0 = min(p[0] for p in clairs)
    cx1 = max(p[0] for p in clairs)
    cy0 = min(p[1] for p in clairs)
    cy1 = max(p[1] for p in clairs)
    mx = (cx1 - cx0) * 0.13
    my = (cy1 - cy0) * 0.13
    return (max(x_fin, cx0 - mx), min(x1, cx1 + mx),
            max(0, cy0 - my), min(src.h - 1, cy1 + my))


def _octets_bout(src, x_fin, x1):
    """Les cernes du bout, ramenes dans un carre."""
    cadre = _cadre_bout(src, x_fin, x1)
    if cadre is None:
        return None
    x_fin, x1, y0, y1 = cadre
    out = bytearray()
    for j in range(BOUT_COTE):
        y = y0 + (y1 - y0) * (j + 0.5) / BOUT_COTE
        for i in range(BOUT_COTE):
            x = x_fin + (x1 - x_fin) * (i + 0.5) / BOUT_COTE
            r, g, b, a = src.pixel(x, y)
            if a < _SEUIL_ALPHA:
                # Hors du rondin : on prend la couleur du bois plutot que du
                # vide. Le bout est decoupe en demi-disque par la geometrie,
                # donc ces coins-la ne se voient pas -- mais un trou
                # transparent qui deborderait d'un pixel se verrait, lui.
                r, g, b = BOIS
            out += bytes((_o(r), _o(g), _o(b), 255))
    return bytes(out), (BOUT_COTE, BOUT_COTE)


def _o(v):
    return min(255, max(0, int(v * 255.0 + 0.5)))


def _texture(octets_taille, repete):
    if octets_taille is None:
        return None
    octets, taille = octets_taille
    try:
        from kivy.graphics.texture import Texture
        tex = Texture.create(size=taille, colorfmt="rgba")
        tex.blit_buffer(octets, colorfmt="rgba", bufferfmt="ubyte")
        tex.wrap = "repeat" if repete else "clamp_to_edge"
        tex.min_filter = tex.mag_filter = "linear"
        return tex
    except Exception:
        return None


def _tuiles():
    if "tuiles" in _cache:
        return _cache["tuiles"]
    ecorce = bout = None
    src = _charge()
    if src is not None:
        etendue = _etendue(src)
        if etendue is not None:
            x0, x1 = etendue
            x_fin = _coupe(src, x0, x1)
            ecorce = _texture(_octets_ecorce(src, x0, x_fin), True)
            bout = _texture(_octets_bout(src, x_fin, x1), False)
    _cache["tuiles"] = (ecorce, bout)
    return _cache["tuiles"]


def ecorce():
    """La texture d'ecorce, raccord dans sa longueur. None si pas d'image."""
    return _tuiles()[0]


def bout():
    """La texture des cernes du bout. None si pas d'image."""
    return _tuiles()[1]


def oublie():
    """Vide le cache -- pour les essais, ou si l'image change."""
    _cache.clear()
