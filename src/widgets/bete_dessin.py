"""
LES BETES, DESSINEES A LA MAIN -- pour l'instant.

Il n'y a pas encore d'images de chevreuil, de sanglier ni d'orignal : elles
sont tracees ici au trait, comme les papillons et les abeilles de
widgets/insects.py. C'est provisoire et c'est assume -- le jour ou les
images arriveront, c'est ce seul fichier qui changera, et rien d'autre dans
le jeu ne s'en apercevra.

TOUT EST EN HAUTEURS AU GARROT. Chaque bete est decrite dans un repere ou le
sol vaut 0, le haut du dos vaut 1, et l'avant est le +x : `P(u, v)` ramene
ces mesures a l'ecran. On lit donc le dessin comme un croquis cote, et une
bete deux fois plus grande n'a rien a changer.

TROIS SILHOUETTES, et on doit les reconnaitre de loin, petites et a
contre-jour. Ce qui les distingue n'est donc pas le detail mais la
CHARPENTE :

    CHEVREUIL  haut sur pattes, fin, l'encolure dressee, le miroir blanc a
               la croupe, de grandes oreilles ;
    SANGLIER   bas et en coin -- massif de l'avant, la tete portee dans le
               prolongement du dos, le groin au ras du sol ;
    ORIGNAL    enorme, la bosse du garrot plus haute que la croupe, le
               museau lourd et tombant, le fanon sous la gorge, les bois en
               palettes.

Deux vues, parce que le jeu regarde la case de deux facons :
`dessine()` DE PROFIL pour la scene, `glyphe()` DE DESSUS pour la grille de
l'ecran Zone -- comme draw_nature_glyph le fait pour les arbres.
"""
import math

from kivy.graphics import Color, Ellipse, Line, Quad, Triangle

from src.animaux import CHEVREUIL, SANGLIER, ORIGNAL

# La robe de chaque espece : le dos, le ventre (plus clair) et les parties a
# l'ombre -- pattes du fond, dessous de la tete.
ROBES = {
    CHEVREUIL: ((0.63, 0.42, 0.24), (0.82, 0.68, 0.50), (0.38, 0.25, 0.14)),
    SANGLIER: ((0.32, 0.28, 0.26), (0.47, 0.42, 0.38), (0.17, 0.15, 0.14)),
    ORIGNAL: ((0.28, 0.20, 0.14), (0.42, 0.33, 0.23), (0.16, 0.11, 0.08)),
}
SABOT = (0.09, 0.08, 0.07)
OEIL = (0.05, 0.04, 0.04)
BOIS = (0.58, 0.49, 0.36)
IVOIRE = (0.93, 0.91, 0.82)

# La boite de chaque espece dans son repere : (u mini, u maxi, v maxi). Elle
# sert au mode action, qui a besoin de la place de la bete A L'ECRAN avant
# meme de l'avoir dessinee.
BOITES = {
    CHEVREUIL: (-0.68, 1.06, 1.58),
    SANGLIER: (-0.68, 1.10, 1.14),
    ORIGNAL: (-0.62, 1.26, 1.70),
}


def boite(espece, cx, base, haut, sens=1.0):
    """(x0, y0, x1, y1) de la bete a l'ecran, sans la dessiner."""
    u0, u1, v1 = BOITES.get(espece, BOITES[CHEVREUIL])
    xa = cx + sens * u0 * haut
    xb = cx + sens * u1 * haut
    return (min(xa, xb), base, max(xa, xb), base + v1 * haut)


def _c(col, alpha=1.0):
    Color(col[0], col[1], col[2], alpha)


class _Repere(object):
    """Le croquis cote : u vers l'avant, v vers le haut, en hauteurs au
    garrot. Toutes les formes passent par lui."""

    __slots__ = ("cx", "base", "h", "sens", "alpha")

    def __init__(self, cx, base, h, sens, alpha):
        self.cx, self.base, self.h = cx, base, h
        self.sens, self.alpha = (1.0 if sens >= 0 else -1.0), alpha

    def p(self, u, v):
        return self.cx + self.sens * u * self.h, self.base + v * self.h

    def ell(self, u, v, lu, lv, col=None):
        if col is not None:
            _c(col, self.alpha)
        x, y = self.p(u, v)
        w, hh = lu * self.h, lv * self.h
        Ellipse(pos=(x - w / 2.0, y - hh / 2.0), size=(w, hh))

    def quad(self, pts, col=None):
        if col is not None:
            _c(col, self.alpha)
        Quad(points=[c for u, v in pts for c in self.p(u, v)])

    def tri(self, pts, col=None):
        if col is not None:
            _c(col, self.alpha)
        Triangle(points=[c for u, v in pts for c in self.p(u, v)])

    def trait(self, a, b, ep, col=None):
        if col is not None:
            _c(col, self.alpha)
        x0, y0 = self.p(*a)
        x1, y1 = self.p(*b)
        Line(points=[x0, y0, x1, y1], width=max(1.0, ep * self.h))

    def patte(self, u, v_haut, ep, col, sabot=True):
        """Une patte : un fuseau du corps au sol, et son sabot."""
        _c(col, self.alpha)
        self.quad([(u - ep, v_haut), (u + ep, v_haut),
                   (u + ep * 0.5, 0.0), (u - ep * 0.5, 0.0)])
        if sabot:
            self.ell(u, ep * 0.5, ep * 2.4, ep * 1.6, SABOT)

    def ombre(self, long_):
        Color(0, 0, 0, 0.26 * self.alpha)
        self.ell(0.1, 0.012, long_, long_ * 0.16)


