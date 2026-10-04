"""
LE SOL DEVANT SOI, EN CASES : ce que voit le joueur penche dans l'ecran de
craft.

Deux grilles POSEES AU SOL, DROITES (sans perspective) :

    a gauche  la PROXIMITE -- ce qui traine sur la case : un CARRE DE SOL
              DEFRICHE, terre, litiere, gravier ou sable selon la zone,
              ses cases tracees au baton. Elle va du bord
              de l'ecran jusqu'a la main gauche, 5 cases de large sur 5 de
              profondeur. C'est le meme sol que la colonne "a proximite" de
              l'inventaire : ce qui est ici y est aussi, et inversement (voir
              GameState.sol_en_cases) ;
    au centre le PLAN DE TRAVAIL, 4 sur 4, dans l'ecart entre les deux
              mains. Toujours visible, d'un gris leger. Pour l'instant rien
              ne s'y passe : on y pose des objets, UN SEUL PAR CASE
              (pas de pile), et le bouton Assembler ouvre la vue
              rapprochee (voir assemblage.py).
    a droite  LE RESULTAT : rien tant que le plan de travail porte moins de
              deux objets ; sinon un "?" -- aucun assemblage ne correspond,
              ou le joueur ne le connait pas encore -- ou l'image de
              l'objet qu'il sait deja fabriquer (voir assemblages.py).

Les objets se GLISSENT d'une case a l'autre, du sol vers une main et d'une
main vers le sol (ou vers l'autre main). Ce widget ne sait que dessiner et
suivre le doigt : ce que devient l'objet, c'est l'ecran qui en decide (voir
`depose`), parce que c'est lui qui connait l'etat du jeu.

LES GRILLES SONT DES RECTANGLES DROITS. Elles ont d'abord fui vers
l'horizon, comme un carrelage vu en perspective : les cases du fond
devenaient minces et les objets y paraissaient minuscules. Elles sont
maintenant a plat face au joueur, toutes les cases d'une grille de la meme
taille. La place de chacune reste une DISPOSITION -- un tiers a gauche
jusqu'a la main, un tiers entre les mains -- et ne passe jamais sous une
main.

TOUS LES OBJETS ONT LA MEME TAILLE (TAILLE_OBJET), quelle que soit la case :
une pierre du plan de travail est aussi grosse qu'une pierre de la
proximite.

Le calcul passe toujours par une HOMOGRAPHIE (la transformation d'un carre
unite vers les quatre coins) et sa reciproque pour retrouver la case sous
le doigt : pour un rectangle, elle se reduit a une simple mise a
l'echelle, mais une autre forme de grille ne demanderait que d'autres
coins.
"""
import os
import random

from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Ellipse, Line, Mesh, Rectangle
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.metrics import dp

from src.game_state import (SOL_COLONNES, SOL_RANGEES, CENTRE_COLONNES,
                            CENTRE_RANGEES)
from src.widgets.player_hands import (PlayerHands, _item_infos,
                                      COUVERTURE_PLEINE, GROSSISSEMENT_MAX)

# L'horizon du decor une fois le joueur penche (voir penche.HORIZON_PENCHE).
# Les grilles n'y fuient plus (elles sont droites) ; garde pour `fuite`.
HORIZON_GRILLES = 0.93

# --- LA PROXIMITE (a gauche) ------------------------------------------- #
# Son bord proche va du bord de l'ecran jusqu'a la main gauche. MESURE sur
# les images des mains, toutes poses et gants confondus : le bord gauche de
# la main gauche ne descend jamais sous 0,287 de la largeur. Le bord droit de
# la grille est pose a 0,28 : il longe la main sans jamais passer dessous.
PROX_GAUCHE = 0.012
PROX_DROITE = 0.28
PROX_PRES = 0.03
PROX_LOIN = 0.52

# --- LE PLAN DE TRAVAIL (au centre) ----------------------------------- #
# MESURE, toutes poses et gants confondus : entre les deux mains, le couloir
# libre ne descend jamais sous 0,393 - 0,607 AU-DESSUS de 0,28 de la
# hauteur. Plus bas, les mains au repos se referment vers le centre. Il
# commence donc juste au-dessus d'elles, droit, dans le couloir.
#
# A MAINS NUES, IL FAIT 2 SUR 2 (voir game_state) : ses cases ont la taille
# de celles de la proximite (0,0536 de la largeur, 0,098 de la hauteur),
# pour qu'un objet passe de l'une a l'autre sans changer d'echelle.
CENTRE_PRES = 0.29
CENTRE_LOIN = 0.29 + 2 * 0.098
CENTRE_DEMI = 0.0536         # demi-largeur

# Couleurs. LES CASES SONT PLEINES, pas transparentes : sur un sol
# transparent, une touffe d'herbe posee dans une prairie se fondait dans
# l'herbe du decor, et une brindille dans la litiere. Un fond uni et clair
# detache chaque objet, quel que soit le sol. Le plan de travail est d'un
# gris leger ; la proximite d'un gris a peine plus chaud et plus sombre,
# pour qu'on distingue d'un coup d'oeil ce qui traine de ce qu'on prepare.
# Les traits, plus sombres, separent les cases.
GRIS_CENTRE = (0.80, 0.81, 0.82, 1.0)
TRAIT_CENTRE = (0.42, 0.43, 0.45, 1.0)
GRIS_PROX = (0.70, 0.68, 0.64, 1.0)
TRAIT_PROX = (0.38, 0.36, 0.33, 1.0)
# La case sous le doigt, pendant un glisser : pleine elle aussi.
VISEE = (0.62, 0.90, 0.64, 1.0)
VISEE_REFUS = (0.92, 0.55, 0.50, 1.0)
# Le fond des cases quand un objet peut y etre lache (voir pulse) : le
# vert de l'inventaire, qui clignote.
CIBLE = (0.70, 0.86, 0.68, 1.0)

