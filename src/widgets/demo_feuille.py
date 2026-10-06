"""
LES MODELES D'UNE FAMILLE (l'equipement en feuille, la pierre taillee),
montres en fantome dans la vue d'assemblage.

Une famille est une recette dont la DISPOSITION de certaines pieces (les
feuilles, les pierres) dit l'objet obtenu (voir assemblages.EQUIPEMENT_
FEUILLE et PIERRE_TAILLEE). Ce qui suit vaut pour toutes ; les feuilles en
sont l'exemple.

Quand le plan de travail porte la recette de l'equipement en feuille, le
milieu de la vue montre, l'un apres l'autre et sans fin, la forme de chaque
piece (voir assemblages.MODELES_FEUILLE) : les feuilles en place, a demi
transparentes, et une main fantome qui apporte la DERNIERE feuille. Une fois
posee, la PIECE QUE DONNE LA RECETTE parait derriere les feuilles. La forme
complete reste DELAI secondes, puis vient la piece suivante ; apres la
derniere, on revient a la premiere. Seules les feuilles sont montrees : les
autres objets de la recette se posent ou l'on veut.

Des que le joueur deplace un objet, le fantome s'efface ; il revient apres
REPRISE secondes sans qu'aucun objet ne bouge.
"""
import math

from kivy.clock import Clock
from kivy.graphics import Color, Rectangle

from src import assemblages
from src.widgets.sol_de_craft import dessine_objet, cadre_image

