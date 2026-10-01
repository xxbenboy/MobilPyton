"""
LE SOL DEVANT SOI, EN CASES : ce que voit le joueur penche dans l'ecran de
craft.

Deux grilles POSEES AU SOL, en perspective :

    a gauche  la PROXIMITE -- ce qui traine sur la case. Elle va du bord
              de l'ecran jusqu'a la main gauche, 4 cases de large sur 7 de
              profondeur. C'est le meme sol que la colonne "a proximite" de
              l'inventaire : ce qui est ici y est aussi, et inversement (voir
              GameState.sol_en_cases) ;
    au centre le PLAN DE TRAVAIL, 4 sur 4, dans l'ecart entre les deux
              mains. Toujours visible, d'un gris leger. Pour l'instant rien
              ne s'y passe : on y pose des objets, c'est tout.
    a droite  rien pour l'instant -- la place du resultat, plus tard.

Les objets se GLISSENT d'une case a l'autre, du sol vers une main et d'une
main vers le sol (ou vers l'autre main). Ce widget ne sait que dessiner et
suivre le doigt : ce que devient l'objet, c'est l'ecran qui en decide (voir
`depose`), parce que c'est lui qui connait l'etat du jeu.

POURQUOI DES COINS FIXES, ET PAS LA PERSPECTIVE DU DECOR. Le decor du jeu
converge tres fort (voir GROUND_DEPTH) : une grille qui la suivrait
exactement irait, depuis le bord gauche, se ranger sous la main gauche, puis
au milieu de l'ecran. La demande est une DISPOSITION -- un tiers a gauche
jusqu'a la main, un tiers entre les mains. Chaque grille est donc un
quadrilatere dont les coins sont choisis pour cela, et dont les bords
fuient vers un point de l'horizon (HORIZON_GRILLES) : elle se lit posee a
plat sur le sol, et ne passe jamais sous une main.

LA PERSPECTIVE DES CASES EST EXACTE, elle : chaque grille est l'image d'un
rectangle par une HOMOGRAPHIE (la transformation d'une photo de sol plat).
Les rangees se resserrent donc en s'eloignant comme sur un vrai carrelage,
et le doigt retrouve sa case par la transformation inverse.
"""
from kivy.graphics import Color, Ellipse, Line, Mesh, Rectangle
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.metrics import dp

from src.game_state import (SOL_COLONNES, SOL_RANGEES, CENTRE_COLONNES,
                            CENTRE_RANGEES)
from src.widgets.player_hands import (PlayerHands, _item_infos,
                                      COUVERTURE_PLEINE, GROSSISSEMENT_MAX)

# L'horizon vers lequel fuient les bords des grilles, en part de la hauteur.
# C'est celui du decor une fois le joueur penche (voir
# craft_screen.HORIZON_PENCHE) : les grilles et le sol partagent la meme
# ligne de fuite.
HORIZON_GRILLES = 0.93

# --- LA PROXIMITE (a gauche) ------------------------------------------- #
# Son bord proche va du bord de l'ecran jusqu'a la main gauche. MESURE sur
# les images des mains, toutes poses et gants confondus : le bord gauche de
# la main gauche ne descend jamais sous 0,287 de la largeur. Le bord droit de
# la grille est pose a 0,28 et fuit VERS LE HAUT, a la verticale : il longe
# la main sans jamais passer dessous.
PROX_GAUCHE = 0.012
PROX_DROITE = 0.28
PROX_PRES = 0.03
PROX_LOIN = 0.52

# --- LE PLAN DE TRAVAIL (au centre) ----------------------------------- #
# MESURE, toutes poses et gants confondus : entre les deux mains, le couloir
# libre ne descend jamais sous 0,393 - 0,607 AU-DESSUS de 0,28 de la
# hauteur. Plus bas, les mains au repos se referment vers le centre et ne
# laissent que 0,448 - 0,550 : un plan de travail pose la aurait ete a moitie
# cache par les doigts. Il commence donc juste au-dessus d'eux, et fuit vers
# le milieu de l'horizon.
CENTRE_PRES = 0.29
CENTRE_LOIN = 0.55
CENTRE_DEMI = 0.098          # demi-largeur du bord proche

# Couleurs. Le plan de travail est TOUJOURS visible, d'un gris leger ; la
# proximite n'a qu'un trace discret -- c'est le sol, pas un meuble.
GRIS_CENTRE = (0.88, 0.89, 0.90, 0.16)
TRAIT_CENTRE = (0.92, 0.93, 0.95, 0.50)
GRIS_PROX = (1.0, 1.0, 1.0, 0.04)
TRAIT_PROX = (1.0, 1.0, 1.0, 0.20)
# La case sous le doigt, pendant un glisser.
VISEE = (0.55, 1.00, 0.65, 0.34)
VISEE_REFUS = (1.00, 0.45, 0.40, 0.30)