# LE RESULTAT, a droite : un carre de la hauteur du plan de travail, dans
# le tiers libre a droite de la main droite (qui ne depasse jamais 0,713 de
# la largeur). Son centre, en part de la largeur.
RESULTAT_X = 0.85
GRIS_RESULTAT = (0.80, 0.81, 0.82, 1.0)
TRAIT_RESULTAT = (0.42, 0.43, 0.45, 1.0)
TEXTE_RESULTAT = (0.30, 0.31, 0.33, 1.0)

# LE SOL DEFRICHE DE LA PROXIMITE : une texture par zone (assets/craft/),
# repetee tous les TUILE_SOL de la hauteur d'ecran. Sans texture (zone
# inconnue, image absente), la proximite garde son gris uni.
_ICI = os.path.dirname(os.path.abspath(__file__))
DOSSIER_CRAFT = os.path.abspath(os.path.join(_ICI, "..", "..", "assets",
                                             "craft"))
TUILE_SOL = 0.40
# Les cases tracees au baton : un sillon sombre, et sous lui la levre de
# terre eclairee. Le trace tremble un peu, comme a main levee.
SILLON = (0.18, 0.12, 0.08, 0.48)
LEVRE = (1.0, 0.95, 0.85, 0.22)
TREMBLE = 0.0035
# LE REBORD : comme au pied d'une pierre, le TERRAIN de la zone deborde sur
# le bord du sol defriche et s'y fond, en bandes de moins en moins opaques,
# le long d'un contour irregulier. Profondeur vers l'interieur et debord
# vers l'exterieur, en part de la hauteur ; nombre de bandes du fondu.
TERRAIN_DE_ZONE = {"Foret": "forest_floor", "Plaine": "grass",
                   "Montagne": "rock", "Lac": "rive"}
REBORD_DEDANS = 0.042
REBORD_DEHORS = 0.010
BANDES_REBORD = 7
# Irregularite du contour (part de la hauteur) et pas entre deux points.
REBORD_TREMBLE = 0.012
REBORD_PAS = 0.018
# Sous le terrain, une levre de terre plus sombre souligne le bord.
LEVRE_REBORD = (0.10, 0.07, 0.04, 0.30)

# Teintes d'une case du sol texture (multipliees a la texture) : visee,
# refus, et cible qui clignote.
VISEE_SOL = (0.70, 1.00, 0.70, 1.0)
REFUS_SOL = (1.00, 0.62, 0.58, 1.0)
CIBLE_SOL = (0.82, 1.00, 0.82, 1.0)
BLANC = (1.0, 1.0, 1.0, 1.0)
_TEXTURES = {}


def texture_craft(nom, repete=False):
    """Une texture d'assets/craft/ (None si absente), gardee en memoire."""
    if nom not in _TEXTURES:
        tex = None
        chemin = os.path.join(DOSSIER_CRAFT, nom + ".png")
        if os.path.isfile(chemin):
            try:
                tex = CoreImage(chemin).texture
                if repete:
                    tex.wrap = "repeat"
            except Exception:
                tex = None
        _TEXTURES[nom] = tex
    return _TEXTURES[nom]


# LA TAILLE D'UN OBJET POSE, en part de la hauteur de l'ecran : LA MEME
# PARTOUT, quelle que soit la case. C'est le cote du carre ou l'image tient
# sans etre deformee. 0,072 fait ~78 px sur 1080 : un peu plus que la
# hauteur d'une case du plan de travail (0,065), bien moins que celle d'une
# case de la proximite (0,098) -- un objet du plan de travail deborde a
# peine de sa case, comme une pierre posee qui depasse d'un carreau.
TAILLE_OBJET = 0.072
OMBRE = (0.0, 0.0, 0.0, 0.28)
# Le nombre d'une pile, en part de la hauteur de l'ecran.
TAILLE_NOMBRE = 0.026

# La case visee pendant un glisser est au plus a cette hauteur au-dessus du
# doigt (en part de l'ecran) : assez pour qu'il ne la cache pas.
VISEE_DOIGT = 0.075

# Taille de l'objet qui suit le doigt, en part de la hauteur de l'ecran.
FANTOME = 0.12
# En deca, un toucher n'est pas un glisser.
SEUIL_GLISSE = dp(14)

# Les mains comme cibles : autour de leur centre (PlayerHands.HAND_FX), sur
# toute la hauteur des images.
MAIN_DEMI_LARGEUR = 0.075
MAIN_HAUT = 0.47


# --------------------------------------------------------------------- #
# L'HOMOGRAPHIE : un carre unite -> un quadrilatere
# --------------------------------------------------------------------- #
def homographie(p0, p1, p2, p3):
    """La matrice 3x3 qui envoie (0,0), (1,0), (1,1), (0,1) sur p0..p3.

    C'est la projection d'un rectangle pose a plat, vu en perspective
    (methode de Heckbert). u va de gauche a droite, v du bord proche au
    bord lointain."""
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = p0, p1, p2, p3
    dx1, dx2, dx3 = x1 - x2, x3 - x2, x0 - x1 + x2 - x3
    dy1, dy2, dy3 = y1 - y2, y3 - y2, y0 - y1 + y2 - y3
    if abs(dx3) < 1e-12 and abs(dy3) < 1e-12:
        g = h = 0.0
    else:
        den = dx1 * dy2 - dx2 * dy1
        g = (dx3 * dy2 - dx2 * dy3) / den
        h = (dx1 * dy3 - dx3 * dy1) / den
    return ((x1 - x0 + g * x1, x3 - x0 + h * x3, x0),
            (y1 - y0 + g * y1, y3 - y0 + h * y3, y0),
            (g, h, 1.0))