def dessine(espece, cx, base, haut, sens=1.0, alpha=1.0, ombre=True):
    """Une bete DE PROFIL, posee par les sabots en (cx, base) et haute de
    `haut` pixels au garrot. `sens` : +1 elle regarde a droite, -1 a gauche.

    Renvoie sa boite (x0, y0, x1, y1) -- c'est elle que le mode action fait
    clignoter, et que vise la chasse."""
    if haut <= 0:
        return (cx, base, cx, base)
    r = _Repere(cx, base, haut, sens, alpha)
    {SANGLIER: _sanglier, ORIGNAL: _orignal}.get(espece, _chevreuil)(r, ombre)
    return boite(espece, cx, base, haut, sens)


# --------------------------------------------------------------------- #
# LE CHEVREUIL : haut sur pattes, fin, l'encolure dressee
# --------------------------------------------------------------------- #
def _chevreuil(r, ombre):
    dos, ventre, sombre = ROBES[CHEVREUIL]
    if ombre:
        r.ombre(1.5)
    ep = 0.030
    # Les deux pattes du FOND, plus sombres et posees avant le corps.
    r.patte(0.30, 0.66, ep, sombre, sabot=False)
    r.patte(-0.36, 0.66, ep, sombre, sabot=False)
    # LE TRONC : un corps un peu fuyant vers la croupe, ferme par deux
    # rondeurs -- le poitrail devant, la cuisse derriere.
    r.quad([(-0.52, 0.96), (0.48, 1.00), (0.50, 0.62), (-0.50, 0.58)], dos)
    r.ell(0.42, 0.80, 0.44, 0.42, dos)
    r.ell(-0.42, 0.80, 0.48, 0.44, dos)
    r.ell(0.00, 0.66, 0.82, 0.22, ventre)
    # LE MIROIR BLANC de la croupe : la tache qu'on voit fuir entre les
    # arbres, et souvent la seule chose qu'on verra de lui.
    Color(0.93, 0.91, 0.86, r.alpha)
    r.ell(-0.56, 0.88, 0.22, 0.30)
    # L'encolure, dressee et FINE -- c'est elle qui fait la legerete de la
    # bete ; une encolure epaisse en ferait un cheval.
    r.quad([(0.42, 0.98), (0.55, 0.92), (0.76, 1.26), (0.65, 1.32)], dos)
    r.ell(0.83, 1.32, 0.32, 0.165, dos)
    r.ell(0.96, 1.26, 0.15, 0.125, sombre)             # le mufle
    # LES GRANDES OREILLES, ouvertes : avec le miroir, c'est elles qui
    # disent "chevreuil" en deux traits.
    r.tri([(0.72, 1.37), (0.63, 1.56), (0.80, 1.43)], dos)
    r.tri([(0.77, 1.38), (0.82, 1.57), (0.87, 1.42)], sombre)
    r.ell(0.87, 1.35, 0.042, 0.042, OEIL)
    # La queue, un eclat blanc sur le miroir.
    Color(0.96, 0.94, 0.90, r.alpha)
    r.ell(-0.58, 0.98, 0.09, 0.13)
    # Les deux pattes de DEVANT (les plus proches), par-dessus le corps.
    r.patte(0.40, 0.70, ep, dos)
    r.patte(-0.44, 0.70, ep, dos)


