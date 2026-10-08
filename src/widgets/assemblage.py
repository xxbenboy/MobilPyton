"""
LA VUE D'ASSEMBLAGE : le joueur se rapproche de son plan de travail.

Le bouton Assembler de l'ecran de craft fait ZOOMER la vue entre les mains :
le plan de travail, qui occupait l'ecart entre elles, s'agrandit jusqu'a
prendre LES DEUX TIERS DE LA LARGEUR de l'ecran, un sixieme restant libre de
chaque cote. Tout le monde zoome ensemble -- decor, sol et objets -- par une
seule transformation (voir Loupe). LES MAINS, ELLES, NE ZOOMENT PAS : elles
sont attachees au joueur et gardent leur taille de tous les ecrans.

DANS CETTE VUE :
- les grilles disparaissent ; seuls les objets du plan de travail restent,
  et ils deviennent LIBRES : ils ne sont plus ranges en cases ;
- ce que tenaient les mains n'est plus montre (il revient a la sortie) ;
- LES MAINS SUIVENT LE DOIGT : un toucher dans la moitie gauche de l'ecran
  mene la main gauche, dans la moitie droite la main droite. LE DOIGT TIENT
  LE BAS DE L'AVANT-BRAS, la ou l'image coupe le bras : toute la main est
  au-dessus de lui, et sa paume, au bout d'un bras qui penche vers
  l'exterieur, tombe vers l'interieur. Le doigt ne cache ainsi ni la main
  ni ce qu'elle tient ; l'objet tenu et la zone ou elle prend suivent la
  paume. Lachee, la main revient a sa place de base, en bas ;
- une main qui PASSE SUR UN OBJET le prend : il colle a la paume tant que
  le doigt reste pose. Il est tenu DANS la paume : la main se dessine
  devant lui, pas l'inverse. Au lacher, l'objet reste EXACTEMENT ou il est, et la
  main repart seule vers sa place.

LES OBJETS SE COLLENT PAR LEURS CASES. Chaque image porte une grille
INVISIBLE de 3 x 3 cases. Un objet porte pres d'un autre s'aligne sur la
grille de celui-ci : il saute a la place libre la plus proche, BORD A BORD,
contre les cases EXTERIEURES de l'autre -- deux grilles ne se chevauchent
jamais. Tant que les grilles se touchent et que l'objet est tenu, elles
se dessinent toutes les deux. Un objet lache PAR-DESSUS un autre est
pousse a cote, a la place libre la plus proche, et y reste colle. Tant
que le doigt bouge, l'aimant suit ; s'il reste immobile une seconde,
l'aimant lache et l'objet revient sous la paume -- il reprend des que le
doigt rebouge. Lache pendant qu'il est aimante, l'objet RESTE COLLE a
l'autre (voir `liens`) ; reprendre l'un des deux les decolle.

RIEN DE TOUT CELA NE TOUCHE A LA PARTIE : les objets ne bougent qu'a
l'ecran. Annuler les remet dans leurs cases, la ou ils etaient avant
d'assembler (voir CraftScreen).
"""
import math
import random

from kivy.clock import Clock
from kivy.graphics import (Color, Ellipse, Line, PushMatrix, PopMatrix,
                           Rectangle, Translate, Scale)
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget

from src.widgets.sol_de_craft import (dessine_objet, cadre_image,
                                      TAILLE_OBJET, CENTRE_PRES, CENTRE_LOIN)

# La part de la largeur que prend le plan de travail une fois rapproche.
PART_PLAN = 2.0 / 3.0
# LE GROSSISSEMENT. Il a ete regle pour que l'ancien plan de 4 x 4 (0,196 de
# la largeur) prenne PART_PLAN de l'ecran. Le plan est maintenant plus petit
# (2 x 2), mais le grossissement reste le meme : c'est lui qui donne leur
# taille aux objets rapproches, et la place pour les assembler.
ZOOM = PART_PLAN / 0.196
# Le milieu du plan de travail dans la vue normale, et ou il arrive une fois
# rapproche : au milieu de l'ecran.
CENTRE_PLAN = (0.5, (CENTRE_PRES + CENTRE_LOIN) / 2.0)
CENTRE_VUE = (0.5, 0.5)
# Duree du rapprochement (et du recul), en secondes.
DUREE_ZOOM = 0.45

# La main rattrape le doigt en douceur (constante de temps, en secondes) :
# vite quand on la mene, un peu moins quand elle revient seule.
SUIVI = 0.05
RETOUR = 0.12
# En deca de ce nombre de pixels, une main est arrivee.
ARRIVEE = 0.5
# Une paume prend l'objet dont le centre passe a moins de cette part de sa
# taille (a l'ecran, zoome).
SAISIE = 0.45
FPS = 60.0