# Part de la case qu'occupe un objet, et son ombre.
OBJET_PART = 0.80
OMBRE = (0.0, 0.0, 0.0, 0.28)
# Un objet pose au sol se lit ECRASE par la perspective : sa hauteur suit
# celle de sa case (voir _dessine_objet), dans ces bornes.
ECRASE_MIN, ECRASE_MAX = 0.50, 0.95

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

    Ses bords fuient vers un point de l'horizon a la verticale de son bord
    droit : c'est ce qui garde ce bord hors de la main gauche."""
    vx, vy = PROX_DROITE, HORIZON_GRILLES
    loin_g = fuite(PROX_GAUCHE, PROX_PRES, vx, vy, PROX_LOIN)
    return ((PROX_GAUCHE, PROX_PRES), (PROX_DROITE, PROX_PRES),
            (PROX_DROITE, PROX_LOIN), loin_g)


def coins_centre():
    """Les quatre coins du plan de travail : il fuit vers le milieu de
    l'horizon, et se resserre donc entre les mains en s'eloignant."""
    vx, vy = 0.5, HORIZON_GRILLES
    g, d = 0.5 - CENTRE_DEMI, 0.5 + CENTRE_DEMI
    return ((g, CENTRE_PRES), (d, CENTRE_PRES),
            fuite(d, CENTRE_PRES, vx, vy, CENTRE_LOIN),
            fuite(g, CENTRE_PRES, vx, vy, CENTRE_LOIN))


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
        pts = [(x + fx * w, y + fy * h) for fx, fy in self.coins]
        self.m = homographie(*pts)
        self.m_inv = inverse(self.m)

    def point(self, u, v):
        return applique(self.m, u, v)

    def case_de(self, col, rang):
        return "%s:%d" % (self.prefixe, rang * self.colonnes + col)

    def col_rang(self, cle):
        i = int(cle.split(":")[1])
        return i % self.colonnes, i // self.colonnes

    def coins_case(self, col, rang):
        c, r = float(self.colonnes), float(self.rangees)
        return [self.point(col / c, rang / r),
                self.point((col + 1) / c, rang / r),
                self.point((col + 1) / c, (rang + 1) / r),
                self.point(col / c, (rang + 1) / r)]

    def sous(self, x, y):
        """La case sous le point (x, y) de l'ecran, ou None."""
        u, v = applique(self.m_inv, x, y)
        if not (0.0 <= u < 1.0 and 0.0 <= v < 1.0):
            return None
        return self.case_de(int(u * self.colonnes), int(v * self.rangees))

    def cles(self):
        return [self.case_de(c, r) for r in range(self.rangees)
                for c in range(self.colonnes)]


