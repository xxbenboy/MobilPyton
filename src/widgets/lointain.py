"""
LE LOINTAIN : les paysages tres lointains, a l'horizon, tout autour du
joueur -- chaines de montagnes a trente ou soixante kilometres, monts plus
proches, collines, lacs qui brillent, lisieres de forets.

Ils ne dependent PAS des cases voisines : une plaine entouree de plaines
paraissait vide, le ciel touchant l'herbe. Ils sont ancres dans le MONDE, par
grandes regions (voir COUCHES) : en marchant d'une case, on les voit glisser
un peu, comme de vrais paysages lointains, sans qu'ils changent.

UN ANGLE DE VUE REALISTE. Un element de hauteur H (metres) a D metres se
voit sous l'angle atan(H / D), moins la courbure de la Terre : un massif de
2000 m a 25 km depasse l'horizon d'environ 4,5 degres, une lisiere de foret a
2 km d'un demi-degre. Le pied de tout ce qui est loin est a l'horizon de
l'oeil ; le terrain de la case (sa crete, voir sol.py) le recouvre la ou il
se dresse, et le laisse voir dans ses creux.

LA BRUME DU LOINTAIN. Plus un paysage est loin, plus sa couleur se fond dans
celle du ciel, celle qui est vraiment affichee a l'horizon (aube, couchant,
meteo) : voir set_brume. La lumiere du jour l'assombrit la nuit (set_teinte).

PAS DE CALCUL A CHAQUE IMAGE : le lointain est construit une fois par case
(regle), en degres ; tourner la tete ne fait que le deplacer (set_camera),
comme le ciel. Il est dessine ENTRE le ciel et les silhouettes des cases
voisines (voir game_screen et vue360).
"""
import math
import random

from kivy.graphics import Color, Mesh, PopMatrix, PushMatrix, Translate
from kivy.uix.widget import Widget

FOV = 90.0
# Une case du monde fait un kilometre de cote.
CASE_M = 1000.0
RAYON_TERRE = 6371000.0
OEIL = 1.6
# Le lointain est construit de AZ_MIN a AZ_MAX degres : de quoi couvrir
# l'ecran pour tout regard entre 0 et 360 degres, sans couture.
AZ_MIN, AZ_MAX = -60.0, 420.0
# Le bas de la TERRE LOINTAINE, sous l'horizon : la crete d'une plaine
# descend jusqu'a deux degres sous l'oeil ; elle recouvre le reste. Les
# reliefs, eux, s'arretent a PIED, un rien sous l'horizon (sans jour avec la
# terre) : on ne voit pas le corps d'une montagne a 40 km sous un lac a 5.
BAS = -3.0
PIED = -0.05
# LA BRUME : une couleur a D metres se fond dans le ciel pour la part
# 1 - exp(-D / PORTEE_BRUME).
PORTEE_BRUME = 50000.0
# LE FLANC A L'OMBRE d'un sommet (celui de droite) : sa couleur, de cette
# part plus sombre. Le relief s'y lit, meme noye de brume.
OMBRE_FLANC = 0.80
# LA NEIGE coiffe les sommets de plus de NEIGE_M metres, sur le haut de leur
# silhouette.
NEIGE_M = 1900.0
NEIGE_HAUT = 0.80
NEIGE_EPAIS = 0.14
BLANC_NEIGE = (0.94, 0.95, 0.99)
BRUME_NEIGE = 0.60