# LA GRILLE INVISIBLE DE CHAQUE IMAGE : 3 x 3 cases, d'un tiers de l'objet.
CASES_OBJET = 3
# L'aimant prend un objet dont la grille passe a moins d'une demi-case du
# contact bord a bord.
PORTEE_AIMANT = CASES_OBJET + 0.5
# Les grilles, quand elles se touchent : TRACEES A LA CRAIE -- un trait
# blanc casse qui tremble un peu, et un second, plus pale, a cote (la craie
# laisse une trainee). Epaisseur en part de la hauteur.
TRAIT_GRILLE = (0.95, 0.94, 0.88, 0.80)
TRAINEE_GRILLE = (0.95, 0.94, 0.88, 0.28)
EPAISSEUR_GRILLE = 0.0024
TREMBLE_CRAIE = 0.10           # en part d'une case
# LA GRILLE DU PLAN, partout et tout le temps dans la vue d'assemblage : des
# cases de la taille de celles des objets (un objet en couvre 3 x 3). Tout
# objet pose s'y cale -- ses cases tombent sur les siennes -- et deux objets
# poses s'alignent donc toujours l'un sur l'autre.
TRAIT_PLAN = (0.95, 0.94, 0.88, 0.16)
EPAISSEUR_PLAN = 0.020          # en part d'une case
# Doigt pose sans bouger pendant ce temps (s) : l'aimant lache.
DELAI_AIMANT = 1.0
# En deca de ce deplacement du doigt (px), il n'a pas bouge.
SEUIL_BOUGE = 6.0
# Deux grilles se touchent bord a bord a cette part de case pres.
TOLERANCE_CONTACT = 0.15



def vue(e, x, y, l, h, ox=0.0, oy=0.0):
    """Ou tombe a l'ecran le point (x, y) de la vue normale, quand le
    rapprochement en est a `e` (0 = vue normale, 1 = rapproche). (ox, oy, l,
    h) est le rectangle de l'ecran."""
    s = 1.0 + (ZOOM - 1.0) * e
    cx, cy = ox + CENTRE_PLAN[0] * l, oy + CENTRE_PLAN[1] * h
    tx = (CENTRE_VUE[0] - CENTRE_PLAN[0]) * l * e
    ty = (CENTRE_VUE[1] - CENTRE_PLAN[1]) * h * e
    return cx + tx + s * (x - cx), cy + ty + s * (y - cy)


def vue_inverse(e, X, Y, l, h, ox=0.0, oy=0.0):
    """Le point de la vue normale qui tombe en (X, Y) a l'ecran."""
    s = 1.0 + (ZOOM - 1.0) * e
    cx, cy = ox + CENTRE_PLAN[0] * l, oy + CENTRE_PLAN[1] * h
    tx = (CENTRE_VUE[0] - CENTRE_PLAN[0]) * l * e
    ty = (CENTRE_VUE[1] - CENTRE_PLAN[1]) * h * e
    return cx + (X - cx - tx) / s, cy + (Y - cy - ty) / s


# CE QUE LES MINI-JEUX DESSINENT SUR UN OBJET, a meme l'objet (sous les
# mains, comme lui) :
# - "morceaux" : les traits deja coupes, en parts de la largeur de l'image ;
#   l'objet est dessine en morceaux, ecartes de ECART_MORCEAU l'un de
#   l'autre ;
# - "a_couper" : les traits qui restent a couper, en pointilles ;
# - "entailles" : [(cote, part)] -- la couche a retirer d'un flanc, de son
#   bord jusqu'au trait en pointilles.
ECART_MORCEAU = 0.045
# - les EMPLACEMENTS (Assemblage.emplacements) : [(nom, fx, fy)], les places
#   ou un mini-jeu attend un objet, dessinees sous les objets.
ALPHA_EMPLACEMENT = 0.30
# - "trou" : False, un trou A PERCER au milieu de l'objet (un rond en
#   pointilles) ; True, le trou perce. Et Assemblage.fils : la corde passee
#   de trou en trou, [(fx, fy)].
TROU = 0.10
COULEUR_TROU = (0.08, 0.06, 0.04, 0.95)
COULEUR_FIL = (0.78, 0.66, 0.42, 1.0)
POINTILLE = 0.035
TRAIT_A_FAIRE = (1.0, 1.0, 0.95, 0.95)
OMBRE_TRAIT = (0.10, 0.08, 0.05, 0.75)
COUCHE_A_RETIRER = (1.0, 0.95, 0.75, 0.28)


