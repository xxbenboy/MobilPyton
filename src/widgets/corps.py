"""
LE CORPS DU PERSONNAGE, dans l'inventaire : une vraie image, habillee de ce
qu'il porte, et qui respire.

L'image de base (assets/Character/Corps.png) montre le rescape en sous-
vetement, de face, bras le long du corps. Chaque piece PORTEE se pose
directement sur la partie du corps qu'elle habille : le chandail sur le
torse, le pantalon sur les jambes, les chaussures aux pieds, le casque sur
la tete, les gants aux mains. Le sac se porte dans le dos : il se dessine
DERRIERE le corps et depasse des epaules.

LE CORPS RESPIRE : un leger gonflement, ancre aux pieds, a la cadence d'un
souffle au repos. Les vetements suivent, puisqu'ils sont dessines dans le
meme repere.
"""
import math
import os

from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.graphics import (Color, Rectangle, PushMatrix, PopMatrix,
                           Scale)

from src import items

_HERE = os.path.dirname(os.path.abspath(__file__))
CORPS_IMAGE = os.path.abspath(os.path.join(_HERE, "..", "..", "assets",
                                           "Character", "Corps.png"))

# LES PARTIES DU CORPS, en part de l'image : (x0, haut, x1, bas), mesurees
# sur Corps.png, le haut de l'image a 0. Chaque vetement est pose dans la
# boite de l'emplacement qu'il habille :
#   casque    : le dessus de la tete, sans cacher les yeux (0,07)
#   chandail  : des epaules (0,175) a la ceinture (0,44), bras compris
#   gant      : les deux mains, au bout des bras (0,50 a 0,56)
#   pantalon  : de la ceinture aux chevilles (0,93)
#   chaussure : les pieds
#   sac       : dans le dos, depasse des epaules
# Chaque boite dit aussi QUELLE PART de l'image y va, et COMMENT :
#   - les gants et les chaussures sont dessines PAR PAIRE sur leur image :
#     la moitie gauche va a la main (au pied) de gauche, la droite a droite.
#     Sans ce partage, chaque pied portait la paire entiere ;
#   - "plein" etire l'image sur toute la boite (un chandail doit couvrir les
#     epaules, un pantalon les deux jambes) ; "garde" garde ses proportions
#     (un casque, un soulier ecrases se voient tout de suite).
ENTIERE, GAUCHE, DROITE = (0.0, 1.0), (0.0, 0.5), (0.5, 1.0)
PARTIES = {
    "casque":    (((0.30, -0.035, 0.74, 0.085), ENTIERE, "garde"),),
    "chandail":  (((0.05, 0.15, 0.99, 0.47), ENTIERE, "plein"),),
    "gant":      (((-0.02, 0.48, 0.14, 0.58), GAUCHE, "garde"),
                  ((0.86, 0.48, 1.02, 0.58), DROITE, "garde")),
    "pantalon":  (((0.13, 0.43, 0.94, 0.93), ENTIERE, "plein"),),
    "chaussure": (((0.11, 0.895, 0.44, 1.00), GAUCHE, "garde"),
                  ((0.59, 0.895, 0.89, 1.00), DROITE, "garde")),
    "sac":       (((0.20, 0.12, 0.84, 0.52), ENTIERE, "garde"),),
}
# Le point de chaque partie ou aboutit le trait de son emplacement (meme
# repere). Les gants, les pantalons et les chaussures visent le cote de leur
# colonne : la main gauche, la jambe et le pied droits.
ANCRES = {
    "casque":    (0.52, 0.06),
    "chandail":  (0.50, 0.30),
    "gant":      (0.06, 0.53),
    "sac":       (0.82, 0.22),
    "pantalon":  (0.72, 0.72),
    "chaussure": (0.74, 0.96),
}
# Ordre de dessin : le sac d'abord (dans le dos, derriere le corps), puis le
# corps, puis ce qui le couvre, du dessous au dessus.
ORDRE_DESSUS = ("pantalon", "chaussure", "chandail", "gant", "casque")

# La respiration : periode d'un souffle au repos, et amplitude du gonflement
# (en part de la taille). Tres faible : on doit la sentir, pas la voir.
PERIODE_SOUFFLE = 4.2
SOUFFLE_Y = 0.006
SOUFFLE_X = 0.004
FPS_SOUFFLE = 30.0

_TEXTURES = {}


def _texture(chemin):
    """Texture d'une image, gardee en memoire (None si absente)."""
    if chemin not in _TEXTURES:
        tex = None
        if chemin and os.path.isfile(chemin):
            try:
                tex = CoreImage(chemin).texture
            except Exception:
                tex = None
        _TEXTURES[chemin] = tex
    return _TEXTURES[chemin]


