"""
LE SOL DU PANORAMA : une seule nappe, sous le joueur, pour tout le tour.

Le joueur se tient au centre d'un sol qui s'etend tout autour de lui et
REMONTE doucement au loin, jusqu'a rejoindre l'horizon : c'est lui qui bouche
la vue. Le decor (arbres, herbe, pierres) est pose dessus par les quatre
panneaux du panorama, qui ne peignent plus de sol eux-memes.

LA NAPPE EST UN MAILLAGE POLAIRE : des anneaux de distance et des secteurs de
direction. Chaque sommet a une place FIXE dans le monde (direction,
distance) ; sa texture lui est collee d'apres cette place, en metres -- elle
ne glisse pas quand on tourne, n'a aucune couture et ne s'etire nulle part,
pas meme sous les pieds. Seule sa place a l'ecran change avec le regard :
meme projection que le ciel et les panneaux (la direction donne x, l'angle
sous l'horizon donne y).

Ne sont recalcules, a chaque mouvement du regard, que les x et y des sommets
des secteurs a l'ecran : quelques centaines d'additions.
"""
import math
import os

from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Mesh
from kivy.uix.widget import Widget

from src.widgets import textures

FOV = 90.0
# L'oeil, a cette hauteur au-dessus du sol sous les pieds (unite : le metre).
OEIL = 1.6
# Les anneaux : de tout pres des pieds jusqu'au bord, ou le sol rejoint la
# crete. Repartis en progression geometrique (serres pres des pieds, la ou un
# metre fait beaucoup d'ecran).
DISTANCE_MIN = 0.03
DISTANCE_MAX = 90.0
ANNEAUX = 40
# Le sol remonte vers le bord en (d / DISTANCE_MAX) ** REMONTEE.
REMONTEE = 2.0
# Les secteurs : un tous les PAS_SECTEUR degres, sur le tour complet.
PAS_SECTEUR = 3.0
SECTEURS = int(round(360.0 / PAS_SECTEUR))
# Marge de secteurs dessines au-dela de chaque bord de l'ecran.
MARGE_SECTEURS = 2
# Une tuile de texture couvre ce cote, en metres. Au-dela de DISTANCE_TEXTURE
# la texture s'agrandit doucement (TEXTURE_LOIN) : vue de si loin, elle
# fourmillerait.
TUILE = 2.2
DISTANCE_TEXTURE = 12.0
TEXTURE_LOIN = 0.45

_TEXTURES = {}


def _texture(nom):
    """La BaseColor `nom`, chargee AVEC SES REDUCTIONS (mipmaps) : le sol
    lointain en est fait. None si l'image n'existe pas."""
    if nom not in _TEXTURES:
        tex = None
        for ext in (".png", ".jpg", ".jpeg"):
            chemin = os.path.join(textures.TEXTURES_DIR,
                                           nom + textures.SUFFIX_BASE + ext)
            if os.path.isfile(chemin):
                try:
                    tex = CoreImage(chemin, mipmap=True).texture
                    tex.wrap = "repeat"
                    tex.min_filter = "linear_mipmap_linear"
                except Exception:
                    tex = None
                break
        _TEXTURES[nom] = tex
    return _TEXTURES[nom]


def _ecart(a):
    return (a + 180.0) % 360.0 - 180.0


