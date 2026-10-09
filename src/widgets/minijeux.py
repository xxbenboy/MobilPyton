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
    1. la recette demande HUIT pierres (empilees sur le plan) ;
    2. les huit pierres sont rangees A GAUCHE DE L'ECRAN ; huit places, en
       cercle autour du milieu du plan, attendent chacune une pierre ;
    3. une pierre lachee sur une place libre, ou un peu a cote, se recentre
       dessus et s'y VERROUILLE : on ne peut plus la reprendre ;
    4. les huit places remplies : le feu de camp est fait.
    Annule, les pierres regagnent leurs cases, comme d'habitude.

LA CORDE
    1. les trois fibres vegetales pendent cote a cote, nouees en haut : une
       a GAUCHE, une au MILIEU, une a DROITE ;
    2. on prend un brin du BORD et on le porte AU-DELA DU MILIEU, entre le
       brin du milieu et celui de l'autre bord (un rond de craie y attend) :
       il passe par-dessus celui du milieu, prend sa place, et celui-ci
       passe au bord. La tresse s'allonge d'un croisement ;
    3. un bord, puis l'autre, en alternant (le meme deux fois de suite ne
       tresse rien : le brin retourne a sa place) ; le brin du milieu ne
       se prend pas ;
    4. chaque brin doit etre croise CINQ FOIS : quinze croisements, et la
       corde est tressee.

LA HACHE
    1. les quatre petits batons attendent a gauche, la pierre coupante et
       la corde a droite ; quatre places, cote a cote, dessinent le manche
       au milieu : chaque baton lache sur une place s'y VERROUILLE ;
    2. la corde en main, passer d'un cote a l'autre du BAS DU MANCHE : un
       tour a chaque passage, quatre tours ;
    3. poser la pierre coupante EN HAUT du manche, sur sa place ;
    4. croiser la corde EN X sur la pierre : d'un coin au coin oppose, une
       diagonale puis l'autre, deux fois -- la hache est solide.
    La corde lachee retourne toujours a sa place.

L'EQUIPEMENT EN FEUILLE (casque, veste, pantalon, gants, souliers)
    la piece est decoupee en TROIS TIERS (gauche, milieu, droite), et
    chaque tiers se fabrique en un tour :
    1. cinq feuilles paraissent au milieu, disposees comme le tiers qu'on
       fait (la manche, le corps, la jambe...) ; on perce un trou au
       COUTEAU au milieu de chacune ;
    2. on passe la CORDE dans les cinq trous : les feuilles cousues
       deviennent le tiers de la piece, qui va attendre a gauche ;
    3. apres trois tours, on pose les trois tiers sur la piece en
       fantome : ils s'y recentrent et s'y verrouillent.
    Les feuilles et les branches du plan sont mises de cote pendant le jeu.