def applique(m, u, v):
    w = m[2][0] * u + m[2][1] * v + m[2][2]
    return ((m[0][0] * u + m[0][1] * v + m[0][2]) / w,
            (m[1][0] * u + m[1][1] * v + m[1][2]) / w)


def inverse(m):
    (a, b, c), (d, e, f), (g, h, i) = m
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    return ((( e * i - f * h) / det, -(b * i - c * h) / det,
             ( b * f - c * e) / det),
            (-(d * i - f * g) / det, ( a * i - c * g) / det,
             -(a * f - c * d) / det),
            (( d * h - e * g) / det, -(a * h - b * g) / det,
             ( a * e - b * d) / det))


def fuite(x, y, vx, vy, y_cible):
    """Le point de la droite (x, y) -> (vx, vy) a la hauteur y_cible."""
    t = (y_cible - y) / (vy - y)
    return x + (vx - x) * t, y_cible


def coins_proximite():
    """Les quatre coins de la proximite, en parts de l'ecran : proche-gauche,
    proche-droit, loin-droit, loin-gauche.

    Un rectangle droit, du bord de l'ecran jusqu'a la main gauche."""
    return ((PROX_GAUCHE, PROX_PRES), (PROX_DROITE, PROX_PRES),
            (PROX_DROITE, PROX_LOIN), (PROX_GAUCHE, PROX_LOIN))


# LE PROFIL DES MAINS, MESURE sur leurs images (toutes poses, gants
# compris) : pour chaque tranche de 0,005 de la largeur, de 0 a 0,5, la
# hauteur du plus haut pixel de main, en part de la LARGEUR de l'ecran (les
# mains sont dessinees a la largeur de l'ecran, leur hauteur suit). Il dit
# ou une zone peut s'etendre sans passer devant une main.
PROFIL_MAINS = (
    0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000,
    0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000,
    0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000,
    0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000,
    0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000,
    0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000,
    0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000,
    0.1484, 0.1668, 0.1672, 0.1664, 0.1642, 0.1604, 0.1540, 0.2070,
    0.2083, 0.2083, 0.2079, 0.1985, 0.2160, 0.2173, 0.2173, 0.2169,
    0.2139, 0.2117, 0.2134, 0.2134, 0.2096, 0.1912, 0.1933, 0.1933,
    0.1891, 0.1257, 0.1262, 0.1262, 0.1249, 0.1236, 0.1210, 0.1185,
    0.1176, 0.1163, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000,
    0.0000, 0.0000, 0.0000, 0.0000,
)
# Un peu d'air entre une zone et la main.
MARGE_MAINS = 0.004


def hauteur_mains(x0, x1, largeur):
    """La plus haute main entre x0 et x1 (pixels), en pixels."""
    n = len(PROFIL_MAINS)
    pas = 0.5 / n
    k0 = max(0, int(x0 / largeur / pas))
    k1 = min(n - 1, int(x1 / largeur / pas))
    if k0 > n - 1:
        return 0.0
    return max(PROFIL_MAINS[k0:k1 + 1]) * largeur


def plus_grand_carre(largeur, hauteur, haut):
    """Le cote (pixels) du plus grand CARRE colle au bord gauche, son haut a
    `haut` (part de la hauteur), qui ne passe devant aucune main."""
    sommet = haut * hauteur
    marge = MARGE_MAINS * largeur
    bas, haut_c = 0.0, sommet
    for _ in range(40):
        c = (bas + haut_c) / 2.0
        if sommet - c >= hauteur_mains(0.0, c + marge, largeur):
            bas = c
        else:
            haut_c = c
    return bas


def coins_carre(largeur, hauteur, haut):
    """Les coins de ce plus grand carre, en parts de l'ecran."""
    c = plus_grand_carre(largeur, hauteur, haut)
    return coins_rect(0.0, haut - c / hauteur, c / largeur, haut)


def coins_rect(gauche, bas, droite, haut):
    """Les quatre coins d'un rectangle droit (parts de l'ecran)."""
    return ((gauche, bas), (droite, bas), (droite, haut), (gauche, haut))


def coins_centre():
    """Les quatre coins du plan de travail : un rectangle droit, entre les
    mains."""
    g, d = 0.5 - CENTRE_DEMI, 0.5 + CENTRE_DEMI
    return ((g, CENTRE_PRES), (d, CENTRE_PRES),
            (d, CENTRE_LOIN), (g, CENTRE_LOIN))


def cadre_image(nom, cote):
    """(largeur, hauteur) de l'image entiere de `nom` dessinee dans un carre
    de `cote` (voir dessine_objet), ou None sans image."""
    tex, couverture, _masse = _item_infos(nom)
    if tex is None:
        return None
    tw, th = tex.size
    grossi = 1.0
    if 0.0 < couverture < COUVERTURE_PLEINE:
        grossi = min(GROSSISSEMENT_MAX,
                     (COUVERTURE_PLEINE / couverture) ** 0.5)
    boite = cote * grossi
    rapport = float(tw) / max(1, th)
    return (boite, boite / rapport) if rapport >= 1.0 \
        else (boite * rapport, boite)