def decalage_morceau(o, u, cote):
    """De combien est pousse, a l'ecran, le morceau de `o` qui contient la
    part `u` de sa largeur (les morceaux s'ecartent depuis le milieu)."""
    traits = sorted(o.get("morceaux", ()))
    j = sum(1 for c in traits if c < u)
    return (j - len(traits) / 2.0) * ECART_MORCEAU * cote


def _pointilles(x, y0, y1, largeur, pas):
    """Un trait vertical en pointilles, souligne d'une ombre."""
    n = max(1, int(abs(y1 - y0) / pas))
    for couleur, dx, w in ((OMBRE_TRAIT, largeur * 0.7, largeur * 1.3),
                           (TRAIT_A_FAIRE, 0.0, largeur)):
        Color(*couleur)
        for k in range(0, n, 2):
            a = y0 + (y1 - y0) * k / float(n)
            b = y0 + (y1 - y0) * min(n, k + 1) / float(n)
            Line(points=[x + dx, a, x + dx, b], width=w)


def dessine_travail(o, cx, cy, cote, ombre=True):
    """L'objet `o` centre en (cx, cy), avec ce qu'un mini-jeu y a fait ou
    montre a faire (voir plus haut). Sans rien de tout cela : dessine_objet.
    """
    coupe = tuple(o.get("coupe", (0.0, 0.0)))
    traits = sorted(o.get("morceaux", ()))
    if not traits:
        dessine_objet(o["nom"], cx, cy, cote, ombre=ombre, coupe=coupe)
    else:
        bords = [0.0] + traits + [1.0]
        for j in range(len(bords) - 1):
            a, b = bords[j], bords[j + 1]
            dx = (j - len(traits) / 2.0) * ECART_MORCEAU * cote
            # Un rien de travers, pour qu'on voie le morceau detache.
            dy = (0.012 if j % 2 else -0.012) * cote
            dessine_objet(o["nom"], cx + dx, cy + dy, cote, ombre=ombre,
                          coupe=(a, 1.0 - b))
    trou = o.get("trou")
    if trou is not None:
        r = TROU * cote
        if trou:
            Color(*TRAIT_A_FAIRE[:3], 0.55)
            Ellipse(pos=(cx - r * 1.15, cy - r * 1.15),
                    size=(r * 2.3, r * 2.3))
            Color(*COULEUR_TROU)
            Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))
        else:
            n = 12
            for k in range(0, n, 2):
                a0 = 360.0 * k / n
                Color(*OMBRE_TRAIT)
                Line(circle=(cx, cy, r, a0, a0 + 360.0 / n),
                     width=max(1.5, cote * 0.020))
                Color(*TRAIT_A_FAIRE)
                Line(circle=(cx, cy, r, a0, a0 + 360.0 / n),
                     width=max(1.0, cote * 0.012))
    a_couper = o.get("a_couper", ())
    entailles = o.get("entailles", ())
    if not a_couper and not entailles:
        return
    cadre = cadre_image(o["nom"], cote)
    if cadre is None:
        return
    iw, ih = cadre
    largeur = max(1.5, cote * 0.016)
    pas = POINTILLE * cote
    for u in a_couper:
        x = cx - iw / 2.0 + u * iw + decalage_morceau(o, u, cote)
        _pointilles(x, cy - ih * 0.55, cy + ih * 0.55, largeur, pas)
    for cote_pierre, u in entailles:
        x = cx - iw / 2.0 + u * iw
        if cote_pierre == "gauche":
            bord = cx - iw / 2.0 + coupe[0] * iw
        else:
            bord = cx + iw / 2.0 - coupe[1] * iw
        Color(*COUCHE_A_RETIRER)
        Rectangle(pos=(min(x, bord), cy - ih * 0.40),
                  size=(abs(x - bord), ih * 0.80))
        _pointilles(x, cy - ih * 0.45, cy + ih * 0.45, largeur, pas)