FEUILLE = assemblages.FEUILLE
ALPHA_FEUILLE = 0.38
ALPHA_MAIN = 0.40
DUREE_MAIN = 2.2            # la main apporte la derniere feuille (s)
DELAI = 3.0                 # la forme complete reste, avant la suivante (s)
FONDU = 0.3                 # apparition / effacement d'une forme (s)
REPRISE = 5.0               # sans objet deplace pendant ce temps : il revient
ALPHA_RESULTAT = 0.75       # la piece fabriquee, derriere les feuilles
APPARITION = 0.5            # son apparition, une fois la feuille posee (s)
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
        self.modeles = assemblages.MODELES_FEUILLE
        self.piece = FEUILLE
        self.asm = asm
        self.couche = couche
        self.mains = mains
        self.annonce = annonce
        self.k = 0
        self.t = 0.0
        self._horloge = None
        self.pause = False
        self._calme = 0.0

    def demarre(self, recette=None):
        """Montre les modeles de la famille `recette` (l'equipement en
        feuille par defaut)."""
        if recette is not None and recette.get("modeles"):
            self.modeles = recette["modeles"]
            self.piece = recette.get("piece", FEUILLE)
        self.k, self.t = 0, 0.0
        self.pause = False
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
            self.annonce(self.modeles[self.k][0])

    # -- geometrie ---------------------------------------------------------- #
    def _places(self, cases):
        """Les feuilles du modele a l'ecran, centrees entre les objets ranges
        sur les cotes, au-dessus des mains.

        TOUJOURS A TAILLE REELLE ET CALEES SUR LA GRILLE DU PLAN, exactement
        la ou se poserait une vraie feuille : un modele reduit pour tenir
        dans la place libre tombait entre les cases, et montrait une forme
        qu'on ne peut pas reproduire. Un modele plus haut que la place libre
        (les bottes, trois feuilles) en garde le haut et descend vers les
        mains."""
        asm = self.asm
        t = asm.case_objet() * 3
        c0, c1 = min(c for c, _r in cases), max(c for c, _r in cases)
        r0, r1 = min(r for _c, r in cases), max(r for _c, r in cases)
        haut = asm.y + HAUT_LIBRE * asm.height
        cy = asm.y + (BAS_LIBRE + HAUT_LIBRE) / 2.0 * asm.height
        cy = min(cy, haut - (r1 - r0 + 1) * t / 2.0)
        bx, by = asm.sur_grille(asm.center_x - (c0 + c1) / 2.0 * t,
                                cy - (r0 + r1) / 2.0 * t)
        return [(bx + c * t, by + r * t) for c, r in cases], t

    def _depart(self):
        """D'ou la main fantome prend la feuille : la plus haute des vraies
        feuilles posees, sinon au-dessus de la paume gauche."""
        asm = self.asm
        portes = [asm.porte(i) for i in (0, 1)]
        feuilles = [o for o in asm.objets if o["nom"] == self.piece
                    and not any(o is p for p in portes)]
        if feuilles:
            o = max(feuilles, key=lambda o: asm.a_l_ecran(o)[1])
            return asm.a_l_ecran(o)
        px, py = self.mains.paume(0)
        return px, py + asm.case_objet() * 3

    def _dessine_resultat(self, nom, places, cote, total):
        """LA PIECE QUE DONNE LA RECETTE, derriere les feuilles : elle parait
        des que la derniere feuille est posee, centree sur le modele et a sa
        taille, et s'efface avec lui."""
        xs = [x for x, _y in places]
        ys = [y for _x, y in places]
        # L'image TIENT DANS le cadre des feuilles (largeur et hauteur), sans
        # le depasser : elle ne deborde ni sur les cotes ni sur les mains.
        larg = max(xs) - min(xs) + cote
        haut = max(ys) - min(ys) + cote
        cadre = cadre_image(nom, 1.0)
        if cadre is None:
            return
        taille = min(larg / cadre[0], haut / cadre[1])
        u = self.t - DUREE_MAIN
        alpha = ALPHA_RESULTAT * min(1.0, u / APPARITION,
                                     (total - self.t) / FONDU)
        dessine_objet(nom, (min(xs) + max(xs)) / 2.0,
                      (min(ys) + max(ys)) / 2.0, taille, ombre=False,
                      alpha=max(0.0, alpha))

    # -- chaque image ------------------------------------------------------- #
    def _pas(self, dt):
        asm = self.asm
        if asm.width <= 0 or asm.height <= 0:
            return
        dt = min(dt, 0.1)
        # LE JOUEUR DEPLACE UN OBJET : le fantome s'efface. Il revient apres
        # REPRISE secondes sans qu'aucun objet ne bouge, en reprenant le
        # modele interrompu depuis son debut.
        if any(asm.porte(i) is not None for i in (0, 1)):
            self._calme = 0.0
            if not self.pause:
                self.pause = True
                self.couche.canvas.clear()
                if self.annonce is not None:
                    self.annonce(None)
            return
        if self.pause:
            self._calme += dt
            if self._calme < REPRISE:
                return
            self.pause = False
            self.t = 0.0
            self._annonce()
        self.t += dt
        if self.t >= DUREE_MAIN + DELAI:
            self.t = 0.0
            self.k = (self.k + 1) % len(self.modeles)
            self._annonce()
        nom, cases = self.modeles[self.k]
        places, cote = self._places(cases)
        total = DUREE_MAIN + DELAI
        fondu = min(1.0, self.t / FONDU, (total - self.t) / FONDU)
        a_feuille = ALPHA_FEUILLE * fondu
        self.couche.canvas.clear()
        with self.couche.canvas:
            if self.t >= DUREE_MAIN:
                self._dessine_resultat(nom, places, cote, total)
            for x, y in places[:-1]:
                dessine_objet(self.piece, x, y, cote, ombre=False,
                              alpha=a_feuille)
            if self.t >= DUREE_MAIN:
                x, y = places[-1]
                dessine_objet(self.piece, x, y, cote, ombre=False,
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
                dessine_objet(self.piece, paume[0], paume[1], cote, ombre=False,
                              alpha=max(alpha, a_feuille))
            image = self.mains.image_main(0)
            if image is not None:
                tex, (ix, iy), (iw, ih) = image
                bx, by = self.mains.paume(0)
                Color(1, 1, 1, alpha)
                Rectangle(texture=tex, pos=(ix + paume[0] - bx,
                                            iy + paume[1] - by),
                          size=(iw, ih))


def etale_sur_les_cotes(asm, piece=FEUILLE):
    """Range les objets de la vue d'assemblage SUR LES COTES de l'ecran,
    pour laisser le milieu au modele fantome : les pieces de la famille (les
    feuilles) a gauche, les autres objets a droite, en blocs de deux
    colonnes. Seule leur place a
    l'ecran change : Annuler les rend toujours a leurs cases."""
    # Colonnes BORD A BORD (le modele le plus large, le casque, fait quatre
    # feuilles : il lui faut tout le milieu), rangees separees d'une case.
    t = asm.case_objet() * 3
    pas_x = t
    pas_y = t + asm.case_objet()
    marge = 0.01 * asm.width + t / 2.0
    haut = asm.y + 0.74 * asm.height
    gauche = [o for o in asm.objets if o["nom"] == piece]
    droite = [o for o in asm.objets if o["nom"] != piece]
    if len(gauche) <= 3 and not droite:
        # PEU DE PIECES ET RIEN D'AUTRE (les deux pierres) : une de chaque
        # cote. Chaque main ne prend que de son cote de l'ecran, et cote a
        # cote, deux pierres feraient deja un couteau.
        gauche, droite = gauche[0::2], gauche[1::2]
    for objets, x0, sens in ((gauche, asm.x + marge, 1),
                             (droite, asm.x + asm.width - marge, -1)):
        # Peu d'objets : une seule colonne, chacun separe du suivant.
        cols = 1 if len(objets) <= 3 else 2
        for n, o in enumerate(objets):
            col, rang = n % cols, n // cols
            px, py = asm.sur_grille(x0 + sens * col * pas_x,
                                    haut - rang * pas_y)
            asm.place_a_l_ecran(o, px, py)


__all__ = ["DemoFeuille", "etale_sur_les_cotes"]
