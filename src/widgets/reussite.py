"""
LA REUSSITE D'UNE RECETTE : un "pouf" magique.

1. Une FUMEE jaillit sur chaque objet consomme par la recette (les outils,
   qui restent, ne s'y perdent pas) ; au plus dense, les objets ont
   disparu dessous (`cache()`).
2. La fumee monte et se dissipe, et laisse PEU A PEU place au nouvel objet,
   au milieu de ceux qui ont disparu : il apparait en APPARITION secondes.
3. Entierement apparu, `apparu()` est appele (l'ecran ouvre la fenetre de
   reussite) et l'objet GLISSE jusqu'a la place que l'ecran lui donne
   (`glisse_vers`), au milieu de la fenetre, ou il reste.

Tout se dessine dans une couche par-dessus le reste (la fenetre comprise).
"""
import math
import os
import random

from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Rectangle
from kivy.uix.widget import Widget

from src.widgets.sol_de_craft import dessine_objet

_ICI = os.path.dirname(os.path.abspath(__file__))
NUAGES = [os.path.join(_ICI, "..", "..", "assets", "Atmospheres", n)
          for n in ("cloud.png", "cloud_2.png", "cloud_3.png",
                    "cloud_4.png")]
_TEXTURES = []

# Les temps (secondes) : la fumee jaillit (POUF), les objets disparaissent
# dessous a CACHE, elle se dissipe (DISSIPE) ; l'objet apparait des le
# debut de la dissipation, en APPARITION ; puis il glisse (GLISSE).
POUF = 0.35
CACHE = 0.28
DISSIPE = 2.2
APPARITION = 3.0
GLISSE = 0.7
# Chaque objet consomme : BOUFFEES nuages, dans un carre de cote BOUFFEE
# fois la taille de l'objet ; ils grossissent de GONFLE et montent de MONTE
# (tailles d'objet) en se dissipant.
BOUFFEES = 6
BOUFFEE = 1.15
GONFLE = 0.8
MONTE = 0.9
COULEUR_FUMEE = (0.93, 0.93, 0.90)
# L'objet nait plus petit (NAISSANCE de sa taille) et grandit en
# apparaissant.
NAISSANCE = 0.55
FPS = 60.0


def _textures():
    if not _TEXTURES:
        for chemin in NUAGES:
            try:
                tex = CoreImage(os.path.abspath(chemin)).texture
            except Exception:
                tex = None
            if tex is not None:
                _TEXTURES.append(tex)
        if not _TEXTURES:
            _TEXTURES.append(None)
    return _TEXTURES


