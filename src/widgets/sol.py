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

UNE RIVE. Au bord d'un lac, une plage entoure le joueur ; vers les cases du
lac, l'EAU commence a quelques metres (son RIVAGE, qui s'eloigne sur les
cotes jusqu'a se refermer sur la terre) et s'etend jusqu'a la BERGE d'en
face, une bande d'herbe lointaine posee sur l'horizon. L'eau est plane, a
son niveau, un peu sous les pieds ; son fond transparait de pres, le ciel
s'y reflete de loin, et elle derive doucement (voir FS_EAU).

LA NAPPE N'EST PAS UN WIDGET (voir Nappe) : le panorama la pose sous ses
quatre panneaux (SolPanorama), mais une scene vue d'un seul cote -- l'ecran
de pose, la carte -- la peint aussi, dans son propre dessin.
"""
import math
import os

from kivy.clock import Clock
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
# plus bleuie par l'air (BRUME_VALLEE, a peine : par temps clair on voit
# loin), et de l'une a l'autre la teinte ne change que d'un cran, sans ligne
# visible. La derniere descend jusque sous
# le rebord.
VALLEE_BANDES = (-0.6, -1.2, -2.0, -3.2, -5.0)
VALLEE_HAUT = VALLEE_BANDES[0]
VALLEE_SOUS_REBORD = 4.0
VERT_VALLEE = (0.17, 0.27, 0.11)
# LE FOND DE VALLEE est un vrai sol, vu d'en haut : de l'herbe, a cette
# profondeur sous l'oeil (metres), en tuiles de ce cote (metres), et un peu
# assombrie (TEINTE_VALLEE). Il n'etait qu'un aplat vert.
PROFONDEUR_VALLEE = 70.0
TUILE_VALLEE = 9.0
TEINTE_VALLEE = (0.78, 0.82, 0.78)
BRUME_VALLEE = (0.24, 0.20, 0.16, 0.12, 0.08)

# L'EAU : son niveau sous les pieds (metres), la berge d'en face (metres),
# les rangees de son maillage, sa tuile (metres) et sa matiere (le fond du
# lac vu a travers l'eau).
NIVEAU_EAU = -0.35
BERGE_LOIN = 260.0
RANGEES_EAU = 10
TUILE_EAU = 3.0
MATIERE_EAU = "water"
# LA BERGE D'EN FACE : de l'herbe, si loin qu'elle n'est plus qu'une
# couleur, a moitie noyee dans le ciel. Elle part un peu sous l'eau (que
# l'eau recouvre) pour qu'aucun jour ne reste entre les deux.
VERT_BERGE = (0.20, 0.30, 0.12)
BRUME_BERGE = 0.16
BERGE_SOUS_EAU = 0.4
# LE SABLE MOUILLE, le long de l'eau : une bande sombre, a demi
# transparente, sur les SABLE_MOUILLE derniers metres de la plage. Le
# rivage n'est plus une decoupe nette.
SABLE_MOUILLE = 1.6
COULEUR_MOUILLE = (0.24, 0.20, 0.14, 0.32)
# L'eau derive a cette cadence (images par seconde) : assez pour qu'elle
# vive, assez peu pour ne rien couter.
EAU_FPS = 15.0

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

# L'eau : son fond, vu a travers deux couches qui derivent l'une contre
# l'autre (c'est ce qui la fait onduler), et le ciel qui s'y reflete d'autant
# plus qu'on la regarde de loin, donc a plat. La coordonnee de texture est la
# position sur l'eau en tuiles : sa longueur donne la distance.
FS_EAU = """
$HEADER$
uniform vec3 eau_ciel;
uniform float eau_t;
void main(void) {
    float d = length(tex_coord0) * %(tuile)f;
    vec2 a = tex_coord0 + vec2(eau_t * 0.010, eau_t * 0.006);
    vec2 b = tex_coord0 * 0.61 + vec2(-eau_t * 0.007, eau_t * 0.004);
    vec3 fond = mix(texture2D(texture0, a).rgb,
                    texture2D(texture0, b).rgb, 0.5);
    float k = 0.30 + 0.62 * smoothstep(3.0, 120.0, d);
    gl_FragColor = vec4(mix(fond * frag_color.rgb, eau_ciel, k),
                        frag_color.a);
}
""" % {"tuile": TUILE_EAU}

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
                    _anisotrope(tex)
                except Exception:
                    tex = None
                break
        _TEXTURES[nom] = tex
    return _TEXTURES[nom]


_ANISOTROPIE = []


def _anisotrope(tex):
    """LE SOL RESTE NET AU LOIN. Vu en enfilade, il est lu dans ses
    reductions (mipmaps), qui le brouillent d'autant plus qu'on le regarde a
    plat : au loin, il devenait un flou qu'on prenait pour de la brume. Le
    filtrage anisotrope y lit les details dans le bon sens. C'est une
    extension d'OpenGL presque partout presente ; absente, rien ne change."""
    if not _ANISOTROPIE:
        niveau = 0.0
        try:
            from kivy.graphics import opengl as gl
            ext = gl.glGetString(gl.GL_EXTENSIONS) or b""
            if b"texture_filter_anisotropic" in ext:
                niveau = 8.0
                try:
                    maxi = gl.glGetFloatv(0x84FF)      # ..._MAX_ANISOTROPY
                    maxi = maxi[0] if isinstance(maxi, (list, tuple)) \
                        else maxi
                    niveau = max(1.0, min(niveau, float(maxi)))
                except Exception:
                    niveau = 4.0
        except Exception:
            niveau = 0.0
        _ANISOTROPIE.append(niveau)
    if _ANISOTROPIE[0] > 1.0:
        try:
            from kivy.graphics import opengl as gl
            tex.bind()
            gl.glTexParameterf(gl.GL_TEXTURE_2D, 0x84FE, _ANISOTROPIE[0])
        except Exception:
            pass


