"""
LE SOL DEVANT SOI, EN CASES : ce que voit le joueur penche dans l'ecran de
craft.

Deux grilles POSEES AU SOL, DROITES (sans perspective) :

    a gauche  la PROXIMITE -- ce qui traine sur la case. Elle va du bord
              de l'ecran jusqu'a la main gauche, 5 cases de large sur 5 de
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
# hauteur. Plus bas, les mains au repos se referment vers le centre et ne
# laissent que 0,448 - 0,550 : un plan de travail pose la aurait ete a moitie
# cache par les doigts. Il commence donc juste au-dessus d'eux, droit, dans
# le couloir (0,402 - 0,598).
CENTRE_PRES = 0.29
CENTRE_LOIN = 0.55
CENTRE_DEMI = 0.098          # demi-largeur

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


def coins_centre():
    """Les quatre coins du plan de travail : un rectangle droit, entre les
    mains."""
    g, d = 0.5 - CENTRE_DEMI, 0.5 + CENTRE_DEMI
    return ((g, CENTRE_PRES), (d, CENTRE_PRES),
            (d, CENTRE_LOIN), (g, CENTRE_LOIN))


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
        plus proche, on tient l'objet juste sous la grille."""
        return self.sous(x, y + (self.y_loin - self.y_pres) / self.rangees)

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
                 **kwargs):
        super().__init__(**kwargs)
        self.depose = depose
        self.couche = couche
        self.actif = False
        self.proximite = _Grille("G", SOL_COLONNES, SOL_RANGEES,
                                 coins_proximite())
        self.centre = _Grille("C", CENTRE_COLONNES, CENTRE_RANGEES,
                              coins_centre())
        # L'INVENTAIRE n'a que la proximite : son milieu est occupe par
        # l'equipement (voir InventoryScreen).
        self.avec_centre = avec_centre
        self._cases = {}
        self._mains = [None, None]
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
    def montre(self, cases, mains):
        """{case: [objet, nombre]} (voir GameState.sol_en_cases) et ce que
        tiennent les mains (source possible d'un glisser)."""
        self._cases = {k: list(v) for k, v in (cases or {}).items()}
        self._mains = list(mains or [None, None])
        self._redessine()

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
            for g in self.grilles():
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
        self._teinte_cases()

    def _teinte_cases(self):
        """La couleur de chaque case : la visee du doigt, sinon le
        clignotement d'une cible, sinon son fond."""
        if self._glisse:
            visee, refus = self._glisse["visee"], self._glisse["refus"]
        else:
            visee, refus = self._visee_ext
        for cle, (couleur, fond) in self._couleurs.items():
            if cle == visee:
                couleur.rgba = VISEE_REFUS if refus else VISEE
            elif self._pulse is not None and cle.startswith("G:"):
                p = self._pulse
                couleur.rgba = tuple(fond[i] + (CIBLE[i] - fond[i]) * p
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

    def _dessine_objet(self, g, col, rang, pile):
        """Un objet pose dans sa case, avec son ombre et son nombre.

        IL A LA MEME TAILLE PARTOUT (TAILLE_OBJET), quelle que soit la case :
        il est centre dans la sienne, son image entiere dans un carre fixe,
        sans deformation."""
        nom, nombre = pile
        tex, couverture, _masse = _item_infos(nom)
        c = float(g.colonnes)
        cx, cy = g.point((col + 0.5) / c, g.vr(rang + 0.5))
        dx, _ = g.point((col + 1) / c, g.vr(rang + 0.5))
        _, bas = g.point((col + 0.5) / c, g.vr(rang))
        cote = self.height * TAILLE_OBJET
        # L'ombre, a plat sous l'objet.
        Color(*OMBRE)
        ow, oh = cote * 0.80, cote * 0.30
        Ellipse(pos=(cx - ow / 2.0, cy - cote * 0.42), size=(ow, oh))
        if tex is not None:
            tw, th = tex.size
            # UNE IMAGE AJOUREE EST GROSSIE, comme dans la main (voir
            # player_hands) : une brindille couvre un dixieme de son cadre,
            # elle disparaissait sinon. Meme regle, meme plafond.
            grossi = 1.0
            if 0.0 < couverture < COUVERTURE_PLEINE:
                grossi = min(GROSSISSEMENT_MAX,
                             (COUVERTURE_PLEINE / couverture) ** 0.5)
            boite = cote * grossi
            rapport = float(tw) / max(1, th)
            iw, ih = (boite, boite / rapport) if rapport >= 1.0 \
                else (boite * rapport, boite)
            Color(1, 1, 1, 1)
            Rectangle(texture=tex, pos=(cx - iw / 2.0, cy - ih / 2.0),
                      size=(iw, ih))
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