def texture_corps():
    return _texture(CORPS_IMAGE)


def _contenir(boite, tex):
    """Le rectangle de `tex` pose dans `boite` (x, y, l, h) sans deformer
    l'image : elle remplit la boite dans un sens et y est centree."""
    x, y, l, h = boite
    if tex is None or tex.width <= 0 or tex.height <= 0:
        return boite
    rapport = tex.width / float(tex.height)
    if l / h > rapport:
        nl = h * rapport
        return (x + (l - nl) / 2.0, y, nl, h)
    nh = l / rapport
    return (x, y + (h - nh) / 2.0, l, nh)


class Corps(object):
    """Le corps dessine dans un rectangle, avec ses vetements.

    `dessine(canvas, rect, porte)` ajoute les instructions au canvas donne ;
    `point(fx, fy)` dit ou tombe un point de l'image dans ce rectangle.
    La respiration modifie l'echelle apres coup, sans redessiner."""

    def __init__(self):
        self.rect = (0.0, 0.0, 0.0, 0.0)
        self._echelle = None
        self._horloge = None
        self._t = 0.0

    # -- geometrie ------------------------------------------------------ #
    @staticmethod
    def rect_dans(x, y, l, h, part_l=0.32, part_h=0.94):
        """Le rectangle du corps dans un panneau : aussi grand que possible
        dans `part_l` de la largeur et `part_h` de la hauteur, centre, les
        pieds un peu au-dessus du bas."""
        tex = texture_corps()
        rapport = (tex.width / float(tex.height)) if tex is not None \
            else 428.0 / 1200.0
        hh = h * part_h
        ll = hh * rapport
        if ll > l * part_l:
            ll = l * part_l
            hh = ll / rapport
        return (x + (l - ll) / 2.0, y + (h - hh) * 0.35, ll, hh)

    def point(self, fx, fy):
        """Un point de l'image (fy compte depuis le HAUT) dans le panneau."""
        x, y, l, h = self.rect
        return (x + fx * l, y + (1.0 - fy) * h)

    def _boite(self, partie):
        x0, haut, x1, bas = partie
        px0, py0 = self.point(x0, bas)
        px1, py1 = self.point(x1, haut)
        return (px0, py0, px1 - px0, py1 - py0)

    # -- dessin --------------------------------------------------------- #
    def dessine(self, canvas, rect, porte):
        """Le corps et `porte` (emplacement -> objet), dans `rect`."""
        self.rect = rect
        x, y, l, h = rect
        with canvas:
            PushMatrix()
            # Le souffle gonfle le corps depuis les pieds.
            self._echelle = Scale(1.0, 1.0, 1.0,
                                  origin=(x + l / 2.0, y + h * 0.02))
            Color(1, 1, 1, 1)
            self._vetement(porte, "sac")
            tex = texture_corps()
            if tex is not None:
                Rectangle(texture=tex, pos=(x, y), size=(l, h))
            for emplacement in ORDRE_DESSUS:
                self._vetement(porte, emplacement)
            PopMatrix()
        self._applique()

    def _vetement(self, porte, emplacement):
        nom = porte.get(emplacement)
        if not nom:
            return
        tex = _texture(items.image_path(nom))
        if tex is None:
            return
        for partie, (u0, u1), mode in PARTIES[emplacement]:
            morceau = tex
            if (u0, u1) != ENTIERE:
                morceau = tex.get_region(u0 * tex.width, 0,
                                         (u1 - u0) * tex.width, tex.height)
            boite = self._boite(partie)
            if mode == "garde":
                boite = _contenir(boite, morceau)
            bx, by, bl, bh = boite
            Rectangle(texture=morceau, pos=(bx, by), size=(bl, bh))

    # -- respiration ---------------------------------------------------- #
    def respire(self, oui):
        if oui and self._horloge is None:
            self._horloge = Clock.schedule_interval(self._souffle,
                                                    1.0 / FPS_SOUFFLE)
        elif not oui and self._horloge is not None:
            self._horloge.cancel()
            self._horloge = None
            self._t = 0.0
            self._applique()

    def _souffle(self, dt):
        self._t += min(dt, 0.1)
        self._applique()

    def gonflement(self):
        """0 au repos (poumons vides), 1 au plus haut du souffle."""
        return 0.5 - 0.5 * math.cos(2.0 * math.pi * self._t
                                    / PERIODE_SOUFFLE)

    def _applique(self):
        if self._echelle is None:
            return
        g = self.gonflement()
        self._echelle.x = 1.0 + SOUFFLE_X * g
        self._echelle.y = 1.0 + SOUFFLE_Y * g
