"""
LES MINI-JEUX D'ASSEMBLAGE : ce qu'il faut reussir pour fabriquer un objet
la premiere fois (voir src/assemblages.py).

Chaque mini-jeu se joue dans la vue d'assemblage, avec les mains libres et
les objets du plan (voir Assemblage). Il coupe l'aimant, suit chaque pas de
la vue, dit au joueur quoi faire (`consigne(texte)`) et appelle `reussi()`
quand c'est fait.

LE COUTEAU EN PIERRE
    1. prendre une pierre dans chaque main ;
    2. frotter la pierre de DROITE contre celle de GAUCHE : contre son flanc
       droit, elle l'amincit d'une couche a droite ; contre son flanc
       gauche, d'une couche a gauche ;
    3. en alternant : un cote, l'autre, le premier, l'autre, et finir par
       le premier -- cinq couches. Frotter deux fois de suite le meme cote
       ne taille rien.

PEU DE TEXTE : une MAIN FANTOME, a demi transparente, montre UNE FOIS
chaque geste (aller prendre les pierres, puis frotter), et l'avancement se
lit en CINQ ENCOCHES gravees sur la pierre qu'on taille.
"""
from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle

from src.widgets.sol_de_craft import dessine_objet

# Part de la largeur de l'image retiree a chaque couche : apres cinq, la
# pierre n'a plus que 55 % de sa largeur -- une lame.
COUCHE = 0.09
AMINCISSEMENTS = 5
# UN FROTTEMENT : la pierre de droite parcourt cette hauteur (en tailles
# d'objet), de haut en bas ou de bas en haut, contre un flanc de l'autre.
FROTTE = 0.7
# CONTRE UN FLANC : ecart horizontal entre les centres (en tailles d'objet),
# de presque superposees a juste cote a cote, et pas trop decalees en
# hauteur.
CONTACT_X = (0.30, 1.15)
CONTACT_Y = 0.75

COTES = ("gauche", "droite")

# LA MAIN FANTOME : son opacite au plus fort, et la duree de chaque geste
# montre (en secondes).
FANTOME_ALPHA = 0.40
DUREE_PRENDRE = 1.1
DUREE_FROTTER = 2.4
FPS_FANTOME = 60.0

# LES ENCOCHES : sous le milieu de la pierre, en tailles d'objet.
ENCOCHE_LONG = 0.14
ENCOCHE_ECART = 0.11
ENCOCHE_BAS = 0.30
GRAVE = (0.13, 0.12, 0.11, 0.92)
GRAVE_LEVRE = (1.0, 1.0, 1.0, 0.40)
A_GRAVER = (0.13, 0.12, 0.11, 0.25)