PEU DE TEXTE : une MAIN FANTOME, a demi transparente, montre UNE FOIS
chaque geste, et ce qu'il reste a faire se voit SUR L'OBJET MEME : la couche
a retirer de la pierre, les traits a couper du brin (voir
assemblage.dessine_travail).
"""
import math

from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle

from src.widgets.sol_de_craft import dessine_objet, cadre_image, TAILLE_OBJET
from src.widgets.assemblage import (decalage_morceau, vue_inverse, ZOOM,
                                    ALPHA_EMPLACEMENT)

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
# Au debut du mini-jeu, les deux pierres sont posees a cette distance (en
# tailles d'objet) de part et d'autre du milieu du plan.
ECART_PIERRES = 0.9

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

    def __init__(self, couche, mains, taille_objet, alpha=None):
        self.couche = couche
        self.mains = mains
        self.taille_objet = taille_objet
        self.alpha = FANTOME_ALPHA if alpha is None else alpha
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
        alpha = self.alpha * min(1.0, p / 0.15, (1.0 - p) / 0.15)
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
                 mains=None, recette=None):
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
        self._ecarte()
        self._annonce("prendre")
        self._montre_prendre()

    def _ecarte(self):
        """Les deux pierres de part et d'autre du milieu du plan : chaque
        main ne prend que de son cote de l'ecran, et la disposition qui a
        choisi l'objet (cote a cote, l'une sur l'autre) les laissait parfois
        du meme cote."""
        asm = self.asm
        pierres = sorted((o for o in asm.objets if o["nom"] == "Pierre"),
                         key=lambda o: (asm.a_l_ecran(o)[0],
                                        -asm.a_l_ecran(o)[1]))
        if len(pierres) != 2:
            return
        mx, my = asm.centre_du_plan()
        t = asm.case_objet() * 3
        for sens, o in zip((-1, 1), pierres):
            asm.place_a_l_ecran(o, *asm.sur_grille(
                mx + sens * ECART_PIERRES * t, my))

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
                 mains=None, recette=None):
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
PRISE_PLACE = 0.65
# LA RESERVE : les huit pierres, au debut, en deux colonnes de quatre au bord
# gauche de l'ecran (parts de la largeur et de la hauteur, et ecart entre
# deux pierres en tailles d'objet).
RESERVE_X = 0.06
RESERVE_Y = 0.74
PAS_RESERVE = 0.80
DUREE_RANGER = 1.6
PIERRE = "Pierre"


class MiniJeuFeu(object):
    """Poser huit pierres en cercle."""

    def __init__(self, assemblage, reussi, consigne, couche=None,
                 mains=None, recette=None):
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
        # TOUTES LES PIERRES A GAUCHE de l'ecran, loin du cercle.
        t = self._taille()
        pierres = [o for o in asm.objets if o["nom"] == PIERRE]
        for n, o in enumerate(pierres):
            col, rang = n // 4, n % 4
            asm.place_a_l_ecran(o, asm.x + RESERVE_X * asm.width
                                + col * PAS_RESERVE * t,
                                asm.y + RESERVE_Y * asm.height
                                - rang * PAS_RESERVE * t)
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
        for o in asm.objets:
            o.pop("verrou", None)
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
                # Lachee sur une place libre ou un peu a cote : elle se
                # recentre dessus, et s'y VERROUILLE.
                o["verrou"] = True
                self.asm.place_a_l_ecran(o, *self.places[k])
                prises.add(k)
        self._annonce()
        if len(prises) >= PLACES_FEU:
            self.fini = True
            self.reussi()


# LA CORDE : trois brins, croises chacun CROISEMENTS_PAR_BRIN fois. Les trois
# places sont cote a cote (ECART_BRINS entre deux, en tailles d'objet), sous
# le milieu du plan (BAS_BRINS) ; le noeud est au-dessus (HAUT_NOEUD), et la
# tresse en descend d'un PAS_TRESSE par croisement. Un brin lache a moins de
# PRISE_MILIEU de la place du milieu y passe.
FIBRE = "Fibre_Vegetale"
BRINS_CORDE = 3
CROISEMENTS_PAR_BRIN = 5
ECART_BRINS = 1.30
BAS_BRINS = -0.40
HAUT_NOEUD = 1.20
PAS_TRESSE = 0.07
LARGE_TRESSE = 0.17
EPAIS_BRIN = 0.06
# UN CROISEMENT : le brin est lache AU-DELA DU MILIEU, vers l'autre bord --
# a moins de PRISE_CROISE (tailles d'objet) du point a mi-chemin entre le
# brin du milieu et celui de l'autre bord.
# Et il doit avoir DEPASSE le brin du milieu d'au moins cette part de
# l'ecart entre deux brins : lache dessus, il ne croise pas.
PRISE_CROISE = 0.45
DEPASSE = 0.25
# La main fantome, bien visible, montre le geste ; tant que le premier
# croisement n'est pas fait, elle le remontre apres REMONTRE secondes sans
# rien tenir.
ALPHA_CORDE = 0.80
DUREE_TRESSER = 2.4
REMONTRE = 2.5
# Une teinte par brin, pour suivre chacun dans la tresse.
TEINTES_BRINS = ((0.86, 0.76, 0.50), (0.70, 0.60, 0.34), (0.95, 0.86, 0.62))
OMBRE_BRIN = (0.22, 0.16, 0.08, 0.85)


class MiniJeuCorde(object):
    """Tresser trois fibres vegetales en corde."""

    def __init__(self, assemblage, reussi, consigne, couche=None,
                 mains=None, recette=None):
        self.asm = assemblage
        self.reussi = reussi
        self.consigne = consigne
        self.couche = couche
        self.mains = mains
        self.fantome = Fantome(couche, mains,
                               lambda: assemblage.case_objet() * 3,
                               alpha=ALPHA_CORDE) \
            if couche is not None and mains is not None else None
        self._attente = 0.0
        # Les brins de gauche a droite : ordre[0] a gauche, ordre[1] au
        # milieu, ordre[2] a droite.
        brins = [o for o in assemblage.objets if o["nom"] == FIBRE]
        self.ordre = sorted(brins, key=lambda o: assemblage.a_l_ecran(o)[0])
        # Chaque croisement : (numero du brin, bord d'ou il vient, 0 ou 2).
        self.croisements = []
        self._tenues = [None, None]
        self._dit = None
        self.fini = False

    def total(self):
        return BRINS_CORDE * CROISEMENTS_PAR_BRIN

    def _taille(self):
        return self.asm.case_objet() * 3

    def place(self, k):
        """La place `k` (0 gauche, 1 milieu, 2 droite), a l'ecran."""
        mx, my = self.asm.centre_du_plan()
        t = self._taille()
        return mx + (k - 1) * ECART_BRINS * t, my + BAS_BRINS * t

    def cible(self, k):
        """Ou lacher le brin du bord `k` pour qu'il croise : entre le brin
        du milieu et celui de l'autre bord, a l'ecran."""
        (ax, ay), (bx, by) = self.place(1), self.place(2 - k)
        return (ax + bx) / 2.0, (ay + by) / 2.0

    def dernier_bord(self):
        return self.croisements[-1][1] if self.croisements else None

    def bord_attendu(self):
        """Le bord dont on doit croiser le brin (None : l'un ou l'autre)."""
        d = self.dernier_bord()
        return None if d is None else 2 - d

    # -- cycle ----------------------------------------------------------- #
    def demarre(self):
        asm = self.asm
        asm.aimant_permis = False
        asm.liens = []
        asm.sur_pas = self._pas
        asm.dessin_jeu = self._dessine
        for n, o in enumerate(self.ordre):
            o["brin"] = n
        self._range()
        self._annonce()
        self._montre()

    def arrete(self):
        asm = self.asm
        if asm.sur_pas == self._pas:
            asm.sur_pas = None
        if asm.dessin_jeu == self._dessine:
            asm.dessin_jeu = None
        asm.aimant_permis = True
        if self.fantome is not None:
            self.fantome.arrete()
        for o in self.ordre:
            o.pop("brin", None)
            o.pop("verrou", None)
        asm._redessine()

    def _range(self):
        """Chaque brin a sa place ; celui du milieu ne se prend pas."""
        portes = [self.asm.porte(i) for i in (0, 1)]
        for k, o in enumerate(self.ordre):
            if k == 1:
                o["verrou"] = True
            else:
                o.pop("verrou", None)
            if not any(o is p for p in portes):
                self.asm.place_a_l_ecran(o, *self.place(k))
        self.asm._redessine()

    # -- la main fantome et les consignes --------------------------------- #
    def _montre(self, bord=None):
        """Une main fantome porte un brin du bord jusqu'au milieu."""
        if self.fantome is None or self.mains is None \
                or len(self.ordre) < BRINS_CORDE:
            return
        if bord is None:
            bord = self.bord_attendu()
        if bord is None:
            bord = 0
        o = self.ordre[bord]
        main = 0 if bord == 0 else 1
        depart = self.place(bord)
        cible = self.cible(bord)
        self.fantome.joue(main, [self.mains.paume(main), depart, depart,
                                 cible, cible], DUREE_TRESSER, objet=o)

    def _annonce(self):
        n = len(self.croisements)
        bord = self.bord_attendu()
        if bord is None:
            texte = "Passe un brin du bord au-dela du milieu (%d/%d)" % (
                n, self.total())
        else:
            texte = "Passe le brin de %s au-dela du milieu (%d/%d)" % (
                "gauche" if bord == 0 else "droite", n, self.total())
        if texte != self._dit:
            self._dit = texte
            self.consigne(texte)

    # -- le dessin de la tresse ------------------------------------------- #
    def _bout_tresse(self):
        """(x, y) du bas de la tresse, a l'ecran : la ou les brins se
        separent."""
        mx, my = self.asm.centre_du_plan()
        t = self._taille()
        return mx, my + (HAUT_NOEUD - PAS_TRESSE * len(self.croisements)) * t

    def _dessine(self):
        """La tresse et les brins libres. Dessines DANS la vue d'assemblage,
        que la loupe grossit : chaque point de l'ecran y est ramene (vue
        inverse), et chaque longueur divisee par le grossissement. Sans
        cela, la tresse etait grossie deux fois et sortait par le haut."""
        if len(self.ordre) < BRINS_CORDE:
            return
        asm = self.asm

        def ici(x, y):
            return vue_inverse(1.0, x, y, asm.width, asm.height,
                               asm.x, asm.y)

        t = self._taille()
        mx, my = asm.centre_du_plan()
        haut = my + HAUT_NOEUD * t
        w = LARGE_TRESSE * t
        epais = max(2.0, EPAIS_BRIN * t / ZOOM)
        # Ou lacher le brin pour croiser : un rond de craie.
        bords = [self.bord_attendu()] if self.bord_attendu() is not None \
            else [0, 2]
        portes = [asm.porte(i) for i in (0, 1)]
        for k in bords:
            if any(self.ordre[k] is p for p in portes) or \
                    not self.croisements:
                x, y = ici(*self.cible(k))
                Color(1.0, 1.0, 0.95, 0.55)
                Line(circle=(x, y, PRISE_CROISE * t * 0.6 / ZOOM),
                     width=max(1.2, epais * 0.35))
        # Les brins LIBRES, du bas de la tresse a chaque brin (ou a la main
        # qui le tient).
        bx, by = self._bout_tresse()
        for k, o in enumerate(self.ordre):
            x, y = self.place(k)
            for i in (0, 1):
                if portes[i] is o:
                    x, y = asm.ou_est_porte(i)
            pts = list(ici(bx + (k - 1) * w * 0.45, by)) + \
                list(ici(x, y + 0.20 * t))
            Color(*OMBRE_BRIN)
            Line(points=pts, width=epais * 1.3)
            Color(*TEINTES_BRINS[o.get("brin", k) % len(TEINTES_BRINS)])
            Line(points=pts, width=epais)
        # LA TRESSE : un chevron par croisement, du noeud vers le bas, le
        # dernier par-dessus.
        for j, (brin, bord) in enumerate(self.croisements):
            s = -1.0 if bord == 0 else 1.0
            y0 = haut - j * PAS_TRESSE * t
            y1 = y0 - PAS_TRESSE * t * 1.9
            pts = list(ici(mx + s * w, y0)) + list(ici(mx - s * w * 0.45, y1))
            Color(*OMBRE_BRIN)
            Line(points=pts, width=epais * 1.6)
            Color(*TEINTES_BRINS[brin % len(TEINTES_BRINS)])
            Line(points=pts, width=epais * 1.2)
        # Le noeud, en haut.
        x, y = ici(mx, haut + 0.03 * t)
        Color(*OMBRE_BRIN)
        Line(circle=(x, y, w * 0.6 / ZOOM), width=epais)

    # -- chaque pas de la vue ---------------------------------------------- #
    def _pas(self, dt):
        if self.fini or len(self.ordre) < BRINS_CORDE:
            return
        tenues = [self.asm.porte(i) for i in (0, 1)]
        lachees = [o for o in self._tenues if o is not None
                   and not any(o is t for t in tenues)]
        self._tenues = tenues
        if any(o is not None for o in tenues):
            self.asm._redessine()       # le brin tenu suit la main
            self._attente = 0.0
        elif not self.croisements and self.fantome is not None \
                and not self.fantome.en_cours():
            self._attente += dt
            if self._attente >= REMONTRE:
                self._attente = 0.0
                self._montre()
        for o in lachees:
            self.lache(o)
            if self.fini:
                return
        self._annonce()

    def lache(self, o):
        """Le brin `o` vient d'etre lache : au milieu, depuis le bon bord,
        il croise ; sinon il retourne a sa place."""
        if not any(o is b for b in self.ordre):
            return
        k = next(n for n, b in enumerate(self.ordre) if b is o)
        ox, oy = self.asm.a_l_ecran(o)
        attendu = self.bord_attendu()
        t = self._taille()
        cote = 1.0 if k == 0 else -1.0
        passe = cote * (ox - self.place(1)[0]) >= DEPASSE * ECART_BRINS * t
        if k != 1 and passe and math.hypot(*(a - b for a, b in zip(
                (ox, oy), self.cible(k)))) <= PRISE_CROISE * t:
            if attendu is not None and k != attendu:
                # Le meme bord deux fois : ca ne tresse rien.
                self._range()
                if self.fantome is not None and not self.fantome.en_cours():
                    self._montre(attendu)
                return
            self.croise(k)
            return
        self._range()

    def croise(self, k):
        """Le brin du bord `k` passe par-dessus celui du milieu."""
        o = self.ordre[k]
        self.ordre[k], self.ordre[1] = self.ordre[1], o
        self.croisements.append((o.get("brin", 0), k))
        self._range()
        self._annonce()
        if len(self.croisements) >= self.total():
            self.fini = True
            self.reussi()

    def croisements_de(self, brin):
        return sum(1 for b, _k in self.croisements if b == brin)


