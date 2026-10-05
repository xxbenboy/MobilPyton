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

UN VERSANT. En montagne, le sol n'est plus a plat sous les pieds : dans
chaque direction il part avec sa PENTE (montante vers les cases de montagne,
descendante a l'oppose) et finit a son bord (la crete, ou le rebord d'ou
l'on voit la vallee). Au-dela d'un rebord, la VALLEE : une bande lointaine,
noyee de brume, sous l'horizon. Le decor des panneaux est pose sur la meme
nappe, par les memes calculs (voir altitude et angle_au_sol).
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
# Le sol rejoint son bord en (d / DISTANCE_MAX) ** REMONTEE.
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

# LA VALLEE, vue d'un rebord : de VALLEE_HAUT (juste sous l'horizon, le plus
# lointain) jusque sous le rebord, que la nappe recouvre. En bandes, du plus
# loin au plus pres (VALLEE_BANDES, en degres) : la plus lointaine est la
# plus noyee dans le ciel (BRUME_VALLEE), et de l'une a l'autre la brume ne
# baisse que d'un cran, sans ligne visible. La derniere descend jusque sous
# le rebord.
VALLEE_BANDES = (-0.6, -1.2, -2.0, -3.2, -5.0)
VALLEE_HAUT = VALLEE_BANDES[0]
VALLEE_SOUS_REBORD = 4.0
VERT_VALLEE = (0.17, 0.27, 0.11)
BRUME_VALLEE = (0.50, 0.42, 0.34, 0.26, 0.18)

# La nappe, avec sa matiere proche (texture0) et sa matiere lointaine
# (sol_loin, recoloree par sol_teinte_loin, et agrandie par
# sol_echelle_loin). La coordonnee de texture est la position au sol en
# tuiles : sa longueur donne la distance.
FS = """
$HEADER$
uniform sampler2D sol_loin;
uniform vec3 sol_teinte_loin;
uniform vec2 sol_fondu;
uniform float sol_echelle_loin;
void main(void) {
    vec4 pres = texture2D(texture0, tex_coord0);
    vec4 loin = texture2D(sol_loin, tex_coord0 * sol_echelle_loin);
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


def altitude(pente, crete, d):
    """La hauteur du sol (metres, 0 sous les pieds) a `d` metres, dans une
    direction ou il part avec cette `pente` (tangente) et finit, a
    DISTANCE_MAX, sur son bord vu a l'angle `crete` (degres au-dessus de
    l'horizon de l'oeil)."""
    bord = OEIL + DISTANCE_MAX * math.tan(math.radians(crete))
    return pente * d + (bord - pente * DISTANCE_MAX) \
        * (d / DISTANCE_MAX) ** REMONTEE


def angle_au_sol(pente, crete, d):
    """L'angle (degres, negatif sous l'horizon) sous lequel l'oeil voit le
    sol a `d` metres dans cette direction."""
    return math.degrees(math.atan2(altitude(pente, crete, d) - OEIL, d))


def _melange(a, b, k):
    return tuple(x * (1.0 - k) + y * k for x, y in zip(a, b))


class SolPanorama(Widget):
    """La nappe du sol. `regle(...)` la cale sur une case, `set_camera(lacet,
    tangage)` sur le regard, `set_teinte(rgb)` sur la lumiere du jour et
    `set_brume(rgb)` sur la couleur du ciel a l'horizon."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.lacet = 0.0
        self.tangage = 0.0
        self._nom = None
        self._horizon = 0.47
        self._crete = None
        self._relief = None
        self._vallee = False
        self._angles = None          # [secteur][anneau] : angle sous l'horizon
        self._uv = None              # [secteur][anneau] : (u, v)
        self._bords = None           # [secteur] : angle du bord du sol
        self._jour = (1.0, 1.0, 1.0)
        self._ciel = (0.70, 0.80, 0.90)
        # LA VALLEE d'abord : la nappe la recouvre partout ou elle est plus
        # haute qu'elle.
        with self.canvas:
            self._couleurs_vallee = []
            self._meshes_vallee = []
            for _ in BRUME_VALLEE:
                self._couleurs_vallee.append(Color(1, 1, 1, 1))
                self._meshes_vallee.append(Mesh(mode="triangles"))
        # Le shader du fondu ; sans lui (pilote trop ancien), la seule
        # matiere proche, comme avant.
        ctx = RenderContext(use_parent_projection=True,
                            use_parent_modelview=True,
                            use_parent_frag_modelview=True)
        ctx.shader.fs = FS
        self._ctx = ctx if ctx.shader.success else None
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
            ctx["sol_echelle_loin"] = 1.0
        self.bind(size=self._recalcule, pos=self._recalcule)

    # -- la case ----------------------------------------------------------- #
    def regle(self, nom_texture, crete, horizon, loin=None,
              teinte_loin=(1.0, 1.0, 1.0), relief=None, vallee=False,
              echelle_loin=1.0):
        """`nom_texture` : la matiere du sol ; `crete(azimut_rad)` -> hauteur
        de la crete a l'ecran (part de la hauteur, tete droite) dans cette
        direction ; `horizon` : la hauteur de l'horizon du ciel.

        `loin` : la matiere qui la remplace au loin (None : la meme), que
        `teinte_loin` recolore ; `echelle_loin` < 1 l'agrandit (une meme
        matiere, vue de loin, y gagne de grandes taches).

        `relief(azimut_rad)` -> (pente, crete en degres) : un VERSANT (voir
        altitude) ; il remplace alors `crete`. `vallee` : montrer la vallee
        au-dela des rebords."""
        self._nom = nom_texture
        self._crete = crete
        self._relief = relief
        self._vallee = bool(vallee)
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
            self._ctx["sol_echelle_loin"] = float(echelle_loin)
        if not self._vallee:
            for m in self._meshes_vallee:
                m.indices = []
                m.vertices = []
        self._applique_vallee()
        self._recalcule()

    def _recalcule(self, *_):
        """Les angles (sous l'horizon) et la texture de chaque sommet : ne
        dependent que de la case et de la taille de l'ecran."""
        if self._nom is None or self.width <= 0 or self.height <= 0:
            return
        ppd = self.width / FOV
        distances = [DISTANCE_MIN * (DISTANCE_MAX / DISTANCE_MIN)
                     ** (i / float(ANNEAUX - 1)) for i in range(ANNEAUX)]
        self._angles, self._uv, self._bords = [], [], []
        for s in range(SECTEURS):
            az = math.radians(s * PAS_SECTEUR)
            if self._relief is not None:
                pente, bord = self._relief(az)
            else:
                # L'angle du BORD du sol dans cette direction : la crete,
                # comptee depuis l'horizon du ciel.
                pente = 0.0
                bord = (self._crete(az) - self._horizon) * self.height / ppd
            angles, uv = [], []
            sa, ca = math.sin(az), math.cos(az)
            for d in distances:
                angles.append(angle_au_sol(pente, bord, d))
                dt = d if d <= DISTANCE_TEXTURE else (
                    DISTANCE_TEXTURE + (d - DISTANCE_TEXTURE) * TEXTURE_LOIN)
                uv.append((dt * sa / TUILE, dt * ca / TUILE))
            self._angles.append(angles)
            self._uv.append(uv)
            self._bords.append(bord)
        self._place()

    def cache(self):
        """Pas de nappe sur cette case (le lac : chaque panneau y peint
        encore son sol)."""
        self._nom = None
        self._angles = None
        self._vallee = False
        for m in [self._mesh] + self._meshes_vallee:
            m.indices = []
            m.vertices = []

    # -- le regard --------------------------------------------------------- #
    def set_camera(self, lacet, tangage):
        self.lacet = float(lacet)
        self.tangage = float(tangage)
        self._place()

    def set_teinte(self, rgb):
        """La couleur de la lumiere du jour (doree le matin, orange au
        couchant), comme le shader des panneaux l'applique a leur decor."""
        self._jour = tuple(float(c) for c in rgb[:3])
        if self._mesh.texture is not None:
            self._couleur.rgb = self._jour
        self._applique_vallee()

    def set_brume(self, rgb):
        """La couleur du ciel a l'horizon, ou se noie la vallee."""
        self._ciel = tuple(float(c) for c in rgb[:3])
        self._applique_vallee()

    def _applique_vallee(self):
        vert = tuple(v * j for v, j in zip(VERT_VALLEE, self._jour))
        for couleur, brume in zip(self._couleurs_vallee, BRUME_VALLEE):
            couleur.rgb = _melange(vert, self._ciel, brume)

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
        bandes = [[] for _ in BRUME_VALLEE]
        for k in range(colonnes):
            s = premier + k
            az = s * PAS_SECTEUR
            x = cx + (az - self.lacet) * ppd
            angles = self._angles[s % SECTEURS]
            uv = self._uv[s % SECTEURS]
            for a, (u, v) in zip(angles, uv):
                verts += [x, y_horizon + a * ppd, u, v]
            if self._vallee:
                bas = min(self._bords[s % SECTEURS], VALLEE_BANDES[-1]) \
                    - VALLEE_SOUS_REBORD
                bords = VALLEE_BANDES + (bas,)
                for i, bande in enumerate(bandes):
                    bande += [x, y_horizon + bords[i] * ppd, 0.0, 0.0,
                              x, y_horizon + bords[i + 1] * ppd, 0.0, 0.0]
        self._mesh.vertices = verts
        if len(self._mesh.indices) != (colonnes - 1) * (ANNEAUX - 1) * 6:
            idx = []
            for k in range(colonnes - 1):
                for i in range(ANNEAUX - 1):
                    p = k * ANNEAUX + i
                    q = p + ANNEAUX
                    idx += [p, q, q + 1, p, q + 1, p + 1]
            self._mesh.indices = idx
        if self._vallee:
            idx = []
            for k in range(colonnes - 1):
                p = 2 * k
                idx += [p, p + 2, p + 3, p, p + 3, p + 1]
            for m, bande in zip(self._meshes_vallee, bandes):
                m.vertices = bande
                if len(m.indices) != len(idx):
                    m.indices = idx


__all__ = ["SolPanorama", "altitude", "angle_au_sol"]