# --------------------------------------------------------------------- #
# LE SANGLIER : bas, en coin, la tete dans le prolongement du dos
# --------------------------------------------------------------------- #
def _sanglier(r, ombre):
    dos, ventre, sombre = ROBES[SANGLIER]
    if ombre:
        r.ombre(1.5)
    ep = 0.042
    r.patte(0.24, 0.52, ep, sombre, sabot=False)
    r.patte(-0.32, 0.52, ep, sombre, sabot=False)
    # LE CORPS EN COIN : haut et large au garrot, qui s'affaisse vers la
    # croupe. C'est la silhouette du sanglier bien plus que ses defenses.
    r.quad([(-0.52, 0.82), (0.30, 1.00), (0.44, 0.52), (-0.50, 0.46)], dos)
    r.ell(0.10, 0.74, 0.90, 0.52, dos)
    r.ell(-0.40, 0.68, 0.36, 0.40, dos)
    r.ell(-0.05, 0.54, 0.70, 0.20, ventre)
    # LES SOIES DU GARROT, herissees le long de l'echine.
    for i in range(7):
        t = i / 6.0
        u = -0.40 + 0.76 * t
        v = 0.80 + 0.21 * t
        r.trait((u, v), (u - 0.05, v + 0.17), 0.018, sombre)
    # La tete, portee BAS, en continuite du dos ; le groin en avant.
    r.quad([(0.28, 1.00), (0.42, 0.52), (0.82, 0.56), (0.72, 0.96)], dos)
    r.ell(0.68, 0.74, 0.50, 0.46, dos)
    r.ell(0.90, 0.60, 0.26, 0.22, dos)
    r.ell(0.99, 0.56, 0.17, 0.15, sombre)              # le groin
    # LES DEFENSES, deux eclats releves. Petites, mais elles disent tout.
    r.trait((0.92, 0.50), (1.02, 0.62), 0.028, IVOIRE)
    r.trait((0.86, 0.48), (0.95, 0.60), 0.022, IVOIRE)
    r.tri([(0.56, 0.92), (0.50, 1.10), (0.70, 0.96)], sombre)   # l'oreille
    r.ell(0.78, 0.80, 0.045, 0.045, OEIL)
    r.trait((-0.52, 0.76), (-0.64, 0.86), 0.020, sombre)        # la queue
    r.patte(0.32, 0.56, ep, dos)
    r.patte(-0.38, 0.56, ep, dos)


# --------------------------------------------------------------------- #
# L'ORIGNAL : la bosse du garrot, le museau tombant, le fanon, les palettes
# --------------------------------------------------------------------- #
def _orignal(r, ombre):
    dos, ventre, sombre = ROBES[ORIGNAL]
    if ombre:
        r.ombre(1.6)
    ep = 0.038
    r.patte(0.28, 0.70, ep, sombre, sabot=False)
    r.patte(-0.34, 0.70, ep, sombre, sabot=False)
    # LE DOS DESCEND VERS L'ARRIERE : la bosse du garrot domine la croupe.
    # De loin, c'est a cette ligne-la qu'on reconnait un orignal.
    r.quad([(-0.46, 0.86), (0.34, 1.00), (0.44, 0.64), (-0.46, 0.62)], dos)
    r.ell(0.00, 0.82, 0.92, 0.46, dos)
    r.ell(0.30, 0.94, 0.50, 0.38, dos)                 # la bosse
    r.ell(-0.40, 0.80, 0.34, 0.40, dos)
    r.ell(0.00, 0.68, 0.74, 0.20, ventre)
    # L'encolure, courte et massive, portee en AVANT et non dressee : un
    # orignal broute, il ne guette pas.
    r.quad([(0.30, 1.02), (0.48, 0.84), (0.76, 1.06), (0.58, 1.26)], dos)
    # LE FANON : cette barbe de peau sous la gorge, que personne d'autre
    # n'a. Elle vaut une signature.
    r.quad([(0.60, 0.98), (0.76, 1.00), (0.74, 0.72), (0.62, 0.76)], sombre)
    # La tete : longue, et le museau qui TOMBE plus bas que la machoire.
    r.ell(0.88, 1.16, 0.42, 0.21, dos)
    r.ell(1.08, 1.06, 0.26, 0.26, dos)
    r.ell(1.15, 1.00, 0.17, 0.16, sombre)
    # LES BOIS EN PALETTES, de part et d'autre du front : deux eventails
    # plats, celui du fond un peu en retrait.
    for recul, pal in ((0.12, sombre), (0.0, BOIS)):
        r.trait((0.76, 1.26), (0.66 - recul, 1.44), 0.040, pal)
        r.tri([(0.72 - recul, 1.38), (0.40 - recul, 1.50),
               (0.58 - recul, 1.66)], pal)
        for i in range(3):
            u = 0.60 - recul - 0.08 * i
            r.trait((u, 1.48), (u - 0.04, 1.64), 0.022, pal)
    r.tri([(0.74, 1.18), (0.62, 1.34), (0.78, 1.28)], sombre)   # l'oreille
    r.ell(0.94, 1.20, 0.045, 0.045, OEIL)
    r.patte(0.36, 0.74, ep, dos)
    r.patte(-0.40, 0.74, ep, dos)