def dessine_objet(nom, cx, cy, cote, ombre=True, coupe=(0.0, 0.0),
                  alpha=1.0):
    """Un objet centre en (cx, cy), son image entiere dans un carre de
    `cote`, avec son ombre a plat dessous. Dessine dans le canvas ouvert.

    `coupe` = (gauche, droite) : la part de la largeur de l'image retiree de
    chaque cote (une pierre qu'on taille). Ce qui reste ne bouge pas."""
    tex, couverture, _masse = _item_infos(nom)
    g, d = coupe
    reste = max(0.0, 1.0 - g - d)
    if ombre:
        Color(OMBRE[0], OMBRE[1], OMBRE[2], OMBRE[3] * alpha)
        ow, oh = cote * 0.80 * reste, cote * 0.30
        ox = cx - cote * 0.40 + cote * 0.80 * g
        Ellipse(pos=(ox, cy - cote * 0.42), size=(ow, oh))
    if tex is None or reste <= 0.0:
        return
    tw, th = tex.size
    # UNE IMAGE AJOUREE EST GROSSIE, comme dans la main (voir player_hands) :
    # une brindille couvre un dixieme de son cadre, elle disparaissait sinon.
    # Meme regle, meme plafond.
    grossi = 1.0
    if 0.0 < couverture < COUVERTURE_PLEINE:
        grossi = min(GROSSISSEMENT_MAX,
                     (COUVERTURE_PLEINE / couverture) ** 0.5)
    boite = cote * grossi
    rapport = float(tw) / max(1, th)
    iw, ih = (boite, boite / rapport) if rapport >= 1.0 \
        else (boite * rapport, boite)
    x0 = cx - iw / 2.0
    if g > 0.0 or d > 0.0:
        tex = tex.get_region(g * tw, 0, reste * tw, th)
        x0 += g * iw
        iw *= reste
    Color(1, 1, 1, alpha)
    Rectangle(texture=tex, pos=(x0, cy - ih / 2.0), size=(iw, ih))


class _Grille(object):
    """Une grille au sol : ses cases, et la transformation qui les pose."""

    def __init__(self, prefixe, colonnes, rangees, coins):
        self.prefixe = prefixe
        self.colonnes = colonnes
        self.rangees = rangees
        self.coins = coins            # en parts de l'ecran
        self.m = None
        self.m_inv = None

    def cale(self, x, y, w, h):
        """Pose la grille sur un widget de cette taille."""
        self.h = h
        pts = [(x + fx * w, y + fy * h) for fx, fy in self.coins]
        self.m = homographie(*pts)
        self.m_inv = inverse(self.m)

        # Les bords de la grille a l'ecran, en bas (proche) et en haut.
        self.y_pres = self.point(0.5, 0.0)[1]
        self.y_loin = self.point(0.5, 1.0)[1]
        self.x_milieu = self.point(0.5, 0.0)[0]

    def point(self, u, v):
        return applique(self.m, u, v)

    def vr(self, t):
        """La profondeur v (0 au bord proche, 1 au fond) de la rangee `t`,
        comptee en rangees (t peut etre fractionnaire : 2,5 est le milieu
        de la troisieme).

        LES RANGEES SONT EGALES A L'ECRAN : la rangee t commence a t / n de
        la hauteur de la grille. Les bords proche et lointain etant
        horizontaux, et les cotes fuyant vers un point de l'horizon, une
        profondeur donnee est une ligne horizontale de l'ecran : il suffit
        de lire la profondeur a cette hauteur, par la transformation
        inverse."""
        if t <= 0:
            return 0.0
        if t >= self.rangees:
            return 1.0
        y = self.y_pres + (self.y_loin - self.y_pres) * t / self.rangees
        return applique(self.m_inv, self.x_milieu, y)[1]

    def rang_de(self, y):
        """La rangee (fractionnaire) a la hauteur `y` de l'ecran."""
        return (y - self.y_pres) / (self.y_loin - self.y_pres) * self.rangees

    def centre(self, cle):
        """Le milieu d'une case a l'ecran."""
        col, rang = self.col_rang(cle)
        return self.point((col + 0.5) / self.colonnes, self.vr(rang + 0.5))

    def case_de(self, col, rang):
        return "%s:%d" % (self.prefixe, rang * self.colonnes + col)

    def col_rang(self, cle):
        i = int(cle.split(":")[1])
        return i % self.colonnes, i // self.colonnes

    def coins_case(self, col, rang):
        c = float(self.colonnes)
        v0, v1 = self.vr(rang), self.vr(rang + 1)
        return [self.point(col / c, v0),
                self.point((col + 1) / c, v0),
                self.point((col + 1) / c, v1),
                self.point(col / c, v1)]

    def sous(self, x, y):
        """La case sous le point (x, y) de l'ecran, ou None."""
        u, _v = applique(self.m_inv, x, y)
        t = self.rang_de(y)
        if not (0.0 <= u < 1.0 and 0.0 <= t < self.rangees):
            return None
        return self.case_de(int(u * self.colonnes), int(t))

    def visee(self, x, y):
        """La case VISEE par un doigt qui porte un objet : celle UNE RANGEE
        AU-DESSUS (plus loin) de la case sous le doigt. Le doigt et l'objet
        qu'il porte cachent la case juste dessous ; celle d'au-dessus reste
        visible quand elle s'allume. C'est la case JUSTE AU-DESSUS A L'ECRAN,
        a la verticale du doigt : les rangees ayant toutes la meme hauteur
        a l'ecran, on remonte simplement d'une rangee. (Rester dans la
        colonne du doigt, elle, ferait glisser la visee de cote : les
        colonnes fuient en biais vers l'horizon.) Pour viser la rangee la
        plus proche, on tient l'objet juste sous la grille.

        Le decalage ne depasse pas la hauteur d'un doigt (VISEE_DOIGT) : sur
        une grande grille aux rangees hautes, remonter d'une rangee entiere
        rendrait la rangee du bas inaccessible au bord de l'ecran."""
        rang = (self.y_loin - self.y_pres) / self.rangees
        return self.sous(x, y + min(rang, VISEE_DOIGT * self.h))

    def cles(self):
        return [self.case_de(c, r) for r in range(self.rangees)
                for c in range(self.colonnes)]