def _doux(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


class Fantome(object):
    """Une main a demi transparente qui montre un geste, une fois.

    `joue(main, chemin, duree, objet)` : la main `main` passe par les points
    `chemin` (ou va sa paume, a l'ecran), en tenant `objet` s'il y en a un.
    Les gestes demandes a la suite se jouent l'un apres l'autre."""

    def __init__(self, couche, mains, taille_objet):
        self.couche = couche
        self.mains = mains
        self.taille_objet = taille_objet
        self._file = []
        self._t = 0.0
        self._horloge = None

    def joue(self, main, chemin, duree, objet=None):
        self._file.append((main, list(chemin), float(duree), objet))
        if self._horloge is None:
            self._t = 0.0
            self._horloge = Clock.schedule_interval(self._pas,
                                                    1.0 / FPS_FANTOME)

    def en_cours(self):
        return bool(self._file)

    def arrete(self):
        self._file = []
        if self._horloge is not None:
            self._horloge.cancel()
            self._horloge = None
        if self.couche is not None:
            self.couche.canvas.clear()

    def _pas(self, dt):
        if not self._file:
            self.arrete()
            return
        self._t += min(dt, 0.1)
        main, chemin, duree, objet = self._file[0]
        p = self._t / duree
        if p >= 1.0:
            self._file.pop(0)
            self._t = 0.0
            if not self._file:
                self.arrete()
            return
        # Le long du chemin, en douceur d'un point a l'autre.
        n = len(chemin) - 1
        k = min(n - 1, int(p * n)) if n > 0 else 0
        t = _doux(p * n - k) if n > 0 else 0.0
        a, b = chemin[k], chemin[min(n, k + 1)]
        paume = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        # Elle apparait et s'efface.
        alpha = FANTOME_ALPHA * min(1.0, p / 0.15, (1.0 - p) / 0.15)
        self._dessine(main, paume, alpha, objet)

    def _dessine(self, main, paume, alpha, objet):
        if self.couche is None or self.mains is None:
            return
        self.couche.canvas.clear()
        image = self.mains.image_main(main)
        bx, by = self.mains.paume(main)
        dx, dy = paume[0] - bx, paume[1] - by
        with self.couche.canvas:
            if objet is not None:
                dessine_objet(objet["nom"], paume[0], paume[1],
                              self.taille_objet(), ombre=False,
                              coupe=tuple(objet.get("coupe", (0.0, 0.0))),
                              alpha=alpha)
            if image is not None:
                tex, (x, y), (w, h) = image
                Color(1, 1, 1, alpha)
                Rectangle(texture=tex, pos=(x + dx, y + dy), size=(w, h))


class MiniJeuCouteau(object):
    """Tailler une pierre en lame avec une autre."""

    def __init__(self, assemblage, reussi, consigne, couche=None,
                 mains=None):
        self.asm = assemblage
        self.reussi = reussi
        self.consigne = consigne
        self.couche = couche
        self.mains = mains
        self.fantome = Fantome(couche, mains,
                               lambda: assemblage.case_objet() * 3) \
            if couche is not None and mains is not None else None
        self.pierre = None
        self._vu_frotter = False
        self.fait = 0
        self.premier = None
        self.attendu = None
        self.phase = None
        self._contact = None
        self._course = 0.0
        self._y = None
        self._dit = None
        self.fini = False

    # -- cycle ----------------------------------------------------------- #
    def demarre(self):
        self.asm.aimant_permis = False
        self.asm.liens = []
        self.asm.sur_pas = self._pas
        self._annonce("prendre")
        self._montre_prendre()

    def arrete(self):
        if self.asm.sur_pas == self._pas:
            self.asm.sur_pas = None
        self.asm.aimant_permis = True
        if self.fantome is not None:
            self.fantome.arrete()
        if self.couche is not None:
            self.couche.canvas.after.clear()

    # -- ce que montre la main fantome ------------------------------------ #
    def _montre_prendre(self):
        """La main gauche va chercher la pierre de gauche, puis la droite
        celle de droite."""
        if self.fantome is None or self.mains is None:
            return
        pierres = sorted((o for o in self.asm.objets if o["nom"] == "Pierre"),
                         key=lambda o: self.asm.a_l_ecran(o)[0])
        if len(pierres) < 2:
            return
        for main, o in ((0, pierres[0]), (1, pierres[-1])):
            depart = self.mains.paume(main)
            self.fantome.joue(main, [depart, self.asm.a_l_ecran(o),
                                     self.asm.a_l_ecran(o)], DUREE_PRENDRE)

    def _montre_frotter(self, gauche, droite):
        """La main droite, sa pierre en main, frotte le flanc droit de
        l'autre : de haut en bas, deux fois."""
        if self.fantome is None:
            return
        lx, ly = self.asm.ou_est_porte(0)
        t = self.asm.case_objet() * 3
        x = lx + 0.8 * t
        haut, bas = ly + 0.4 * t, ly - 0.4 * t
        self.fantome.joue(1, [(x, haut), (x, bas), (x, haut), (x, bas),
                              (x, haut)], DUREE_FROTTER, objet=droite)

    # -- les encoches ------------------------------------------------------ #
    def _dessine_encoches(self):
        """Cinq encoches sur la pierre qu'on taille : gravees pour les couches
        faites, a peine marquees pour les autres."""
        if self.couche is None:
            return
        self.couche.canvas.after.clear()
        o = self.pierre
        if o is None:
            return
        if self.asm.porte(0) is o:
            cx, cy = self.asm.ou_est_porte(0)
        elif self.asm.porte(1) is o:
            cx, cy = self.asm.ou_est_porte(1)
        else:
            cx, cy = self.asm.a_l_ecran(o)
        t = self.asm.case_objet() * 3
        largeur = max(1.5, t * 0.022)
        y0 = cy - ENCOCHE_BAS * t - ENCOCHE_LONG * t / 2.0
        y1 = y0 + ENCOCHE_LONG * t
        with self.couche.canvas.after:
            for k in range(AMINCISSEMENTS):
                x = cx + (k - (AMINCISSEMENTS - 1) / 2.0) * ENCOCHE_ECART * t
                if k < self.fait:
                    Color(*GRAVE_LEVRE)
                    Line(points=[x + largeur, y0, x + largeur, y1],
                         width=largeur * 0.6)
                    Color(*GRAVE)
                    Line(points=[x, y0, x, y1], width=largeur)
                else:
                    Color(*A_GRAVER)
                    Line(points=[x, y0 + (y1 - y0) * 0.3, x, y1],
                         width=largeur * 0.7)

    # -- les consignes ---------------------------------------------------- #
    def _annonce(self, phase):
        self.phase = phase
        if phase == "prendre":
            texte = "Une pierre dans chaque main"
        elif self.attendu is None:
            texte = "Frotte la droite contre un flanc de la gauche"
        else:
            texte = "Maintenant, son flanc %s" % self.attendu
        if texte != self._dit:
            self._dit = texte
            self.consigne(texte)

    # -- chaque pas de la vue ---------------------------------------------- #
    def _pas(self, dt):
        if self.fini:
            return
        gauche, droite = self.asm.porte(0), self.asm.porte(1)
        self._dessine_encoches()
        if not (gauche and droite and gauche["nom"] == "Pierre"
                and droite["nom"] == "Pierre"):
            self._contact = None
            self._annonce("prendre")
            return
        if self.pierre is None:
            self.pierre = gauche
        self._annonce("frotter")
        if not self._vu_frotter:
            self._vu_frotter = True
            if self.fantome is not None:
                self.fantome.arrete()
            self._montre_frotter(gauche, droite)
        lx, ly = self.asm.ou_est_porte(0)
        rx, ry = self.asm.ou_est_porte(1)
        taille = self.asm.case_objet() * 3
        dx, dy = rx - lx, ry - ly
        contact = (CONTACT_X[0] * taille <= abs(dx) <= CONTACT_X[1] * taille
                   and abs(dy) <= CONTACT_Y * taille)
        cote = "droite" if dx > 0 else "gauche"
        if not contact or cote != self._contact:
            # Un nouveau frottement commence (ou rien ne frotte).
            self._contact = cote if contact else None
            self._course = 0.0
            self._y = ry
            return
        self._course += abs(ry - self._y)
        self._y = ry
        if self._course < FROTTE * taille:
            return
        self._course = 0.0
        if self.attendu is not None and cote != self.attendu:
            return              # le meme flanc deux fois : rien ne se taille
        self.amincit(gauche, cote)

    def amincit(self, pierre, cote):
        """Une couche de moins sur ce flanc de la pierre."""
        pierre["coupe"][COTES.index(cote)] += COUCHE
        self.fait += 1
        self._dessine_encoches()
        if self.premier is None:
            self.premier = cote
        self.attendu = COTES[1 - COTES.index(cote)]
        if self.fait >= AMINCISSEMENTS:
            self.fini = True
            self.reussi()
        else:
            self._annonce("frotter")


MINIJEUX = {
    "couteau": MiniJeuCouteau,
}


__all__ = ["MiniJeuCouteau", "Fantome", "MINIJEUX", "COUCHE",
           "AMINCISSEMENTS"]
