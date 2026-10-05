"""
LES ZONES VOISINES, EN MODE DEPLACEMENT.

Le bouton Deplacer ne propose plus une croix de boutons : les quatre cases
voisines CLIGNOTENT dans le paysage, la ou on les voit -- une bande posee sur
l'horizon de leur direction, avec leur nom. On tourne la tete pour les
chercher, et on touche celle ou l'on veut aller.

La bande suit la LIGNE DE L'HORIZON de la scene dans sa direction (voir
ZoneScenery.crete_tour) : sur la crete en montagne, sur la berge d'en face
au bord d'un lac. Elle tourne avec le regard, comme le reste du monde.

Une case ou l'on ne va pas (le lac) clignote aussi, d'une autre couleur, et
dit pourquoi. Au-dela du bord de la carte, rien.
"""
import math

from kivy.clock import Clock
from kivy.graphics import Color, Line, Mesh, RoundedRectangle
from kivy.uix.label import Label
from kivy.uix.widget import Widget

FOV = 90.0
# La bande de chaque direction : sa demi-largeur (degres), et sa hauteur
# autour de la crete (degres sous et au-dessus).
DEMI_LARGEUR = 38.0
SOUS_CRETE = 3.0
SUR_CRETE = 9.0
PAS = 3.0
# Le toucher est plus genereux que le dessin (degres en plus, en bas et en
# haut).
MARGE_TOUCHER = (4.0, 8.0)
# Couleurs : une case ou l'on peut aller, une ou l'on ne peut pas.
JAUNE = (1.0, 0.86, 0.25)
GRIS = (0.62, 0.72, 0.84)
# Le battement : alpha du remplissage entre ces deux valeurs, a cette
# periode (secondes).
ALPHA = (0.16, 0.42)
PERIODE = 1.1
# Le nom de la zone, en part de la hauteur de l'ecran.
TAILLE_NOM = 0.045


def _ecart(a):
    return (a + 180.0) % 360.0 - 180.0