# L'EQUIPEMENT EN FEUILLE. Les cinq feuilles de chaque tiers, en tailles
# d'objet autour du milieu du plan (releve de HAUSSE_FEUILLES), dans l'ordre
# ou la main fantome les montre : la forme du morceau qu'on coud.
#
# QUINZE FORMES TOUTES DIFFERENTES : chaque tiers de chaque piece a la
# sienne, on ne coud jamais deux fois le meme dessin.
# Casque : un bord qui monte, le sommet en dome, l'autre bord.
_MONTE = ((-1.0, -0.8), (-0.75, -0.3), (-0.45, 0.15), (-0.05, 0.5),
          (0.45, 0.7))
_DOME = ((-1.1, 0.35), (-0.55, 0.6), (0, 0.7), (0.55, 0.6), (1.1, 0.35))
_DESCEND_CASQUE = ((-0.5, 0.8), (-0.05, 0.6), (0.35, 0.25), (0.6, -0.25),
                   (0.75, -0.8))
# Veste : une manche droite en diagonale, le corps en V (l'encolure), l'autre
# manche coudee.
_MANCHE_G = ((0.8, 0.8), (0.4, 0.4), (0, 0), (-0.4, -0.4), (-0.8, -0.8))
_ENCOLURE = ((-0.8, 0.8), (-0.4, 0.35), (0, -0.1), (0.4, 0.35), (0.8, 0.8))
_MANCHE_D = ((-0.9, 0.7), (-0.45, 0.45), (0, 0.2), (0.35, -0.25),
             (0.6, -0.8))
# Pantalon : deux jambes qui s'evasent chacune de son cote, la ceinture droite.
_JAMBE_G = ((0.2, 0.9), (0.05, 0.45), (-0.1, 0), (-0.25, -0.45),
            (-0.4, -0.9))