def _doux(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


class EffetReussite(Widget):
    """La couche du pouf, de l'objet qui apparait et qui glisse."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.objet = None
        self._horloge = None
        self._t = 0.0
        self._bouffees = []
        self._cache = None
        self._apparu = None
        self._depart = None          # (x, y, cote) de l'objet apparu
        self._arrivee = None         # (x, y, cote) ou il glisse
        self._t_glisse = None

    # -- cycle ----------------------------------------------------------- #
    def demarre(self, consommes, objet, cote, cache=None, apparu=None):
        """`consommes` : [(x, y)] a l'ecran des objets que la recette
        consomme ; `objet` : le nom de l'objet fabrique ; `cote` : la taille
        d'un objet a l'ecran ; `cache()` : les objets doivent disparaitre ;
        `apparu()` : l'objet est entierement apparu."""
        self.arrete()
        self.objet = objet
        self._cache = cache
        self._apparu = apparu
        if consommes:
            cx = sum(x for x, _y in consommes) / float(len(consommes))
            cy = sum(y for _x, y in consommes) / float(len(consommes))
        else:
            cx, cy = self.center_x, self.center_y
        self._depart = (cx, cy, cote)
        hasard = random.Random(len(consommes) * 7 + 3)
        tex = _textures()
        self._bouffees = []
        for x, y in (consommes or [(cx, cy)]):
            for k in range(BOUFFEES):
                a = 2.0 * math.pi * k / BOUFFEES + hasard.uniform(-0.4, 0.4)
                r = hasard.uniform(0.05, 0.35) * cote
                self._bouffees.append({
                    "x": x + math.cos(a) * r, "y": y + math.sin(a) * r,
                    "taille": cote * BOUFFEE * hasard.uniform(0.75, 1.1),
                    "tex": tex[k % len(tex)],
                    "derive": hasard.uniform(-0.25, 0.25) * cote,
                    "retard": hasard.uniform(0.0, 0.10)})
        self._t = 0.0
        self._t_glisse = None
        self._arrivee = None
        self._horloge = Clock.schedule_interval(self._pas, 1.0 / FPS)
        self._dessine()

    def glisse_vers(self, x, y, cote):
        """L'objet glisse jusqu'en (x, y), a la taille `cote`."""
        self._arrivee = (x, y, cote)
        self._t_glisse = 0.0
        if self._horloge is None:
            self._horloge = Clock.schedule_interval(self._pas, 1.0 / FPS)

    def arrete(self):
        if self._horloge is not None:
            self._horloge.cancel()
            self._horloge = None
        self.objet = None
        self._bouffees = []
        self.canvas.clear()

    def en_cours(self):
        return self.objet is not None

    def position(self):
        """(x, y, cote, opacite) de l'objet a l'ecran, maintenant."""
        if self._depart is None:
            return None
        x, y, cote = self._depart
        p = _doux((self._t - POUF) / APPARITION)
        cote = cote * (NAISSANCE + (1.0 - NAISSANCE) * p)
        if self._t_glisse is not None and self._arrivee is not None:
            g = _doux(self._t_glisse / GLISSE)
            ax, ay, ac = self._arrivee
            x, y, cote = (x + (ax - x) * g, y + (ay - y) * g,
                          cote + (ac - cote) * g)
        return x, y, cote, p

    # -- chaque image ---------------------------------------------------- #
    def _pas(self, dt):
        dt = min(dt, 0.1)
        avant = self._t
        self._t += dt
        if avant < CACHE <= self._t and self._cache is not None:
            self._cache()
        fin_apparition = POUF + APPARITION
        if avant < fin_apparition <= self._t and self._apparu is not None:
            self._apparu()
        if self._t_glisse is not None:
            self._t_glisse += dt
        self._dessine()
        fumee_finie = self._t >= POUF + DISSIPE
        glisse_fini = self._t_glisse is not None and \
            self._t_glisse >= GLISSE
        if fumee_finie and glisse_fini and self._horloge is not None:
            # Tout est en place : plus rien ne bouge.
            self._horloge.cancel()
            self._horloge = None

    def _dessine(self):
        self.canvas.clear()
        if self.objet is None:
            return
        with self.canvas:
            # L'objet, sous la fumee qui se dissipe.
            pos = self.position()
            if pos is not None and pos[3] > 0.0:
                x, y, cote, p = pos
                dessine_objet(self.objet, x, y, cote, ombre=False, alpha=p)
            for b in self._bouffees:
                t = self._t - b["retard"]
                if t <= 0.0:
                    continue
                if t < POUF:
                    k = _doux(t / POUF)
                    alpha, gonfle, monte = 0.95 * k, 0.45 + 0.55 * k, 0.0
                else:
                    d = (t - POUF) / DISSIPE
                    if d >= 1.0:
                        continue
                    alpha = 0.95 * (1.0 - _doux(d))
                    gonfle = 1.0 + GONFLE * d
                    monte = MONTE * d
                taille = b["taille"] * gonfle
                cote = self._depart[2]
                bx = b["x"] + b["derive"] * (monte / MONTE if MONTE else 0)
                by = b["y"] + monte * cote
                Color(COULEUR_FUMEE[0], COULEUR_FUMEE[1], COULEUR_FUMEE[2],
                      alpha)
                tex = b["tex"]
                if tex is not None:
                    w = taille
                    h = taille * tex.height / float(max(1, tex.width)) * 1.6
                    Rectangle(texture=tex, pos=(bx - w / 2.0, by - h / 2.0),
                              size=(w, h))
                else:
                    Rectangle(pos=(bx - taille / 2.0, by - taille / 2.0),
                              size=(taille, taille))


__all__ = ["EffetReussite", "APPARITION", "POUF", "GLISSE"]