class ZonesVoisines(Widget):
    """Le calque des zones voisines. `montre(zones, crete)` l'allume,
    `set_camera(lacet, tangage)` le cale sur le regard, `cache()` l'eteint,
    `zone_sous(x, y)` dit quelle zone un doigt touche."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.lacet = 0.0
        self.tangage = 0.0
        self.horizon = 0.47
        self._zones = []
        self._crete = None
        self._formes = []           # [(zone, Color de fond, Mesh, Line)]
        self._labels = []
        self._horloge = None
        self._t = 0.0
        self.bind(size=self._place, pos=self._place)

    # -- allumer / eteindre ------------------------------------------------ #
    def montre(self, zones, crete, horizon):
        """`zones` : [{"direction": 0..3, "titre": texte, "va": bool}] ;
        `crete(azimut_rad)` : la hauteur de la crete a l'ecran (part de la
        hauteur, tete droite) ; `horizon` : celle de l'horizon du ciel."""
        self.cache()
        self._zones = list(zones)
        self._crete = crete
        self.horizon = float(horizon)
        with self.canvas:
            for z in self._zones:
                coul = JAUNE if z["va"] else GRIS
                fond = Color(coul[0], coul[1], coul[2], ALPHA[0])
                mesh = Mesh(mode="triangles")
                Color(coul[0], coul[1], coul[2], 0.85)
                bord = Line(width=1.6)
                self._formes.append((z, fond, mesh, bord))
        for z in self._zones:
            lab = Label(text=z["titre"], bold=True, halign="center",
                        valign="middle",
                        font_size=max(16.0, TAILLE_NOM * self.height),
                        color=(1, 1, 1, 1) if z["va"] else (0.85, 0.9, 1, 1),
                        padding=(12, 6), size_hint=(None, None))
            # Une pastille sombre derriere le nom : il se lit sur le ciel
            # comme sur le feuillage.
            with lab.canvas.before:
                Color(0.0, 0.0, 0.0, 0.5)
                fond = RoundedRectangle(radius=[8])
            lab.bind(texture_size=lambda w, ts: setattr(w, "size", ts),
                     pos=lambda w, _p, f=fond: self._pastille(w, f),
                     size=lambda w, _s, f=fond: self._pastille(w, f))
            self.add_widget(lab)
            self._labels.append(lab)
        self._horloge = Clock.schedule_interval(self._bat, 1.0 / 30.0)
        self._place()

    def cache(self):
        if self._horloge is not None:
            self._horloge.cancel()
            self._horloge = None
        self.canvas.clear()
        for lab in self._labels:
            self.remove_widget(lab)
        self._formes = []
        self._labels = []
        self._zones = []

    @staticmethod
    def _pastille(lab, fond):
        fond.pos = lab.pos
        fond.size = lab.size

    def allume(self):
        return bool(self._zones)

    def _bat(self, dt):
        self._t += dt
        k = 0.5 - 0.5 * math.cos(2.0 * math.pi * self._t / PERIODE)
        a = ALPHA[0] + (ALPHA[1] - ALPHA[0]) * k
        for z, fond, _m, _b in self._formes:
            fond.a = a if z["va"] else a * 0.6

    # -- le regard ----------------------------------------------------------- #
    def set_camera(self, lacet, tangage):
        self.lacet = float(lacet)
        self.tangage = float(tangage)
        self._place()

    def _ppd(self):
        return max(1.0, self.width) / FOV

    def _y_crete(self, azimut):
        """Le y a l'ecran de la crete dans cette direction (degres)."""
        ppd = self._ppd()
        part = self._crete(math.radians(azimut)) if self._crete else \
            self.horizon
        return self.y + part * self.height - self.tangage * ppd

    def _x(self, azimut):
        return self.center_x + _ecart(azimut - self.lacet) * self._ppd()

    def _place(self, *_):
        if not self._formes or self.width <= 0:
            return
        ppd = self._ppd()
        for (z, _fond, mesh, bord), lab in zip(self._formes, self._labels):
            centre = z["direction"] * FOV
            # Seulement si la bande est (au moins en partie) a l'ecran.
            if abs(_ecart(centre - self.lacet)) > FOV / 2.0 + DEMI_LARGEUR:
                mesh.vertices, mesh.indices = [], []
                bord.points = []
                lab.opacity = 0.0
                continue
            n = int(2 * DEMI_LARGEUR / PAS) + 1
            verts, haut, bas = [], [], []
            x0 = self._x(centre)
            for i in range(n):
                az = centre - DEMI_LARGEUR + i * PAS
                x = x0 + (az - centre) * ppd
                yc = self._y_crete(az)
                yb, yh = yc - SOUS_CRETE * ppd, yc + SUR_CRETE * ppd
                verts += [x, yb, 0.0, 0.0, x, yh, 0.0, 0.0]
                bas.append((x, yb))
                haut.append((x, yh))
            idx = []
            for i in range(n - 1):
                p = 2 * i
                idx += [p, p + 2, p + 3, p, p + 3, p + 1]
            mesh.vertices = verts
            mesh.indices = idx
            contour = bas + haut[::-1] + bas[:1]
            bord.points = [c for pt in contour for c in pt]
            # Le nom, au-dessus du milieu de la bande, garde dans l'ecran.
            lx = min(max(x0, self.x + lab.width / 2.0 + 8),
                     self.right - lab.width / 2.0 - 8)
            if abs(_ecart(centre - self.lacet)) > FOV / 2.0 + 4.0:
                lx = x0                         # hors champ : il le suit
            ly = self._y_crete(centre) + SUR_CRETE * ppd + 6
            lab.center_x = lx
            lab.y = ly
            lab.opacity = 1.0

    # -- le toucher ---------------------------------------------------------- #
    def zone_sous(self, x, y):
        """La zone (dict de `montre`) sous ce point de l'ecran, ou None."""
        if not self._zones or self.width <= 0:
            return None
        ppd = self._ppd()
        azimut = self.lacet + (x - self.center_x) / ppd
        meilleure = None
        for z in self._zones:
            centre = z["direction"] * FOV
            ecart_az = abs(_ecart(azimut - centre))
            if ecart_az > DEMI_LARGEUR + 2.0:
                continue
            yc = self._y_crete(azimut)
            bas = yc - (SOUS_CRETE + MARGE_TOUCHER[0]) * ppd
            haut = yc + (SUR_CRETE + MARGE_TOUCHER[1]) * ppd
            if bas <= y <= haut and (meilleure is None
                                     or ecart_az < meilleure[0]):
                meilleure = (ecart_az, z)
        return meilleure[1] if meilleure else None


__all__ = ["ZonesVoisines"]