class SolDeCraft(Widget):
    """Les deux grilles, les objets qui y sont poses, et le glisser.

    `depose(source, cible)` est appele au lacher, avec deux couples
    ("case", "G:3") / ("main", 0) ; il rend True si le depot a eu lieu.
    `couche` est le widget ou se dessine l'objet qui suit le doigt : il doit
    passer par-dessus les mains."""

    def __init__(self, depose=None, couche=None, avec_centre=True,
                 coins_prox=None, **kwargs):
        super().__init__(**kwargs)
        self.depose = depose
        self.couche = couche
        self.actif = False
        # La proximite peut etre posee ailleurs que par defaut : l'ecran qui
        # la montre sait ou elle doit aller (voir set_coins_proximite).
        self.proximite = _Grille("G", SOL_COLONNES, SOL_RANGEES,
                                 coins_prox or coins_proximite())
        self.centre = _Grille("C", CENTRE_COLONNES, CENTRE_RANGEES,
                              coins_centre())
        # L'INVENTAIRE n'a que la proximite : son milieu est occupe par
        # l'equipement (voir InventoryScreen).
        self.avec_centre = avec_centre
        self._cases = {}
        self._mains = [None, None]
        # Ce que montre le carre de droite : None, "?" ou un nom d'objet.
        self.resultat = None
        # La zone ou l'on est : elle choisit le sol de la proximite.
        self.zone = None
        self._glisse = None
        self._nombres = []
        # Les couleurs des cases, gardees pour etre RETEINTES sans tout
        # redessiner : le clignotement d'une cible tourne a trente images par
        # seconde, et refaire la grille et ses objets a chaque fois serait du
        # travail pour rien.
        self._couleurs = {}
        # Une visee imposee du dehors (l'inventaire mene son propre glisser,
        # voir visee_externe), et le clignotement des cases ou lacher.
        self._visee_ext = (None, False)
        self._pulse = None
        self.bind(pos=self._redessine, size=self._redessine)

    # -- ce que montre le sol ------------------------------------------ #
    def montre(self, cases, mains, resultat=None):
        """{case: [objet, nombre]} (voir GameState.sol_en_cases), ce que
        tiennent les mains (source possible d'un glisser), et ce que montre
        le carre du resultat (None, "?" ou un nom d'objet)."""
        self._cases = {k: list(v) for k, v in (cases or {}).items()}
        self._mains = list(mains or [None, None])
        self.resultat = resultat if self.avec_centre else None
        self._redessine()

    def rect_resultat(self):
        """Le carre du resultat a l'ecran : (x, y, cote)."""
        cote = (CENTRE_LOIN - CENTRE_PRES) * self.height
        return (self.x + RESULTAT_X * self.width - cote / 2.0,
                self.y + CENTRE_PRES * self.height, cote)

    def set_coins_proximite(self, coins):
        """Pose la proximite sur ces quatre coins (parts de l'ecran)."""
        coins = tuple(tuple(float(v) for v in c) for c in coins)
        if coins != tuple(self.proximite.coins):
            self.proximite.coins = coins
            self._redessine()

    def set_zone(self, zone):
        if zone != self.zone:
            self.zone = zone
            self._redessine()

    def texture_sol(self):
        """Le sol defriche : UNE image fournie pour toutes les zones
        (sol_defriche.png) si elle existe, sinon celle de la zone."""
        commun = texture_craft("sol_defriche", repete=True)
        if commun is not None:
            return commun
        if not self.zone:
            return None
        return texture_craft("sol_%s" % self.zone, repete=True)

    def grilles(self):
        if not self.avec_centre:
            return (self.proximite,)
        return (self.proximite, self.centre)

    def visee_externe(self, cle, refus=False):
        """La case que vise un glisser mene par l'ecran lui-meme (voir
        l'inventaire), ou None."""
        if (cle, refus) != self._visee_ext:
            self._visee_ext = (cle, refus)
            self._teinte_cases()

    def pulse(self, allume, force=1.0):
        """Fait clignoter la proximite : on peut y lacher l'objet tenu.

        Meme interface que les cibles de l'inventaire (voir
        drag_drop.make_highlightable), pour qu'il la traite comme les
        autres."""
        self._pulse = force if allume else None
        self._teinte_cases()

    # -- dessin -------------------------------------------------------- #
    def _redessine(self, *_):
        self.canvas.clear()
        for lbl in self._nombres:
            if lbl.parent is self:
                self.remove_widget(lbl)
        self._nombres = []
        if self.width <= 0 or self.height <= 0:
            return
        for g in self.grilles():
            g.cale(self.x, self.y, self.width, self.height)
        self._couleurs = {}
        with self.canvas:
            # LES DEUX ZONES SONT DU SOL DEFRICHE, bordees par le terrain.
            for g in self.grilles():
                if self.texture_sol() is not None:
                    self._dessine_sol(g, self.texture_sol())
                    self._dessine_rebord(g)
                    continue
                fond, trait = ((GRIS_PROX, TRAIT_PROX) if g is self.proximite
                               else (GRIS_CENTRE, TRAIT_CENTRE))
                self._dessine_grille(g, fond, trait)
            # Du plus LOIN au plus pres : un objet de la rangee de devant
            # passe devant celui de derriere.
            for g in self.grilles():
                for rang in reversed(range(g.rangees)):
                    for col in range(g.colonnes):
                        cle = g.case_de(col, rang)
                        pile = self._cases.get(cle)
                        if pile is None:
                            continue
                        if self._glisse and self._glisse["source"] == \
                                ("case", cle):
                            continue    # il est dans la main du doigt
                        self._dessine_objet(g, col, rang, pile)
            if self.resultat is not None:
                self._dessine_resultat()
        self._teinte_cases()

    def _dessine_resultat(self):
        x, y, cote = self.rect_resultat()
        ecorce = texture_craft("ecorce")
        if ecorce is not None:
            # UN MORCEAU D'ECORCE DE BOULEAU, le ? trace au charbon dessus ;
            # un objet connu y est pose tel quel.
            Color(1, 1, 1, 1)
            Rectangle(texture=ecorce, pos=(x, y), size=(cote, cote))
            charbon = texture_craft("charbon_question")
            if self.resultat == "?" and charbon is not None:
                m = cote * 0.12
                Rectangle(texture=charbon, pos=(x + m, y + m),
                          size=(cote - 2 * m, cote - 2 * m))
                return
            if self.resultat != "?":
                dessine_objet(self.resultat, x + cote / 2.0, y + cote / 2.0,
                              cote * 0.66, ombre=False)
                return
        Color(*GRIS_RESULTAT)
        Rectangle(pos=(x, y), size=(cote, cote))
        Color(*TRAIT_RESULTAT)
        Line(rectangle=(x, y, cote, cote),
             width=max(1.0, self.height * 0.0024))
        if self.resultat == "?":
            lbl = Label(text="?", bold=True, color=TEXTE_RESULTAT,
                        font_size=cote * 0.62, size=(cote, cote),
                        pos=(x, y))
            self.add_widget(lbl)
            self._nombres.append(lbl)
        else:
            dessine_objet(self.resultat, x + cote / 2.0, y + cote / 2.0,
                          cote * 0.72, ombre=False)

    def _teinte_cases(self):
        """La couleur de chaque case : la visee du doigt, sinon le
        clignotement d'une cible, sinon son fond."""
        if self._glisse:
            visee, refus = self._glisse["visee"], self._glisse["refus"]
        else:
            visee, refus = self._visee_ext
        for cle, (couleur, fond) in self._couleurs.items():
            # Une case texturee a un fond blanc : on la TEINTE.
            sol = fond == BLANC
            if cle == visee:
                if sol:
                    couleur.rgba = REFUS_SOL if refus else VISEE_SOL
                else:
                    couleur.rgba = VISEE_REFUS if refus else VISEE
            elif self._pulse is not None and cle.startswith("G:"):
                p = self._pulse
                cible = CIBLE_SOL if sol else CIBLE
                couleur.rgba = tuple(fond[i] + (cible[i] - fond[i]) * p
                                     for i in range(4))
            else:
                couleur.rgba = fond

    def _dessine_grille(self, g, fond, trait):
        for rang in range(g.rangees):
            for col in range(g.colonnes):
                cle = g.case_de(col, rang)
                self._couleurs[cle] = (Color(*fond), fond)
                pts = g.coins_case(col, rang)
                Mesh(vertices=[v for p in pts for v in (p[0], p[1], 0, 0)],
                     indices=[0, 1, 2, 0, 2, 3], mode="triangles")
        Color(*trait)
        largeur = max(1.0, self.height * 0.0016)
        for col in range(g.colonnes + 1):
            u = col / float(g.colonnes)
            a, b = g.point(u, 0.0), g.point(u, 1.0)
            Line(points=[a[0], a[1], b[0], b[1]], width=largeur)
        for rang in range(g.rangees + 1):
            v = g.vr(rang)
            a, b = g.point(0.0, v), g.point(1.0, v)
            Line(points=[a[0], a[1], b[0], b[1]], width=largeur)

    def _dessine_sol(self, g, tex):
        """La proximite en SOL DEFRICHE : chaque case porte la texture de la
        zone (repetee, d'un seul tenant d'une case a l'autre), et les cases
        sont tracees au baton."""
        tuile = TUILE_SOL * self.height
        for rang in range(g.rangees):
            for col in range(g.colonnes):
                cle = g.case_de(col, rang)
                self._couleurs[cle] = (Color(*BLANC), BLANC)
                pts = g.coins_case(col, rang)
                Mesh(vertices=[v for p in pts
                               for v in (p[0], p[1], p[0] / tuile,
                                         p[1] / tuile)],
                     indices=[0, 1, 2, 0, 2, 3], mode="triangles",
                     texture=tex)
        # Les traits : meme hasard a chaque dessin (le trace ne frissonne
        # pas), un peu de tremblement perpendiculaire.
        hasard = random.Random(7)
        largeur = max(1.5, self.height * 0.0028)
        tremble = TREMBLE * self.height

        def trace(a, b):
            n = 9
            pts = []
            dx, dy = b[0] - a[0], b[1] - a[1]
            long = max(1e-6, (dx * dx + dy * dy) ** 0.5)
            nx, ny = -dy / long, dx / long
            for k in range(n + 1):
                t = k / float(n)
                j = hasard.uniform(-1, 1) * tremble if 0 < k < n else 0.0
                pts.append((a[0] + dx * t + nx * j, a[1] + dy * t + ny * j))
            Color(*LEVRE)
            Line(points=[v for p in pts for v in (p[0] + largeur * 0.5,
                                                  p[1] - largeur * 0.9)],
                 width=largeur * 0.7)
            Color(*SILLON)
            Line(points=[v for p in pts for v in p], width=largeur)

        for col in range(g.colonnes + 1):
            u = col / float(g.colonnes)
            trace(g.point(u, 0.0), g.point(u, 1.0))
        for rang in range(g.rangees + 1):
            v = g.vr(rang)
            trace(g.point(0.0, v), g.point(1.0, v))

    def _contour(self, g, hasard):
        """Le tour de la grille, point par point dans le sens trigonometrique,
        avec pour chacun sa normale vers l'exterieur et son tremblement."""
        (x0, y0), (x1, _), (_, y1), _ = [g.point(u, v) for u, v in
                                         ((0, 0), (1, 0), (1, 1), (0, 1))]
        pas = max(4.0, REBORD_PAS * self.height)
        pts = []
        for (ax, ay), (bx, by), n in (((x0, y0), (x1, y0), (0, -1)),
                                      ((x1, y0), (x1, y1), (1, 0)),
                                      ((x1, y1), (x0, y1), (0, 1)),
                                      ((x0, y1), (x0, y0), (-1, 0))):
            long = abs(bx - ax) + abs(by - ay)
            k = max(2, int(long / pas))
            for j in range(k):
                t = j / float(k)
                pts.append((ax + (bx - ax) * t, ay + (by - ay) * t, n,
                            hasard.uniform(-1.0, 1.0)))
        # Les coins : la normale en diagonale, pour que les bandes tournent.
        propre = []
        for i, (x, y, n, j) in enumerate(pts):
            pn = pts[i - 1][2]
            if pn != n:
                n = ((n[0] + pn[0]) * 0.7071, (n[1] + pn[1]) * 0.7071)
            propre.append((x, y, n, j))
        # Un tremblement lisse : chaque point fait la moyenne avec ses voisins.
        lisse = []
        for i, (x, y, n, j) in enumerate(propre):
            jm = (propre[i - 1][3] + j + propre[(i + 1) % len(propre)][3]) / 3.0
            lisse.append((x, y, n, jm))
        return lisse

    def _dessine_rebord(self, g):
        """Le terrain de la zone deborde sur le bord du sol defriche."""
        nom = TERRAIN_DE_ZONE.get(self.zone)
        tex, tuile = None, 1.0
        if nom:
            try:
                from src.widgets import textures
                tex = textures.base_texture(nom)
                tuile = textures.tile_for(nom) / 1080.0 * self.height
            except Exception:
                tex = None
        if tex is not None:
            try:
                tex.wrap = "repeat"
            except Exception:
                pass
        hasard = random.Random(11 if g is self.proximite else 23)
        contour = self._contour(g, hasard)
        n = len(contour)
        dedans = REBORD_DEDANS * self.height
        dehors = REBORD_DEHORS * self.height
        tremble = REBORD_TREMBLE * self.height

        def anneau(d):
            """Le contour decale de `d` vers l'interieur (negatif : dehors),
            tremblement compris."""
            out = []
            for x, y, (nx, ny), j in contour:
                e = d - j * tremble
                out.append((x - nx * e, y - ny * e))
            return out

        # La levre sombre, juste sous le terrain.
        bord = anneau(dedans * 0.55)
        Color(*LEVRE_REBORD)
        Line(points=[v for p in bord + bord[:1] for v in p],
             width=max(1.0, self.height * 0.003))
        # Les bandes, de l'exterieur (opaque) vers l'interieur (transparent).
        for b in range(BANDES_REBORD):
            d0 = -dehors + (dedans + dehors) * b / BANDES_REBORD
            d1 = -dehors + (dedans + dehors) * (b + 1) / BANDES_REBORD
            alpha = 0.95 * (1.0 - b / float(BANDES_REBORD)) ** 1.4
            a0, a1 = anneau(d0), anneau(d1)
            verts, idx = [], []
            for i in range(n):
                for (x, y) in (a0[i], a1[i]):
                    verts += [x, y, x / tuile, y / tuile]
                k = 2 * i
                k2 = 2 * ((i + 1) % n)
                idx += [k, k + 1, k2, k + 1, k2 + 1, k2]
            # Sans image du terrain, un aplat de couleur dessinerait un cadre
            # plutot qu'un rebord : on s'en tient alors a la levre.
            if tex is not None:
                Color(1, 1, 1, alpha)
                Mesh(vertices=verts, indices=idx, mode="triangles",
                     texture=tex)

    def _dessine_objet(self, g, col, rang, pile):
        """Un objet pose dans sa case, avec son ombre et son nombre.

        IL A LA MEME TAILLE PARTOUT (TAILLE_OBJET), quelle que soit la case :
        il est centre dans la sienne, son image entiere dans un carre fixe,
        sans deformation."""
        nom, nombre = pile
        c = float(g.colonnes)
        cx, cy = g.point((col + 0.5) / c, g.vr(rang + 0.5))
        dx, _ = g.point((col + 1) / c, g.vr(rang + 0.5))
        _, bas = g.point((col + 0.5) / c, g.vr(rang))
        dessine_objet(nom, cx, cy, self.height * TAILLE_OBJET)
        if nombre > 1:
            taille = self.height * TAILLE_NOMBRE
            lbl = Label(text="x%d" % nombre, bold=True,
                        color=(1, 1, 1, 0.95), font_size=taille)
            lbl.size = (taille * 2.4, taille * 1.3)
            lbl.pos = (dx - lbl.size[0] - taille * 0.15, bas + taille * 0.1)
            self.add_widget(lbl)
            self._nombres.append(lbl)

    # -- qu'y a-t-il sous le doigt ? ----------------------------------- #
    def sous_le_doigt(self, x, y):
        """("case", cle), ("main", i) ou None."""
        for g in self.grilles():
            cle = g.sous(x, y)
            if cle is not None:
                return ("case", cle)
        for i, fx in enumerate(PlayerHands.HAND_FX):
            mx = self.x + fx * self.width
            if (abs(x - mx) <= MAIN_DEMI_LARGEUR * self.width
                    and self.y <= y <= self.y + MAIN_HAUT * self.height):
                return ("main", i)
        return None

    def vise_depot(self, x, y):
        """Ou irait l'objet lache en (x, y) : ("case", cle) -- la case une
        rangee au-dessus du doigt, voir _Grille.visee --, ("main", i) ou
        None. La SAISIE, elle, prend la case sous le doigt (sous_le_doigt)."""
        for g in self.grilles():
            cle = g.visee(x, y)
            if cle is not None:
                return ("case", cle)
        cible = self.sous_le_doigt(x, y)
        return cible if cible is not None and cible[0] == "main" else None

    def objet_de(self, cible):
        if cible is None:
            return None
        if cible[0] == "case":
            pile = self._cases.get(cible[1])
            return pile[0] if pile else None
        return self._mains[cible[1]]

    # -- le glisser ---------------------------------------------------- #
    def on_touch_down(self, touch):
        # Sans `depose`, c'est l'ecran qui mene le glisser (l'inventaire,
        # voir drag_drop) : le sol ne fait que dessiner.
        if not self.actif or self.depose is None:
            return False
        source = self.sous_le_doigt(touch.x, touch.y)
        nom = self.objet_de(source)
        if nom is None:
            return False
        self._glisse = {"source": source, "nom": nom, "depart": touch.pos,
                        "bouge": False, "visee": None, "refus": False,
                        "fantome": None}
        if hasattr(touch, "grab"):
            touch.grab(self)
        return True

    def on_touch_move(self, touch):
        g = self._glisse
        if g is None or not self._est_le_mien(touch):
            return False
        if not g["bouge"]:
            dx = touch.x - g["depart"][0]
            dy = touch.y - g["depart"][1]
            if (dx * dx + dy * dy) ** 0.5 < SEUIL_GLISSE:
                return True
            g["bouge"] = True
            self._cree_fantome()
        self._place_fantome(touch.x, touch.y)
        cible = self.vise_depot(touch.x, touch.y)
        visee = cible[1] if cible and cible[0] == "case" else None
        refus = self._refuse(g, cible)
        if visee != g["visee"] or refus != g["refus"]:
            g["visee"], g["refus"] = visee, refus
            self._teinte_cases()
        return True

    def on_touch_up(self, touch):
        g = self._glisse
        if g is None or not self._est_le_mien(touch):
            return False
        if hasattr(touch, "ungrab"):
            touch.ungrab(self)
        self._efface_fantome()
        self._glisse = None
        if g["bouge"]:
            cible = self.vise_depot(touch.x, touch.y)
            if cible is not None and cible != g["source"] and self.depose:
                self.depose(g["source"], cible)
        self._redessine()
        return True

    def annule(self):
        """Abandonne un glisser en cours (on quitte l'ecran, par exemple)."""
        self._efface_fantome()
        self._glisse = None
        self._redessine()

    def _est_le_mien(self, touch):
        courant = getattr(touch, "grab_current", None)
        return courant is None or courant is self

    def _refuse(self, g, cible):
        """La cible refusera-t-elle ? Seulement pour colorer la visee : la
        decision reste a l'ecran (voir `depose`)."""
        if cible is None or cible == g["source"]:
            return False
        dessus = self.objet_de(cible)
        source = g["source"]
        if source[0] == "case" and cible[0] == "main":
            return dessus is not None
        vers_plan = cible[0] == "case" and cible[1].startswith("C:")
        if source[0] == "main" and cible[0] == "case":
            return dessus is not None and (dessus != g["nom"] or vers_plan)
        if source[0] == "case" and cible[0] == "case" and dessus is not None:
            # Un objet par case du plan de travail (voir deplace_au_sol).
            pile = self._cases.get(source[1]) or [None, 1]
            depuis_plan = source[1].startswith("C:")
            if vers_plan:
                return dessus == g["nom"] or pile[1] > 1
            if depuis_plan and dessus != g["nom"]:
                return self._cases[cible[1]][1] > 1
        return False

    # -- l'objet qui suit le doigt ------------------------------------- #
    def _cree_fantome(self):
        couche = self.couche if self.couche is not None else self
        tex = _item_infos(self._glisse["nom"])[0]
        taille = FANTOME * self.height
        if tex is not None:
            tw, th = tex.size
            if tw >= th:
                w, h = taille, taille * th / max(1, tw)
            else:
                w, h = taille * tw / max(1, th), taille
        else:
            w = h = taille
        with couche.canvas.after:
            couleur = Color(1, 1, 1, 0.92)
            rect = Rectangle(texture=tex, size=(w, h), pos=(0, 0))
        self._glisse["fantome"] = (couche, couleur, rect)
        # Des le premier glisser, la case source se vide a l'ecran : l'objet
        # est dans la main du doigt.
        self._redessine()

    def _place_fantome(self, x, y):
        f = self._glisse["fantome"] if self._glisse else None
        if f is None:
            return
        rect = f[2]
        w, h = rect.size
        # Un peu AU-DESSUS du doigt : sous lui, on ne verrait pas ce qu'on
        # porte.
        rect.pos = (x - w / 2.0, y - h * 0.15)

    def _efface_fantome(self):
        f = self._glisse["fantome"] if self._glisse else None
        if f is None:
            return
        couche, couleur, rect = f
        try:
            couche.canvas.after.remove(couleur)
            couche.canvas.after.remove(rect)
        except Exception:
            couche.canvas.after.clear()
        self._glisse["fantome"] = None


__all__ = ["SolDeCraft", "dessine_objet", "homographie", "applique",
           "inverse",
           "coins_proximite", "coins_centre"]