_CEINTURE = ((-1.1, 0), (-0.55, 0), (0, 0), (0.55, 0), (1.1, 0))
_JAMBE_D = ((-0.3, 0.9), (-0.25, 0.45), (-0.1, 0), (0.15, -0.45),
            (0.45, -0.9))
# Gant : le pouce en crochet, la paume en pentagone, les doigts en dents.
_POUCE = ((0.6, -0.8), (0.2, -0.6), (-0.1, -0.25), (-0.2, 0.2), (-0.1, 0.65))
_PAUME = ((0, 0.7), (0.6, 0.25), (0.4, -0.5), (-0.4, -0.5), (-0.6, 0.25))
_DOIGTS = ((-1.0, -0.4), (-0.5, 0.5), (0, -0.4), (0.5, 0.5), (1.0, -0.4))
# Soulier : la tige en equerre, la semelle en sourire, la pointe qui file.
_TIGE = ((-0.6, 0.9), (-0.6, 0.45), (-0.6, 0), (-0.15, -0.15), (0.3, -0.15))
_SEMELLE = ((-1.1, 0.25), (-0.55, -0.1), (0, -0.25), (0.55, -0.1),
            (1.1, 0.25))
_POINTE = ((-1.1, 0.25), (-0.55, 0.15), (0, 0), (0.55, -0.15), (1.1, -0.3))
# Sac : une bretelle en arc, la poche en U, le rabat qui descend en marche.
_BRETELLE = ((-0.6, -0.8), (-0.75, -0.25), (-0.6, 0.3), (-0.2, 0.7),
             (0.3, 0.8))
_POCHE = ((-0.6, 0.6), (-0.6, 0.0), (0.0, -0.45), (0.6, 0.0), (0.6, 0.6))
_RABAT = ((-1.0, 0.6), (-0.5, 0.6), (0.0, 0.15), (0.5, -0.3), (1.0, -0.3))
PATRONS_FEUILLE = {
    "Casque_De_Feuille": (_MONTE, _DOME, _DESCEND_CASQUE),  # bord, sommet, bord
    "Veste_De_Feuille": (_MANCHE_G, _ENCOLURE, _MANCHE_D),  # manche, corps, manche
    "Pantalon_De_Feuille": (_JAMBE_G, _CEINTURE, _JAMBE_D),  # jambe, ceinture, jambe
    "Gant_De_Feuille": (_POUCE, _PAUME, _DOIGTS),          # pouce, paume, doigts
    "Soulier_De_Feuille": (_TIGE, _SEMELLE, _POINTE),      # tige, pied, pointe
    "Sac_De_Feuille": (_BRETELLE, _POCHE, _RABAT),         # bretelle, poche, rabat
}
TIERS = 3
HAUSSE_FEUILLES = 0.05
PRISE_TROU = 0.20           # en taille d'objet : la lame ou la corde y passe
PRISE_MORCEAU = 0.50
CORDE = "Corde"
DUREE_PERCER = 1.6
DUREE_ENFILER = 2.2
# Ou attendent le couteau et la corde (a droite), et les tiers finis (a
# gauche), en parts de l'ecran.
PLACE_COUTEAU = (0.80, 0.62)
PLACE_CORDE = (0.80, 0.36)
PLACE_TIERS = (0.12, 0.78, -0.25)     # x, y du premier, pas vertical