def altitude(pente, crete, d):
    """La hauteur du sol (metres, 0 sous les pieds) a `d` metres, dans une
    direction ou il part avec cette `pente` (tangente) et finit, a
    DISTANCE_MAX, sur son bord vu a l'angle `crete` (degres au-dessus de
    l'horizon de l'oeil)."""
    bord = OEIL + DISTANCE_MAX * math.tan(math.radians(crete))
    return pente * d + (bord - pente * DISTANCE_MAX) \
        * (d / DISTANCE_MAX) ** REMONTEE


def pente_vers(z, crete, d):
    """La pente qui fait passer le sol par l'altitude `z` a `d` metres, s'il
    finit sur `crete` (l'inverse d'altitude)."""
    bord = OEIL + DISTANCE_MAX * math.tan(math.radians(crete))
    q = (d / DISTANCE_MAX) ** REMONTEE
    den = d - DISTANCE_MAX * q
    return (z - bord * q) / den if abs(den) > 1e-6 else 0.0


def angle_au_sol(pente, crete, d):
    """L'angle (degres, negatif sous l'horizon) sous lequel l'oeil voit le
    sol a `d` metres dans cette direction."""
    return math.degrees(math.atan2(altitude(pente, crete, d) - OEIL, d))


def angle_eau(d):
    """L'angle sous lequel l'oeil voit l'eau a `d` metres."""
    return math.degrees(math.atan2(NIVEAU_EAU - OEIL, d))


def _melange(a, b, k):
    return tuple(x * (1.0 - k) + y * k for x, y in zip(a, b))


def _contexte(fs):
    """Un contexte de dessin a ce shader, pose dans le canvas en cours ; None
    si le shader ne se compile pas."""
    ctx = RenderContext(use_parent_projection=True,
                        use_parent_modelview=True,
                        use_parent_frag_modelview=True)
    ctx.shader.fs = fs
    return ctx if ctx.shader.success else None


