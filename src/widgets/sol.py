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

DEUX MATIERES, PRES ET LOIN. En foret, la terre brune n'est vraie qu'aux
pieds : au loin, ce que l'oeil voit du sol, c'est l'herbe qui le couvre. La
nappe passe donc, avec la distance, de la matiere proche a une matiere
lointaine (l'herbe de la plaine, recoloree au vert des touffes de la foret).
Le fondu se fait dans le shader, d'apres la distance que porte deja la
coordonnee de texture : aucune couture, aucun anneau.
"""
import math
import os

from kivy.core.image import Image as CoreImage
from kivy.graphics import BindTexture, Color, Mesh, RenderContext
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
# Le fondu de la matiere proche vers la lointaine : entiere jusqu'a PRES_PLEIN,
# disparue a PRES_FIN (distances de texture, en metres : au-dela de
# DISTANCE_TEXTURE elles sont resserrees, voir plus haut ; PRES_FIN vaut
# ainsi une quinzaine de metres reels).
PRES_PLEIN = 4.0
PRES_FIN = 14.0

# La nappe, avec sa matiere proche (texture0) et sa matiere lointaine
# (sol_loin, recoloree par sol_teinte_loin). La coordonnee de texture est la
# position au sol en tuiles : sa longueur donne la distance.
FS = """
$HEADER$
uniform sampler2D sol_loin;
uniform vec3 sol_teinte_loin;
uniform vec2 sol_fondu;
void main(void) {
    vec4 pres = texture2D(texture0, tex_coord0);
    vec4 loin = texture2D(sol_loin, tex_coord0);
    loin.rgb *= sol_teinte_loin;
    float d = length(tex_coord0) * %(tuile)f;
    float k = 1.0 - smoothstep(sol_fondu.x, sol_fondu.y, d);
    gl_FragColor = frag_color * mix(loin, pres, k);
}
""" % {"tuile": TUILE}

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
        # Le shader du fondu ; sans lui (pilote trop ancien), la seule
        # matiere proche, comme avant.
        ctx = RenderContext(use_parent_projection=True,
                            use_parent_modelview=True,
                            use_parent_frag_modelview=True)
        ctx.shader.fs = FS
        self._ctx = ctx if ctx.shader.success else None
        with self.canvas:
            if self._ctx is not None:
                self.canvas.add(ctx)
        cible = self._ctx if self._ctx is not None else self.canvas
        with cible:
            self._couleur = Color(1, 1, 1, 1)
            self._loin = BindTexture(index=1) if self._ctx is not None \
                else None
            self._mesh = Mesh(mode="triangles")
        if self._ctx is not None:
            ctx["sol_loin"] = 1
            ctx["sol_teinte_loin"] = [1.0, 1.0, 1.0]
            ctx["sol_fondu"] = [PRES_PLEIN, PRES_FIN]
        self.bind(size=self._recalcule, pos=self._recalcule)

    # -- la case ----------------------------------------------------------- #
    def regle(self, nom_texture, crete, horizon, loin=None,
              teinte_loin=(1.0, 1.0, 1.0)):
        """`nom_texture` : la matiere du sol ; `crete(azimut_rad)` -> hauteur
        de la crete a l'ecran (part de la hauteur, tete droite) dans cette
        direction ; `horizon` : la hauteur de l'horizon du ciel.

        `loin` : la matiere qui la remplace au loin (None : la meme), que
        `teinte_loin` recolore."""
        self._nom = nom_texture
        self._crete = crete
        self._horizon = float(horizon)
        tex = _texture(nom_texture)
        self._mesh.texture = tex
        if tex is None:
            self._couleur.rgb = textures.fallback(nom_texture)[:3]
        if self._ctx is not None:
            tex_loin = _texture(loin) if loin else None
            if tex_loin is None or tex is None:
                tex_loin, teinte_loin = tex, (1.0, 1.0, 1.0)
            self._loin.texture = tex_loin
            self._ctx["sol_teinte_loin"] = [float(c) for c in teinte_loin[:3]]
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