class MiniJeuFeuille(object):
    """Coudre une piece d'equipement en feuille, tiers par tiers."""

    def __init__(self, assemblage, reussi, consigne, couche=None,
                 mains=None, recette=None):
        self.asm = assemblage
        self.reussi = reussi
        self.consigne = consigne
        self.couche = couche
        self.mains = mains
        self.piece = (recette or {}).get("result") or "Veste_De_Feuille"
        self.patrons = PATRONS_FEUILLE.get(self.piece,
                                           PATRONS_FEUILLE["Veste_De_Feuille"])
        self.fantome = Fantome(couche, mains,
                               lambda: assemblage.case_objet() * 3) \
            if couche is not None and mains is not None else None
        self.tour = 0
        self.phase = None           # "percer", "enfiler", "assembler"
        self.feuilles = []          # les cinq du tour, objets de la vue
        self.enfilees = []
        self.tiers = []             # les morceaux finis
        self._ajoutes = []          # tout ce que le jeu a mis dans la vue
        self._caches = []
        self._tenus = [None, None]
        self._vus = set()
        self._dit = None
        self.fini = False

    def _taille(self):
        return self.asm.case_objet() * 3

    def _milieu(self):
        mx, my = self.asm.centre_du_plan()
        return mx, my + HAUSSE_FEUILLES * self.asm.height

    def _ajoute(self, nom, px, py, **extra):
        o = {"nom": nom, "x": 0.0, "y": 0.0, "x0": 0.0, "y0": 0.0,
             "xa": 0.0, "ya": 0.0, "coupe": [0.0, 0.0]}
        o.update(extra)
        self.asm.objets.append(o)
        self.asm.place_a_l_ecran(o, px, py)
        o["x0"], o["y0"] = o["x"], o["y"]
        self._ajoutes.append(o)
        return o

    def _premier(self, nom):
        return next((o for o in self.asm.objets if o["nom"] == nom
                     and not o.get("cache")
                     and not any(o is a for a in self._ajoutes)), None)

    def _tenu(self, nom):
        """La main qui tient un `nom` (droite d'abord), ou None."""
        for i in (1, 0):
            o = self.asm.porte(i)
            if o is not None and o["nom"] == nom:
                return i
        return None

    # -- cycle ----------------------------------------------------------- #
    def demarre(self):
        asm = self.asm
        asm.aimant_permis = False
        asm.liens = []
        asm.sur_pas = self._pas
        # Les feuilles et les branches du plan, mises de cote : ce sont les
        # feuilles du jeu qu'on perce et qu'on coud.
        for o in asm.objets:
            if o["nom"] in ("Feuille", "Small_Stick"):
                o["cache"] = True
                self._caches.append(o)
        w, h = asm.width, asm.height
        for nom, (fx, fy) in ((COUTEAU, PLACE_COUTEAU), (CORDE, PLACE_CORDE)):
            o = self._premier(nom)
            if o is not None:
                asm.place_a_l_ecran(o, asm.x + fx * w, asm.y + fy * h)
        self._nouveau_tour()

    def arrete(self):
        asm = self.asm
        if asm.sur_pas == self._pas:
            asm.sur_pas = None
        asm.aimant_permis = True
        if self.fantome is not None:
            self.fantome.arrete()
        for i in (0, 1):
            if any(asm._porte[i] is a for a in self._ajoutes):
                asm._porte[i] = None
                asm._aimante[i] = None
        asm.objets = [o for o in asm.objets
                      if not any(o is a for a in self._ajoutes)]
        for o in self._caches:
            o.pop("cache", None)
        self._ajoutes, self._caches = [], []
        asm.emplacements = []
        asm.fils = []
        asm._redessine()

    # -- les tours ------------------------------------------------------- #
    def _nouveau_tour(self):
        mx, my = self._milieu()
        t = self._taille()
        self.feuilles = [self._ajoute("Feuille", mx + dx * t, my + dy * t,
                                      verrou=True, trou=False)
                         for dx, dy in self.patrons[self.tour]]
        self.enfilees = []
        self.asm.fils = []
        self.phase = "percer"
        self.asm._redessine()
        self._annonce()
        self._montre("percer")

    def _tiers_fini(self):
        """Les cinq feuilles cousues deviennent le tiers de la piece : il va
        attendre a gauche, et le tour suivant commence."""
        asm = self.asm
        asm.objets = [o for o in asm.objets
                      if not any(o is f for f in self.feuilles)]
        self._ajoutes = [o for o in self._ajoutes
                         if not any(o is f for f in self.feuilles)]
        k = self.tour
        x, y, pas = PLACE_TIERS
        # Le tiers est l'image ENTIERE rognee : son milieu visible est
        # decale du centre de l'objet. On le range par ce qu'on en voit.
        decale = (k - 1) * self._largeur_piece() / TIERS
        morceau = self._ajoute(self.piece, asm.x + x * asm.width - decale,
                               asm.y + (y + k * pas) * asm.height,
                               verrou=True, tiers=k,
                               coupe=[k / float(TIERS),
                                      1.0 - (k + 1) / float(TIERS)])
        self.tiers.append(morceau)
        self.feuilles, self.enfilees = [], []
        asm.fils = []
        self.tour += 1
        if self.tour < TIERS:
            self._nouveau_tour()
            return
        # LES TROIS TIERS : on les pose sur la piece en fantome.
        self.phase = "assembler"
        mx, my = self._milieu()
        fx, fy = vue_inverse(1.0, mx, my, asm.width, asm.height,
                             asm.x, asm.y)
        asm.emplacements = [(self.piece, (fx - asm.x) / asm.width,
                             (fy - asm.y) / asm.height, False)]
        for m in self.tiers:
            m.pop("verrou", None)
        asm._redessine()
        self._annonce()
        self._montre("assembler")

    def _largeur_piece(self):
        cadre = cadre_image(self.piece, self._taille())
        return cadre[0] if cadre else self._taille()

    # -- ce que montre la main fantome ------------------------------------ #
    def _montre(self, quoi):
        if quoi in self._vus or self.fantome is None or self.mains is None:
            return
        self._vus.add(quoi)
        asm = self.asm
        if quoi in ("percer", "enfiler"):
            nom = COUTEAU if quoi == "percer" else CORDE
            o = self._premier(nom)
            if o is None or not self.feuilles:
                return
            depart = asm.a_l_ecran(o)
            trous = [asm.a_l_ecran(f) for f in self.feuilles[:3]]
            self.fantome.joue(1, [self.mains.paume(1), depart] + trous,
                              DUREE_PERCER if quoi == "percer"
                              else DUREE_ENFILER, objet=o)
        elif quoi == "assembler" and self.tiers:
            m = self.tiers[0]
            depart = asm.a_l_ecran(m)
            self.fantome.joue(0, [self.mains.paume(0), depart, depart,
                                  self._milieu()], DUREE_RANGER, objet=m)

    def _annonce(self):
        if self.phase == "percer":
            n = sum(1 for f in self.feuilles if f.get("trou"))
            texte = ("Perce les feuilles au couteau (%d/5) - morceau %d/%d"
                     % (n, self.tour + 1, TIERS))
        elif self.phase == "enfiler":
            texte = ("Passe la corde dans les trous (%d/5) - morceau %d/%d"
                     % (len(self.enfilees), self.tour + 1, TIERS))
        else:
            n = sum(1 for m in self.tiers if m.get("verrou"))
            texte = "Assemble les morceaux (%d/%d)" % (n, TIERS)
        if texte != self._dit:
            self._dit = texte
            self.consigne(texte)

    # -- chaque pas de la vue ---------------------------------------------- #
    def _range_outils(self):
        """L'outil qui ne sert pas a l'etape en cours, lache, retourne a sa
        place a droite : on le retrouve toujours au meme endroit."""
        asm = self.asm
        tenus = [asm.porte(i) for i in (0, 1)]
        for nom, (fx, fy), etape in ((COUTEAU, PLACE_COUTEAU, "percer"),
                                     (CORDE, PLACE_CORDE, "enfiler")):
            if self.phase == etape:
                continue
            o = self._premier(nom)
            if o is None or any(o is t for t in tenus):
                continue
            px, py = asm.x + fx * asm.width, asm.y + fy * asm.height
            ox, oy = asm.a_l_ecran(o)
            if math.hypot(ox - px, oy - py) > 1.0:
                asm.place_a_l_ecran(o, px, py)

    def _pas(self, dt):
        if self.fini:
            return
        asm = self.asm
        prise = PRISE_TROU * self._taille()
        self._range_outils()
        if self.phase == "percer":
            main = self._tenu(COUTEAU)
            if main is not None:
                lx, ly = asm.ou_est_porte(main)
                for f in self.feuilles:
                    fx, fy = asm.a_l_ecran(f)
                    if not f["trou"] and math.hypot(lx - fx,
                                                    ly - fy) <= prise:
                        f["trou"] = True
                        asm._redessine()
                if all(f["trou"] for f in self.feuilles):
                    self.phase = "enfiler"
                    self._montre("enfiler")
        elif self.phase == "enfiler":
            main = self._tenu(CORDE)
            if main is not None:
                cx, cy = asm.ou_est_porte(main)
                for f in self.feuilles:
                    if any(f is e for e in self.enfilees):
                        continue
                    fx, fy = asm.a_l_ecran(f)
                    if math.hypot(cx - fx, cy - fy) <= prise:
                        self.enfilees.append(f)
                        asm.fils = [(e["x"], e["y"]) for e in self.enfilees]
                        asm._redessine()
                if len(self.enfilees) >= len(self.feuilles):
                    self._tiers_fini()
        elif self.phase == "assembler":
            tenus = [asm.porte(i) for i in (0, 1)]
            lachees = [o for o in self._tenus if o is not None
                       and not any(o is t for t in tenus)]
            self._tenus = tenus
            mx, my = self._milieu()
            for m in lachees:
                if not any(m is t for t in self.tiers) or m.get("verrou"):
                    continue
                ox, oy = asm.a_l_ecran(m)
                if math.hypot(ox - mx, oy - my) <= PRISE_MORCEAU \
                        * self._taille():
                    # Sur sa place, ou un peu a cote : il s'y recentre et
                    # s'y verrouille.
                    m["verrou"] = True
                    asm.place_a_l_ecran(m, mx, my)
            if self.tiers and all(m.get("verrou") for m in self.tiers):
                self.fini = True
                self._annonce()
                self.reussi()
                return
        self._annonce()