class SolPanorama(Widget):
    """La nappe du sol. `regle(zone, crete, horizon)` la cale sur une case,
    `set_camera(lacet, tangage)` sur le regard, `set_teinte(rgb)` sur la
    lumiere du jour."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.lacet = 0.0
        self.tangage = 0.0
        self._nom = None
        self._horizon = 0.47
        self._angles = None          # [secteur][anneau] : angle sous l'horizon
        self._uv = None              # [secteur][anneau] : (u, v)
        with self.canvas:
            self._couleur = Color(1, 1, 1, 1)
            self._mesh = Mesh(mode="triangles")
        self.bind(size=self._recalcule, pos=self._recalcule)

    # -- la case ----------------------------------------------------------- #
    def regle(self, nom_texture, crete, horizon):
        """`nom_texture` : la matiere du sol ; `crete(azimut_rad)` -> hauteur
        de la crete a l'ecran (part de la hauteur, tete droite) dans cette
        direction ; `horizon` : la hauteur de l'horizon du ciel."""
        self._nom = nom_texture
        self._crete = crete
        self._horizon = float(horizon)
        tex = _texture(nom_texture)
        self._mesh.texture = tex
        if tex is None:
            self._couleur.rgb = textures.fallback(nom_texture)[:3]
        self._recalcule()

    def _recalcule(self, *_):
        """Les angles (sous l'horizon) et la texture de chaque sommet : ne
        dependent que de la case et de la taille de l'ecran."""
        if self._nom is None or self.width <= 0 or self.height <= 0:
            return
        ppd = self.width / FOV
        distances = [DISTANCE_MIN * (DISTANCE_MAX / DISTANCE_MIN)
                     ** (i / float(ANNEAUX - 1)) for i in range(ANNEAUX)]
        self._angles, self._uv = [], []
        for s in range(SECTEURS):
            az = math.radians(s * PAS_SECTEUR)
            # L'angle du BORD du sol dans cette direction : la crete, comptee
            # depuis l'horizon du ciel.
            bord = math.radians((self._crete(az) - self._horizon)
                                * self.height / ppd)
            haut_bord = OEIL + DISTANCE_MAX * math.tan(bord)
            angles, uv = [], []
            sa, ca = math.sin(az), math.cos(az)
            for d in distances:
                z = haut_bord * (d / DISTANCE_MAX) ** REMONTEE
                angles.append(math.degrees(math.atan2(z - OEIL, d)))
                dt = d if d <= DISTANCE_TEXTURE else (
                    DISTANCE_TEXTURE + (d - DISTANCE_TEXTURE) * TEXTURE_LOIN)
                uv.append((dt * sa / TUILE, dt * ca / TUILE))
            self._angles.append(angles)
            self._uv.append(uv)
        self._place()

    def cache(self):
        """Pas de nappe sur cette case (montagne, lac : chaque panneau y peint
        encore son sol)."""
        self._nom = None
        self._angles = None
        self._mesh.indices = []
        self._mesh.vertices = []

    # -- le regard --------------------------------------------------------- #
    def set_camera(self, lacet, tangage):
        self.lacet = float(lacet)
        self.tangage = float(tangage)
        self._place()

    def set_teinte(self, rgb):
        """La couleur de la lumiere du jour (doree le matin, orange au
        couchant), comme le shader des panneaux l'applique a leur decor."""
        if self._mesh.texture is not None:
            self._couleur.rgb = tuple(rgb[:3])

    def _place(self):
        """Les sommets des secteurs a l'ecran, a leur place pour ce regard."""
        if self._angles is None:
            return
        w, h = self.width, self.height
        ppd = w / FOV
        y_horizon = self.y + self._horizon * h - self.tangage * ppd
        cx = self.center_x
        demi = int(math.ceil((FOV / 2.0) / PAS_SECTEUR)) + MARGE_SECTEURS
        premier = int(math.floor(self.lacet / PAS_SECTEUR)) - demi
        colonnes = 2 * demi + 2
        verts = []
        for k in range(colonnes):
            s = premier + k
            az = s * PAS_SECTEUR
            x = cx + (az - self.lacet) * ppd
            angles = self._angles[s % SECTEURS]
            uv = self._uv[s % SECTEURS]
            for a, (u, v) in zip(angles, uv):
                verts += [x, y_horizon + a * ppd, u, v]
        self._mesh.vertices = verts
        if len(self._mesh.indices) != (colonnes - 1) * (ANNEAUX - 1) * 6:
            idx = []
            for k in range(colonnes - 1):
                for i in range(ANNEAUX - 1):
                    p = k * ANNEAUX + i
                    q = p + ANNEAUX
                    idx += [p, q, q + 1, p, q + 1, p + 1]
            self._mesh.indices = idx


__all__ = ["SolPanorama"]
