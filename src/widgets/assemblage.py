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
  mene la main gauche, dans la moitie droite la main droite. La paume se
  place AU-DESSUS du doigt et un peu VERS L'INTERIEUR, pour que le doigt ne
  cache pas ce qu'elle prend. Lachee, la main revient a sa place de base, en bas ;
- une main qui PASSE SUR UN OBJET le prend : il colle a la paume tant que
  le doigt reste pose. Il est tenu DANS la paume : la main se dessine
  devant lui, pas l'inverse. Au lacher, l'objet reste EXACTEMENT ou il est, et la
  main repart seule vers sa place.

RIEN DE TOUT CELA NE TOUCHE A LA PARTIE : les objets ne bougent qu'a
l'ecran. Annuler les remet dans leurs cases, la ou ils etaient avant
d'assembler (voir CraftScreen).
"""
import math

from kivy.clock import Clock
from kivy.graphics import PushMatrix, PopMatrix, Translate, Scale
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget

from src.widgets.sol_de_craft import (dessine_objet, TAILLE_OBJET,
                                      CENTRE_PRES, CENTRE_LOIN, CENTRE_DEMI)

# La part de la largeur que prend le plan de travail une fois rapproche.
PART_PLAN = 2.0 / 3.0
# Le grossissement qui l'y amene : il fait 2 x CENTRE_DEMI de large.
ZOOM = PART_PLAN / (2.0 * CENTRE_DEMI)
# Le milieu du plan de travail dans la vue normale, et ou il arrive une fois
# rapproche : au milieu de l'ecran.
CENTRE_PLAN = (0.5, (CENTRE_PRES + CENTRE_LOIN) / 2.0)
CENTRE_VUE = (0.5, 0.5)
# Duree du rapprochement (et du recul), en secondes.
DUREE_ZOOM = 0.45

# LA PAUME SE POSE AU-DESSUS DU DOIGT, de cette part de la hauteur, et un
# peu VERS L'INTERIEUR, de cette part de la largeur (la main gauche a droite
# du doigt, la droite a gauche) : sous le doigt, on ne verrait ni la main ni
# ce qu'elle tient. L'objet tenu et la zone ou elle prend suivent la paume.
LEVE_PAUME = 0.08
VERS_INTERIEUR = 0.035
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
        self.bind(pos=self._redessine, size=self._redessine)

    # -- ce qu'il y a sur le plan ---------------------------------------- #
    def charge(self, objets):
        """[(nom, fx, fy)] : les objets du plan, au milieu de leur case."""
        self.objets = [{"nom": n, "x": fx, "y": fy, "x0": fx, "y0": fy,
                        "xa": fx, "ya": fy} for n, fx, fy in objets]
        self._porte = [None, None]
        self._redessine()

    def vide(self):
        self.lache_tout()
        self.objets = []
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
            # Du plus loin (haut) au plus pres : celui de devant passe devant.
            for o in sorted(self.objets, key=lambda o: -o["y"]):
                if any(o is p for p in portes):
                    continue
                dessine_objet(o["nom"], self.x + o["x"] * self.width,
                              self.y + o["y"] * self.height, cote)
        self._dessine_portes()

    def _dessine_portes(self):
        if self.couche is None:
            return
        self.couche.canvas.clear()
        cote = TAILLE_OBJET * self.height * ZOOM
        with self.couche.canvas:
            for i in (0, 1):
                if self._porte[i] is not None:
                    px, py = self.paume(i)
                    dessine_objet(self._porte[i]["nom"], px, py, cote,
                                  ombre=False)

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

    def a_l_ecran(self, o):
        return vue(1.0, self.x + o["x"] * self.width,
                   self.y + o["y"] * self.height, self.width, self.height,
                   self.x, self.y)

    def _prend(self, i):
        """La paume `i` passe-t-elle sur un objet libre ? Elle le prend."""
        px, py = self.paume(i)
        rayon = SAISIE * TAILLE_OBJET * self.height * ZOOM
        portes = [o for o in self._porte if o is not None]
        meilleur, dist = None, rayon
        for o in self.objets:
            if any(o is p for p in portes):
                continue
            ox, oy = self.a_l_ecran(o)
            d = math.hypot(ox - px, oy - py)
            if d <= dist:
                meilleur, dist = o, d
        if meilleur is not None:
            self._porte[i] = meilleur
            self._redessine()

    def _pose(self, i):
        """L'objet porte par la main `i` reste exactement ou il est."""
        o = self._porte[i]
        self._porte[i] = None
        px, py = self.paume(i)
        x, y = vue_inverse(1.0, px, py, self.width, self.height,
                           self.x, self.y)
        o["x"] = (x - self.x) / self.width
        o["y"] = (y - self.y) / self.height
        self._redessine()

    def _cible(self, i):
        """Ou va la main `i` : vers le doigt qui la mene (la paume au-dessus
        et vers l'interieur), sinon a sa place de base."""
        doigt = self._doigts[i]
        if doigt is None or self.mains is None:
            return (0.0, 0.0)
        bx, by = self.paume(i)
        bx -= self._decale[i][0]
        by -= self._decale[i][1]
        vers = 1.0 if i == 0 else -1.0
        px = min(max(doigt.x + vers * VERS_INTERIEUR * self.width, self.x),
                 self.x + self.width)
        py = min(max(doigt.y + LEVE_PAUME * self.height, self.y),
                 self.y + self.height)
        return (px - bx, py - by)

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
                if self._porte[i] is None:
                    self._prend(i)
        self._dessine_portes()
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
        if hasattr(touch, "grab"):
            touch.grab(self)
        self._demarre()
        return True

    def on_touch_move(self, touch):
        return self._main_de(touch) is not None

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