class Nappe(object):
    """Les instructions de la nappe, a creer DANS un bloc `with canvas`.
    `cadre(x, y, w, h)` la cale sur la surface ou elle se dessine,
    `regle(...)` sur une case, `set_camera(lacet, tangage)` sur le regard,
    `set_teinte(rgb)` sur la lumiere du jour, `set_brume(rgb)` sur la
    couleur du ciel a l'horizon et `set_temps(t)` sur l'heure de l'eau."""

    def __init__(self):
        self.x = self.y = 0.0
        self.width = self.height = 0.0
        self.lacet = 0.0
        self.tangage = 0.0
        self._nom = None
        self._horizon = 0.47
        self._crete = None
        self._relief = None
        self._vallee = False
        self._rivage = None
        self._berge = None
        self._angles = None          # [secteur][anneau] : angle sous l'horizon
        self._uv = None              # [secteur][anneau] : (u, v)
        self._bords = None           # [secteur] : angle du bord du sol
        self._eau = None             # [secteur] : [(angle, u, v)] ou None
        self._berges = None          # [secteur] : (bas, haut) de la berge
        self._mouille = None         # [secteur] : (bas, haut) du sable mouille
        self._jour = (1.0, 1.0, 1.0)
        self._ciel = (0.70, 0.80, 0.90)
        # Du plus loin au plus pres : la vallee, la berge d'en face, la
        # nappe, puis l'eau, qui recouvre la nappe partout ou elle s'etend.
        self._couleurs_vallee = []
        self._meshes_vallee = []
        for _ in BRUME_VALLEE:
            self._couleurs_vallee.append(Color(1, 1, 1, 1))
            self._meshes_vallee.append(Mesh(mode="triangles"))
        self._couleur_berge = Color(1, 1, 1, 1)
        self._mesh_berge = Mesh(mode="triangles")
        # Le shader du fondu ; sans lui (pilote trop ancien), la seule
        # matiere proche.
        self._ctx = _contexte(FS)
        if self._ctx is not None:
            with self._ctx:
                self._couleur = Color(1, 1, 1, 1)
                self._loin = BindTexture(index=1)
                self._mesh = Mesh(mode="triangles")
            self._ctx["sol_loin"] = 1
            self._ctx["sol_teinte_loin"] = [1.0, 1.0, 1.0]
            self._ctx["sol_fondu"] = [PRES_PLEIN, PRES_FIN]
            self._ctx["sol_echelle_loin"] = 1.0
        else:
            self._couleur = Color(1, 1, 1, 1)
            self._loin = None
            self._mesh = Mesh(mode="triangles")
        self._couleur_mouille = Color(*COULEUR_MOUILLE)
        self._mesh_mouille = Mesh(mode="triangles")
        # L'eau ; sans son shader, son fond seul, a demi teinte de ciel.
        self._ctx_eau = _contexte(FS_EAU)
        if self._ctx_eau is not None:
            with self._ctx_eau:
                self._couleur_eau = Color(1, 1, 1, 1)
                self._mesh_eau = Mesh(mode="triangles")
            self._ctx_eau["eau_ciel"] = list(self._ciel)
            self._ctx_eau["eau_t"] = 0.0
        else:
            self._couleur_eau = Color(1, 1, 1, 1)
            self._mesh_eau = Mesh(mode="triangles")

    # -- la surface et la case --------------------------------------------- #
    def cadre(self, x, y, w, h):
        if (x, y, w, h) == (self.x, self.y, self.width, self.height):
            return
        self.x, self.y, self.width, self.height = x, y, w, h
        self._recalcule()

    def regle(self, nom_texture, crete, horizon, loin=None,
              teinte_loin=(1.0, 1.0, 1.0), relief=None, vallee=False,
              echelle_loin=1.0, fondu=(PRES_PLEIN, PRES_FIN), rivage=None,
              berge=None):
        """`nom_texture` : la matiere du sol ; `crete(azimut_rad)` -> hauteur
        de la crete a l'ecran (part de la hauteur, tete droite) dans cette
        direction ; `horizon` : la hauteur de l'horizon du ciel.

        `loin` : la matiere qui la remplace au loin (None : la meme), que
        `teinte_loin` recolore ; `echelle_loin` < 1 l'agrandit (une meme
        matiere, vue de loin, y gagne de grandes taches). `fondu` : les
        distances (metres de texture) ou elle commence a la remplacer, et
        ou elle l'a remplacee.

        `relief(azimut_rad)` -> (pente, crete en degres) : un VERSANT (voir
        altitude) ; il remplace alors `crete`. `vallee` : montrer la vallee
        au-dela des rebords.

        `rivage(azimut_rad)` -> distance (metres) ou l'eau commence dans
        cette direction, ou None ; `berge(azimut_rad)` -> l'angle (degres)
        du haut de la berge d'en face."""
        self._nom = nom_texture
        self._crete = crete
        self._relief = relief
        self._vallee = bool(vallee)
        self._rivage = rivage
        self._berge = berge
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
            self._ctx["sol_fondu"] = [float(fondu[0]), float(fondu[1])]
        self._mesh_eau.texture = _texture(MATIERE_EAU)
        self._mesh_berge.texture = _texture("grass")
        tex_vallee = _texture("grass") if self._vallee else None
        for m in self._meshes_vallee:
            m.texture = tex_vallee
        self._vide(self._meshes_vallee + [self._mesh_berge, self._mesh_eau,
                                          self._mesh_mouille])
        self._applique_couleurs()
        self._recalcule()

    @staticmethod
    def _vide(meshes):
        for m in meshes:
            m.indices = []
            m.vertices = []

    def _recalcule(self):
        """Les angles (sous l'horizon) et la texture de chaque sommet : ne
        dependent que de la case et de la taille de l'ecran."""
        if self._nom is None or self.width <= 0 or self.height <= 0:
            return
        ppd = self.width / FOV
        distances = [DISTANCE_MIN * (DISTANCE_MAX / DISTANCE_MIN)
                     ** (i / float(ANNEAUX - 1)) for i in range(ANNEAUX)]
        self._angles, self._uv, self._bords = [], [], []
        self._eau = [] if self._rivage is not None else None
        self._berges = [] if self._rivage is not None else None
        self._mouille = [] if self._rivage is not None else None
        bas_berge = angle_eau(BERGE_LOIN) - BERGE_SOUS_EAU
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
            if self._rivage is not None:
                # L'eau, de son rivage a la berge d'en face. Pas d'eau dans
                # cette direction : une rangee de largeur nulle, a la berge.
                r = self._rivage(az)
                r = BERGE_LOIN if r is None else max(0.5, min(BERGE_LOIN, r))
                if r < DISTANCE_MAX:
                    self._mouille.append((
                        angle_au_sol(pente, bord, max(0.1, r - SABLE_MOUILLE)),
                        angle_eau(r)))
                else:
                    self._mouille.append((angle_eau(BERGE_LOIN),) * 2)
                rangs = []
                for i in range(RANGEES_EAU):
                    d = r * (BERGE_LOIN / r) ** (i / float(RANGEES_EAU - 1))
                    rangs.append((angle_eau(d), d * sa / TUILE_EAU,
                                  d * ca / TUILE_EAU))
                self._eau.append(rangs)
                self._berges.append((bas_berge, self._berge(az)))
        self._place()

    def cache(self):
        """Pas de nappe sur cette case."""
        self._nom = None
        self._angles = None
        self._vallee = False
        self._rivage = None
        self._vide([self._mesh, self._mesh_berge, self._mesh_eau,
                    self._mesh_mouille] + self._meshes_vallee)

    def a_de_l_eau(self):
        return self._nom is not None and self._rivage is not None

    # -- le regard et la lumiere ------------------------------------------- #
    def set_camera(self, lacet, tangage):
        self.lacet = float(lacet)
        self.tangage = float(tangage)
        self._place()

    def set_teinte(self, rgb):
        """La couleur de la lumiere du jour (doree le matin, orange au
        couchant), comme le shader des panneaux l'applique a leur decor."""
        self._jour = tuple(float(c) for c in rgb[:3])
        self._applique_couleurs()

    def set_brume(self, rgb):
        """La couleur du ciel a l'horizon : la vallee et la berge s'y
        noient, l'eau la reflete."""
        self._ciel = tuple(float(c) for c in rgb[:3])
        self._applique_couleurs()

    def set_temps(self, t):
        """L'heure de l'eau (secondes), qui la fait deriver."""
        if self._ctx_eau is not None:
            self._ctx_eau["eau_t"] = float(t % 1000.0)

    def _applique_couleurs(self):
        if self._mesh.texture is not None:
            self._couleur.rgb = self._jour
        herbe = textures.average_color("grass") or (0.33, 0.42, 0.10)
        texturee = bool(self._meshes_vallee) and \
            self._meshes_vallee[0].texture is not None
        if texturee:
            # La texture porte la couleur : la teinte ne fait que l'assombrir
            # un peu, et la ramener vers le ciel d'un soupcon.
            vert = tuple(t * j for t, j in zip(TEINTE_VALLEE, self._jour))
            ciel = tuple(c / max(0.05, m) for c, m in
                         zip(self._ciel, herbe[:3]))
        else:
            vert = tuple(v * j for v, j in zip(VERT_VALLEE, self._jour))
            ciel = self._ciel
        for couleur, brume in zip(self._couleurs_vallee, BRUME_VALLEE):
            couleur.rgb = _melange(vert, ciel, brume)
        # La berge : l'herbe, dont la texture lointaine n'est plus que sa
        # couleur moyenne -- la teinte la ramene a ce vert, puis au ciel.
        herbe = textures.average_color("grass") or (0.33, 0.42, 0.10)
        vert = tuple(v * j / max(0.05, m) for v, j, m in
                     zip(VERT_BERGE, self._jour, herbe[:3]))
        ciel = tuple(c / max(0.05, m) for c, m in zip(self._ciel, herbe[:3]))
        if self._mesh_berge.texture is None:
            vert = tuple(v * j for v, j in zip(VERT_BERGE, self._jour))
            ciel = self._ciel
        self._couleur_berge.rgb = _melange(vert, ciel, BRUME_BERGE)
        if self._ctx_eau is not None:
            self._couleur_eau.rgb = self._jour
            self._ctx_eau["eau_ciel"] = list(self._ciel)
        else:
            self._couleur_eau.rgb = _melange(self._jour, self._ciel, 0.5)

    # -- la place a l'ecran ------------------------------------------------ #
    def _colonnes(self):
        """(premier secteur, nombre de colonnes) a dessiner pour ce
        regard."""
        demi = int(math.ceil((FOV / 2.0) / PAS_SECTEUR)) + MARGE_SECTEURS
        premier = int(math.floor(self.lacet / PAS_SECTEUR)) - demi
        return premier, 2 * demi + 2

    def _y_horizon(self, ppd):
        return self.y + self._horizon * self.height - self.tangage * ppd

    def _place(self):
        """Les sommets des secteurs a l'ecran, a leur place pour ce regard."""
        if self._angles is None or self.width <= 0:
            return
        ppd = self.width / FOV
        y_horizon = self._y_horizon(ppd)
        cx = self.x + self.width / 2.0
        premier, colonnes = self._colonnes()
        verts = []
        bandes = [[] for _ in BRUME_VALLEE]
        eau, berge, mouille = [], [], []
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
                sa = math.sin(math.radians(az))
                ca = math.cos(math.radians(az))
                uv = []
                for a in bords:
                    # Le point du fond de vallee vu sous cet angle.
                    d = PROFONDEUR_VALLEE / math.tan(math.radians(
                        -min(a, -0.05)))
                    uv.append((d * sa / TUILE_VALLEE, d * ca / TUILE_VALLEE))
                for i, bande in enumerate(bandes):
                    bande += [x, y_horizon + bords[i] * ppd,
                              uv[i][0], uv[i][1],
                              x, y_horizon + bords[i + 1] * ppd,
                              uv[i + 1][0], uv[i + 1][1]]
            if self._eau is not None:
                for a, u, v in self._eau[s % SECTEURS]:
                    eau += [x, y_horizon + a * ppd, u, v]
                m0, m1 = self._mouille[s % SECTEURS]
                mouille += [x, y_horizon + m0 * ppd, 0.0, 0.0,
                            x, y_horizon + m1 * ppd, 0.0, 0.0]
                b0, b1 = self._berges[s % SECTEURS]
                berge += [x, y_horizon + b0 * ppd, az * 0.25, b0 * 2.0,
                          x, y_horizon + b1 * ppd, az * 0.25, b1 * 2.0]
        self._mesh.vertices = verts
        if len(self._mesh.indices) != (colonnes - 1) * (ANNEAUX - 1) * 6:
            self._mesh.indices = self._grille(colonnes, ANNEAUX)
        bande_idx = self._grille(colonnes, 2)
        if self._vallee:
            for m, bande in zip(self._meshes_vallee, bandes):
                m.vertices = bande
                if len(m.indices) != len(bande_idx):
                    m.indices = bande_idx
        if self._eau is not None:
            self._mesh_eau.vertices = eau
            if len(self._mesh_eau.indices) != \
                    (colonnes - 1) * (RANGEES_EAU - 1) * 6:
                self._mesh_eau.indices = self._grille(colonnes, RANGEES_EAU)
            self._mesh_berge.vertices = berge
            if len(self._mesh_berge.indices) != len(bande_idx):
                self._mesh_berge.indices = bande_idx
            self._mesh_mouille.vertices = mouille
            if len(self._mesh_mouille.indices) != len(bande_idx):
                self._mesh_mouille.indices = bande_idx

    @staticmethod
    def _grille(colonnes, rangs):
        idx = []
        for k in range(colonnes - 1):
            for i in range(rangs - 1):
                p = k * rangs + i
                q = p + rangs
                idx += [p, q, q + 1, p, q + 1, p + 1]
        return idx

    def boite_eau(self, bas_min=None):
        """(x0, y0, x1, y1) a l'ecran de l'eau qu'on voit, pour ce regard :
        de son bord le plus proche a la berge d'en face. None si aucune eau
        n'est en vue. `bas_min` : le bas de la boite ne descend pas plus
        bas."""
        if self._eau is None or self.width <= 0:
            return None
        ppd = self.width / FOV
        y_horizon = self._y_horizon(ppd)
        cx = self.x + self.width / 2.0
        premier, colonnes = self._colonnes()
        xs, bas = [], []
        for k in range(colonnes):
            s = premier + k
            x = cx + (s * PAS_SECTEUR - self.lacet) * ppd
            rangs = self._eau[s % SECTEURS]
            if not (self.x <= x <= self.x + self.width):
                continue
            if rangs[-1][0] - rangs[0][0] < 0.05:
                continue                        # pas d'eau ici
            xs.append(x)
            bas.append(y_horizon + rangs[0][0] * ppd)
        if not xs:
            return None
        haut = y_horizon + angle_eau(BERGE_LOIN) * ppd
        y0 = min(bas)
        if bas_min is not None:
            y0 = max(y0, bas_min)
        if haut - y0 < 4.0:
            return None
        return (min(xs), y0, max(xs), haut)


