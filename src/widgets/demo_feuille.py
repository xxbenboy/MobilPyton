"""
LES MODELES D'EQUIPEMENT EN FEUILLE, montres en fantome dans la vue
d'assemblage.

Quand le plan de travail porte la recette de l'equipement en feuille, le
milieu de la vue montre, l'un apres l'autre et sans fin, la forme de chaque
piece (voir assemblages.MODELES_FEUILLE) : les feuilles en place, a demi
transparentes, et une main fantome qui apporte la DERNIERE feuille. La forme
complete reste DELAI secondes, puis vient la piece suivante ; apres la
derniere, on revient a la premiere. Seules les feuilles sont montrees : les
autres objets de la recette se posent ou l'on veut.
"""
import math

from kivy.clock import Clock
from kivy.graphics import Color, Rectangle

from src import assemblages
from src.widgets.sol_de_craft import dessine_objet

FEUILLE = assemblages.FEUILLE
ALPHA_FEUILLE = 0.38
ALPHA_MAIN = 0.40
DUREE_MAIN = 2.2            # la main apporte la derniere feuille (s)
DELAI = 3.0                 # la forme complete reste, avant la suivante (s)
FONDU = 0.3                 # apparition / effacement d'une forme (s)
# L'espace du modele, en parts de la hauteur : sous le titre, au-dessus des
# mains.
BAS_LIBRE = 0.30
HAUT_LIBRE = 0.88
FPS = 60.0