class SolDeCraft(Widget):
    """Les deux grilles, les objets qui y sont poses, et le glisser.

    `depose(source, cible)` est appele au lacher, avec deux couples
    ("case", "G:3") / ("main", 0) ; il rend True si le depot a eu lieu.
    `couche` est le widget ou se dessine l'objet qui suit le doigt : il doit
    passer par-dessus les mains."""

    def __init__(self, depose=None, couche=None, **kwargs):
        super().__init__(**kwargs)
        self.depose = depose
        self.couche = couche
        self.actif = False
        self.proximite = _Grille("G", SOL_COLONNES, SOL_RANGEES,
                                 coins_proximite())
        self.centre = _Grille("C", CENTRE_COLONNES, CENTRE_RANGEES,
                              coins_centre())
        self._cases = {}
        self._mains = [None, None]
        self._glisse = None
        self._nombres = []
        self.bind(pos=self._redessine, size=self._redessine)

    # -- ce que montre le sol ------------------------------------------ #
    def montre(self, cases, mains):
        """{case: [objet, nombre]} (voir GameState.sol_en_cases) et ce que
        tiennent les mains (source possible d'un glisser)."""
        self._cases = {k: list(v) for k, v in (cases or {}).items()}
        self._mains = list(mains or [None, None])
        self._redessine()

    def grilles(self):
        return (self.proximite, self.centre)

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
        visee = self._glisse["visee"] if self._glisse else None
        refus = self._glisse["refus"] if self._glisse else False
        with self.canvas:
            self._dessine_grille(self.proximite, GRIS_PROX, TRAIT_PROX, visee,
                                 refus)
            self._dessine_grille(self.centre, GRIS_CENTRE, TRAIT_CENTRE,
                                 visee, refus)
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

    def _dessine_grille(self, g, fond, trait, visee, refus):
        for rang in range(g.rangees):
            for col in range(g.colonnes):
                cle = g.case_de(col, rang)
                if cle == visee:
                    Color(*(VISEE_REFUS if refus else VISEE))
                else:
                    Color(*fond)
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
            v = rang / float(g.rangees)
            a, b = g.point(0.0, v), g.point(1.0, v)
            Line(points=[a[0], a[1], b[0], b[1]], width=largeur)

    def _dessine_objet(self, g, col, rang, pile):
        """Un objet pose au sol dans sa case, avec son ombre et son nombre.

        IL EST ECRASE PAR LA PERSPECTIVE, a la mesure de sa case : une case
        lointaine est plus basse que large, l'objet qui y repose aussi. Sans
        cela il se tiendrait debout face au joueur, comme une carte a jouer
        plantee dans la terre."""
        nom, nombre = pile
        tex, couverture, _masse = _item_infos(nom)
        c, r = float(g.colonnes), float(g.rangees)
        cx, cy = g.point((col + 0.5) / c, (rang + 0.5) / r)
        gx, _ = g.point(col / c, (rang + 0.5) / r)
        dx, _ = g.point((col + 1) / c, (rang + 0.5) / r)
        _, bas = g.point((col + 0.5) / c, rang / r)
        _, haut = g.point((col + 0.5) / c, (rang + 1) / r)
        larg_case, haut_case = dx - gx, haut - bas
        ecrase = max(ECRASE_MIN, min(ECRASE_MAX,
                                     1.6 * haut_case / max(1.0, larg_case)))
        # L'ombre, a plat sous l'objet.
        Color(*OMBRE)
        ow, oh = larg_case * 0.78, haut_case * 0.42
        Ellipse(pos=(cx - ow / 2.0, cy - oh * 0.75), size=(ow, oh))
        if tex is None:
            return
        tw, th = tex.size
        # UNE IMAGE AJOUREE EST GROSSIE, comme dans la main (voir
        # player_hands) : une brindille couvre un dixieme de son cadre, et
        # dans une case du fond elle disparaissait. Meme regle, meme plafond.
        grossi = 1.0
        if 0.0 < couverture < COUVERTURE_PLEINE:
            grossi = min(GROSSISSEMENT_MAX,
                         (COUVERTURE_PLEINE / couverture) ** 0.5)
        iw = larg_case * OBJET_PART * grossi
        ih = iw * float(th) / max(1, tw) * ecrase
        if ih > haut_case * 1.9:
            # Un objet tres haut (une branche dressee) ne deborde pas sur la
            # case de derriere.
            iw *= haut_case * 1.9 / ih
            ih = haut_case * 1.9
        Color(1, 1, 1, 1)
        Rectangle(texture=tex, pos=(cx - iw / 2.0, cy - ih * 0.35),
                  size=(iw, ih))
        if nombre > 1:
            lbl = Label(text="x%d" % nombre, bold=True,
                        color=(1, 1, 1, 0.95),
                        font_size=max(dp(9), haut_case * 0.34))
            lbl.size = (larg_case * 0.5, haut_case * 0.45)
            lbl.pos = (dx - lbl.size[0] - larg_case * 0.04,
                       bas + haut_case * 0.02)
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

    def objet_de(self, cible):
        if cible is None:
            return None
        if cible[0] == "case":
            pile = self._cases.get(cible[1])
            return pile[0] if pile else None
        return self._mains[cible[1]]

    # -- le glisser ---------------------------------------------------- #
    def on_touch_down(self, touch):
        if not self.actif:
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
        cible = self.sous_le_doigt(touch.x, touch.y)
        visee = cible[1] if cible and cible[0] == "case" else None
        refus = self._refuse(g, cible)
        if visee != g["visee"] or refus != g["refus"]:
            g["visee"], g["refus"] = visee, refus
            self._redessine()
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
            cible = self.sous_le_doigt(touch.x, touch.y)
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
        if g["source"][0] == "case" and cible[0] == "main":
            return dessus is not None
        if g["source"][0] == "main" and cible[0] == "case":
            return dessus is not None and dessus != g["nom"]
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


__all__ = ["SolDeCraft", "homographie", "applique", "inverse",
           "coins_proximite", "coins_centre"]