# LA HACHE, disposee comme sur son image (assets/items/Hache.png). Le manche
# est un FAISCEAU de quatre petits batons cote a cote, dresse a ANGLE_MANCHE
# degres ; l'image d'un baton est en biais a ANGLE_BATON degres : un baton
# range sur le manche est donc TOURNE de la difference. Les batons s'y
# collent de PAS_FAISCEAU (tailles d'objet) en PAS_FAISCEAU, en travers.
# Mesures sur l'image, en tailles d'objet depuis le milieu du manche (releve
# de HAUSSE_HACHE, part de la hauteur), le long du manche puis en travers :
# - le BAS du manche, ou la corde s'enroule, a BAS_MANCHE ;
# - la PIERRE, couchee en travers du haut du manche, en (A_PIERRE,
#   B_PIERRE), a ECHELLE_PIERRE de sa taille : moitie moins longue que le
#   manche ;
# - le COLLIER de corde, juste sous la pierre, a COLLIER ;
# - le NOEUD (la ou la corde se croise en X sur la pierre), a NOEUD_X.
ANGLE_MANCHE = 61.8
ANGLE_BATON = 36.5
AXE_MANCHE = (math.cos(math.radians(ANGLE_MANCHE)),
              math.sin(math.radians(ANGLE_MANCHE)))
BATONS_MANCHE = 4
PAS_FAISCEAU = 0.075
HAUSSE_HACHE = 0.03
BAS_MANCHE = -0.66
A_PIERRE = 0.61
B_PIERRE = -0.07
ECHELLE_PIERRE = 0.80
COLLIER = 0.41
NOEUD_X = 0.62
# Un baton lache a moins de PRISE_BATON (tailles d'objet) d'une place libre
# du faisceau s'y range et s'y VERROUILLE ; la pierre, a moins de
# PRISE_PIERRE de sa place.
PRISE_BATON = 0.35
PRISE_PIERRE = 0.45
# LA CORDE AUTOUR DU BAS : la main qui tient la corde passe d'un cote du
# faisceau a l'autre (au-dela de LARGE_MANCHE, de part et d'autre de son
# axe), a moins de ZONE_BAS du bas du manche le long de l'axe : un tour.
# TOURS_BAS tours, dessines serres (ECART_TOURS) en travers du faisceau, sur
# DEMI_TOUR de chaque cote.
TOURS_BAS = 4
LARGE_MANCHE = 0.22
ZONE_BAS = 0.24
ECART_TOURS = 0.045
DEMI_TOUR = 0.15
# LA CORDE EN X sur la pierre : la main passe d'un coin du noeud (a
# COIN_X de son milieu au moins, le long du manche ET en travers) au coin
# OPPOSE : un trait de la croix. Les deux diagonales en alternance,
# TRAITS_X traits (deux X). La croix suit le MANCHE, qui est en biais : ses
# deux bras le croisent chacun a 45 degres. Comptee sur les axes de
# l'ecran, l'un des bras courait presque le long des batons -- un "+".
# Comme sur l'image, chaque trait fait aussi un tour du COLLIER, sous la
# pierre.
TRAITS_X = 4
COIN_X = 0.12
PORTEE_X = 0.50
DEMI_X = 0.11                           # la croix dessinee
# Ou attendent les batons (a gauche, en deux colonnes) et la pierre et la
# corde (a droite), en parts de l'ecran : chaque main prend de son cote.
PLACES_BATONS = ((0.08, 0.66), (0.18, 0.66), (0.08, 0.40), (0.18, 0.40))
PLACE_PIERRE = (0.82, 0.64)
PLACE_CORDE_HACHE = (0.82, 0.38)
DUREE_ENROULER = 2.6
DUREE_CROISER = 2.8
ALPHA_HACHE = 0.65
PIERRE_COUPANTE = "Pierre_Coupante"
BATON = "Small_Stick"