def _doux(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


class DemoFeuille(object):
    """`asm` : la vue d'assemblage ; `couche` : ou dessiner (au-dessus des
    mains) ; `mains` : les mains du joueur ; `annonce(nom)` : prevenu a
    chaque nouveau modele."""

    def __init__(self, asm, couche, mains, annonce=None):
        self.asm = asm
        self.couche = couche
        self.mains = mains
        self.annonce = annonce
        self.k = 0
        self.t = 0.0
        self._horloge = None

    def demarre(self):
        self.k, self.t = 0, 0.0
        self._annonce()
        if self._horloge is None:
            self._horloge = Clock.schedule_interval(self._pas, 1.0 / FPS)

    def arrete(self):
        if self._horloge is not None:
            self._horloge.cancel()
            self._horloge = None
        self.couche.canvas.clear()

    def _annonce(self):
        if self.annonce is not None:
            self.annonce(assemblages.MODELES_FEUILLE[self.k][0])

    # -- geometrie ---------------------------------------------------------- #
    def _places(self, cases):
        """Les feuilles du modele a l'ecran, centrees entre les objets ranges
        sur les cotes, au-dessus des mains. Calees sur la grille du plan ; un
        modele trop grand pour cet espace (les bottes, trois feuilles de
        haut) est montre en plus petit."""
        asm = self.asm
        t = asm.case_objet() * 3
        cx = asm.center_x
        cy = asm.y + (BAS_LIBRE + HAUT_LIBRE) / 2.0 * asm.height
        larg_libre = asm.width - 2 * (0.01 * asm.width + 2 * t) - 0.2 * t
        haut_libre = (HAUT_LIBRE - BAS_LIBRE) * asm.height
        c0, c1 = min(c for c, _r in cases), max(c for c, _r in cases)
        r0, r1 = min(r for _c, r in cases), max(r for _c, r in cases)
        s = min(1.0, larg_libre / ((c1 - c0 + 1) * t),
                haut_libre / ((r1 - r0 + 1) * t))
        u = t * s
        bx = cx - (c0 + c1) / 2.0 * u
        by = cy - (r0 + r1) / 2.0 * u
        if s >= 1.0:
            bx, by = asm.sur_grille(bx, by)
        return [(bx + c * u, by + r * u) for c, r in cases], u

    def _depart(self):
        """D'ou la main fantome prend la feuille : la plus haute des vraies
        feuilles posees, sinon au-dessus de la paume gauche."""
        asm = self.asm
        portes = [asm.porte(i) for i in (0, 1)]
        feuilles = [o for o in asm.objets if o["nom"] == FEUILLE
                    and not any(o is p for p in portes)]
        if feuilles:
            o = max(feuilles, key=lambda o: asm.a_l_ecran(o)[1])
            return asm.a_l_ecran(o)
        px, py = self.mains.paume(0)
        return px, py + asm.case_objet() * 3

    # -- chaque image ------------------------------------------------------- #
    def _pas(self, dt):
        asm = self.asm
        if asm.width <= 0 or asm.height <= 0:
            return
        self.t += min(dt, 0.1)
        if self.t >= DUREE_MAIN + DELAI:
            self.t = 0.0
            self.k = (self.k + 1) % len(assemblages.MODELES_FEUILLE)
            self._annonce()
        places, cote = self._places(assemblages.MODELES_FEUILLE[self.k][1])
        total = DUREE_MAIN + DELAI
        fondu = min(1.0, self.t / FONDU, (total - self.t) / FONDU)
        a_feuille = ALPHA_FEUILLE * fondu
        self.couche.canvas.clear()
        with self.couche.canvas:
            for x, y in places[:-1]:
                dessine_objet(FEUILLE, x, y, cote, ombre=False,
                              alpha=a_feuille)
            if self.t >= DUREE_MAIN:
                x, y = places[-1]
                dessine_objet(FEUILLE, x, y, cote, ombre=False,
                              alpha=a_feuille)
                return
            # La main fantome : de sa place, vers une vraie feuille, puis
            # jusqu'a la place de la derniere feuille du modele.
            depart = self._depart()
            chemin = [self.mains.paume(0), depart, depart, places[-1],
                      places[-1]]
            p = self.t / DUREE_MAIN
            n = len(chemin) - 1
            k = min(n - 1, int(p * n))
            u = _doux(p * n - k)
            a, b = chemin[k], chemin[k + 1]
            paume = (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)
            alpha = ALPHA_MAIN * min(1.0, p / 0.12, (1.0 - p) / 0.12 + 0.6)
            if k >= 1:                       # la feuille est prise
                dessine_objet(FEUILLE, paume[0], paume[1], cote, ombre=False,
                              alpha=max(alpha, a_feuille))
            image = self.mains.image_main(0)
            if image is not None:
                tex, (ix, iy), (iw, ih) = image
                bx, by = self.mains.paume(0)
                Color(1, 1, 1, alpha)
                Rectangle(texture=tex, pos=(ix + paume[0] - bx,
                                            iy + paume[1] - by),
                          size=(iw, ih))


def etale_sur_les_cotes(asm):
    """Range les objets de la vue d'assemblage SUR LES COTES de l'ecran,
    pour laisser le milieu au modele fantome : les feuilles a gauche, les
    autres objets a droite, en blocs de deux colonnes. Seule leur place a
    l'ecran change : Annuler les rend toujours a leurs cases."""
    # Colonnes BORD A BORD (le modele le plus large, le casque, fait quatre
    # feuilles : il lui faut tout le milieu), rangees separees d'une case.
    t = asm.case_objet() * 3
    pas_x = t
    pas_y = t + asm.case_objet()
    marge = 0.01 * asm.width + t / 2.0
    haut = asm.y + 0.74 * asm.height
    gauche = [o for o in asm.objets if o["nom"] == FEUILLE]
    droite = [o for o in asm.objets if o["nom"] != FEUILLE]
    for objets, x0, sens in ((gauche, asm.x + marge, 1),
                             (droite, asm.x + asm.width - marge, -1)):
        for n, o in enumerate(objets):
            col, rang = n % 2, n // 2
            px, py = asm.sur_grille(x0 + sens * col * pas_x,
                                    haut - rang * pas_y)
            asm.place_a_l_ecran(o, px, py)


__all__ = ["DemoFeuille", "etale_sur_les_cotes"]