class SolPanorama(Widget):
    """La nappe du panorama, sous ses quatre panneaux (voir Nappe). Elle
    fait aussi deriver l'eau."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            self.nappe = Nappe()
        self._horloge = None
        self.bind(size=self._cadre, pos=self._cadre)

    def _cadre(self, *_):
        self.nappe.cadre(self.x, self.y, self.width, self.height)

    def regle(self, *args, **kwargs):
        self.nappe.cadre(self.x, self.y, self.width, self.height)
        self.nappe.regle(*args, **kwargs)
        self._regle_horloge()

    def cache(self):
        self.nappe.cache()
        self._regle_horloge()

    def _regle_horloge(self):
        if self.nappe.a_de_l_eau():
            if self._horloge is None:
                self._horloge = Clock.schedule_interval(self._tic,
                                                        1.0 / EAU_FPS)
        elif self._horloge is not None:
            self._horloge.cancel()
            self._horloge = None

    def _tic(self, _dt):
        self.nappe.set_temps(Clock.get_boottime())

    def set_camera(self, lacet, tangage):
        self.nappe.set_camera(lacet, tangage)

    def set_teinte(self, rgb):
        self.nappe.set_teinte(rgb)

    def set_brume(self, rgb):
        self.nappe.set_brume(rgb)

    def boite_eau(self, bas_min=None):
        return self.nappe.boite_eau(bas_min)


__all__ = ["SolPanorama", "Nappe", "altitude", "angle_au_sol", "angle_eau",
           "pente_vers"]