# LES COUCHES, du plus loin au plus pres. Chacune est semee par REGIONS de
# `maille` kilometres : une region porte ses elements avec la probabilite
# `part`, a une distance comprise dans `portee` (km) du joueur.
#   cle       : nom (et graine) de la couche
#   maille    : cote d'une region (km)
#   part      : chance qu'une region porte un element
#   portee    : distances ou il se voit (km)
#   haut      : hauteur reelle (m), tiree entre ces bornes
#   large     : demi-largeur reelle (m)
#   pics      : nombre de sommets par element (un massif en a plusieurs)
#   forme     : "pic" (aretes vives), "dos" (collines rondes), "lisiere"
#               (cime d'une foret, dentelee), "lac" (une lame d'eau)
#   couleur   : couleur propre, avant la brume
#   pas       : finesse de la silhouette (degres)
COUCHES = (
    {"cle": "cimes", "maille": 20.0, "part": 0.60, "portee": (22.0, 60.0),
     "haut": (1800.0, 4000.0), "large": (3500.0, 9000.0), "pics": (3, 6),
     "forme": "pic", "couleur": (0.42, 0.46, 0.55), "pas": 0.35},
    {"cle": "monts", "maille": 11.0, "part": 0.45, "portee": (11.0, 26.0),
     "haut": (700.0, 2000.0), "large": (2000.0, 5500.0), "pics": (2, 4),
     "forme": "pic", "couleur": (0.34, 0.38, 0.42), "pas": 0.30},
    {"cle": "collines", "maille": 5.0, "part": 0.55, "portee": (4.5, 13.0),
     "haut": (80.0, 300.0), "large": (1200.0, 3600.0), "pics": (1, 3),
     "forme": "dos", "couleur": (0.27, 0.34, 0.23), "pas": 0.30},
    {"cle": "lacs", "maille": 6.0, "part": 0.40, "portee": (2.5, 8.0),
     "haut": (0.0, 0.0), "large": (700.0, 2600.0), "pics": (1, 1),
     "forme": "lac", "couleur": (0.70, 0.80, 0.90), "pas": 0.25},
    {"cle": "forets", "maille": 3.0, "part": 0.50, "portee": (1.3, 4.5),
     "haut": (15.0, 25.0), "large": (500.0, 2200.0), "pics": (1, 1),
     "forme": "lisiere", "couleur": (0.13, 0.21, 0.13), "pas": 0.12},
)
# LA TERRE LOINTAINE, sous tous les reliefs : la plaine qui s'etend jusqu'a
# l'horizon, a mi-brume.
TERRE = {"couleur": (0.30, 0.36, 0.22), "brume": 0.45}
# L'eau d'un lac lointain renvoie le ciel, un peu eclairci.
ECLAT_LAC = 1.10
# Dans une brume epaisse (fog_level 1), le lointain s'efface de cette part.
EFFACE_BROUILLARD = 0.88


def ecart(a):
    """Un angle ramene entre -180 et 180 degres."""
    return (a + 180.0) % 360.0 - 180.0


def angle_vu(hauteur, distance):
    """L'angle (degres) sous lequel l'oeil voit le haut d'un relief de
    `hauteur` metres a `distance` metres, courbure de la Terre comprise."""
    chute = distance * distance / (2.0 * RAYON_TERRE)
    return math.degrees(math.atan2(hauteur - OEIL - chute, distance))


def _brume(distance):
    return 1.0 - math.exp(-distance / PORTEE_BRUME)


def elements(graine, x, y):
    """Les elements lointains vus de la case (x, y) du monde, couche par
    couche : {cle: [element]}, chaque element un dict (az, distance, haut,
    demi-largeur angulaire, forme, alea)."""
    out = {}
    for c in COUCHES:
        maille = c["maille"]
        dmin, dmax = c["portee"]
        r = int(math.ceil(dmax / maille)) + 1
        mx0, my0 = int(math.floor(x / maille)), int(math.floor(y / maille))
        lst = []
        for my in range(my0 - r, my0 + r + 1):
            for mx in range(mx0 - r, mx0 + r + 1):
                h = random.Random("%s:lointain:%s:%d:%d"
                                  % (graine, c["cle"], mx, my))
                if h.random() >= c["part"]:
                    continue
                cx = (mx + h.uniform(0.15, 0.85)) * maille
                cy = (my + h.uniform(0.15, 0.85)) * maille
                base = h.uniform(*c["haut"])
                for k in range(h.randint(*c["pics"])):
                    # Les sommets d'un massif, autour de son centre.
                    ex = cx + h.uniform(-0.25, 0.25) * maille * (k > 0)
                    ey = cy + h.uniform(-0.25, 0.25) * maille * (k > 0)
                    dx, dy = (ex - x) * CASE_M, (ey - y) * CASE_M
                    d = math.hypot(dx, dy)
                    if not (dmin * 1000.0 <= d <= dmax * 1000.0):
                        continue
                    haut = base * (1.0 if k == 0 else h.uniform(0.55, 0.95))
                    large = h.uniform(*c["large"])
                    lst.append({
                        # Le nord est vers les y decroissants (comme les
                        # cases voisines, voir horizon.voisin_dans).
                        "az": math.degrees(math.atan2(dx, -dy)) % 360.0,
                        "d": d, "haut": haut,
                        "w": math.degrees(math.atan2(large, d)),
                        "phase": h.uniform(0.0, 6.283),
                        "neige": c["forme"] == "pic" and haut >= NEIGE_M})
        out[c["cle"]] = lst
    return out