class MiniJeuHache(object):
    """Emmancher une pierre coupante sur un faisceau de batons, a la
    corde."""

    PHASES = ("batons", "bas", "pierre", "croix")

    def __init__(self, assemblage, reussi, consigne, couche=None,
                 mains=None, recette=None):
        self.asm = assemblage
        self.reussi = reussi
        self.consigne = consigne
        self.couche = couche
        self.mains = mains
        self.fantome = Fantome(couche, mains,
                               lambda: assemblage.case_objet() * 3,
                               alpha=ALPHA_HACHE) \
            if couche is not None and mains is not None else None
        objets = assemblage.objets
        self.batons = [o for o in objets if o["nom"] == BATON]
        self.pierre = next((o for o in objets
                            if o["nom"] == PIERRE_COUPANTE), None)
        self.corde = next((o for o in objets if o["nom"] == CORDE), None)
        self.phase = None
        self.fantomes = []          # les places montrees en fantome
        self.places = []            # les places du faisceau, a l'ecran
        self.ranges = {}            # place -> baton
        self.tours = 0              # autour du bas
        self.traits = []            # "\\" ou "/", sur la pierre
        self._cote = None           # de quel cote du manche est la corde
        self._coin = None           # dans quel coin du noeud elle est
        self._tenues = [None, None]
        self._vus = set()
        self._dit = None
        self.fini = False

    def _taille(self):
        return self.asm.case_objet() * 3

    # -- la geometrie du manche (a l'ecran) ------------------------------- #
    def _axes(self):
        """(u, v) : l'axe du manche, et sa perpendiculaire (vers le haut
        gauche)."""
        ux, uy = AXE_MANCHE
        n = math.hypot(ux, uy)
        ux, uy = ux / n, uy / n
        return (ux, uy), (-uy, ux)

    def centre(self):
        mx, my = self.asm.centre_du_plan()
        return mx, my + HAUSSE_HACHE * self.asm.height

    def _le_long(self, a, b=0.0):
        """Le point a `a` tailles d'objet le long de l'axe du manche, et `b`
        en travers, depuis son milieu."""
        (ux, uy), (vx, vy) = self._axes()
        cx, cy = self.centre()
        t = self._taille()
        return cx + (a * ux + b * vx) * t, cy + (a * uy + b * vy) * t

    def bas(self):
        return self._le_long(BAS_MANCHE)

    def place_pierre(self):
        return self._le_long(A_PIERRE, B_PIERRE)

    def noeud(self):
        return self._le_long(NOEUD_X)

    def _maison(self, o):
        """La place d'attente de `o`, a l'ecran."""
        asm = self.asm
        if o is self.pierre:
            fx, fy = PLACE_PIERRE
        elif o is self.corde:
            fx, fy = PLACE_CORDE_HACHE
        else:
            k = next((n for n, b in enumerate(self.batons) if b is o), 0)
            fx, fy = PLACES_BATONS[k % len(PLACES_BATONS)]
        return asm.x + fx * asm.width, asm.y + fy * asm.height

    def _ramene(self, o):
        if o is not None and not o.get("verrou"):
            self.asm.place_a_l_ecran(o, *self._maison(o))

    # -- cycle ----------------------------------------------------------- #
    def demarre(self):
        asm = self.asm
        asm.aimant_permis = False
        asm.liens = []
        asm.sur_pas = self._pas
        asm.dessin_jeu = self._dessine_places
        asm.dessin_dessus = self._dessine
        n = BATONS_MANCHE
        self.places = [self._le_long(0.0, (k - (n - 1) / 2.0) * PAS_FAISCEAU)
                       for k in range(n)]
        for o in self.batons + [self.pierre, self.corde]:
            self._ramene(o)
        self._entre("batons")

    def arrete(self):
        asm = self.asm
        if asm.sur_pas == self._pas:
            asm.sur_pas = None
        if asm.dessin_dessus == self._dessine:
            asm.dessin_dessus = None
        if asm.dessin_jeu == self._dessine_places:
            asm.dessin_jeu = None
        asm.aimant_permis = True
        asm.emplacements = []
        if self.fantome is not None:
            self.fantome.arrete()
        for o in asm.objets:
            for cle in ("verrou", "angle", "echelle"):
                o.pop(cle, None)
        asm._redessine()

    def _entre(self, phase):
        self.phase = phase
        self._cote = self._coin = None
        self._places_montrees()
        self.asm._redessine()
        self._annonce()
        self._montre()

    def _places_montrees(self):
        """Les places qui attendent, en fantome (voir _dessine_places) :
        celles des batons libres, couches le long du manche, puis celle de
        la pierre, a sa taille sur le manche."""
        if self.phase == "batons":
            self.fantomes = [(BATON, p, ANGLE_MANCHE - ANGLE_BATON, 1.0)
                             for k, p in enumerate(self.places)
                             if k not in self.ranges]
        elif self.phase == "pierre":
            self.fantomes = [(PIERRE_COUPANTE, self.place_pierre(), 0.0,
                              ECHELLE_PIERRE)]
        else:
            self.fantomes = []
        self.asm.emplacements = []

    def _dessine_places(self):
        """Les places en fantome, SOUS les objets : tournees et a la taille
        ou les objets s'y poseront (les emplacements de la vue ne savent
        pas tourner)."""
        asm = self.asm
        cote = TAILLE_OBJET * asm.height
        for nom, (px, py), angle, echelle in self.fantomes:
            x, y = vue_inverse(1.0, px, py, asm.width, asm.height,
                               asm.x, asm.y)
            dessine_objet(nom, x, y, cote * echelle, ombre=False,
                          alpha=ALPHA_EMPLACEMENT, angle=angle)

    # -- la main fantome et les consignes --------------------------------- #
    def _montre(self):
        if self.phase in self._vus or self.fantome is None \
                or self.mains is None:
            return
        self._vus.add(self.phase)
        asm = self.asm
        t = self._taille()
        if self.phase == "batons":
            libres = [o for o in self.batons if not o.get("verrou")]
            k = next((k for k in range(len(self.places))
                      if k not in self.ranges), None)
            if not libres or k is None:
                return
            o = libres[0]
            depart = asm.a_l_ecran(o)
            self.fantome.joue(0, [self.mains.paume(0), depart, depart,
                                  self.places[k], self.places[k]],
                              DUREE_RANGER, objet=o)
        elif self.phase == "pierre" and self.pierre is not None:
            depart = asm.a_l_ecran(self.pierre)
            cible = self.place_pierre()
            self.fantome.joue(1, [self.mains.paume(1), depart, depart,
                                  cible, cible], DUREE_RANGER,
                              objet=self.pierre)
        elif self.phase in ("bas", "croix") and self.corde is not None:
            depart = asm.a_l_ecran(self.corde)
            if self.phase == "bas":
                pts = [self._le_long(BAS_MANCHE, s * (LARGE_MANCHE + 0.12))
                       for s in (1, -1, 1, -1)]
                duree = DUREE_ENROULER
            else:
                e = COIN_X + 0.10
                pts = [self._le_long(NOEUD_X - e, e),
                       self._le_long(NOEUD_X + e, -e),
                       self._le_long(NOEUD_X + e, e),
                       self._le_long(NOEUD_X - e, -e)]
                duree = DUREE_CROISER
            self.fantome.joue(1, [self.mains.paume(1), depart, depart] + pts,
                              duree, objet=self.corde)

    def _annonce(self):
        if self.phase == "batons":
            texte = "Colle les 4 batons cote a cote (%d/%d)" % (
                len(self.ranges), BATONS_MANCHE)
        elif self.phase == "bas":
            texte = "Enroule la corde autour du bas des batons (%d/%d)" % (
                self.tours, TOURS_BAS)
        elif self.phase == "pierre":
            texte = "Fixe la pierre en haut des batons"
        else:
            texte = "Croise la corde en X sur la pierre (%d/%d)" % (
                len(self.traits), TRAITS_X)
        if texte != self._dit:
            self._dit = texte
            self.consigne(texte)

    # -- le dessin de la corde, par-dessus les objets ---------------------- #
    def _dessine(self):
        asm = self.asm
        t = self._taille()

        def ici(x, y):
            return vue_inverse(1.0, x, y, asm.width, asm.height,
                               asm.x, asm.y)

        epais = max(1.5, 0.022 * t / ZOOM)
        traits = []
        # Les tours du bas, en travers du faisceau, cote a cote.
        for k in range(self.tours):
            a = BAS_MANCHE + (k - (TOURS_BAS - 1) / 2.0) * ECART_TOURS
            traits.append((self._le_long(a, DEMI_TOUR),
                           self._le_long(a, -DEMI_TOUR)))
        # Le collier sous la pierre : un tour par trait de la croix.
        for k in range(len(self.traits)):
            a = COLLIER + (k - (TRAITS_X - 1) / 2.0) * ECART_TOURS
            traits.append((self._le_long(a, DEMI_TOUR),
                           self._le_long(a, -DEMI_TOUR)))
        # La croix, sur le noeud du manche et de la pierre, a 45 degres du
        # manche. Le second X se pose a cote du premier, le long du manche :
        # chaque trait reussi ajoute de la corde a l'ecran.
        k = DEMI_X
        paires = (TRAITS_X + 1) // 2
        for j, sens in enumerate(self.traits):
            a = NOEUD_X + (j // 2 - (paires - 1) / 2.0) * 2 * ECART_TOURS
            if sens == "\\":
                traits.append((self._le_long(a - k, k),
                               self._le_long(a + k, -k)))
            else:
                traits.append((self._le_long(a + k, k),
                               self._le_long(a - k, -k)))
        # La corde qui pend du dernier tour jusqu'a la main qui la tient.
        main = self._main_corde()
        if main is not None and (self.tours or self.traits):
            depart = traits[-1][1]
            traits.append((depart, asm.ou_est_porte(main)))
        for (ax, ay), (bx, by) in traits:
            pts = list(ici(ax, ay)) + list(ici(bx, by))
            Color(*OMBRE_BRIN)
            Line(points=pts, width=epais * 1.4)
            Color(*TEINTES_BRINS[0])
            Line(points=pts, width=epais)

    # -- chaque pas de la vue ---------------------------------------------- #
    def _main_corde(self):
        for i in (1, 0):
            if self.corde is not None and self.asm.porte(i) is self.corde:
                return i
        return None

    def _pas(self, dt):
        if self.fini:
            return
        asm = self.asm
        tenus = [asm.porte(i) for i in (0, 1)]
        lachees = [o for o in self._tenues if o is not None
                   and not any(o is t for t in tenus)]
        self._tenues = tenus
        for o in lachees:
            self.lache(o)
            if self.fini:
                return
        main = self._main_corde()
        if main is not None:
            self.suit_corde(*asm.ou_est_porte(main))
            asm._redessine()        # la corde pend jusqu'a la main
        self._annonce()

    def lache(self, o):
        """`o` vient d'etre lache : a sa place, il s'y range ; sinon il
        retourne attendre a la sienne."""
        asm = self.asm
        t = self._taille()
        ox, oy = asm.a_l_ecran(o)
        if self.phase == "batons" and any(o is b for b in self.batons):
            libres = [(math.hypot(ox - px, oy - py), k)
                      for k, (px, py) in enumerate(self.places)
                      if k not in self.ranges]
            if libres:
                d, k = min(libres)
                if d <= PRISE_BATON * t:
                    self.ranges[k] = o
                    o["verrou"] = True
                    o["angle"] = ANGLE_MANCHE - ANGLE_BATON
                    asm.place_a_l_ecran(o, *self.places[k])
                    self._places_montrees()
                    asm._redessine()
                    if len(self.ranges) >= BATONS_MANCHE:
                        self._entre("bas")
                    return
        elif self.phase == "pierre" and o is self.pierre:
            px, py = self.place_pierre()
            if math.hypot(ox - px, oy - py) <= PRISE_PIERRE * t:
                o["verrou"] = True
                # Comme sur l'image : moitie moins longue que le manche, et
                # le haut des batons passe devant elle.
                o["echelle"] = ECHELLE_PIERRE
                asm.place_a_l_ecran(o, px, py)
                self._entre("croix")
                return
        self._ramene(o)
        asm._redessine()

    def suit_corde(self, x, y):
        """La main qui tient la corde est en (x, y)."""
        t = self._taille()
        if self.phase == "bas":
            (ux, uy), (vx, vy) = self._axes()
            bx, by = self.bas()
            a = ((x - bx) * ux + (y - by) * uy) / t
            b = ((x - bx) * vx + (y - by) * vy) / t
            if abs(a) > ZONE_BAS:
                self._cote = None       # partie loin du bas du manche
                return
            cote = 1 if b >= LARGE_MANCHE else (-1 if b <= -LARGE_MANCHE
                                                 else None)
            if cote is None:
                return
            if self._cote is not None and cote != self._cote:
                self.tours += 1
                self.asm._redessine()
                if self.tours >= TOURS_BAS:
                    self._entre("pierre")
                    return
            self._cote = cote
        elif self.phase == "croix":
            # Sur les axes du MANCHE : dx le long, dy en travers.
            (ux, uy), (vx, vy) = self._axes()
            nx, ny = self.noeud()
            dx = ((x - nx) * ux + (y - ny) * uy) / t
            dy = ((x - nx) * vx + (y - ny) * vy) / t
            if max(abs(dx), abs(dy)) > PORTEE_X:
                self._coin = None
                return
            if abs(dx) < COIN_X or abs(dy) < COIN_X:
                return
            coin = (1 if dx > 0 else -1, 1 if dy > 0 else -1)
            avant, self._coin = self._coin, coin
            if avant is None or avant != (-coin[0], -coin[1]):
                return
            # D'un coin au coin oppose : un trait. Bas du manche et dessus
            # <-> haut du manche et dessous, c'est "\\" ; l'autre, "/".
            sens = "\\" if coin[0] != coin[1] else "/"
            if self.traits and self.traits[-1] == sens:
                return                  # la meme diagonale : l'autre !
            self.traits.append(sens)
            self.asm._redessine()
            if len(self.traits) >= TRAITS_X:
                self.fini = True
                self._annonce()
                self.reussi()


MINIJEUX = {
    "couteau": MiniJeuCouteau,
    "fibre": MiniJeuFibre,
    "feu": MiniJeuFeu,
    "feuille": MiniJeuFeuille,
    "corde": MiniJeuCorde,
    "hache": MiniJeuHache,
}


__all__ = ["MiniJeuCouteau", "MiniJeuFibre", "MiniJeuFeu", "MiniJeuFeuille",
           "MiniJeuCorde", "MiniJeuHache",
           "Fantome", "MINIJEUX", "COUCHE",
           "AMINCISSEMENTS"]
