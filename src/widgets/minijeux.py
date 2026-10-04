"""
LES MINI-JEUX D'ASSEMBLAGE : ce qu'il faut reussir pour fabriquer un objet,
CHAQUE FOIS (voir src/assemblages.py).

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

LA FIBRE VEGETALE
    1. prendre le couteau en pierre dans une main ;
    2. le brin a couper est pose AU MILIEU DU PLAN, quelle que soit la place
       ou le joueur l'avait mis ; CINQ TRAITS EN POINTILLES y montrent ou
       couper ;
    3. un coup de couteau a travers le brin, de haut en bas ou de bas en
       haut, coupe le trait le plus proche : le brin s'ouvre en morceaux ;
    4. trois brins, l'un apres l'autre : les feuilles d'abord, puis les
       herbes (deux feuilles et une herbe : feuille, feuille, herbe).

LE FEU DE CAMP
    1. la recette ne demande que QUATRE pierres, mais au debut du jeu chaque
       pierre se DEDOUBLE : il y en a huit ;
    2. huit places, en cercle autour du milieu du plan, attendent chacune
       une pierre ; une pierre lachee pres d'une place libre s'y range ;
    3. les huit places remplies : le feu de camp est fait.
    Annule, les pierres en double disparaissent : les quatre vraies
    regagnent leurs cases, comme d'habitude.

PEU DE TEXTE : une MAIN FANTOME, a demi transparente, montre UNE FOIS
chaque geste, et ce qu'il reste a faire se voit SUR L'OBJET MEME : la couche
a retirer de la pierre, les traits a couper du brin (voir
assemblage.dessine_travail).
"""
import math

from kivy.clock import Clock
from kivy.graphics import Color, Rectangle

from src.widgets.sol_de_craft import dessine_objet, cadre_image
from src.widgets.assemblage import decalage_morceau, vue_inverse

COUTEAU = "Couteau_En_Pierre"

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
        for o in self.asm.objets:
            o.pop("entailles", None)
        self.asm._redessine()

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

    # -- l'entaille a faire -------------------------------------------- #
    def _marque_entailles(self):
        """Sur la pierre qu'on taille, la COUCHE A RETIRER : du bord du flanc
        attendu jusqu'a un trait en pointilles (les deux flancs au premier
        coup, quand l'un ou l'autre convient)."""
        o = self.pierre
        if o is None:
            return
        cotes = COTES if self.attendu is None else (self.attendu,)
        g, d = o["coupe"]
        o["entailles"] = [("gauche", g + COUCHE) if c == "gauche"
                          else ("droite", 1.0 - d - COUCHE) for c in cotes]
        self.asm._redessine()

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
        if not (gauche and droite and gauche["nom"] == "Pierre"
                and droite["nom"] == "Pierre"):
            self._contact = None
            self._annonce("prendre")
            return
        if self.pierre is None:
            self.pierre = gauche
            self._marque_entailles()
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
        if self.premier is None:
            self.premier = cote
        self.attendu = COTES[1 - COTES.index(cote)]
        if self.fait >= AMINCISSEMENTS:
            self.fini = True
            pierre.pop("entailles", None)
            self.asm._redessine()
            self.reussi()
        else:
            self._marque_entailles()
            self._annonce("frotter")


# LA FIBRE : chaque brin se coupe en CINQ TRAITS, a ces parts de la largeur
# de son image. Un coup de couteau traverse le brin -- de plus haut que
# HAUT_BRIN au-dessus de son milieu a plus bas que HAUT_BRIN au-dessous, ou
# l'inverse -- et coupe le trait restant le plus proche, s'il en passe a
# moins de PRISE_TRAIT ecart(s) entre deux traits.
TRAITS = tuple((k + 1) / 6.0 for k in range(5))
HAUT_BRIN = 0.22
PRISE_TRAIT = 0.75
LARGE_COUP = 0.75
ORDRE_BRINS = ("Feuille", "Herbe")
DUREE_COUPER = 2.2
# Ou se rangent les brins qui attendent (a gauche du milieu) et le couteau
# (a droite), en tailles d'objet depuis le milieu du plan.
RANGE_BRINS = (-1.25, 0.0)
PAS_BRINS = (-0.35, 0.55)
RANGE_COUTEAU = (1.30, -0.15)