def profil(couche, lst):
    """La silhouette d'une couche : [(az, haut, bas, sommet, neige, ombre)]
    tous les `pas` degres de AZ_MIN a AZ_MAX -- le haut et le bas de la
    bande (degres), le sommet de l'element qui la domine, s'il est enneige,
    et si l'on est sur son flanc a l'ombre (a droite du sommet).

    LE MEME A UN TOUR PRES : la silhouette est calculee sur un seul tour et
    repetee, et ses ressauts se comptent depuis le sommet de chaque element.
    Calculee directement de AZ_MIN a AZ_MAX, elle differait d'un tour a
    l'autre, et les sommets sautaient quand le regard passait le nord."""
    n0 = max(1, int(round(360.0 / couche["pas"])))
    pas = 360.0 / n0
    hauts = [None] * n0
    sommets = [0.0] * n0
    dominant = [None] * n0
    flancs = [False] * n0
    forme = couche["forme"]
    for i, e in enumerate(lst):
        p = angle_vu(e["haut"], e["d"]) if forme != "lac" else 0.0
        w = max(0.05, e["w"])
        k0 = int(math.floor((e["az"] - w) / pas))
        k1 = int(math.ceil((e["az"] + w) / pas))
        for kk in range(k0, k1 + 1):
            k = kk % n0
            s = ecart(kk * pas - e["az"])      # depuis le sommet
            t = abs(s) / w
            if t >= 1.0:
                continue
            if forme == "pic":
                v = p * (1.0 - t) ** 1.25
                # Des aretes : le relief se casse en ressauts.
                v *= 1.0 + 0.07 * math.sin(s * 0.9 + e["phase"]) \
                    + 0.04 * math.sin(s * 2.3 + 2 * e["phase"])
            elif forme == "dos":
                v = p * math.cos(t * math.pi / 2.0) ** 2
            elif forme == "lisiere":
                bord = min(1.0, (1.0 - t) / 0.12)
                v = p * bord * (0.82 + 0.10 * math.sin(s * 14.0 + e["phase"])
                                + 0.08 * math.sin(s * 31.0))
            else:                                   # un lac : une lame
                v = 0.0
            if hauts[k] is None or v > hauts[k]:
                hauts[k] = v
                sommets[k] = p
                dominant[k] = i
                flancs[k] = s > 0.0
    # UN SOMMET CACHE (derriere un plus haut du meme massif) n'a ni neige ni
    # flanc a l'ombre : on ne voit pas son sommet, il ne gagnait que quelques
    # points dans un col, et y laissait des carres de neige flottants.
    visibles = {dominant[int(round(e["az"] / pas)) % n0]
                for e in lst} - {None}
    out = []
    for kk in range(int(math.floor(AZ_MIN / pas)),
                    int(math.ceil(AZ_MAX / pas)) + 1):
        k = kk % n0
        az = kk * pas
        if hauts[k] is None:
            out.append((az, BAS, BAS, 0.0, False, False))
        elif forme == "lac":
            # La lame d'eau, a peine sous l'horizon de l'oeil.
            out.append((az, 0.0, -0.22, 0.0, False, False))
        else:
            vu = dominant[k] in visibles
            # Le relief s'arrete a l'horizon de l'oeil (PIED) : sous lui,
            # c'est la terre lointaine et les lacs, plus pres, qu'on voit.
            out.append((az, max(0.0, hauts[k]), PIED, sommets[k],
                        vu and lst[dominant[k]]["neige"],
                        vu and flancs[k] and forme == "pic"))
    return out