class Loupe(FloatLayout):
    """Un conteneur dont tout le contenu zoome ensemble (voir `vue`)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.e = 0.0
        with self.canvas.before:
            PushMatrix()
            self._deplace = Translate(0, 0, 0)
            self._echelle = Scale(1.0, 1.0, 1.0, origin=(0, 0))
        with self.canvas.after:
            PopMatrix()
        self.bind(pos=lambda *_: self.regle(self.e),
                  size=lambda *_: self.regle(self.e))

    def regle(self, e):
        self.e = float(e)
        s = 1.0 + (ZOOM - 1.0) * self.e
        cx = self.x + CENTRE_PLAN[0] * self.width
        cy = self.y + CENTRE_PLAN[1] * self.height
        self._echelle.origin = (cx, cy)
        self._echelle.x = self._echelle.y = s
        self._deplace.x = (CENTRE_VUE[0] - CENTRE_PLAN[0]) * self.width * self.e
        self._deplace.y = (CENTRE_VUE[1] - CENTRE_PLAN[1]) * self.height \
            * self.e


class Assemblage(Widget):
    """Les objets libres du plan de travail, et les mains qui les prennent.

    Il vit DANS la Loupe : ses objets se dessinent aux coordonnees de la vue
    normale, et zooment avec elle. Ceux que porte une main se dessinent dans
    `couche`, SOUS les mains (l'objet est dans la paume, la main devant
    lui), a la taille zoomee. Les touchers, eux,
    arrivent en coordonnees de l'ecran."""

    def __init__(self, mains=None, couche=None, **kwargs):
        super().__init__(**kwargs)
        self.mains = mains
        self.couche = couche
        self.actif = False
        # Chaque objet : nom, position (en parts de l'ecran, vue normale),
        # sa case d'origine, et le depart d'un retour en case.
        self.objets = []
        self._doigts = [None, None]
        self._porte = [None, None]
        self._decale = [[0.0, 0.0], [0.0, 0.0]]
        self._horloge = None
        # L'aimant de chaque main : l'objet auquel l'objet porte s'aligne et
        # ou il se pose (a l'ecran), s'il est actif, depuis combien de temps
        # le doigt est immobile, et ou il etait.
        self._aimante = [None, None]
        self._aimant = [True, True]
        self._immobile = [0.0, 0.0]
        self._ancre = [None, None]
        # Les objets colles l'un a l'autre : des paires (a, b).
        self.liens = []
        # Un mini-jeu coupe l'aimant (les pierres qu'on frotte ne doivent pas
        # se coller), et se fait prevenir a chaque pas (sur_pas(dt)).
        self.aimant_permis = True
        self.sur_pas = None
        self.emplacements = []
        self.fils = []
        # Ce qu'un mini-jeu dessine lui-meme sous les objets (la tresse de
        # la corde) : dessin_jeu(), appele dans le canvas ; et PAR-DESSUS
        # (la corde enroulee autour du manche de la hache) : dessin_dessus().
        self.dessin_jeu = None
        self.dessin_dessus = None
        self.bind(pos=self._redessine, size=self._redessine)

    # -- ce qu'il y a sur le plan ---------------------------------------- #
    def charge(self, objets):
        """[(nom, fx, fy)] : les objets du plan, au milieu de leur case."""
        # Cales sur la grille du plan des le depart.
        objets = [(n,) + self.grille_fraction(fx, fy) for n, fx, fy in objets]
        self.objets = [{"nom": n, "x": fx, "y": fy, "x0": fx, "y0": fy,
                        "xa": fx, "ya": fy, "coupe": [0.0, 0.0]}
                       for n, fx, fy in objets]
        self._porte = [None, None]
        self._aimante = [None, None]
        self.liens = []
        self._redessine()

    def vide(self):
        self.lache_tout()
        self.objets = []
        self.aimant_permis = True
        self.sur_pas = None
        self.emplacements = []
        self.fils = []
        self.dessin_jeu = None
        self.dessin_dessus = None
        self._arrete()
        self._decale = [[0.0, 0.0], [0.0, 0.0]]
        if self.mains is not None:
            for i in (0, 1):
                self.mains.decale(i, 0.0, 0.0)
        self._redessine()

    def lache_tout(self):
        """Les doigts sont oublies, ce que portent les mains est pose la ou
        il est, et elles repartent vers leur place."""
        for i in (0, 1):
            doigt = self._doigts[i]
            if doigt is not None and hasattr(doigt, "ungrab"):
                doigt.ungrab(self)
            self._doigts[i] = None
            if self._porte[i] is not None:
                self._pose(i)
        self._demarre()

    def fige_depart(self):
        """Retient ou est chaque objet : le point de depart du retour."""
        for o in self.objets:
            o["xa"], o["ya"] = o["x"], o["y"]

    def ramene(self, p):
        """Chaque objet a `p` du chemin entre ou il etait (fige_depart) et sa
        case d'origine."""
        for o in self.objets:
            o["x"] = o["xa"] + (o["x0"] - o["xa"]) * p
            o["y"] = o["ya"] + (o["y0"] - o["ya"]) * p
        self._redessine()

    # -- dessin ------------------------------------------------------------ #
    def _redessine(self, *_):
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return
        portes = [o for o in self._porte if o is not None]
        cote = TAILLE_OBJET * self.height
        with self.canvas:
            self._dessine_grille_plan(cote / CASES_OBJET)
            # LES PLACES A REMPLIR d'un mini-jeu, sous les objets : l'objet
            # attendu, en fantome, dans un rond de craie.
            for place in self.emplacements:
                nom, fx, fy = place[:3]
                rond = place[3] if len(place) > 3 else True
                px, py = self.x + fx * self.width, self.y + fy * self.height
                if rond:
                    Color(*TRAIT_A_FAIRE[:3], 0.55)
                    Line(circle=(px, py, cote * 0.42),
                         width=max(1.2, cote * 0.018))
                dessine_objet(nom, px, py, cote, ombre=False,
                              alpha=ALPHA_EMPLACEMENT)
            if self.dessin_jeu is not None:
                self.dessin_jeu()
            # Du plus loin (haut) au plus pres : celui de devant passe devant.
            # Un objet marque "dessus" par un mini-jeu (la pierre fixee sur
            # le manche de la hache) passe devant tous les autres.
            for o in sorted(self.objets,
                            key=lambda o: (bool(o.get("dessus")), -o["y"])):
                if any(o is p for p in portes) or o.get("cache"):
                    continue
                dessine_travail(o, self.x + o["x"] * self.width,
                                self.y + o["y"] * self.height, cote)
            # LA CORDE ENFILEE d'un mini-jeu, de trou en trou.
            if len(self.fils) >= 2:
                pts = [v for fx, fy in self.fils
                       for v in (self.x + fx * self.width,
                                 self.y + fy * self.height)]
                Color(*OMBRE_TRAIT)
                Line(points=pts, width=max(1.5, cote * 0.030))
                Color(*COULEUR_FIL)
                Line(points=pts, width=max(1.2, cote * 0.020))
            if self.dessin_dessus is not None:
                self.dessin_dessus()
        self._dessine_portes()

    def _dessine_grille_plan(self, case):
        """La grille du plan, sur toute la vue (en coordonnees d'avant le
        grossissement : la loupe la grossit avec le reste)."""
        if case <= 0:
            return
        ox = self.x + CENTRE_PLAN[0] * self.width
        oy = self.y + CENTRE_PLAN[1] * self.height
        Color(*TRAIT_PLAN)
        largeur = max(1.0, EPAISSEUR_PLAN * case)
        k0 = int(math.floor((self.x - ox) / case))
        k1 = int(math.ceil((self.x + self.width - ox) / case))
        for k in range(k0, k1 + 1):
            x = ox + k * case
            Line(points=[x, self.y, x, self.y + self.height], width=largeur)
        k0 = int(math.floor((self.y - oy) / case))
        k1 = int(math.ceil((self.y + self.height - oy) / case))
        for k in range(k0, k1 + 1):
            y = oy + k * case
            Line(points=[self.x, y, self.x + self.width, y], width=largeur)

    def grille_fraction(self, fx, fy):
        """Le point (parts du widget, avant grossissement) cale sur la grille
        du plan."""
        if self.width <= 0 or self.height <= 0:
            return fx, fy
        case = TAILLE_OBJET * self.height / CASES_OBJET
        ox = CENTRE_PLAN[0] * self.width
        oy = CENTRE_PLAN[1] * self.height
        x, y = fx * self.width, fy * self.height
        x = ox + (round((x - ox) / case - 0.5) + 0.5) * case
        y = oy + (round((y - oy) / case - 0.5) + 0.5) * case
        return x / self.width, y / self.height

    def sur_grille(self, px, py):
        """Le point de l'ecran ou se cale un objet lache en (px, py) : ses
        cases sur celles de la grille du plan."""
        c = self.case_objet()
        ox, oy = self.centre_du_plan()
        return (ox + (round((px - ox) / c - 0.5) + 0.5) * c,
                oy + (round((py - oy) / c - 0.5) + 0.5) * c)

    def _dessine_portes(self):
        if self.couche is None:
            return
        self.couche.canvas.clear()
        cote = TAILLE_OBJET * self.height * ZOOM
        with self.couche.canvas:
            for i in (0, 1):
                if self._porte[i] is not None:
                    px, py = self.ou_est_porte(i)
                    o = self._porte[i]
                    dessine_travail(o, px, py, cote, ombre=False)
            # LES GRILLES QUI SE TOUCHENT, tant que l'objet est tenu.
            for i in (0, 1):
                if self._porte[i] is not None and \
                        self._aimante[i] is not None:
                    self._dessine_grille(*self.ou_est_porte(i))
                    self._dessine_grille(
                        *self.a_l_ecran(self._aimante[i][0]))

    def _dessine_grille(self, cx, cy):
        c = self.case_objet()
        n = CASES_OBJET
        x0, y0 = cx - n * c / 2.0, cy - n * c / 2.0
        largeur = max(1.0, EPAISSEUR_GRILLE * self.height)
        # Meme hasard a chaque image : le trait de craie ne frissonne pas.
        hasard = random.Random(3)
        traits = []
        for k in range(n + 1):
            traits.append(((x0 + k * c, y0), (x0 + k * c, y0 + n * c)))
            traits.append(((x0, y0 + k * c), (x0 + n * c, y0 + k * c)))
        for (ax, ay), (bx, by) in traits:
            pts = []
            pas = 6
            vertical = ax == bx
            for j in range(pas + 1):
                t = j / float(pas)
                d = hasard.uniform(-1, 1) * TREMBLE_CRAIE * c * 0.25 \
                    if 0 < j < pas else 0.0
                x = ax + (bx - ax) * t + (d if vertical else 0.0)
                y = ay + (by - ay) * t + (0.0 if vertical else d)
                pts.append((x, y))
            ox, oy = (largeur * 0.9, 0.0) if vertical else (0.0, -largeur)
            Color(*TRAINEE_GRILLE)
            Line(points=[v for p in pts for v in (p[0] + ox, p[1] + oy)],
                 width=largeur * 0.8)
            Color(*TRAIT_GRILLE)
            Line(points=[v for p in pts for v in p], width=largeur)

    # -- les mains --------------------------------------------------------- #
    def paume(self, i):
        """Le creux de la paume `i` a l'ecran, deplacement compris."""
        if self.mains is None:
            return (0.0, 0.0)
        bx, by = self.mains.paume(i)
        # Le souffle deplace aussi les mains : l'objet porte le suit.
        souffle = getattr(self.mains, "_shift", None)
        sx, sy = (souffle.x, souffle.y) if souffle is not None else (0, 0)
        return bx + self._decale[i][0] + sx, by + self._decale[i][1] + sy

    def place_a_l_ecran(self, o, px, py):
        """Pose l'objet `o` pour qu'il paraisse en (px, py) a l'ecran."""
        x, y = vue_inverse(1.0, px, py, self.width, self.height,
                           self.x, self.y)
        o["x"] = (x - self.x) / self.width
        o["y"] = (y - self.y) / self.height
        self._redessine()

    def centre_du_plan(self):
        """Le milieu du plan de travail rapproche, a l'ecran."""
        return (self.x + CENTRE_VUE[0] * self.width,
                self.y + CENTRE_VUE[1] * self.height)

    def a_l_ecran(self, o):
        return vue(1.0, self.x + o["x"] * self.width,
                   self.y + o["y"] * self.height, self.width, self.height,
                   self.x, self.y)

    def _prend(self, i):
        """La paume `i` passe-t-elle sur un objet libre ? Elle le prend --
        mais seulement s'il est aussi la ou le doigt l'emmene : en chemin
        vers l'endroit touche, la main passe sur d'autres objets sans les
        ramasser."""
        px, py = self.paume(i)
        rayon = SAISIE * TAILLE_OBJET * self.height * ZOOM
        vx, vy = self.paume_visee(i)
        portes = [o for o in self._porte if o is not None]
        meilleur, dist = None, rayon
        for o in self.objets:
            if any(o is p for p in portes) or o.get("verrou") \
                    or o.get("cache"):
                continue            # deja tenu, ou mis de cote par un mini-jeu
            ox, oy = self.a_l_ecran(o)
            d = math.hypot(ox - px, oy - py)
            if d <= dist and math.hypot(ox - vx, oy - vy) <= rayon:
                meilleur, dist = o, d
        if meilleur is not None:
            self._porte[i] = meilleur
            self.decolle(meilleur)
            self._redessine()

    def paume_visee(self, i):
        """Ou sera la paume `i` une fois arrivee sous le doigt qui la mene."""
        if self.mains is None:
            return self.paume(i)
        bx, by = self.mains.paume(i)
        tx, ty = self._cible(i)
        souffle = getattr(self.mains, "_shift", None)
        sx, sy = (souffle.x, souffle.y) if souffle is not None else (0, 0)
        return bx + tx + sx, by + ty + sy

    def _pose(self, i):
        """L'objet porte par la main `i` reste exactement ou il est."""
        o = self._porte[i]
        px, py = self.ou_est_porte(i)
        colle = self._aimante[i]
        # TOUJOURS calee sur la grille du plan.
        px, py = self.sur_grille(px, py)
        if colle is None and self.aimant_permis and \
                self._chevauche(px, py, o):
            # LACHE PAR-DESSUS UN AUTRE : pousse a la place libre la plus
            # proche, a cote, et colle.
            colle = self._place_libre(px, py, o)
            if colle is not None:
                px, py = colle[1], colle[2]
        self._porte[i] = None
        self._aimante[i] = None
        if colle is not None:
            self.liens.append((o, colle[0]))
        x, y = vue_inverse(1.0, px, py, self.width, self.height,
                           self.x, self.y)
        o["x"] = (x - self.x) / self.width
        o["y"] = (y - self.y) / self.height
        self._redessine()

    # -- l'aimant ---------------------------------------------------------- #
    def case_objet(self):
        """Le cote d'une case de la grille invisible d'un objet, a l'ecran."""
        return TAILLE_OBJET * self.height * ZOOM / CASES_OBJET

    def _libres(self, o):
        """Les objets poses, hors `o` et ceux que portent les mains."""
        portes = [p for p in self._porte if p is not None]
        return [b for b in self.objets if b is not o
                and not any(b is p for p in portes)]

    def _chevauche(self, x, y, o):
        """Une grille centree en (x, y) chevaucherait-elle celle d'un objet
        pose ?"""
        bord = CASES_OBJET * self.case_objet() - 1e-6
        for b in self._libres(o):
            bx, by = self.a_l_ecran(b)
            if abs(x - bx) < bord and abs(y - by) < bord:
                return True
        return False

    def _places(self, b):
        """Les places BORD A BORD contre la grille de `b` : sur chaque cote,
        alignees sur ses cases, et partageant au moins une case de bord
        (un simple coin ne colle pas)."""
        bx, by = self.a_l_ecran(b)
        c, n = self.case_objet(), CASES_OBJET
        for k in range(-(n - 1), n):
            for kx, ky in ((n, k), (-n, k), (k, n), (k, -n)):
                yield bx + kx * c, by + ky * c

    def _place_libre(self, x, y, o, pres=None):
        """(objet, x, y) : la place bord a bord la plus proche de (x, y), qui
        ne chevauche aucune grille ; parmi les objets `pres` (tous par
        defaut). None s'il n'y en a pas."""
        meilleur, dist = None, None
        for b in (pres if pres is not None else self._libres(o)):
            for sx, sy in self._places(b):
                if self._chevauche(sx, sy, o):
                    continue
                d = math.hypot(sx - x, sy - y)
                if dist is None or d < dist:
                    meilleur, dist = (b, sx, sy), d
        return meilleur

    def _cherche_aimant(self, i):
        """(objet, x, y) : la place libre bord a bord la plus proche contre un
        objet que l'objet porte par la main `i` approche ; ou None."""
        o = self._porte[i]
        if o is None or not self._aimant[i] or self._doigts[i] is None \
                or not self.aimant_permis:
            return None
        px, py = self.paume(i)
        portee = PORTEE_AIMANT * self.case_objet()
        pres = []
        for b in self._libres(o):
            bx, by = self.a_l_ecran(b)
            if abs(px - bx) <= portee and abs(py - by) <= portee:
                pres.append(b)
        if not pres:
            return None
        return self._place_libre(px, py, o, pres)

    def porte(self, i):
        """L'objet que porte la main `i`, ou None."""
        return self._porte[i]

    def ou_est_porte(self, i):
        """Ou se dessine l'objet de la main `i` : aimante, ou dans la
        paume."""
        if self._aimante[i] is not None:
            return self._aimante[i][1], self._aimante[i][2]
        return self.paume(i)

    def decolle(self, o):
        """Defait les liens de `o` : on l'a repris."""
        self.liens = [(a, b) for a, b in self.liens
                      if a is not o and b is not o]

    def contacts(self):
        """Les paires d'objets COLLES pour la recette : ceux que l'aimant a
        lies, et tous ceux dont les grilles se touchent bord a bord.

        Reprendre un objet defait ses liens ; ses voisins, eux, restent la ou
        ils sont. Sans ce releve, un objet toujours colle a l'ecran comptait
        pour seul, et l'assemblage ratait."""
        c, n = self.case_objet(), CASES_OBJET
        tol = TOLERANCE_CONTACT * c
        paires = list(self.liens)
        for i, a in enumerate(self.objets):
            ax, ay = self.a_l_ecran(a)
            for b in self.objets[i + 1:]:
                if any((p is a and q is b) or (p is b and q is a)
                       for p, q in paires):
                    continue
                bx, by = self.a_l_ecran(b)
                dx, dy = abs(ax - bx), abs(ay - by)
                if (abs(dx - n * c) <= tol and dy < n * c + tol) or \
                        (abs(dy - n * c) <= tol and dx < n * c + tol):
                    # Bord a bord, ou COIN A COIN : en diagonale, deux objets
                    # se tiennent aussi (le casque en est fait).
                    paires.append((a, b))
                elif a["nom"] == b["nom"] and dx < n * c - tol \
                        and dy < n * c - tol:
                    # Encore EN PILE (pareils, l'un sur l'autre) : une pile
                    # qu'on n'a pas defaite tient ensemble.
                    paires.append((a, b))
        return paires

    def colles(self, o):
        """Les objets colles a `o`."""
        return [b if a is o else a for a, b in self.liens
                if a is o or b is o]

    def _cible(self, i):
        """Ou va la main `i` : le bas de son avant-bras sous le doigt qui la
        mene, sinon a sa place de base."""
        doigt = self._doigts[i]
        if doigt is None or self.mains is None:
            return (0.0, 0.0)
        bx, by = self.mains.bas_avant_bras(i)
        # Le souffle deplace aussi la main : on le retranche, pour que le
        # bras reste bien sous le doigt.
        souffle = getattr(self.mains, "_shift", None)
        if souffle is not None:
            bx += souffle.x
            by += souffle.y
        return (doigt.x - bx, doigt.y - by)

    def _tick(self, dt):
        dt = min(dt, 0.1)
        encore = False
        for i in (0, 1):
            tx, ty = self._cible(i)
            cx, cy = self._decale[i]
            tau = SUIVI if self._doigts[i] is not None else RETOUR
            k = 1.0 - math.exp(-dt / tau)
            nx, ny = cx + (tx - cx) * k, cy + (ty - cy) * k
            if math.hypot(tx - nx, ty - ny) < ARRIVEE:
                nx, ny = tx, ty
            else:
                encore = True
            self._decale[i] = [nx, ny]
            if self.mains is not None:
                self.mains.decale(i, nx, ny)
            if self._doigts[i] is not None:
                encore = True
                self._immobile[i] += dt
                if self._immobile[i] >= DELAI_AIMANT:
                    self._aimant[i] = False
                if self._porte[i] is None:
                    self._prend(i)
            self._aimante[i] = self._cherche_aimant(i)
        self._dessine_portes()
        if self.sur_pas is not None:
            self.sur_pas(dt)
        if not encore:
            self._arrete()

    def _demarre(self):
        if self._horloge is None:
            self._horloge = Clock.schedule_interval(self._tick, 1.0 / FPS)

    def _arrete(self):
        if self._horloge is not None:
            self._horloge.cancel()
            self._horloge = None

    # -- les doigts -------------------------------------------------------- #
    def _main_de(self, touch):
        for i in (0, 1):
            if self._doigts[i] is touch:
                return i
        return None

    def on_touch_down(self, touch):
        if not self.actif:
            return False
        i = 0 if touch.x < self.x + self.width / 2.0 else 1
        if self._doigts[i] is not None:
            return True
        self._doigts[i] = touch
        self._ancre[i] = (touch.x, touch.y)
        self._immobile[i] = 0.0
        self._aimant[i] = True
        if hasattr(touch, "grab"):
            touch.grab(self)
        self._demarre()
        return True

    def on_touch_move(self, touch):
        i = self._main_de(touch)
        if i is None:
            return False
        ax, ay = self._ancre[i]
        if math.hypot(touch.x - ax, touch.y - ay) > SEUIL_BOUGE:
            # Le doigt rebouge : l'aimant reprend.
            self._ancre[i] = (touch.x, touch.y)
            self._immobile[i] = 0.0
            self._aimant[i] = True
        return True

    def on_touch_up(self, touch):
        i = self._main_de(touch)
        if i is None:
            return False
        if hasattr(touch, "ungrab"):
            touch.ungrab(self)
        self._doigts[i] = None
        if self._porte[i] is not None:
            self._pose(i)
        self._demarre()
        return True


__all__ = ["Assemblage", "Loupe", "vue", "vue_inverse", "ZOOM", "PART_PLAN",
           "DUREE_ZOOM"]