class MiniJeuFibre(object):
    """Decouper au couteau trois brins en morceaux."""

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
        # Les brins dans l'ordre ou on les coupe : feuilles, puis herbes ;
        # de gauche a droite a egalite.
        self.brins = sorted(
            (o for o in assemblage.objets if o["nom"] in ORDRE_BRINS),
            key=lambda o: (ORDRE_BRINS.index(o["nom"]),
                           assemblage.a_l_ecran(o)[0]))
        self.actuel = 0
        self._coup = None           # [cote de depart, x cumules, nombre]
        self._vu_couper = False
        self._dit = None
        self.fini = False

    # -- cycle ----------------------------------------------------------- #
    def demarre(self):
        self.asm.aimant_permis = False
        self.asm.liens = []
        self.asm.sur_pas = self._pas
        for o in self.brins:
            o["morceaux"] = []
        self._range()
        self._annonce()
        self._montre_prendre()

    def arrete(self):
        if self.asm.sur_pas == self._pas:
            self.asm.sur_pas = None
        self.asm.aimant_permis = True
        if self.fantome is not None:
            self.fantome.arrete()
        for o in self.brins:
            o.pop("a_couper", None)
            o.pop("morceaux", None)
        self.asm._redessine()

    # -- ou sont les choses ---------------------------------------------- #
    def main_du_couteau(self):
        for i in (1, 0):
            o = self.asm.porte(i)
            if o is not None and o["nom"] == COUTEAU:
                return i
        return None

    def _taille(self):
        return self.asm.case_objet() * 3

    def _centre(self, o):
        for i in (0, 1):
            if self.asm.porte(i) is o:
                return self.asm.ou_est_porte(i)
        return self.asm.a_l_ecran(o)

    def _range(self):
        """Le brin a couper AU MILIEU DU PLAN, ceux qui attendent a sa
        gauche, ceux deja coupes plus loin, le couteau a sa droite (s'il
        n'est pas deja en main). Peu importe ou le joueur les avait mis."""
        mx, my = self.asm.centre_du_plan()
        t = self._taille()
        autres = [o for n, o in enumerate(self.brins) if n != self.actuel]
        for n, o in enumerate(self.brins):
            if n == self.actuel:
                px, py = mx, my
            else:
                k = autres.index(o)
                px = mx + (RANGE_BRINS[0] + PAS_BRINS[0] * k) * t
                py = my + (RANGE_BRINS[1] + PAS_BRINS[1] * k) * t
            if not any(self.asm.porte(i) is o for i in (0, 1)):
                self.asm.place_a_l_ecran(o, px, py)
            o["a_couper"] = [u for u in TRAITS
                             if u not in o["morceaux"]] \
                if n == self.actuel else []
        couteau = next((o for o in self.asm.objets if o["nom"] == COUTEAU),
                       None)
        if couteau is not None and self.main_du_couteau() is None:
            self.asm.place_a_l_ecran(couteau, mx + RANGE_COUTEAU[0] * t,
                                     my + RANGE_COUTEAU[1] * t)
        self.asm._redessine()

    def x_trait(self, u, o):
        """Ou passe, a l'ecran, le trait `u` du brin `o`."""
        cx, _ = self._centre(o)
        t = self._taille()
        cadre = cadre_image(o["nom"], t)
        iw = cadre[0] if cadre else t
        return cx - iw / 2.0 + u * iw + decalage_morceau(o, u, t)

    def _ecart_traits(self, o):
        t = self._taille()
        cadre = cadre_image(o["nom"], t)
        return (cadre[0] if cadre else t) / 6.0

    # -- ce que montre la main fantome ------------------------------------ #
    def _montre_prendre(self):
        """La main droite va chercher le couteau."""
        if self.fantome is None or self.mains is None:
            return
        couteau = next((o for o in self.asm.objets if o["nom"] == COUTEAU),
                       None)
        if couteau is None:
            return
        depart = self.mains.paume(1)
        lieu = self.asm.a_l_ecran(couteau)
        self.fantome.joue(1, [depart, lieu, lieu], DUREE_PRENDRE)

    def _montre_couper(self, main, couteau):
        """Le couteau passe a travers le brin, sur deux traits : un coup vers
        le bas, un coup vers le haut."""
        if self.fantome is None or self.actuel >= len(self.brins):
            return
        o = self.brins[self.actuel]
        _, cy = self._centre(o)
        t = self._taille()
        haut, bas = cy + (HAUT_BRIN + 0.15) * t, cy - (HAUT_BRIN + 0.15) * t
        x0, x1 = self.x_trait(TRAITS[1], o), self.x_trait(TRAITS[3], o)
        self.fantome.joue(main, [(x0, haut), (x0, bas), (x1, bas),
                                 (x1, haut)], DUREE_COUPER, objet=couteau)

    # -- les consignes ---------------------------------------------------- #
    def _annonce(self):
        if self.main_du_couteau() is None:
            texte = "Prends le couteau"
        else:
            o = self.brins[self.actuel]
            texte = "Coupe %s sur les pointilles (%d/%d)" % (
                "la feuille" if o["nom"] == "Feuille" else "l'herbe",
                self.actuel + 1, len(self.brins))
        if texte != self._dit:
            self._dit = texte
            self.consigne(texte)

    # -- chaque pas de la vue ---------------------------------------------- #
    def _pas(self, dt):
        if self.fini or not self.brins:
            return
        main = self.main_du_couteau()
        self._annonce()
        if main is None:
            self._coup = None
            return
        couteau = self.asm.porte(main)
        if not self._vu_couper:
            self._vu_couper = True
            if self.fantome is not None:
                self.fantome.arrete()
            self._montre_couper(main, couteau)
        o = self.brins[self.actuel]
        x, y = self.asm.ou_est_porte(main)
        cx, cy = self._centre(o)
        t = self._taille()
        if abs(x - cx) > LARGE_COUP * t:
            self._coup = None        # parti loin du brin, sur le cote
            return
        if y >= cy + HAUT_BRIN * t:
            cote = "haut"
        elif y <= cy - HAUT_BRIN * t:
            cote = "bas"
        else:
            cote = None
        if cote is not None:
            if self._coup is not None and self._coup[0] != cote \
                    and self._coup[2] > 0:
                # Traverse de part en part : le coup est donne.
                xm = self._coup[1] / self._coup[2]
                self._coup = [cote, 0.0, 0]
                self.coupe_pres(xm)
                return
            self._coup = [cote, 0.0, 0]   # pret a traverser
            return
        if self._coup is not None:
            self._coup[1] += x
            self._coup[2] += 1

    def coupe_pres(self, x):
        """Un coup de couteau a travers le brin en cours, a l'abscisse `x` :
        le trait restant le plus proche est coupe, s'il est assez pres."""
        o = self.brins[self.actuel]
        restants = o.get("a_couper", [])
        if not restants:
            return
        u = min(restants, key=lambda v: abs(self.x_trait(v, o) - x))
        if abs(self.x_trait(u, o) - x) > PRISE_TRAIT * self._ecart_traits(o):
            return
        self.coupe(u)

    def coupe(self, u):
        """Le trait `u` du brin en cours est coupe."""
        o = self.brins[self.actuel]
        if u not in o.get("a_couper", []):
            return
        o["a_couper"] = [v for v in o["a_couper"] if v != u]
        o["morceaux"] = sorted(o["morceaux"] + [u])
        if not o["a_couper"]:
            self.actuel += 1
            if self.actuel >= len(self.brins):
                self.fini = True
                self.asm._redessine()
                self.reussi()
                return
            self._range()
        self.asm._redessine()
        self._annonce()