class Lointain(Widget):
    """Les paysages lointains, sur tout le tour (voir le haut du fichier).
    `regle(graine, x, y)` a chaque case, `set_camera(lacet, tangage)` a
    chaque regard, `set_teinte(rgb)` et `set_brume(rgb)` avec la lumiere."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.horizon = 0.49
        self.lacet = 0.0
        self.tangage = 0.0
        self._profils = []          # [(couche, profil, distance type)]
        self._jour = (1.0, 1.0, 1.0)
        self._ciel = (0.70, 0.80, 0.90)
        self._brouillard = 0.0
        self._cle = None
        self._couleurs = []         # [(Color, couleur propre, brume, eau)]
        with self.canvas:
            PushMatrix()
            self._t = Translate(0, 0)
        with self.canvas.after:
            PopMatrix()
        self.bind(size=self._construit, pos=self._place)

    # -- la case ------------------------------------------------------------ #
    def regle(self, graine, x, y):
        cle = (graine, int(x), int(y))
        if cle == self._cle:
            return
        self._cle = cle
        tout = elements(graine, x, y)
        self._profils = []
        for c in COUCHES:
            lst = tout.get(c["cle"], [])
            dist = (sum(e["d"] for e in lst) / len(lst)) if lst else \
                sum(c["portee"]) * 500.0
            self._profils.append((c, profil(c, lst), dist))
        self._construit()

    # -- le dessin (une fois par case, ou si la taille change) -------------- #
    def _construit(self, *_):
        self.canvas.remove_group("lointain")
        self._couleurs = []
        if self.width <= 0 or self.height <= 0 or not self._profils:
            self._place()
            return
        ppd = self.width / FOV
        with self.canvas:
            # La terre lointaine, sous tout le reste.
            c = Color(1, 1, 1, 1, group="lointain")
            self._couleurs.append((c, TERRE["couleur"], TERRE["brume"], False))
            self._bande([(AZ_MIN, 0.0, BAS), (AZ_MAX, 0.0, BAS)], ppd)
            for couche, prof, dist in self._profils:
                eau = couche["forme"] == "lac"
                c = Color(1, 1, 1, 1, group="lointain")
                self._couleurs.append((c, couche["couleur"], _brume(dist),
                                       eau))
                self._bande([(az, haut, bas) if haut > bas else None
                             for az, haut, bas, _s, _n, _o in prof], ppd)
                if any(o for *_r, o in prof):
                    # Le flanc a l'ombre de chaque sommet, par-dessus.
                    c = Color(1, 1, 1, 1, group="lointain")
                    self._couleurs.append((c, tuple(
                        v * OMBRE_FLANC for v in couche["couleur"]),
                        _brume(dist), False))
                    self._bande([(az, haut, bas) if o and haut > bas else None
                                 for az, haut, bas, _s, _n, o in prof], ppd)
                if any(n for *_r, n, _o in prof):
                    c = Color(1, 1, 1, 1, group="lointain")
                    # La neige reste vive de loin : moins noyee de brume.
                    self._couleurs.append((c, BLANC_NEIGE,
                                           _brume(dist) * BRUME_NEIGE, False))
                    self._bande(self._neige(prof), ppd)
        self._applique()
        self._place()

    @staticmethod
    def _neige(prof):
        """La neige des sommets : le haut de leur silhouette, au-dessus de
        NEIGE_HAUT de leur hauteur, sur NEIGE_EPAIS au plus."""
        out = []
        for az, haut, _bas, sommet, neige, _ombre in prof:
            if neige and haut > NEIGE_HAUT * sommet:
                out.append((az, haut, max(NEIGE_HAUT * sommet,
                                          haut - NEIGE_EPAIS * sommet)))
            else:
                out.append(None)
        return out

    def _bande(self, points, ppd):
        """Un ruban de (az, haut, bas) en degres, en un seul Mesh. Un point
        None interrompt le ruban : relie a un point absent, le ruban
        tirait une fine lame jusqu'en bas de la bande."""
        verts, idx = [], []
        prec = None
        for az_haut_bas in points:
            if az_haut_bas is None:
                prec = None
                continue
            az, haut, bas = az_haut_bas
            x = az * ppd
            n = len(verts) // 4
            verts += [x, bas * ppd, 0.0, 0.0, x, haut * ppd, 0.0, 0.0]
            if prec is not None:
                idx += [prec, prec + 1, n + 1, prec, n + 1, n]
            prec = n
        if idx:
            Mesh(vertices=verts, indices=idx, mode="triangles",
                 group="lointain")

    # -- le regard ---------------------------------------------------------- #
    def set_camera(self, lacet, tangage):
        self.lacet = float(lacet) % 360.0
        self.tangage = float(tangage)
        self._place()

    def _place(self, *_):
        ppd = self.width / FOV if self.width > 0 else 1.0
        self._t.x = self.center_x - self.lacet * ppd
        self._t.y = self.y + self.horizon * self.height - self.tangage * ppd

    # -- la lumiere --------------------------------------------------------- #
    def set_teinte(self, rgb):
        """La lumiere du jour (doree le matin, sombre la nuit)."""
        self._jour = tuple(float(v) for v in rgb[:3])
        self._applique()

    def set_brume(self, rgb, brouillard=0.0):
        """La couleur du ciel a l'horizon, ou le lointain se fond.
        `brouillard` : l'epaisseur de la brume VUE ici et maintenant (0 a 1,
        voir GameState.fog_level) ; le lointain s'y efface d'autant."""
        self._ciel = tuple(float(v) for v in rgb[:3])
        self._brouillard = max(0.0, min(1.0, float(brouillard)))
        self._applique()

    def _applique(self):
        f = EFFACE_BROUILLARD * self._brouillard
        for c, propre, k, eau in self._couleurs:
            k = k + (1.0 - k) * f
            if eau:
                # L'eau renvoie le ciel, eclairci : elle brille au loin --
                # et s'efface comme le reste dans la brume.
                vu = tuple(min(1.0, v * ECLAT_LAC + 0.03) for v in self._ciel)
                col = tuple(a * 0.75 + b * 0.25 for a, b in zip(vu, propre))
                c.rgb = tuple(a * (1.0 - f) + b * f
                              for a, b in zip(col, self._ciel))
                continue
            vu = tuple(p * j for p, j in zip(propre, self._jour))
            c.rgb = tuple(a * (1.0 - k) + b * k for a, b in zip(vu, self._ciel))


__all__ = ["Lointain", "elements", "profil", "angle_vu", "COUCHES"]