# --------------------------------------------------------------------- #
# VUE DE DESSUS : la grille de l'ecran Zone
# --------------------------------------------------------------------- #
def glyphe(espece, cx, cy, size, cap=0.0):
    """Une bete VUE DE DESSUS, centree en (cx, cy), dans une boite de cote
    `size` ; `cap` est sa direction en degres (0 = vers le haut, le nord).

    Vue d'en haut, une bete n'est qu'un dos et une tete : on la reconnait a
    sa MASSE -- l'orignal remplit sa case, le chevreuil non -- et a ce qui
    depasse : les bois, le groin."""
    dos, ventre, sombre = ROBES.get(espece, ROBES[CHEVREUIL])
    a = math.radians(cap)
    ux, uy = math.sin(a), math.cos(a)          # vers l'avant
    nx, ny = -uy, ux                           # en travers

    def ell(d, t, lu, lt, col=None, al=1.0):
        if col is not None:
            Color(col[0], col[1], col[2], al)
        px = cx + ux * d + nx * t
        py = cy + uy * d + ny * t
        Ellipse(pos=(px - lu / 2.0, py - lt / 2.0), size=(lu, lt))
        return px, py

    if espece == SANGLIER:
        lg, la = size * 0.74, size * 0.40
    elif espece == ORIGNAL:
        lg, la = size * 0.86, size * 0.40
    else:
        lg, la = size * 0.68, size * 0.27
    Color(0, 0, 0, 0.25)                       # l'ombre portee
    ell(-size * 0.03, -size * 0.04, lg * 1.04, la * 1.08)
    ell(0.0, 0.0, lg, la, dos)                             # le tronc
    ell(-lg * 0.26, 0.0, lg * 0.46, la * 0.92, dos)        # la croupe
    hx, hy = ell(lg * 0.52, 0.0, la * 0.82, la * 0.74, dos)   # la tete
    if espece == ORIGNAL:
        Color(*BOIS)
        for s in (-1, 1):
            Line(points=[hx, hy,
                         hx + ux * size * 0.08 + nx * s * size * 0.24,
                         hy + uy * size * 0.08 + ny * s * size * 0.24],
                 width=max(1.0, size * 0.05))
    elif espece == SANGLIER:
        ell(lg * 0.74, 0.0, la * 0.40, la * 0.40, sombre)     # le groin
    else:
        for s in (-1, 1):                                     # les oreilles
            ell(lg * 0.50, s * la * 0.52, la * 0.34, la * 0.34, dos)
    ell(lg * 0.06, 0.0, lg * 0.46, la * 0.42, ventre, 0.85)   # l'echine


def glyphe_piste(cx, cy, size, sang=False, cap=0.0, aplati=1.0):
    """DES TRACES : quelques foulees qui s'en vont, et du sang si la bete
    est blessee. C'est tout ce qu'il reste d'elle.

    `aplati` ecrase le dessin en hauteur : 1 pour la grille de l'ecran
    Zone, qui regarde le sol d'aplomb ; moins pour la scene, qui le voit en
    enfilade -- une trace ronde y serait un trou, pas une empreinte.

    CHAQUE FOULEE A SON AUREOLE DE TERRE : le sabot creuse et retourne le
    sol autour de lui. Sans elle, une empreinte brun sombre sur de l'herbe
    sombre ne se voyait tout simplement pas."""
    a = math.radians(cap)
    ux, uy = math.sin(a), math.cos(a) * aplati
    nx, ny = -math.cos(a), math.sin(a) * aplati

    def tache(px, py, lu, lv, col, al):
        Color(col[0], col[1], col[2], al)
        Ellipse(pos=(px - lu / 2.0, py - lv * aplati / 2.0),
                size=(lu, lv * aplati))

    for i in range(4):
        d = (i - 1.5) * size * 0.26
        t = (size * 0.11) * (1 if i % 2 else -1)
        px, py = cx + ux * d + nx * t, cy + uy * d + ny * t
        al = 0.92 - 0.13 * i
        tache(px, py, size * 0.26, size * 0.24, (0.47, 0.39, 0.27), al * 0.65)
        for s in (-1, 1):          # un sabot fendu : deux demi-lunes
            qx = px + nx * s * size * 0.05
            qy = py + ny * s * size * 0.05
            tache(qx, qy, size * 0.085, size * 0.115, (0.17, 0.12, 0.07), al)
    if sang:
        for d, t in ((-0.30, 0.17), (0.04, -0.13), (0.33, 0.10)):
            px = cx + ux * size * d + nx * size * t
            py = cy + uy * size * d + ny * size * t
            tache(px, py, size * 0.10, size * 0.10, (0.62, 0.06, 0.07), 0.95)


__all__ = ["dessine", "boite", "glyphe", "glyphe_piste", "ROBES", "BOITES"]