# LE FEU DE CAMP : huit places sur un cercle de RAYON_CERCLE (en tailles
# d'objet), un peu au-dessus du milieu du plan pour passer au-dessus des
# mains. Une pierre lachee a moins de PRISE_PLACE d'une place libre s'y range.
PLACES_FEU = 8
RAYON_CERCLE = 0.95
HAUSSE_CERCLE = 0.05
PRISE_PLACE = 0.50
DUREE_RANGER = 1.6
PIERRE = "Pierre"


class MiniJeuFeu(object):
    """Poser huit pierres en cercle."""

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
        self.doubles = []
        self.places = []            # a l'ecran
        self._tenues = [None, None]  # ce que tenaient les mains au pas d'avant
        self._dit = None
        self._vu = False
        self.fini = False

    def _taille(self):
        return self.asm.case_objet() * 3

    # -- cycle ----------------------------------------------------------- #
    def demarre(self):
        asm = self.asm
        asm.aimant_permis = False
        asm.liens = []
        asm.sur_pas = self._pas
        mx, my = asm.centre_du_plan()
        my += HAUSSE_CERCLE * asm.height
        r = RAYON_CERCLE * self._taille()
        self.places = [(mx + r * math.sin(2 * math.pi * k / PLACES_FEU),
                        my + r * math.cos(2 * math.pi * k / PLACES_FEU))
                       for k in range(PLACES_FEU)]
        asm.emplacements = []
        for px, py in self.places:
            x, y = vue_inverse(1.0, px, py, asm.width, asm.height,
                               asm.x, asm.y)
            asm.emplacements.append((PIERRE, (x - asm.x) / asm.width,
                                     (y - asm.y) / asm.height))
        # CHAQUE PIERRE SE DEDOUBLE : sa jumelle parait juste a cote, a la
        # premiere place libre bord a bord.
        for o in [o for o in asm.objets if o["nom"] == PIERRE]:
            jumelle = {"nom": PIERRE, "x": o["x"], "y": o["y"],
                       "x0": o["x0"], "y0": o["y0"], "xa": o["x"],
                       "ya": o["y"], "coupe": [0.0, 0.0], "double": True}
            ox, oy = asm.a_l_ecran(o)
            libre = asm._place_libre(ox, oy, jumelle, pres=[o])
            if libre is None:
                libre = (o, ox + self._taille(), oy)
            asm.objets.append(jumelle)
            asm.place_a_l_ecran(jumelle, libre[1], libre[2])
            self.doubles.append(jumelle)
        asm._redessine()
        self._annonce()
        self._montre()

    def arrete(self):
        asm = self.asm
        if asm.sur_pas == self._pas:
            asm.sur_pas = None
        asm.aimant_permis = True
        if self.fantome is not None:
            self.fantome.arrete()
        # Les pierres en double n'ont jamais existe : elles disparaissent,
        # meme tenues en main.
        for i in (0, 1):
            if any(asm._porte[i] is d for d in self.doubles):
                asm._porte[i] = None
                asm._aimante[i] = None
        asm.objets = [o for o in asm.objets
                      if not any(o is d for d in self.doubles)]
        self.doubles = []
        asm.emplacements = []
        asm._redessine()

    # -- les places -------------------------------------------------------- #
    def libres(self):
        """Les pierres posees (pas en main)."""
        portes = [self.asm.porte(i) for i in (0, 1)]
        return [o for o in self.asm.objets if o["nom"] == PIERRE
                and not any(o is p for p in portes)]

    def remplies(self):
        """Les indices des places ou une pierre est rangee."""
        pres = 0.08 * self._taille()
        out = set()
        for o in self.libres():
            ox, oy = self.asm.a_l_ecran(o)
            for k, (px, py) in enumerate(self.places):
                if math.hypot(ox - px, oy - py) <= pres:
                    out.add(k)
        return out

    def _montre(self):
        """Une main fantome porte une pierre jusqu'a une place."""
        if self.fantome is None or self.mains is None or not self.places:
            return
        pierres = self.libres()
        if not pierres:
            return
        o = min(pierres, key=lambda p: self.asm.a_l_ecran(p)[1])
        ox, oy = self.asm.a_l_ecran(o)
        main = 0 if ox < self.asm.center_x else 1
        cible = min(self.places, key=lambda p: math.hypot(p[0] - ox,
                                                          p[1] - oy))
        self.fantome.joue(main, [self.mains.paume(main), (ox, oy),
                                 (ox, oy), cible, cible], DUREE_RANGER,
                          objet=o)

    def _annonce(self):
        texte = "Place les pierres en cercle (%d/%d)" % (len(self.remplies()),
                                                         PLACES_FEU)
        if texte != self._dit:
            self._dit = texte
            self.consigne(texte)

    # -- chaque pas de la vue ---------------------------------------------- #
    def _pas(self, dt):
        if self.fini:
            return
        prises = self.remplies()
        prise = PRISE_PLACE * self._taille()
        # Seule une pierre qu'une main vient de LACHER se range : celles qui
        # attendent pres du cercle depuis le debut restent ou elles sont.
        tenues = [self.asm.porte(i) for i in (0, 1)]
        lachees = [o for o in self._tenues if o is not None
                   and not any(o is t for t in tenues)]
        self._tenues = tenues
        for o in lachees:
            ox, oy = self.asm.a_l_ecran(o)
            if any(math.hypot(ox - px, oy - py) <= 0.08 * self._taille()
                   for px, py in self.places):
                continue
            proches = [(math.hypot(ox - px, oy - py), k)
                       for k, (px, py) in enumerate(self.places)
                       if k not in prises]
            if not proches:
                continue
            d, k = min(proches)
            if d <= prise:
                # Lachee pres d'une place libre : elle s'y range.
                self.asm.place_a_l_ecran(o, *self.places[k])
                prises.add(k)
        self._annonce()
        if len(prises) >= PLACES_FEU:
            self.fini = True
            self.reussi()


MINIJEUX = {
    "couteau": MiniJeuCouteau,
    "fibre": MiniJeuFibre,
    "feu": MiniJeuFeu,
}


__all__ = ["MiniJeuCouteau", "MiniJeuFibre", "MiniJeuFeu", "Fantome", "MINIJEUX", "COUCHE",
           "AMINCISSEMENTS"]
