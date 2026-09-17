"""
Decor de zone en vue RAPPROCHEE (immersive).

Le joueur est AU MILIEU de la scene : la decoration remplit tout le cadre, pas
seulement une bande en bas. On voit donc :
- Foret    : on est entoure d'arbres (du sol a la canopee),
- Plaine   : on est dans les hautes herbes jusqu'a l'horizon,
- Montagne : on est sur la pente (la roche occupe le cadre),
- Lac      : on est au bord de l'eau (grande etendue d'eau + roseaux).

`set_scene(zone_type, seed)` change la scene. Redessine seulement quand la zone
change (pas a chaque frame).

`set_daylight(secondes)` fait suivre l'HEURE a la scene : couleur de la
lumiere et ombres portees. Il ne redessine RIEN -- il ne fait que retoucher
deux uniformes du shader et repositionner les ombres deja en place. C'est ce
qui permet au decor de vivre au fil de la journee sans reconstruire ses
centaines de formes a chaque minute.
"""
import math
import random

from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.graphics import (Color, Ellipse, Rectangle, Triangle, Line, Quad,
                           Mesh, RenderContext, PushMatrix, PopMatrix, Rotate)

from src import world, items
from src.widgets import textures, pbr, foliage, daylight
from src.widgets import horizon
from src.widgets.textures import paint, paint_color, tiled_coords
from src.widgets.installed_layer import grid_to_screen
from src.widgets import build_grid
from src.widgets import log_skin

_ZONE_SEED = {"Foret": 1, "Plaine": 2, "Montagne": 3, "Lac": 4}

# Nombre d'objets RECOLTABLES (disponibles) par type et par case : petit nombre
# aleatoire (comme avant). Chaque recolte retire du DECOR une part egale du
# nombre d'objets visibles (ex. 9 visibles / 3 disponibles -> 3 retires/recolte).
_AVAIL_MIN = 2
_AVAIL_MAX = 5

# Plancher VERTICAL des objets recoltables : ils ne sont JAMAIS places sous ce
# niveau (~ la hauteur des jointures des mains du joueur). Fraction de la
# hauteur d'ecran. On les repartit donc de cette ligne jusqu'au haut du terrain.
_HARVEST_FLOOR = 0.18

# APLATISSEMENT DES FORMES POSEES A PLAT. Une case de la grille est un carre
# sur le sol ; vue depuis les yeux du joueur elle se couche, et sa profondeur
# a l'ecran ne fait plus que cette fraction de sa largeur. Tout ce qui repose
# a plat -- le foyer, un plan de construction, les cases interdites -- doit
# partager la MEME valeur, sinon ces formes ne se posent plus sur la meme
# grille et se decalent les unes des autres.
_PLAT_PROFONDEUR = 0.55

# Retrait du marquage d'une EMPRISE vers l'interieur de ses cases, en fraction
# de case. Pris pile au bord, deux emprises voisines se toucheraient et leurs
# cordes se liraient comme une seule cloture traversant le terrain.
_EMPRISE_RETRAIT = 0.14

# Retrecissement du bord du FOND par rapport a celui de devant. C'est la seule
# part de perspective qu'on garde pour ces formes : celle qui se lit.
_EMPRISE_FUITE = 0.82

# Hauteur d'un cube de construction, en fraction de la LARGEUR d'un cube.
# Un peu moins que sa largeur : la vue etant rasante, la hauteur n'est pas
# foreshortenue alors que le sol l'est, et un rapport de un pour un donnait
# une tour plutot qu'un abri. On ne prend PAS la profondeur pour reference :
# elle est ecrasee par la vue rasante -- elle ne fait que la moitie de la
# largeur -- et s'en servir donnerait une maison aplatie comme une galette.
_CUBE_HAUTEUR = 0.82

# ASSOMBRISSEMENT DES FACES D'UNE CONSTRUCTION. La vue du jeu est FIXE : il n'y
# a pas de normale a tourner ici comme dans le chantier, seulement quatre
# valeurs qui disent de combien chaque orientation est dans l'ombre. La face
# ARRIERE ne se dessine jamais, mais le flanc lointain d'une buche, lui, se
# voit : d'ou une valeur pour elle aussi.
_OMBRE_DESSUS = 1.00
_OMBRE_DEVANT = 0.62
_OMBRE_DERRIERE = 0.40
_OMBRE_GAUCHE = 0.44
_OMBRE_DROITE = 0.52


def _peau_bois(tex, ombre, points, tex_coords, eventail=False):
    """Un polygone habille de bois : la texture si on l'a, sinon la couleur.

    L'ECLAIREMENT EST ADOUCI quand il y a une texture. L'image de l'objet
    porte deja son propre modele -- elle a ete dessinee ronde -- et lui
    appliquer le notre par-dessus noircissait les flancs deux fois."""
    f = (1.0 - _ECLAT_BUCHE * (1.0 - ombre)) if tex is not None else ombre
    if tex is not None:
        Color(f, f, f, 1)
    else:
        r, g, b = log_skin.BOIS
        Color(min(1.0, r * f), min(1.0, g * f), min(1.0, b * f), 1)
    verts = []
    for i in range(0, len(points), 2):
        verts += [points[i], points[i + 1], tex_coords[i], tex_coords[i + 1]]
    n = len(points) // 2
    if eventail:
        indices, mode = list(range(n)), "triangle_fan"
    else:
        indices, mode = [0, 1, 2, 0, 2, 3], "triangles"
    Mesh(vertices=verts, indices=indices, mode=mode, texture=tex)


# Combien on garde de l'assombrissement quand la texture est la (voir
# _peau_bois).
_ECLAT_BUCHE = 0.55

# Ce qui reste de lumiere au fond de la rainure entre deux buches.
_CREUX_BUCHE = 0.42


# L'ATELIER, en fractions de la largeur de son emprise : hauteur de ses pieds,
# puis epaisseur de son plateau. Un etabli arrive a la taille : plus bas on
# travaille a genoux, plus haut on ne voit plus ce qu'on fait.
_ETABLI_HAUTEUR = 0.30
_ETABLI_PLATEAU = 0.09

# Taille des flammes selon l'etat du feu (voir game_state.FIRE_LEVELS).
# "braise" = plus de flamme du tout, seules les braises rougeoient.
_FLAME_SCALE = {"grand": 1.00, "moyen": 0.66, "petit": 0.36, "braise": 0.0}

# Langues de flamme : (decalage horizontal, taille, couleur).
_FLAME_TONGUES = ((-0.20, 0.62, (0.90, 0.32, 0.07, 1)),
                  (0.19, 0.70, (0.94, 0.44, 0.10, 1)),
                  (0.00, 1.00, (0.98, 0.62, 0.14, 1)),
                  (0.00, 0.45, (1.00, 0.88, 0.38, 1)))

# Cadence de l'animation du feu. 30 images/s suffisent largement pour un
# vacillement credible, et c'est deux fois moins de travail que 60.
_FLAME_FPS = 30.0

# --- BALANCEMENT DE LA VEGETATION ----------------------------------------- #
# Une scene compte jusqu'a 130 touffes d'herbe de 5 brins : les animer toutes
# ferait 650 formes a repositionner par image, bien trop pour un telephone.
# On n'anime donc que les touffes du PREMIER PLAN (les plus grandes, celles
# qu'on regarde), et a cadence reduite : le reste est immobile et personne ne
# le remarque, parce que le regard suit ce qui bouge devant.
SWAY = True
_SWAY_MAX = 30          # nombre de brins animes au plus
_SWAY_FPS = 15.0        # images par seconde du balancement
# Amplitude du balancement, en fraction de la HAUTEUR du brin (a vent 1.0) :
# un brin haut se courbe donc plus qu'un brin ras, comme en vrai.
_SWAY_AMPLITUDE = 0.06
# Inclinaison PERMANENTE dans le sens du vent : l'herbe ne revient jamais tout
# a fait droite tant qu'il souffle, elle oscille autour d'une position penchee.
_SWAY_BIAS = 0.35

# Force du vent par meteo : le decor se courbe quand il souffle.
_WIND = {"clair": 0.55, "nuageux": 0.9, "pluie": 1.5, "neige": 1.0,
         "orage": 2.6, "blizzard": 3.0}
_WIND_DEFAULT = 0.8

# Ombre portee : aplatissement de l'ellipse (x la largeur de l'objet).
_SHADOW_FLAT = 0.30

# --- PROFONDEUR DU SOL ----------------------------------------------------- #
# Le sol est vu EN OBLIQUE, pas de face : ce qui est loin doit paraitre plus
# petit. Une texture simplement repetee a taille constante donne au contraire
# un papier peint -- l'oeil n'y lit aucune distance.
#
# On traite donc le sol comme un PLAN vu par une camera. A la profondeur t
# (0 en bas de l'ecran, 1 sur la crete), la distance vaut :
#
#       k(t) = 1 / (1 - t * (1 - 1/GROUND_DEPTH))
#
# soit 1 au premier plan et GROUND_DEPTH au fond. La texture n'est plus
# indexee par la position a l'ecran mais par CETTE distance : les tuiles se
# resserrent en montant (v) et s'ecartent du point de fuite (u), donc
# retrecissent dans les deux sens a la fois. C'est le sol des vieux jeux
# "mode 7".
#
# GROUND_DEPTH = de combien de fois le fond est PLUS LOIN que le premier plan.
# Attention, la tuile ne retrecit pas du meme facteur dans les deux sens : un
# sol vu en oblique est vu de plus en plus RASANT a mesure qu'il s'eloigne. Au
# fond, la tuile est donc GROUND_DEPTH fois plus etroite mais GROUND_DEPTH AU
# CARRE fois plus BASSE -- c'est cet ecrasement qui fait que l'oeil lit un sol
# qui file au loin, et non un mur.
#
# D'ou une valeur mesuree : a 3.6, la tuile d'herbe (448 px au sol) fait
# encore ~124 x 35 px sur la crete. La profondeur saute aux yeux et l'image
# reste lisible ; plus haut, elle se reduirait a quelques pixels de bouillie.
# Mettre 1.0 revient a l'ancienne repetition reguliere, sans profondeur.
GROUND_DEPTH = 3.6

# Nombre de bandes horizontales du maillage du sol. La perspective est une
# COURBE, mais la carte graphique interpole en LIGNE DROITE d'un sommet a
# l'autre : trop peu de bandes et la courbe se voit en segments. Les bandes
# sont reparties par distance egale, donc serrees pres de la crete, la ou tout
# change vite.
GROUND_ROWS = 14

# Fleurs de plaine : couleur de repli ET image correspondante. On tire la
# PAIRE d'un coup : sans cela, une fleur tiree "jaune" pouvait se voir poser
# l'image d'une fleur rouge.
_FLOWERS = (((1.00, 1.00, 0.92, 1), "flower_white"),
            ((0.96, 0.85, 0.28, 1), "flower_yellow"),
            ((0.92, 0.42, 0.52, 1), "flower_red"),
            ((0.72, 0.52, 0.92, 1), "flower_purple"),
            ((0.46, 0.58, 0.94, 1), "flower_blue"))

# Image du decor propre a chaque zone : une pierre de foret est moussue, une
# pierre de montagne est nue. Le decor pioche ici plutot que de coder le nom
# en dur a chaque appel.
_ZONE_SPRITES = {
    "Foret":    {"stone": "stone_forest", "branch": "branch_forest",
                 "bush": "bush_forest", "plant": "fern",
                 "mushroom": "mushroom_forest"},
    "Plaine":   {"stone": "stone_plain", "branch": "branch_plain",
                 "bush": "bush_plain", "plant": "plant_leafy",
                 "mushroom": "mushroom_forest"},
    "Montagne": {"stone": "stone_mountain", "branch": "branch_plain",
                 "bush": "bush_plain", "plant": "plant_leafy",
                 "mushroom": "mushroom_forest"},
    "Lac":      {"stone": "pebble", "branch": "branch_plain",
                 "bush": "bush_plain", "plant": "plant_leafy",
                 "mushroom": "mushroom_forest"},
}


class ZoneScenery(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._zone = "Foret"
        self._seed = 0
        self._mode = "scene"        # "scene" = vue horizon ; "ground" = vue sol
        # Recolte : nombre deja recolte par objet (applique au dessin pour
        # MASQUER les objets recoltes) et totaux/budgets calcules a la
        # construction de la scene.
        self._taken = {}
        self._neighbours = {}
        self._ord = {}
        self._harvest_total = {}
        self._avail = {}            # {nom: nb recoltable} (aleatoire, par case)
        self.harvest_total = {}     # {nom: total visible dans la scene}
        self.harvest_max = {}       # {nom: nombre de recoltes possibles}
        # Cellules 5x5 occupees par un objet INSTALLE (fire pit, ...) :
        # les objets du decor qui tombent dans la zone visuelle de ces
        # cellules ne sont PAS dessines. Recalcule en debut de _redraw.
        self._blocked_grid = set()
        self._blocked_bboxes = []
        # Objets INSTALLES sur la case : [(nom, gx, gy), ...]. Ils sont
        # dessines DANS la scene (et non dans une couche au-dessus) pour que
        # le tri par profondeur s'applique aussi a eux : un feu de camp pose
        # derriere un buisson passe donc bien DERRIERE ce buisson.
        self._installed = []
        # Cellules dont le GROS element a ete RETIRE (arbre abattu) : elles
        # restent vides, contrairement aux cases bloquees par un objet pose,
        # qui masquent en plus les petits objets du sol.
        self._removed_grid = set()
        # Flammes ANIMEES : les instructions de dessin sont creees une seule
        # fois avec la scene (donc a la bonne profondeur, masquees par ce qui
        # est devant), puis seules leurs coordonnees et leur opacite changent
        # a chaque image. L'horloge ne tourne que s'il y a un feu allume.
        self._flames = []
        self._flame_ev = None
        self._flame_t = 0.0
        # Heure de la scene (midi par defaut) : commande la couleur de la
        # lumiere et la direction des ombres.
        self._seconds = 12 * 3600.0
        # Ombres portees deja dessinees : on les DEPLACE quand le soleil
        # tourne, au lieu de reconstruire la scene.
        self._shadows = []
        # Touffes animees par le vent + leur horloge (voir SWAY).
        self._sway = []
        self._sway_ev = None
        self._sway_t = 0.0
        self._wind = _WIND_DEFAULT
        # Eclairage par shader. Il est desormais installe DES QUE l'eclairage
        # est actif, et non plus seulement quand des cartes de normales
        # existent : c'est lui qui porte aussi la COULEUR de la lumiere (doree
        # le matin, orange au couchant, bleue la nuit), qui doit fonctionner
        # meme sans aucune texture. Sans carte Normal, les cartes neutres
        # rendent le relief exactement nul : le rendu reste celui d'avant.
        self._pbr = pbr.LIGHTING
        if self._pbr:
            self.canvas = RenderContext(use_parent_projection=True,
                                        use_parent_modelview=True,
                                        use_parent_frag_modelview=True)
            pbr.setup(self.canvas)
        self.bind(pos=self._redraw, size=self._redraw)

    # -- heure du jour : lumiere et ombres ------------------------------- #
    def set_daylight(self, seconds):
        """Cale la scene sur l'heure : couleur de la lumiere et ombres.

        Aucune forme n'est recreee : on retouche les uniformes du shader et on
        replace les ombres existantes. Appelable a chaque rafraichissement sans
        crainte."""
        self._seconds = float(seconds)
        self._apply_light()
        off, length, alpha = daylight.shadow(self._seconds)
        for sh in self._shadows:
            self._place_shadow(sh, off, length, alpha)

    def set_wind(self, kind):
        """Force du vent, d'apres la meteo : le decor se courbe davantage."""
        self._wind = _WIND.get(kind, _WIND_DEFAULT)

    def _apply_light(self):
        if self._pbr:
            pbr.set_light(self.canvas, daylight.light_dir(self._seconds),
                          daylight.light_tint(self._seconds))

    def _place_shadow(self, sh, off, length, alpha):
        """Etire et decale une ombre selon la position de l'astre."""
        w = sh["w"] * length
        h = sh["w"] * _SHADOW_FLAT
        cx = sh["cx"] + off * sh["w"]
        sh["e"].pos = (cx - w / 2.0, sh["y"] - h / 2.0)
        sh["e"].size = (w, h)
        sh["c"].a = alpha * sh["k"]

    def _shadow(self, cx, base, width, opacity=1.0):
        """Ombre portee au sol, orientee par l'heure.

        A appeler DANS un bloc `with canvas`, AVANT l'element lui-meme. Avant,
        chaque element ecrivait son ombre en dur, toujours au meme endroit et
        a la meme opacite : a midi comme au couchant, toutes les ombres
        tombaient du meme cote. Elles sont desormais enregistrees ici et
        suivent le soleil (voir set_daylight)."""
        off, length, alpha = daylight.shadow(self._seconds)
        sh = {"c": Color(0, 0, 0, 0), "e": Ellipse(),
              "cx": cx, "y": base, "w": float(width), "k": opacity}
        self._shadows.append(sh)
        self._place_shadow(sh, off, length, alpha)

    # -- liaison des cartes PBR (normal/packed) pour une surface ---------- #
    def _bind_pbr(self, name):
        if self._pbr:
            pbr.bind_maps(textures.normal_texture(name),
                          textures.packed_texture(name))

    def _reset_pbr(self):
        if self._pbr:
            pbr.reset_maps()

    def set_scene(self, zone_type, seed=0, taken=None, blocked_grid=None,
                  installed=None, removed_grid=None, neighbours=None):
        """Vue a l'horizon (sol en bas + ciel).

        `taken` = {nom: nombre deja recolte} pour masquer les objets recoltes.
        `installed` = [(nom, gx, gy[, allume[, niveau]]), ...] : objets poses
        sur la case. Ils sont dessines dans la scene, a leur profondeur ; un
        foyer allume y montre ses flammes, hautes ou basses selon `niveau`
        ("grand", "moyen", "petit", "braise").
        `removed_grid` = iterable de (gx, gy) : gros elements ABATTUS, qui ne
        sont plus dessines du tout.
        `blocked_grid` = iterable de (gx, gy) : cellules occupees par un objet
        INSTALLE (feu de camp, ...) ; deduit de `installed` si absent. Les
        objets du decor qui tombent dans la zone visuelle d'une case bloquee ne
        sont PAS dessines (mais restent collectables via explorer : le budget
        de recolte est preserve).
        `neighbours` = {"face"/"gauche"/"droite": type de zone ou None} : les
        cases voisines, qui apparaissent en silhouette a l'horizon (voir
        horizon.py). Depend de l'ORIENTATION du joueur, donc tourner change le
        fond de la scene."""
        self._zone = zone_type
        self._seed = seed
        self._mode = "scene"
        self._taken = dict(taken or {})
        self._installed = [(o[0], int(o[1]), int(o[2]),
                            bool(o[3]) if len(o) > 3 else False,
                            o[4] if len(o) > 4 else "grand")
                           for o in (installed or [])]
        if blocked_grid is None:
            # L'EMPRISE, pas seulement l'ancrage : un plan de construction
            # couvre quatre cases, et le decor doit s'ecarter des quatre.
            blocked_grid = [c for n, gx, gy, _l, _v in self._installed
                            for c in items.footprint_cells(n, gx, gy)]
        self._blocked_grid = set((int(g[0]), int(g[1]))
                                 for g in (blocked_grid or []))
        self._removed_grid = set((int(g[0]), int(g[1]))
                                 for g in (removed_grid or []))
        self._neighbours = dict(neighbours or {})
        self._redraw()

    def set_taken(self, taken):
        """Met a jour les objets recoltes (masques) et redessine la scene."""
        self._taken = dict(taken or {})
        self._redraw()

    def _avail_for(self, name):
        """Nombre d'objets de ce type RECOLTABLES sur la case (petit, aleatoire
        mais stable pour une case donnee)."""
        if name not in self._avail:
            rng = random.Random(f"{self._seed}:{self._zone}:{name}:avail")
            self._avail[name] = rng.randint(_AVAIL_MIN, _AVAIL_MAX)
        return self._avail[name]

    def _take_or_skip(self, name):
        """Compte un objet recoltable et dit s'il faut le MASQUER (deja recolte).
        A appeler pour CHAQUE objet recoltable lors de la construction.

        Chaque recolte retire une PART EGALE des objets visibles : avec `avail`
        recoltes possibles, la k-ieme recolte a masque ~k/avail des objets."""
        i = self._ord.get(name, 0)
        self._ord[name] = i + 1
        self._harvest_total[name] = self._ord[name]
        taken = self._taken.get(name, 0)
        return (i % self._avail_for(name)) < taken

    # OU S'ARRETE LE SOL DE CHAQUE ZONE, en part de la hauteur de l'ecran :
    # le point le plus BAS de sa surface proche, celle ou reposent les
    # elements. C'est la valeur sur laquelle la grille se resserre.
    #
    # ON PREND LE MINIMUM de la courbe, pas sa valeur a l'endroit exact de la
    # case. Le sol ondule, et suivre l'ondulation aurait demande de connaitre
    # les phases tirees au sort A L'INTERIEUR de chaque scene -- or la grille
    # est aussi lue AVANT le dessin (les cases bloquees) et DEHORS (le toucher,
    # dans game_screen). Au minimum, un element du fond est au pire pose un peu
    # en avant de la crete ; il n'est JAMAIS en l'air, et c'est ce qui compte.
    #
    # Les zones absentes gardent la grille d'origine : la pente de la montagne
    # commence a 0,60 et le lac s'etend jusqu'a 0,60, tous deux au-dessus de
    # la derniere rangee -- rien n'y flotte.
    SOL_DE_GRILLE = {
        "Foret": 0.42 - 0.025 - 0.012,          # voir floor_curve dans _foret
        "Plaine": (0.55 - 0.06 - 0.13) - 0.030 - 0.014,   # voir field_curve
    }

    # OU LE SOL RENCONTRE LE CIEL, en part de la hauteur de l'ecran : la CRETE
    # de la scene. C'est le POINT DE FUITE DES NUAGES -- en s'eloignant ils s'y
    # rapetissent et s'y tassent (voir animated_background).
    #
    # ON PREND LA VALEUR MOYENNE de la courbe, et non son maximum comme le fait
    # SOL_DE_GRILLE juste au-dessus. Les deux ne servent pas a la meme chose :
    # la grille doit garantir que RIEN NE FLOTTE, elle prend donc le pire cas ;
    # les nuages doivent converger la ou l'oeil lit l'horizon, c'est-a-dire au
    # milieu de l'ondulation. Et le terrain, dessine par-dessus, cache l'ecart.
    #
    # CES QUATRE VALEURS SONT TRES DIFFERENTES, et c'est pour cela qu'il a fallu
    # ce dictionnaire plutot qu'une constante : entre la foret et le lac,
    # l'horizon se deplace de presque un quart de la hauteur de l'ecran. Une
    # valeur unique aurait fait flotter les nuages lointains bien au-dessus de
    # la ligne d'eau -- exactement le defaut qu'on cherche a corriger.
    CRETE = {
        "Foret": 0.42 + 0.05,       # voir horizon_curve dans _foret
        "Plaine": 0.55 - 0.06,      # voir edge / horizon_curve dans _plaine
        "Montagne": 0.60,           # surf(0.0) : le pied de la pente
        # LE LAC, C'EST 0,75 ET NON 0,70. On avait pris 0,70, qui est la
        # hauteur ou _lac appelle _horizon -- mais _horizon dessine les
        # silhouettes LOINTAINES, derriere la scene. Le sol, lui, ce sont les
        # collines d'herbe, dont la mesure donne un profil de 0,711 a 0,760.
        # A 0,70 les nuages auraient converge SOUS le sol.
        "Lac": 0.75,                # voir colline() dans _lac
    }

    # Pour les ecrans SANS scene (menu, inventaire, atelier...) : il n'y a pas
    # de sol, mais les nuages ont quand meme besoin d'un point de fuite.
    CRETE_DEFAUT = 0.49

    def hauteur_horizon(self):
        """Part de la hauteur d'ecran ou le sol rencontre le ciel."""
        return self.CRETE.get(self._zone, self.CRETE_DEFAUT)

    def grille(self, gx, gy):
        """(fx, fy, taille) d'une case, corrige du sol de la zone.

        TOUT CE QUI TOUCHE A LA GRILLE PASSE PAR ICI : le decor de proximite,
        les objets installes, leur emprise, les cases bloquees et le toucher
        dans game_screen. Si deux d'entre eux projetaient differemment, un feu
        de camp ne serait plus la ou le doigt le cherche."""
        return grid_to_screen(gx, gy, self.SOL_DE_GRILLE.get(self._zone))

    def _compute_blocked_bboxes(self):
        """Reconstruit les rectangles d'ecran couverts par les objets installes
        (feu de camp, ...) a partir des cellules 5x5 (_blocked_grid)."""
        self._blocked_bboxes = []
        if not self._blocked_grid or self.width <= 0 or self.height <= 0:
            return
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        for (gx, gy) in self._blocked_grid:
            fx, fy, size = self.grille(gx, gy)
            cx = x0 + fx * w
            cy = y0 + fy * h
            # Meme forme aplatie que tout ce qui repose a plat, + petite
            # marge (15 %) pour bien couvrir les objets qui debordent.
            hw = size * w * 0.5 * 1.15
            hh = size * w * _PLAT_PROFONDEUR * 0.5 * 1.15
            self._blocked_bboxes.append((cx, cy, hw, hh))

    def _is_blocked(self, x, y, top=None):
        """True si l'element tombe dans la zone visuelle d'un objet installe
        (feu de camp) sur cette case.

        `top` = hauteur atteinte par l'element. Les plantes poussent VERS LE
        HAUT depuis leur base : n'examiner que la base laisserait une touffe
        enracinee juste devant le foyer monter au milieu des flammes. Avec
        `top`, c'est tout le segment [base, sommet] qui est teste."""
        for cx, cy, hw, hh in self._blocked_bboxes:
            if abs(x - cx) >= hw:
                continue
            if top is None:
                if abs(y - cy) < hh:
                    return True
            elif y <= cy + hh and top >= cy - hh:
                return True
        return False

    def _iter_nature_big(self):
        """Itere les GROS elements du decor de la case, positionnes sur la
        GRILLE 5x5 (les memes cases sont refusees a l'installation d'objets).

        Genere (kind, rang, depth, tx, tb, jit) : type ("tree"/"bush"/
        "rock"/"nugget"), RANG de l'element parmi ceux de son type, profondeur
        0..1, position ecran de la base, et un rng stable pour les variations
        (taille...). Les cases occupees par un objet INSTALLE sont sautees
        (l'objet installe a la priorite d'affichage).

        LE RANG sert a REPARTIR les variantes d'un meme type. Le decor choisit
        d'ordinaire son image d'apres la position, ce qui peut donner cinq
        fois la meme pierre sur une case qui n'en porte que cinq ; avec le
        rang, on distribue les modeles en rond."""
        rangs = {}
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        # Trie du plus LOINTAIN au plus proche (gy decroissant) : les zones qui
        # dessinent directement (sans liste triee) obtiennent ainsi le bon
        # ordre de recouvrement.
        for (ggx, ggy), kind in sorted(
                world.nature_blocked_cells(self._zone, self._seed).items(),
                key=lambda kv: (-kv[0][1], kv[0][0])):
            if ((ggx, ggy) in self._blocked_grid
                    or (ggx, ggy) in self._removed_grid):
                continue
            gfx, gfy, _gs = self.grille(ggx, ggy)
            jit = random.Random(f"{self._seed}:{ggx}:{ggy}:big")
            rang = rangs.get(kind, 0)
            rangs[kind] = rang + 1
            depth = ggy / 4.0
            # AUCUN decalage : l'element est pose EXACTEMENT au centre de sa
            # case, comme un objet installe. C'est ce qui permet de retrouver
            # la meme position dans la grille de placement et dans le jeu.
            tx = x0 + gfx * w
            tb = y0 + gfy * h
            yield kind, rang, depth, tx, tb, jit

    def _installed_items(self):
        """Objets INSTALLES, prets a etre tries avec le reste du decor.

        Renvoie [(y_base, fonction_de_dessin), ...] : la meme forme que les
        elements du decor, donc le tri par profondeur les melange correctement
        (ce qui est plus PROCHE est dessine par-dessus)."""
        out = []
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        for name, gx, gy, lit, level in self._installed:
            fx, fy, size = self.grille(gx, gy)
            cx = x0 + fx * w
            cy = y0 + fy * h
            s = size * w
            if name == "Feu_de_camp":
                # Pose A PLAT et etale de part et d'autre de son centre : son
                # bord PROCHE descend d'une demi-profondeur sous (cx, cy).
                # C'est la qu'il touche le sol, donc c'est la sa cle de tri --
                # sans quoi il passerait pour plus lointain qu'il ne parait, et
                # l'herbe situee derriere se dessinerait par-dessus (meme piege
                # que les buissons).
                out.append((cy - s * _PLAT_PROFONDEUR / 2.0,
                            lambda cx=cx, cy=cy, s=s, lit=lit,
                            lv=level: self._fire_pit(cx, cy, s, lit, lv)))
            elif name == items.BLUEPRINT_T1:
                coins = self._emprise_coins(name, gx, gy)
                base = min(c[1] for c in coins)
                if lit and level:
                    # CHANTIER TERMINE : ce n'est plus un plan, c'est une
                    # construction. Les piquets et la corde n'ont plus rien a
                    # dire -- ils marquaient une intention, elle est realisee.
                    out.append((base,
                                lambda c=coins, b=level: self._batiment(c, b)))
                else:
                    out.append((base, lambda c=coins: self._blueprint(c)))
            elif name == items.WORKBENCH_T1:
                coins = self._emprise_coins(name, gx, gy)
                base = min(c[1] for c in coins)
                out.append((base, lambda c=coins: self._etabli(c)))
        return out

    def _emprise_coins(self, name, gx, gy):
        """Les quatre coins ECRAN de l'emprise au sol d'un objet pose.

        Un objet qui couvre plusieurs cases ne peut pas etre dessine a partir
        d'un centre et d'une taille : la perspective retrecit chaque rangee, et
        sa rangee du fond est plus etroite que celle de devant. On projette
        donc les coins eux-memes, aux DEMI-cases qui bordent l'emprise.

        Rendus dans l'ordre : devant-gauche, devant-droite, fond-droite,
        fond-gauche -- le sens du tour de corde.

        LA FORME SUIT LA CONVENTION DU FOYER, et pas la geometrie vraie. La
        grille est en realite tres ecrasee -- une case fait environ trois fois
        plus large que profonde -- et le foyer ne la respecte pas : il est
        dessine comme un disque aplati a 0,55, donc bien plus rond que sa case.
        Un plan dessine, lui, avec les vrais coins projetes ressortait deux
        fois plus plat que le foyer d'a cote, et penche de surcroit, la grille
        convergeant vers le centre de l'ecran. Cela se lisait comme une cloture
        de travers.

        On garde donc de la perspective ce qui se LIT -- le bord du fond plus
        etroit que celui de devant -- et on laisse le reste, qui ne se lit pas
        et jure avec le decor."""
        fw, fh = items.footprint(name)
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        # RETRAIT vers l'interieur. Pris exactement au bord des cases, le
        # marquage touchait ses voisins et se lisait comme une cloture qui
        # traverse le terrain. Un chantier est balise A L'INTERIEUR de son
        # emprise -- comme le foyer, qui n'occupe pas toute sa case non plus.
        m = _EMPRISE_RETRAIT
        cgx = gx + (fw - 1) / 2.0            # colonne du milieu de l'emprise
        cgy = gy + (fh - 1) / 2.0            # rangee du milieu
        fx_c, fy_c, taille = self.grille(cgx, cgy)
        cx, cy = x0 + fx_c * w, y0 + fy_c * h
        # Largeur : celle du foyer pour UNE case, multipliee par l'emprise.
        large = taille * w * (fw - 2.0 * m)
        # Profondeur : le meme aplatissement que le foyer, a l'echelle de
        # l'emprise. Un carre de cases reste donc un carre aplati, pas une
        # bande.
        prof = taille * w * _PLAT_PROFONDEUR * (fh - 2.0 * m)
        y_av, y_ar = cy - prof / 2.0, cy + prof / 2.0
        av, ar = large / 2.0, large / 2.0 * _EMPRISE_FUITE
        return [(cx - av, y_av), (cx + av, y_av),
                (cx + ar, y_ar), (cx - ar, y_ar)]

    def _batiment(self, coins, bati):
        """La construction achevee d'un chantier, vue depuis le jeu.

        `bati` est l'ensemble des (x, y, z, piece) batis. Le volume du chantier
        fait huit cubes de cote ; on plaque cette grille sur l'emprise au sol
        du plan par INTERPOLATION entre ses quatre coins -- ainsi le batiment
        se retrecit vers le fond exactement comme l'emprise qui le porte, sans
        qu'on ait a refaire une perspective a part.

        ON N'EN DESSINE QUE LA PEAU : une face qui a un cube voisin ne se voit
        pas, et la dessiner quand meme ne coutait pas seulement du temps -- les
        faces internes des cubes de devant recouvraient tout, et la maison se
        lisait comme un empilement de bandes plates. Ecartees, il ne reste que
        la silhouette, avec ses decrochements.

        La hauteur d'un cube est prise sur la LARGEUR de l'emprise, pas sur sa
        profondeur : la profondeur est ecrasee par la vue rasante (elle ne fait
        que la moitie de la largeur), et s'en servir donnerait une maison
        aplatie comme une galette.

        UN NIVEAU N'EST PAS A LA HAUTEUR DE SON INDICE : un pan de mur vaut
        quatre dalles. On passe donc par build_grid.z_bas / z_haut, les memes
        que le chantier -- sinon la maison finie n'aurait pas la silhouette du
        chantier qu'on vient de batir."""
        (x_ag, y_ag), (x_ad, y_ad), (x_fd, y_fd), (x_fg, y_fg) = coins
        nx, ny, _nz = build_grid.VOLUME_T1
        haut = (x_ad - x_ag) / float(nx) * _CUBE_HAUTEUR
        pleins = {(c[0], c[1], c[2]) for c in bati}

        def coin(cx, cy, hz):
            """Un sommet de la grille du chantier, en coordonnees ecran.

            `hz` est une hauteur CONTINUE en unites de cube, pas un indice de
            niveau."""
            u, v = cx / float(nx), cy / float(ny)
            xg = x_ag + (x_fg - x_ag) * v
            yg = y_ag + (y_fg - y_ag) * v
            xd = x_ad + (x_fd - x_ad) * v
            yd = y_ad + (y_fd - y_ad) * v
            return xg + (xd - xg) * u, yg + (yd - yg) * u + hz * haut

        # Les faces d'un cube : le voisin qui la cache, puis ses quatre
        # sommets et son assombrissement. Pas de face du DESSOUS ni de face
        # ARRIERE : dans une vue rasante venant du devant, elles ne se voient
        # jamais, meme au bord du batiment.
        FACES = (
            ((0, 0, 1), ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)),
             _OMBRE_DESSUS),
            ((0, -1, 0), ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)),
             _OMBRE_DEVANT),
            ((-1, 0, 0), ((0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)),
             _OMBRE_GAUCHE),
            ((1, 0, 0), ((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)),
             _OMBRE_DROITE),
        )

        # LES BUCHES DU PLANCHER, calculees sur le sol ENTIER. C'est la meme
        # fonction que le chantier : on voit ici la maison qu'on vient d'y
        # batir, et un plancher qui changerait de buches en sortant du menu
        # dirait que ce n'est pas la meme.
        bandes = build_grid.buches_du_plancher(bati)

        # Du plus LOIN au plus proche, et du bas vers le haut : dans une vue
        # rasante, ce qui est devant et ce qui est haut recouvre le reste.
        for (x, y, z, piece) in sorted(bati,
                                       key=lambda c: (-c[1], c[2], c[0])):
            r, g, b = items.build_part_color(piece)
            bas, sommet = build_grid.z_bas(z), build_grid.z_haut(z)
            plancher = (bandes is not None and piece == "sol"
                        and build_grid.etape_de(z) == 0)
            if plancher:
                # LE PLANCHER EST FAIT DE BUCHES, comme dans le chantier : sa
                # surface est ronde et porte l'ecorce, ses bouts en travers
                # montrent les cernes. Il se dessine d'un seul tenant et non
                # face par face : l'ordre de ses morceaux lui est propre, et
                # le tableau des faces le prenait a l'envers.
                self._buches(coin, (x, y, z), bandes, pleins)
                continue
            for (dx, dy, dz), sommets, ombre in FACES:
                if (x + dx, y + dy, z + dz) in pleins:
                    continue                    # cachee par un voisin
                pts = []
                for sx, sy, sz in sommets:
                    px, py = coin(x + sx, y + sy, sommet if sz else bas)
                    pts += [px, py]
                Color(min(1.0, r * ombre), min(1.0, g * ombre),
                      min(1.0, b * ombre), 1)
                Quad(points=pts)
                # L'ARETE DE CHAQUE CUBE, sombre et fine. Sans elle, les
                # faces d'une meme couleur fusionnaient en larges bandes
                # plates et l'on ne voyait plus que la maison est BATIE de
                # pieces : c'est le quadrillage qui le dit.
                Color(r * 0.22, g * 0.22, b * 0.22, 0.85)
                Line(points=pts + pts[:2], width=1.0)

    @staticmethod
    def _buches(coin, cube, bandes, pleins):
        """Un cube de plancher, en BUCHES ENTIERES.

        `coin` est celui de _batiment : il plaque la grille du chantier sur
        l'emprise au sol du plan, donc les buches fuient vers le fond comme
        tout le reste, sans qu'il y ait de perspective a refaire ici.

        La vue du jeu est FIXE : pas de normale a tourner comme dans le
        chantier, seulement le tableau d'assombrissement des faces. Le rond
        d'une buche s'obtient en passant de l'ombre de son flanc a celle de sa
        crete -- les deux flancs ne regardent pas du meme cote, donc ils ne
        recoivent pas la meme lumiere.

        L'ORDRE COMPTE, et il n'est pas celui des faces d'un cube : l'ame,
        puis la surface, puis le noyau, puis les bouts. Les cernes viennent en
        dernier parce qu'ils sont a la face la plus proche de ce cote-la ;
        avant, l'ecorce des tranches leur mordait dessus."""
        axe, _bornes = bandes
        x, y, z = cube
        bas, haut = build_grid.z_bas(z), build_grid.z_haut(z)
        milieu = (bas + haut) / 2.0
        demi = build_grid.demi_buche(bandes, build_grid.hauteur_niveau(z))

        def expose(dx, dy):
            return (x + dx, y + dy, z) not in pleins

        # L'AME : deux buches voisines ne se touchent qu'en un POINT, et le
        # plancher serait fendu d'un trait fin tout du long. Elle le bouche,
        # et donne au passage sa profondeur a la rainure.
        pts = []
        for gx, gy in ((0, 0), (1, 0), (1, 1), (0, 1)):
            px, py = coin(x + gx, y + gy, milieu)
            pts += [px, py]
        _peau_bois(log_skin.ecorce(), _OMBRE_DESSUS * _CREUX_BUCHE, pts,
                   [0, 0, 1, 0, 1, 1, 0, 1])

        # LA SURFACE, vue de dessus : c'est tout ce qu'on en voit d'ici.
        gauche, droite = ((_OMBRE_DEVANT, _OMBRE_DERRIERE) if axe == 0
                          else (_OMBRE_GAUCHE, _OMBRE_DROITE))
        _a, tranches = build_grid.tranches_buches(cube, bandes)
        for l0, l1, s0, s1, t0, t1, _w0, _w1 in tranches:
            t = (t0 + t1) / 2.0
            flanc = gauche if t < 0.5 else droite
            f = flanc + (_OMBRE_DESSUS - flanc) * build_grid.profil_buche(t)
            h0 = milieu + build_grid.hauteur_buche(t0, demi)
            h1 = milieu + build_grid.hauteur_buche(t1, demi)
            pts, tc = [], []
            for l, s, tt, h in ((l0, s0, t0, h0), (l1, s0, t0, h0),
                                (l1, s1, t1, h1), (l0, s1, t1, h1)):
                gx, gy = (l, s) if axe == 0 else (s, l)
                px, py = coin(gx, gy, h)
                pts += [px, py]
                tc += [l / log_skin.MOTIF, tt]
            _peau_bois(log_skin.ecorce(), f, pts, tc)

        # LES BOUTS, sur les faces exposees EN TRAVERS des buches. Sur les
        # autres, le flanc d'une buche EST le bord du plancher : il n'y a rien
        # a ajouter. Sauf devant, ou l'on voit le dessous des rondins -- une
        # bande d'ombre, pas une dalle.
        for dx, dy, ombre in ((0, -1, _OMBRE_DEVANT), (-1, 0, _OMBRE_GAUCHE),
                              (1, 0, _OMBRE_DROITE)):
            if not expose(dx, dy):
                continue
            if ((dx != 0) if axe == 0 else (dy != 0)):
                ZoneScenery._bouts(coin, cube, bandes, demi, (dx, dy), ombre)
            elif dy < 0:
                # LE DESSOUS DES BUCHES, vu de devant : la ou le plancher
                # s'arrete dans le sens de leur longueur, on regarde sous le
                # ventre du premier rondin.
                pts = []
                for gx, gy, h in ((0, 0, bas), (1, 0, bas),
                                  (1, 0, milieu), (0, 0, milieu)):
                    px, py = coin(x + gx, y + gy, h)
                    pts += [px, py]
                u0 = x / log_skin.MOTIF
                _peau_bois(log_skin.ecorce(), ombre * _CREUX_BUCHE, pts,
                           [u0, 0.8, u0 + 1.0 / log_skin.MOTIF, 0.8,
                            u0 + 1.0 / log_skin.MOTIF, 0.2, u0, 0.2])

    @staticmethod
    def _bouts(coin, cube, bandes, demi, face, ombre):
        """Les cernes des rondins scies, sur une face en travers."""
        x, y, z = cube
        dx, dy = face
        bas, haut = build_grid.z_bas(z), build_grid.z_haut(z)
        milieu = (bas + haut) / 2.0
        bord = (x + (1 if dx > 0 else 0)) if dx else (y + (1 if dy > 0 else 0))

        def pt(s, h):
            return coin(*((bord, s) if dx else (s, bord)), h)

        # LE NOYAU d'abord : deux rondins voisins ne se touchent qu'en un
        # point, et les creux qui restent au-dessus et au-dessous laissaient
        # voir le decor au travers.
        c0, c1 = (y, y + 1) if dx else (x, x + 1)
        r0, r1 = c0 / log_skin.MOTIF, c1 / log_skin.MOTIF
        pts = []
        for s, h in ((c0, bas), (c1, bas), (c1, haut), (c0, haut)):
            px, py = pt(s, h)
            pts += [px, py]
        _peau_bois(log_skin.ecorce(), ombre * _CREUX_BUCHE, pts,
                   [r0, 0.9, r1, 0.9, r1, 0.1, r0, 0.1])
        for w0, w1, t0, t1 in build_grid.buches_du_cube(cube, bandes):
            pts, tc = [], []
            for s, dz in build_grid.contour_bout(w0, w1, demi, t0, t1):
                px, py = pt(s, milieu + dz)
                pts += [px, py]
                tc += list(build_grid.uv_bout(s, dz, w0, w1, demi))
            _peau_bois(log_skin.bout(), ombre, pts, tc, eventail=True)

    def _etabli(self, coins):
        """L'atelier : un plateau de rondins sur quatre pieds.

        C'est un MEUBLE, pas une marque au sol : il a de la hauteur, et son
        plateau se voit de dessus alors que ses pieds se voient de face. On le
        monte donc sur l'emprise plutot que de la remplir -- l'emprise est
        l'encombrement au sol, ce qu'on ne pourra plus traverser.

        Le plateau est fait des memes buches que le plancher, et pour la meme
        raison : c'est le meme bois, et deux bois differents dans un meme
        campement se verraient."""
        (x_ag, y_ag), (x_ad, y_ad), (x_fd, y_fd), (x_fg, y_fg) = coins
        large = x_ad - x_ag
        haut = large * _ETABLI_HAUTEUR
        ep = large * _ETABLI_PLATEAU

        def coin(u, v, dz):
            """Un point de l'emprise, eleve de `dz`."""
            xg = x_ag + (x_fg - x_ag) * v
            yg = y_ag + (y_fg - y_ag) * v
            xd = x_ad + (x_fd - x_ad) * v
            yd = y_ad + (y_fd - y_ad) * v
            return xg + (xd - xg) * u, yg + (yd - yg) * u + dz

        # L'OMBRE PORTEE, d'abord : sans elle le meuble flotte au-dessus du
        # sol, puisque rien d'autre ne dit ou ses pieds le touchent.
        Color(0.0, 0.0, 0.0, 0.22)
        Quad(points=[c for u, v in ((0.02, 0.02), (0.98, 0.02),
                                    (0.98, 0.98), (0.02, 0.98))
                     for c in coin(u, v, 0.0)])
        # LES QUATRE PIEDS. Ceux du fond d'abord : le plateau les recouvrira
        # en partie, et c'est ce recouvrement qui donne sa profondeur au
        # meuble.
        pied = large * 0.055
        for u, v in ((0.12, 0.88), (0.88, 0.88), (0.12, 0.12), (0.88, 0.12)):
            bx, by = coin(u, v, 0.0)
            tx, ty = coin(u, v, haut)
            Color(0.34, 0.23, 0.13, 1)
            Quad(points=[bx - pied, by, bx + pied, by,
                         tx + pied, ty, tx - pied, ty])
        # LE PLATEAU : sa tranche, puis son dessus en rondins.
        bas, sommet = haut, haut + ep
        Color(0.33, 0.22, 0.13, 1)
        Quad(points=[*coin(0.0, 0.0, bas), *coin(1.0, 0.0, bas),
                     *coin(1.0, 0.0, sommet), *coin(0.0, 0.0, sommet)])
        rondins = 5
        for i in range(rondins):
            v0, v1 = i / rondins, (i + 1) / rondins
            # Du fond vers l'avant : le rondin de devant recouvre celui du
            # fond, comme partout ailleurs dans cette vue rasante.
            v0, v1 = 1.0 - v1, 1.0 - v0
            milieu = (v0 + v1) / 2.0
            galbe = build_grid.profil_buche(milieu)
            f = _OMBRE_DEVANT + (_OMBRE_DESSUS - _OMBRE_DEVANT) * galbe
            pts = []
            for u, v in ((0.0, v0), (1.0, v0), (1.0, v1), (0.0, v1)):
                pts += list(coin(u, v, sommet))
            _peau_bois(log_skin.ecorce(), f, pts,
                       [0, 0, 2, 0, 2, 1, 0, 1])

    def _blueprint(self, coins):
        """Plan de construction : quatre piquets relies par une corde.

        C'est un CHANTIER MARQUE AU SOL, pas un objet pose dessus : il ne doit
        rien cacher, seulement dire "ici". D'ou des piquets courts et une corde
        fine -- on doit pouvoir voir le sol a travers.

        `coins` vient de _emprise_coins : les quatre angles de l'emprise, deja
        mis en perspective. Le quadrilatere est donc plus etroit au fond qu'au
        devant, sans qu'on ait a le truquer -- un carre parfait, vu depuis le
        sol, se lirait comme un panneau dresse a la verticale."""
        (x_ag, y_ag), (x_ad, y_ad), (x_fd, y_fd), (x_fg, y_fg) = coins
        # Reference de taille : la largeur du bord PROCHE. Tout le reste en
        # decoule, donc un plan pose au loin s'amenuise de lui-meme.
        w = max(1.0, x_ad - x_ag)
        # LES PIQUETS SONT COURTS, et c'est ce qui fait tout. Hauts, la corde
        # s'eloignait du sol et l'ensemble se lisait comme un filet dresse
        # entre quatre poteaux -- un but de football. Bas, la corde epouse le
        # quadrilatere pose par terre, et l'oeil lit une EMPRISE. Un jalon de
        # chantier arrive au genou, pas a l'epaule.
        # Ceux du fond sont un peu plus courts : ils sont plus loin.
        pieux = ((x_ag, y_ag, w * 0.15), (x_ad, y_ad, w * 0.15),
                 (x_fd, y_fd, w * 0.115), (x_fg, y_fg, w * 0.115))

        # Pas d'ombre portee d'ensemble : quatre piquets fins n'en projettent
        # pas. Une tache sous le carre se lisait comme une fosse creusee.

        # La CORDE d'abord, les piquets par-dessus : elle est nouee derriere
        # eux, et cela evite un trait qui traverserait le bois.
        Color(0.76, 0.70, 0.54, 1)
        fil = max(1.0, w * 0.012)
        for i in range(4):
            x1, y1, t1 = pieux[i]
            x2, y2, t2 = pieux[(i + 1) % 4]
            # Une corde tendue entre deux piquets PEND. Trois points suffisent
            # a le dire ; deux donneraient un trait de regle, qui ne
            # ressemblerait pas a une corde.
            creux = (t1 + t2) * 0.5 * 0.16
            Line(points=[x1, y1 + t1, (x1 + x2) / 2.0,
                         (y1 + t1 + y2 + t2) / 2.0 - creux, x2, y2 + t2],
                 width=fil)

        for px, py, ht in pieux:
            ep = max(1.2, w * 0.022)
            # Le trait part LEGEREMENT AU-DESSUS du sol : son embout arrondi
            # deborde de la moitie de son epaisseur, et sans ce decalage le
            # piquet s'enfoncerait de quelques pixels sous le point ou il est
            # cense toucher terre -- donc sous sa propre cle de tri, ce qui
            # laissait passer une touffe d'herbe par-dessus.
            bas = py + ep * 0.68
            Color(0.30, 0.21, 0.13, 1)                    # cote a l'ombre
            Line(points=[px, bas, px, py + ht], width=ep * 1.35)
            Color(0.46, 0.33, 0.19, 1)                    # bois eclaire
            Line(points=[px - ep * 0.3, bas, px - ep * 0.3, py + ht], width=ep)

    def _fire_pit(self, cx, cy, w, lit=False, level="grand"):
        """Foyer de pierres vu en angle (cercle aplati + anneau de pierres).

        Allume, il montre ses braises et ses flammes, d'autant plus hautes
        qu'il lui reste du combustible (voir _FLAME_SCALE). C'est la MEME
        scene qui sert au jeu et au fond de l'ecran de proximite : le feu a
        donc partout le meme aspect."""
        h = w * _PLAT_PROFONDEUR
        scale = _FLAME_SCALE.get(level, 1.0) if lit else 0.0
        glow_c = ember_c = None
        if lit:                                        # lueur autour du foyer
            glow_c = Color(1.0, 0.55, 0.15, 0.14)
            glow_e = Ellipse(pos=(cx - w * 0.85, cy - h * 0.9),
                             size=(w * 1.7, w * 1.7))
        Color(0.10, 0.08, 0.06, 0.85)                  # cendres du foyer
        Ellipse(pos=(cx - w / 2, cy - h / 2), size=(w, h))
        if lit:                                        # braises rougeoyantes
            ember_c = Color(0.85, 0.30, 0.07, 0.95)
            Ellipse(pos=(cx - w * 0.32, cy - h * 0.30),
                    size=(w * 0.64, h * 0.60))
        n = 10                                         # anneau de pierres
        r = min(w, h) * 0.15
        for i in range(n):
            a = 2 * math.pi * i / n
            sx = cx + (w / 2 - r) * math.cos(a)
            sy = cy + (h / 2 - r) * math.sin(a)
            if i % 2 == 0:
                Color(0.52, 0.42, 0.34, 1)
            else:
                Color(0.66, 0.58, 0.50, 1)
            Ellipse(pos=(sx - r, sy - r), size=(r * 2, r * 2))
        tongues = []
        if scale > 0:                                  # langues de flamme
            for off, sc, col in _FLAME_TONGUES:
                c = Color(*col)
                tongues.append((c, Triangle(), off, sc))
        if lit:
            self._flames.append({
                "cx": cx, "cy": cy, "w": w, "h": h, "scale": scale,
                "glow_c": glow_c, "glow_e": glow_e, "ember_c": ember_c,
                "tongues": tongues, "phase": 1.7 * len(self._flames)})
            self._shape_flame(self._flames[-1], 0.0)

    # -- vacillement -------------------------------------------------- #
    def _shape_flame(self, fl, t):
        """Place les flammes d'un foyer a l'instant t (rien n'est recree).

        Deux sinusoides de frequences differentes par langue : le mouvement ne
        se repete pas de facon perceptible, et chaque langue vit sa vie."""
        cx, cy, w, h = fl["cx"], fl["cy"], fl["w"], fl["h"]
        ph, scale = fl["phase"], fl["scale"]
        for i, (col, tri, off, sc) in enumerate(fl["tongues"]):
            p = ph + i * 2.1
            flick = (1.0 + 0.20 * math.sin(t * (3.3 + 0.7 * i) + p)
                     + 0.09 * math.sin(t * (8.1 + 1.3 * i) + p * 1.9))
            sway = 0.05 * w * math.sin(t * 2.4 + p)
            fw = w * 0.34 * sc * scale
            fh = w * 0.80 * sc * scale * flick
            bx = cx + off * w
            tri.points = [bx - fw / 2, cy - h * 0.10,
                          bx + fw / 2, cy - h * 0.10,
                          bx + off * w * 0.35 + sway, cy + fh]
            col.a = min(1.0, 0.82 + 0.18 * flick)
        pulse = (0.80 + 0.20 * math.sin(t * 2.7 + ph)
                 + 0.08 * math.sin(t * 6.1 + ph * 1.4))
        if fl["glow_c"] is not None:
            # Une braise eclaire encore un peu : la lueur ne descend pas a 0.
            fl["glow_c"].a = 0.14 * max(0.35, scale) * pulse
            gr = w * 0.85 * max(0.5, scale) * (0.94 + 0.10 * pulse)
            fl["glow_e"].pos = (cx - gr, cy - h * 0.9)
            fl["glow_e"].size = (gr * 2, gr * 2)
        if fl["ember_c"] is not None:
            fl["ember_c"].a = min(1.0, 0.72 + 0.28 * pulse)

    def _sync_flame_clock(self):
        """L'horloge du feu ne tourne que s'il y a quelque chose a animer."""
        if self._flames and self._flame_ev is None:
            self._flame_ev = Clock.schedule_interval(self._tick_flames,
                                                     1.0 / _FLAME_FPS)
        elif not self._flames and self._flame_ev is not None:
            self._flame_ev.cancel()
            self._flame_ev = None

    def _tick_flames(self, dt):
        self._flame_t += dt
        for fl in self._flames:
            self._shape_flame(fl, self._flame_t)

    # -- balancement de la vegetation ----------------------------------- #
    def _keep_tallest_sway(self):
        """Ne garde que les touffes du PREMIER PLAN pour l'animation.

        Les autres restent dessinees, simplement immobiles : on lache juste
        leurs references. C'est ce qui garde le cout du vent constant, que la
        scene compte dix touffes ou cent trente."""
        if len(self._sway) > _SWAY_MAX:
            self._sway.sort(key=lambda bl: bl["h"], reverse=True)
            del self._sway[_SWAY_MAX:]

    def _sync_sway_clock(self):
        """L'horloge du vent ne tourne que s'il y a quelque chose a balancer."""
        self._keep_tallest_sway()
        if self._sway and self._sway_ev is None:
            self._sway_ev = Clock.schedule_interval(self._tick_sway,
                                                    1.0 / _SWAY_FPS)
        elif not self._sway and self._sway_ev is not None:
            self._sway_ev.cancel()
            self._sway_ev = None

    def _tick_sway(self, dt):
        """Courbe la pointe de chaque brin. La BASE ne bouge pas : un brin
        d'herbe plie, il ne glisse pas sur le sol."""
        # Chaque ecran a son propre decor, mais un seul est AFFICHE : inutile
        # de faire onduler l'herbe des quatre autres, que personne ne voit.
        if self.get_root_window() is None:
            return
        self._sway_t += dt
        push = _SWAY_AMPLITUDE * self._wind
        for bl in self._sway:
            t = self._sway_t * bl["speed"] + bl["phase"]
            wave = _SWAY_BIAS + math.sin(t) + 0.35 * math.sin(t * 2.3 + 1.1)
            dx = wave * push * bl["h"]
            bl["tri"].points = [bl["x0"], bl["y"], bl["x1"], bl["y"],
                                bl["tipx"] + dx, bl["tipy"]]

    # -- image du decor (si elle a ete fournie) -------------------------- #
    def _zs(self, key):
        """Nom de l'image de cet element pour la ZONE en cours."""
        return _ZONE_SPRITES.get(self._zone,
                                 _ZONE_SPRITES["Foret"]).get(key)

    def _sprite(self, name, cx, base, height, pick=None, width=None,
                teinte=None, coupe_bas=0.0, crans=None):
        """Dessine l'IMAGE de cet element, posee par son BAS sur (cx, base).

        Renvoie Vrai si une image existait et a ete dessinee ; Faux si aucune
        image n'a ete fournie, auquel cas l'appelant garde son dessin
        geometrique d'origine. C'est ce qui rend les images facultatives : le
        jeu tourne a l'identique sans elles, et s'habille au fur et a mesure
        qu'on en depose.

        La VARIANTE est deduite de la position : deux elements voisins ne
        prennent pas la meme image, et un element garde la sienne quand la
        scene est redessinee. `pick` permet de l'IMPOSER, pour les rares
        elements dont on veut garantir la variete plutot que la laisser au
        hasard des positions (voir les pepites).

        `teinte` multiplie l'image. Nos images viennent de photos, eclairees
        chacune dans son studio ; la scene, elle, a ses couleurs et sa
        lumiere. La teinte est ce qui rattache l'une a l'autre.

        `coupe_bas` en retranche le bas -- une fraction de sa hauteur -- au
        lieu de le dessiner. C'est ainsi qu'un element s'ENFONCE dans le sol :
        la part enterree n'est pas recouverte, elle n'est pas dessinee du
        tout, et l'on n'a donc aucune couleur de terre a faire correspondre.

        `crans` DENTELLE cette coupe au lieu de la laisser droite : une liste
        de decalages en pixels, un par colonne. C'est l'APPELANT qui la
        fabrique, parce qu'il est parfois seul a pouvoir le faire -- la pepite
        doit poser exactement les memes crans sur son image et sur les voiles
        qu'elle peint par-dessus (voir _etalonne_pepite). Deux tirages
        separes, et le voile debordait dans les echancrures."""
        if not name:
            return False
        if pick is None:
            pick = int(abs(cx) * 7.13 + abs(base) * 3.71)
        tex = foliage.sprite(name, pick)
        if tex is None:
            return False
        # On dimensionne d'ordinaire par la HAUTEUR : c'est elle qui compte
        # pour un arbre ou une plante. Un element large et bas -- une pierre
        # posee au sol -- se mesure au contraire a sa LARGEUR, sinon deux
        # images d'aplatissements differents ne font plus la meme taille.
        if width is not None:
            tw, th = tex.size
            height = width * (float(th) / float(tw)) if tw else width
        w, h = foliage.size_for(tex, height)
        # CARTES DE RELIEF, SI ELLES ONT ETE FOURNIES (nom_R / nom_P a cote de
        # l'image). L'element est alors eclaire par le soleil de la scene et
        # son cote clair suit l'heure, au lieu de porter un relief peint une
        # fois pour toutes. On ne lie que s'il y a quelque chose a lier : une
        # scene pose des centaines de sprites, et deux BindTexture par sprite
        # sans carte derriere ne seraient que du poids dans le canvas.
        nor, pak = foliage.relief(name, pick)
        relief = self._pbr and (nor is not None or pak is not None)
        if relief:
            pbr.bind_maps(nor, pak)
        Color(*((tuple(teinte[:3]) if teinte else (1, 1, 1)) + (1,)))
        f = min(0.90, max(0.0, float(coupe_bas)))
        if f <= 0.0:
            Rectangle(pos=(cx - w / 2.0, base), size=(w, h), texture=tex)
        elif not crans:
            # Coins dans l'ordre de Kivy (bas-gauche, bas-droit, haut-droit,
            # haut-gauche) et v qui DESCEND dans l'image quand l'ecran monte :
            # voir la note de sens dans textures.py. Le bas du rectangle lit
            # donc la ligne 1-f du PNG, et tout ce qu'il y a dessous est
            # laisse sous terre.
            Rectangle(pos=(cx - w / 2.0, base), size=(w, h * (1.0 - f)),
                      texture=tex,
                      tex_coords=(0, 1.0 - f, 1, 1.0 - f, 1, 0, 0, 0))
        else:
            self._sprite_enfoui(tex, cx, base, w, h, f, crans)
        if relief:
            # Sans ce retour au neutre, TOUT ce qui est dessine ensuite --
            # l'herbe, les formes vectorielles, les autres sprites -- garderait
            # le relief de celui-ci.
            self._reset_pbr()
        return True

    def _sprite_enfoui(self, tex, cx, base, w, h, f, crans):
        """L'image, coupee a la ligne du sol par un bord DENTELE.

        Un rectangle suffisait tant que la coupe etait droite ; une coupe
        irreguliere demande un maillage -- une colonne par cran, chacune avec
        son propre bas.

        POURQUOI DENTELER. La pierre etait tranchee par une horizontale
        parfaite, comme un sol l'etait avant sa frange. Le meme defaut appelle
        le meme remede : rien dans la nature ne finit au cordeau, et une
        pierre a demi enterree encore moins -- la terre monte plus haut d'un
        cote que de l'autre.

        V SUIT LE BORD, et c'est tout l'interet de le faire ici plutot que de
        masquer le bas avec quelque chose : la ou la coupe remonte, on lit
        PLUS HAUT dans l'image. La pierre n'est donc ni etiree ni comprimee,
        elle est reellement rognee -- exactement comme la coupe droite, mais
        en dents de scie.

        Le pas de v par pixel d'ecran vaut 1/h : l'image entiere (v de 0 a 1)
        occupe h pixels."""
        n = len(crans) - 1
        gauche = cx - w / 2.0
        haut = base + h * (1.0 - f)
        verts, idx = [], []
        for i in range(n + 1):
            u = i / n
            x = gauche + u * w
            d = crans[i]
            verts += [x, base + d, u, (1.0 - f) - d / h]     # bas, dentele
            verts += [x, haut, u, 0.0]                       # haut, droit
            if i:
                p = (i - 1) * 2
                idx += [p, p + 1, p + 2, p + 1, p + 3, p + 2]
        Mesh(vertices=verts, indices=idx, mode="triangles", texture=tex)

    def _crans_de_pepite(self, largeur, variante):
        """Les crans du bas d'une pierre, de gauche a droite.

        Meme recette que la frange du sol (voir _frange) : un grain large pour
        les bosses, un grain fin pour la dentelure. Il n'y a PAS d'extinction
        aux extremites, au contraire du sol : une pierre a des bords, et c'est
        justement la, sur ses flancs, que la terre monte le plus."""
        n = max(8, int(largeur / self.SEGMENT_CRAN))
        ampl = largeur * self.FRANGE_PEPITE
        rng = random.Random("%s:%s:%s:crans" % (self._seed, largeur, variante))
        gros = [rng.uniform(-1.0, 1.0) for _ in range(n // 5 + 2)]
        out = []
        for i in range(n + 1):
            t = i / n * (len(gros) - 1)
            j = min(len(gros) - 2, int(t))
            large = gros[j] * (1 - (t - j)) + gros[j + 1] * (t - j)
            fin = rng.uniform(-1.0, 1.0)
            out.append(((1.0 - self.POIDS_FIN) * large
                        + self.POIDS_FIN * fin) * ampl)
        return out

    def reveille(self):
        """A appeler quand le jeu revient de l'arriere-plan.

        Le contexte graphique a pu etre detruit pendant ce temps. Le shader de
        relief est donc REINSTALLE -- ses uniformes (numeros d'unites de
        texture, direction et couleur de la lumiere) vivaient dans le contexte
        perdu, et sans eux la scene s'eclaire n'importe comment -- puis la
        scene est redessinee de zero."""
        if self._pbr:
            pbr.setup(self.canvas)
            self._apply_light()
        self._redraw()

    def set_ground(self, zone_type, seed=0):
        """Vue VERS LE BAS : on regarde le sol, qui remplit tout l'ecran."""
        self._zone = zone_type
        self._seed = seed
        self._mode = "ground"
        self._redraw()

    # ------------------------------------------------------------------ #
    def _redraw(self, *_):
        # ON TESTE LA TAILLE AVANT D'EFFACER. L'inverse -- effacer puis
        # renoncer -- laissait un canvas VIDE derriere lui : une fenetre
        # reduite passe par une taille nulle, et si rien ne redemande de
        # redessiner ensuite, la scene ne revient jamais. Garder l'ancien
        # dessin ne coute rien : il n'est de toute facon pas visible.
        if self.width <= 0 or self.height <= 0:
            return
        self.canvas.clear()
        # Les anciennes instructions de flamme viennent d'etre effacees avec
        # le canvas : on repart d'une liste vide (elle sera remplie par
        # _fire_pit pour chaque foyer allume de la scene). Idem pour les
        # ombres portees et les touffes balancees par le vent, qui gardent des
        # references vers des instructions qui n'existent plus.
        self._flames = []
        self._shadows = []
        self._sway = []
        # Reinitialise le comptage des objets recoltables pour cette passe.
        self._ord = {}
        self._harvest_total = {}
        self._avail = {}
        # Recalcule les bboxes des cases bloquees (objets installes) au cas ou
        # la taille du widget a change depuis le dernier set_scene.
        self._compute_blocked_bboxes()
        rng = random.Random(_ZONE_SEED.get(self._zone, 0) * 100000 + self._seed)
        with self.canvas:
            self._reset_pbr()        # cartes neutres par defaut (unites 1 et 2)
            if self._mode == "ground":
                self._ground_view(rng)
            else:
                {
                    "Foret": self._foret,
                    "Plaine": self._plaine,
                    "Montagne": self._montagne,
                    "Lac": self._lac,
                }.get(self._zone, self._foret)(rng)
        # Totaux visibles + nombre de recoltes possibles par objet : on ne peut
        # pas recolter plus de fois qu'il n'y a d'objets visibles.
        self.harvest_total = dict(self._harvest_total)
        self.harvest_max = {n: min(self._avail_for(n), t)
                            for n, t in self.harvest_total.items() if t > 0}
        self._apply_light()
        self._sync_flame_clock()
        self._sync_sway_clock()

    # ------------------------------------------------------------------ #
    # BORDURES : la case voisine deborde dans la scene
    # ------------------------------------------------------------------ #
    # L'horizon dit ce qu'il y a AU LOIN. Mais une foret voisine ne commence
    # pas a l'horizon : elle commence au BORD DE LA CASE, donc au bord de
    # l'ecran, en vraie taille.
    #
    # LE PRINCIPE : on ne dessine pas "une bordure", on POSE LES ELEMENTS DE
    # LA CASE VOISINE SUR LA MEME GRILLE que ceux de la case actuelle, une
    # colonne plus loin. Ils passent par grid_to_screen comme tous les autres,
    # et leurs tailles sont calculees avec les MEMES formules. Ils se
    # comportent donc exactement comme s'ils appartenaient a la scene -- meme
    # perspective, meme taille, meme aspect -- et ils sont MELANGES au tri par
    # profondeur, si bien qu'un arbre voisin proche passe devant une touffe
    # d'herbe lointaine.
    #
    # UNE SEULE DIFFERENCE : ils ne sont pas interactifs. Ils ne passent ni par
    # _take_or_skip ni par _is_blocked -- ils ne sont pas sur la case du
    # joueur, on ne les ramasse pas et ils ne bloquent rien.
    #
    # Une PLAINE voisine n'ajoute rien : de l'herbe a cote de l'herbe ne se
    # verrait pas.

    # Colonne VIRTUELLE de chaque cote. La grille du jeu va de 0 a 4 ; -1 et 5
    # sont donc les premieres colonnes de la case d'a cote.
    _EDGE_COL = {"gauche": -1, "droite": 5}

    # Rangees utilisees, de la plus proche a la plus lointaine. On s'arrete a
    # la 3e : au-dela, la perspective ramene tout vers le centre de l'ecran, et
    # une colonne VOISINE y arriverait au milieu de l'image -- ce qui ne
    # voudrait plus rien dire.
    _EDGE_ROWS = (0, 1, 2)

    # LES ZONES SANS DEBORDEMENT SUR LES BORDS. La montagne et le lac ne
    # recoivent plus les elements de la case d'a cote le long de leurs bords :
    # ni les arbres, ni les rochers, ni les galets, ni la pente ou la rive
    # voisines. Leur decor s'arrete au cadre.
    #
    # L'HORIZON, LUI, RESTE. Ce sont deux choses differentes, et il ne faut
    # surtout pas les confondre : l'horizon montre ce qu'il y a AU LOIN, il
    # situe la case dans le monde et aide a s'orienter ; le debordement pose
    # des objets DANS la scene, au premier plan, le long du bord. C'est ce
    # second qui encombrait la pente et la berge. Les couper tous les deux --
    # ce qui avait ete fait d'abord -- privait la case de son paysage.
    SANS_BORDS_VOISINS = {"Montagne", "Lac"}

    def _edge_items(self):
        """Les elements de la case voisine qui debordent dans la scene.

        Renvoie [(y_base, fonction), ...] : la meme forme que le decor de la
        case, pour que le tri par profondeur les melange avec lui.

        Deux sortes d'elements :
        - un FOND par cote (la pente de la montagne, la rive du lac), pose une
          seule fois et tres en arriere : c'est le TERRAIN voisin, il doit
          passer derriere tout le reste ;
        - des OBJETS poses sur la grille, rang par rang, exactement comme ceux
          de la case."""
        out = []
        if self._zone in self.SANS_BORDS_VOISINS:
            return out
        for cote, col in self._EDGE_COL.items():
            zone = self._neighbours.get(cote)
            fond = {"Montagne": self._edge_slope,
                    "Lac": self._edge_shore}.get(zone)
            if fond is not None:
                fond(out, cote)
            pose = {"Foret": self._edge_tree,
                    "Montagne": self._edge_boulder,
                    "Lac": self._edge_pebble}.get(zone)
            if pose is None:
                continue
            for row in self._EDGE_ROWS:
                # Hasard STABLE par emplacement, et propre aux bordures : la
                # scene garde ainsi exactement le meme decor, qu'il y ait des
                # voisins ou non (cf. _graine_voisins).
                jit = random.Random("%d:%s:%d:bord" % (self._seed, cote, row))
                gfx, gfy, _gs = self.grille(col, row)
                pose(out, self.x + gfx * self.width,
                     self.y + gfy * self.height, row / 4.0, jit)
        return out

    def _edge_side(self, cote):
        """(x du bord d'ecran, sens vers l'interieur) pour un cote."""
        if cote == "gauche":
            return self.x, 1.0
        return self.x + self.width, -1.0

    def _edge_tree(self, out, tx, tb, depth, jit):
        """Un arbre de la foret voisine.

        Les formules de taille sont RECOPIEES de _foret, volontairement : ces
        arbres doivent etre indiscernables de ceux de la case, sinon la
        frontiere se verrait."""
        w, h = self.width, self.height
        th = (1.00 - 0.58 * depth) * jit.uniform(0.85, 1.10) * h
        if jit.random() < 0.5:
            tw = (0.11 - 0.05 * depth) * jit.uniform(0.85, 1.15) * w
            out.append((tb, lambda: self._pine(tx, tb, tw, th,
                                               (0.06, 0.15, 0.09, 1))))
        else:
            sc = 1.0 - 0.6 * depth
            out.append((tb, lambda: self._forest_tree(tx, tb, th, sc)))

    def _edge_boulder(self, out, tx, tb, depth, jit):
        """Un bloc de la montagne voisine, taille comme ceux de _montagne."""
        rr = (0.085 - 0.045 * depth) * jit.uniform(0.85, 1.15) * self.height
        out.append((tb, lambda: self._big_rock(tx, tb, rr)))

    def _edge_pebble(self, out, tx, tb, depth, jit):
        """Un galet de la rive voisine, comme ceux de _lac."""
        rr = jit.uniform(0.012, 0.03) * self.height
        out.append((tb, lambda: self._pebble(tx, tb, rr)))

    def _edge_slope(self, out, cote):
        """LE PIED de la montagne voisine : la ou le terrain commence a monter.

        Pas un sommet. Un sommet a cette distance serait enorme, et faux : la
        case d'a cote commence a quelques dizaines de metres, on n'en voit donc
        que le bas. Ce qu'il faut lire, c'est "le sol se releve a partir
        d'ici" -- d'ou un pan qui part du niveau du terrain vers l'interieur et
        s'eleve franchement en approchant du bord de l'ecran."""
        w, h = self.width, self.height
        bord, vers = self._edge_side(cote)
        dedans = bord + vers * 0.34 * w
        bas = self.y
        def dessin():
            self._tquad("rock", [bord, bas, dedans, bas,
                                 dedans, bas + 0.17 * h,
                                 bord, bas + 0.54 * h])
            # Bas plus sombre, comme la pente de _montagne : c'est ce qui lui
            # donne du volume au lieu d'un aplat triangulaire.
            self._tquad("rock_dark", [bord, bas, dedans, bas,
                                      dedans, bas + 0.05 * h,
                                      bord, bas + 0.14 * h])
        # Tres "loin" : le terrain voisin passe derriere tout le decor.
        out.append((self.y + 0.95 * h, dessin))

    def _edge_shore(self, out, cote):
        """LE BORD du lac voisin : la rive d'abord, l'eau ensuite.

        L'eau seule se lirait comme une flaque. C'est la bande de sable entre
        l'herbe et l'eau qui dit qu'il y a une BERGE, donc une etendue
        derriere. Les deux sont dessinees avec les textures du lac, et la rive
        s'amincit en remontant : elle s'eloigne."""
        w, h = self.width, self.height
        bord, vers = self._edge_side(cote)
        def bande(part, haut):
            loin = bord + vers * part * w
            return [bord, self.y, loin, self.y,
                    bord + vers * part * 0.55 * w, self.y + haut * h,
                    bord, self.y + haut * 1.20 * h]
        def dessin():
            self._tquad("sand", bande(0.34, 0.34))
            # L'eau reste EN RETRAIT du bord interieur : le liseré de sable
            # laisse visible est exactement ce qui fait la berge.
            self._tquad("water", bande(0.22, 0.27))
        out.append((self.y + 0.95 * h, dessin))

    def _graine_voisins(self):
        """Graine de hasard propre aux VOISINS : elle depend de la case et de
        ce qui l'entoure, et de rien d'autre."""
        graine = self._seed
        for cote in sorted(self._neighbours):
            graine = graine * 31 + hash(self._neighbours[cote]) % 9973
        return graine

    def _horizon(self, crest):
        """Pose les paysages voisins sur la ligne d'horizon de la scene.

        `crest(fx)` donne le y de cette ligne. A appeler AVANT le terrain : le
        sol dessine ensuite recouvre le pied des silhouettes, qui n'ont donc
        pas besoin d'etre decoupees proprement en bas.

        L'HORIZON A SON PROPRE HASARD, et ce n'est pas un detail. Toute la
        scene est tiree d'un seul generateur : s'il servait aussi a l'horizon,
        le nombre de tirages changerait avec les voisins, et TOUT le decor se
        reorganiserait -- les touffes d'herbe, les pierres, les objets a
        recolter. Le joueur verrait sa case se reconstruire rien qu'en
        tournant sur lui-meme. Ici, la ligne d'horizon depend des voisins,
        et rien d'autre n'en depend."""
        horizon.draw(self._neighbours, self.x, self.width, crest,
                     self.height, random.Random(self._graine_voisins()))

    # -- helpers textures (surface plane texturee, sinon couleur de repli) - #
    def _trect(self, name, x, y, w, h, tile_px=None):
        """Rectangle texture (repete) si la texture existe, sinon aplat couleur."""
        if tile_px is None:
            tile_px = textures.tile_for(name)
        tex = paint(name)
        self._bind_pbr(name)
        if tex is not None:
            Rectangle(pos=(x, y), size=(w, h), texture=tex,
                      tex_coords=tiled_coords(w, h, tile_px))
        else:
            Rectangle(pos=(x, y), size=(w, h))
        self._reset_pbr()

    def _tquad(self, name, points, tile_px=None):
        """Quad texture (repetition basee sur la position monde), sinon aplat."""
        if tile_px is None:
            tile_px = textures.tile_for(name)
        tex = paint(name)
        self._bind_pbr(name)
        if tex is not None:
            x0, y0 = self.x, self.y
            tc = []
            for i in range(0, 8, 2):
                # v NEGATIF vers le haut : voir la note de sens dans
                # textures.py (sans quoi la roche s'affiche a l'envers).
                tc += [(points[i] - x0) / tile_px,
                       -(points[i + 1] - y0) / tile_px]
            Quad(points=points, texture=tex, tex_coords=tc)
        else:
            Quad(points=points)
        self._reset_pbr()

    # -- vue VERS LE BAS (sol qui remplit l'ecran) ---------------------- #
    def _ground_view(self, rng):
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        zone = self._zone

        if zone == "Lac":                              # surface de l'eau vue d'en haut
            self._trect("water", x0, y0, w, h)
            for _ in range(70):                        # ondulations / reflets
                ly = y0 + rng.uniform(0, 1) * h
                lx = x0 + rng.uniform(0, 0.7) * w
                Color(0.34, 0.58, 0.76, rng.uniform(0.2, 0.5))
                Line(points=[lx, ly, lx + rng.uniform(0.1, 0.35) * w, ly],
                     width=1.4)
            for _ in range(rng.randint(4, 8)):         # nenuphars
                gx = x0 + rng.uniform(0, 1) * w
                gy = y0 + rng.uniform(0, 1) * h
                r = rng.uniform(0.03, 0.06) * h
                if self._sprite("lily_pad", gx, gy - r * 0.8, r * 1.6):
                    continue
                Color(0.16, 0.40, 0.20, 1)
                Ellipse(pos=(gx - r, gy - r * 0.8), size=(r * 2, r * 1.6))
            return

        if zone == "Montagne":
            base = (0.34, 0.34, 0.38)
            ground_tex = "rock"
        elif zone == "Foret":
            base = (0.16, 0.18, 0.11)
            ground_tex = "forest_floor"
        else:                                          # Plaine
            base = (0.24, 0.42, 0.18)
            ground_tex = "grass"

        self._trect(ground_tex, x0, y0, w, h)
        # Legeres taches de variation du sol : APLATIES et discretes (avant
        # c'etaient de gros ovales verts qui ressemblaient a des buissons vus
        # de haut). Larges et basses -> lisent comme des nuances de sol.
        for _ in range(10):
            gx = x0 + rng.uniform(0, 1) * w
            gy = y0 + rng.uniform(0, 1) * h
            rw = rng.uniform(0.10, 0.20) * w
            rh = rng.uniform(0.02, 0.05) * h
            Color(min(1, base[0] * 1.12), min(1, base[1] * 1.12),
                  min(1, base[2] * 1.12), 0.25)
            Ellipse(pos=(gx - rw / 2, gy - rh / 2), size=(rw, rh))

        def rnd():
            return x0 + rng.uniform(0, 1) * w, y0 + rng.uniform(0, 1) * h

        # Meme regle qu'a l'horizon : on collecte (base, dessin) et on trie du
        # plus loin au plus proche. Ces elements etaient dessines dans l'ordre
        # ou ils etaient tires, c'est-a-dire au hasard : une touffe du haut de
        # l'ecran pouvait recouvrir une touffe du bas, pourtant plus proche.
        # La composition ne change pas -- seul l'ordre de recouvrement.
        items = []

        if zone == "Plaine":
            greens = [(0.22, 0.42, 0.16, 1), (0.28, 0.48, 0.18, 1),
                      (0.18, 0.38, 0.14, 1)]
            for _ in range(110):                       # gazon partout
                gx, gy = rnd()
                gh = rng.uniform(0.04, 0.09) * h
                col = rng.choice(greens)
                items.append((gy, lambda gx=gx, gy=gy, gh=gh, col=col:
                              self._grass_tuft(gx, gy, gh, col, scale=0.8)))
            for _ in range(rng.randint(8, 14)):        # petites pierres
                gx, gy = rnd()
                r = rng.uniform(0.015, 0.035) * h
                items.append((gy, lambda gx=gx, gy=gy, r=r:
                              self._stone(gx, gy, r,
                                          sprite=self._zs("stone"))))
            for _ in range(rng.randint(5, 9)):          # fleurs (peu nombreuses)
                gx, gy = rnd()
                col, fsprite = rng.choice(_FLOWERS)
                r = rng.uniform(0.018, 0.032) * h
                pet = rng.choice((5, 6))
                items.append((gy - self.DEBORD_FLEUR * r,
                              lambda gx=gx, gy=gy, r=r, col=col, pet=pet,
                              fsprite=fsprite:
                              self._flower(gx, gy, r, col, petals=pet,
                                           sprite=fsprite)))
        elif zone == "Foret":
            leaves = [(0.45, 0.32, 0.14, 1), (0.36, 0.40, 0.16, 1),
                      (0.52, 0.38, 0.18, 1), (0.30, 0.26, 0.12, 1)]
            for _ in range(150):                       # litiere de feuilles
                gx, gy = rnd()
                s = rng.uniform(0.012, 0.024) * h
                col = rng.choice(leaves)
                items.append((gy - self.DEBORD_FEUILLE * s,
                              lambda gx=gx, gy=gy, s=s, col=col:
                              self._leaf(gx, gy, s, col)))
            for _ in range(rng.randint(10, 16)):       # brindilles
                gx, gy = rnd()
                ln = rng.uniform(0.05, 0.10) * w
                items.append((gy - self.DEBORD_BRANCHE * ln,
                              lambda gx=gx, gy=gy, ln=ln:
                              self._branch(gx, gy, ln,
                                           sprite=self._zs("branch"))))
            for _ in range(45):                        # touffes sombres
                gx, gy = rnd()
                gh = rng.uniform(0.03, 0.07) * h
                items.append((gy, lambda gx=gx, gy=gy, gh=gh:
                              self._grass_tuft(gx, gy, gh,
                                               (0.12, 0.22, 0.13, 1),
                                               scale=0.7)))
            for _ in range(rng.randint(8, 14)):        # pierres mousseuses
                gx, gy = rnd()
                r = rng.uniform(0.02, 0.045) * h
                items.append((gy, lambda gx=gx, gy=gy, r=r:
                              self._stone(gx, gy, r,
                                          sprite=self._zs("stone"))))
        else:                                          # Montagne (rocaille)
            for _ in range(rng.randint(45, 65)):       # rochers / galets
                gx, gy = rnd()
                r = rng.uniform(0.02, 0.06) * h
                items.append((gy, lambda gx=gx, gy=gy, r=r:
                              self._stone(gx, gy, r,
                                          sprite=self._zs("stone"))))
            for _ in range(rng.randint(8, 14)):        # touffes rares
                gx, gy = rnd()
                gh = rng.uniform(0.03, 0.06) * h
                items.append((gy, lambda gx=gx, gy=gy, gh=gh:
                              self._grass_tuft(gx, gy, gh,
                                               (0.22, 0.34, 0.16, 1),
                                               scale=0.7)))

        items.sort(key=lambda it: it[0], reverse=True)
        for _, fn in items:
            fn()

    # -- helpers -------------------------------------------------------- #
    def _pine(self, cx, base, tw, th, color, shadow=True):
        if shadow:
            self._shadow(cx, base, tw * 0.9)
        if self._sprite("pine_tree", cx, base, th):
            return
        tex = paint_color("foliage", color)
        self._bind_pbr("foliage")
        Triangle(points=[cx - tw / 2, base, cx + tw / 2, base,
                         cx, base + th * 0.72], texture=tex)
        Triangle(points=[cx - tw * 0.36, base + th * 0.32,
                         cx + tw * 0.36, base + th * 0.32, cx, base + th],
                 texture=tex)
        self._reset_pbr()

    # -- LE DEBORD : ou un element touche-t-il VRAIMENT le sol ? --------- #
    #
    # La scene est dessinee du plus loin au plus proche, chaque element
    # recouvrant ceux du fond. L'ordre vient d'une cle de tri, et cette cle
    # doit etre l'endroit ou l'element TOUCHE LE SOL -- son point le plus
    # proche du joueur.
    #
    # Or la plupart des elements sont poses par leur base, mais quelques-uns
    # sont dessines autour d'un point CENTRAL et descendent donc sous celui-ci.
    # Un buisson, par exemple, deborde de 40 % de son rayon -- six pour cent de
    # l'ecran. Trie sur son centre, il passait pour plus lointain qu'il ne
    # paraissait, et l'herbe situee DERRIERE lui se dessinait par-dessus.
    #
    # Ces valeurs sont donc le debord de chaque forme sous sa base, en fraction
    # de sa propre taille. Elles ne sont pas estimees : elles sont mesurees sur
    # le dessin reel (voir test_profondeur). Si tu modifies l'une de ces
    # methodes, remesure.
    DEBORD_PEPITE = 0.10       # x son rayon (l'ombre au sol comprise)
    DEBORD_BUISSON = 0.40      # x son rayon
    DEBORD_BAIES = 0.30        # x son rayon
    DEBORD_BRANCHE = 0.08      # x sa longueur (l'ombre du bois comprise)
    DEBORD_FEUILLE = 0.40      # x sa taille
    DEBORD_FLEUR = 0.33        # x son rayon

    def _grass_tuft(self, cx, base, height, color, scale=1.0, sprite=None):
        if self._sprite(sprite, cx, base, height * 1.15):
            return
        bw = max(1.2, self.width * 0.0035 * scale)
        r, g, b, a = color
        # 5 brins fins en eventail, longueurs/inclinaisons/teintes variees.
        for off, hsc, lean in ((-1.3, 0.65, -0.55), (-0.6, 0.85, -0.25),
                               (0.0, 1.0, 0.08), (0.6, 0.88, 0.30),
                               (1.3, 0.70, 0.60)):
            bx = cx + off * bw
            tipx = bx + lean * bw * 2.4
            tipy = base + height * hsc
            sh = 0.88 + 0.24 * ((off + 1.3) / 2.6)        # nuance par brin
            Color(min(1.0, r * sh), min(1.0, g * sh), min(1.0, b * sh), a)
            tri = Triangle(points=[bx - bw, base, bx + bw, base, tipx, tipy])
            if SWAY:
                # Chaque brin garde sa propre allure et son propre depart : une
                # touffe qui ondulerait d'un seul bloc ferait carton-pate.
                self._sway.append({
                    "tri": tri, "x0": bx - bw, "x1": bx + bw, "y": base,
                    "tipx": tipx, "tipy": tipy, "h": height * hsc,
                    "speed": 1.5 + 0.55 * hsc + 0.3 * off,
                    "phase": (cx * 0.11 + base * 0.07 + off * 1.9) % 6.28})

    def _bush(self, cx, cy, r, color, sprite=None):
        cr, cg, cb, ca = color
        self._shadow(cx, cy - r * 0.1, r * 2.6)           # ombre au sol
        if self._sprite(sprite, cx, cy - r * 0.35, r * 2.1):
            return
        self._bind_pbr("foliage")
        dtex = paint_color("foliage", (cr * 0.7, cg * 0.7, cb * 0.7, 1))  # masse sombre
        Ellipse(pos=(cx - r * 1.4, cy - r * 0.3), size=(r * 1.3, r * 1.0), texture=dtex)
        Ellipse(pos=(cx + r * 0.2, cy - r * 0.3), size=(r * 1.3, r * 1.0), texture=dtex)
        Ellipse(pos=(cx - r, cy - r * 0.4), size=(r * 2, r * 1.2), texture=dtex)
        ltex = paint_color("foliage", (cr, cg, cb, 1))    # feuillage clair (haut)
        Ellipse(pos=(cx - r * 0.9, cy + r * 0.1), size=(r * 1.8, r * 1.0), texture=ltex)
        Ellipse(pos=(cx - r * 1.2, cy), size=(r * 1.1, r * 0.8), texture=ltex)
        Ellipse(pos=(cx + r * 0.2, cy), size=(r * 1.1, r * 0.8), texture=ltex)
        self._reset_pbr()

    # -- scenes (plein cadre) ------------------------------------------- #
    def _leaf(self, cx, cy, size, color):
        """Feuille morte au sol (litiere). Posee a plat : aucune ombre."""
        if self._sprite("leaf_litter", cx, cy - size * 0.4, size * 0.8):
            return
        Color(*color)
        Ellipse(pos=(cx - size, cy - size * 0.4), size=(size * 2, size * 0.8))

    def _forest_tree(self, cx, base, th, scale, shadow=True):
        """Arbre feuillu : tronc conique + amas de feuillage sombre.

        `shadow` est coupe pour la ligne d'arbres de l'HORIZON : une ombre
        portee n'a pas de sens a cette distance, et il y en aurait une
        trentaine a replacer a chaque mouvement du soleil pour rien."""
        if shadow:
            self._shadow(cx, base, th * 0.45)
        if self._sprite("forest_tree", cx, base, th):
            return
        tw = max(2.0, self.width * 0.012 * scale)
        btex = paint_color("bark", (0.28, 0.19, 0.11, 1))
        self._bind_pbr("bark")
        Quad(points=[cx - tw, base, cx + tw, base,
                     cx + tw * 0.5, base + th * 0.6, cx - tw * 0.5, base + th * 0.6],
             texture=btex)
        self._reset_pbr()
        fr = th * 0.32
        fy = base + th * 0.55
        ftex = paint_color("foliage", (0.09, 0.18, 0.11, 1))
        self._bind_pbr("foliage")
        for dx, dy in ((-0.5, 0.0), (0.5, 0.05), (0.0, 0.35),
                       (-0.3, 0.42), (0.35, 0.40), (0.0, 0.05)):
            Ellipse(pos=(cx + dx * fr - fr * 0.7, fy + dy * fr),
                    size=(fr * 1.4, fr * 1.3), texture=ftex)
        self._reset_pbr()
        Color(0.14, 0.26, 0.15, 1)                        # reflet de lumiere
        Ellipse(pos=(cx - fr * 0.45, fy + fr * 0.3), size=(fr * 0.9, fr * 0.8))

    def _foret(self, rng):
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        floor = 0.42                      # hauteur moyenne du sol forestier

        p1 = rng.uniform(0, 6.28)
        p2 = rng.uniform(0, 6.28)

        def far_curve(fx):
            return y0 + (floor + 0.05 + 0.03 * math.sin(fx * 6.28 * 1.3 + p1)
                         + 0.015 * math.sin(fx * 6.28 * 2.7 + p2)) * h

        def floor_curve(fx):
            return y0 + (floor + 0.025 * math.sin(fx * 6.28 * 1.1 + p1 + 1.0)
                         + 0.012 * math.sin(fx * 6.28 * 2.4 + p2)) * h

        def place(maxt=1.0, fx=None, floor=0.0):
            if fx is None:
                fx = rng.uniform(0, 1)
            fx = min(0.999, max(0.001, fx))
            surf = (floor_curve(fx) - y0) / h
            lo = min(floor, surf)              # plancher (jointures des mains)
            hi = surf * maxt
            if hi < lo:
                hi = lo
            fy = lo + (hi - lo) * rng.random()
            t = (fy / surf) if surf else 0.0
            return (x0 + fx * w, y0 + fy * h, 1.0 - 0.70 * t, t)

        def clusters(count, spread):
            centers = [rng.uniform(0.05, 0.95) for _ in range(max(1, count))]
            return lambda: rng.choice(centers) + rng.gauss(0, spread)

        leaf_pick = clusters(rng.randint(4, 6), 0.13)
        grass_pick = clusters(rng.randint(3, 5), 0.12)
        stone_pick = clusters(rng.randint(2, 3), 0.06)
        fern_pick = clusters(rng.randint(3, 4), 0.09)
        mush_pick = clusters(rng.randint(2, 3), 0.05)

        # Sol forestier (terre/mousse) ondule, deux tons.
        # Les paysages voisins d'abord : ils sont derriere tout le reste.
        self._horizon(lambda fx: far_curve(fx) - 0.010 * h)

        self._fill_curve(far_curve, "forest_floor_far")
        self._fill_curve(floor_curve, "forest_floor", estompe=True)

        GREENS = [(0.10, 0.20, 0.12), (0.08, 0.17, 0.10), (0.12, 0.24, 0.14)]
        LEAVES = [(0.45, 0.32, 0.14, 1), (0.36, 0.40, 0.16, 1),
                  (0.52, 0.38, 0.18, 1), (0.30, 0.26, 0.12, 1)]

        def f_grass(gx, gb, gh, col, sc):
            return lambda: self._grass_tuft(gx, gb, gh, col, scale=sc)

        items = []   # (y_base, fonction) -> tri par profondeur

        # Litiere de feuilles mortes (beaucoup, en plaques). [recoltable: Feuille]
        for _ in range(100):
            fx = leaf_pick() if rng.random() < 0.8 else None
            lx, ly, sc, t = place(fx=fx, floor=_HARVEST_FLOOR)
            s = rng.uniform(0.010, 0.022) * h * sc
            col = rng.choice(LEAVES)
            if not self._take_or_skip("Feuille") and not self._is_blocked(lx, ly):
                items.append((ly - self.DEBORD_FEUILLE * s,
                              lambda lx=lx, ly=ly, s=s, col=col:
                              self._leaf(lx, ly, s, col)))
        # Pierres mousseuses (en tas). [recoltable: Pierre]
        for _ in range(rng.randint(6, 10)):
            sx, sy, sc, t = place(1.0, fx=stone_pick(), floor=_HARVEST_FLOOR)
            r = rng.uniform(0.02, 0.05) * h * sc
            if not self._take_or_skip("Pierre") and not self._is_blocked(sx, sy):
                items.append((sy, lambda sx=sx, sy=sy, r=r:
                              self._stone(sx, sy, r,
                                          sprite=self._zs("stone"))))
        # Branches au sol. [recoltable: Small_Stick]
        for _ in range(rng.randint(7, 11)):
            bx, by, sc, t = place(1.0, floor=_HARVEST_FLOOR)
            ln = rng.uniform(0.06, 0.13) * w * sc
            if not self._take_or_skip("Small_Stick") and not self._is_blocked(bx, by):
                items.append((by - self.DEBORD_BRANCHE * ln,
                              lambda bx=bx, by=by, ln=ln:
                              self._branch(bx, by, ln,
                                           sprite=self._zs("branch"))))
        # Herbe de sous-bois (sombre), en touffes (dense).
        for _ in range(130):
            fx = grass_pick() if rng.random() < 0.72 else None
            gx, gb, sc, t = place(fx=fx)
            gh = rng.uniform(0.05, 0.13) * h * sc
            if self._is_blocked(gx, gb, gb + gh):
                continue
            items.append((gb, f_grass(gx, gb, gh, rng.choice(GREENS) + (1,), sc)))
        # Fougeres / plantes (bosquets).
        for _ in range(rng.randint(8, 12)):
            px, py, sc, t = place(fx=fern_pick())
            s = rng.uniform(0.05, 0.10) * h * sc
            if self._is_blocked(px, py, py + s * 1.05):
                continue
            items.append((py, lambda px=px, py=py, s=s:
                          self._plant(px, py, s, sprite=self._zs("plant"))))
        # (Les buissons de sous-bois sont desormais des GROS elements places
        #  sur la grille 5x5, voir plus bas.)
        # Champignons (uniquement bruns pour l'instant).
        # [recoltable: Brown_Mushroom]
        if rng.random() < 0.8:
            for _ in range(rng.randint(2, 4)):
                mx, my, sc, t = place(1.0, fx=mush_pick(), floor=_HARVEST_FLOOR)
                s = rng.uniform(0.03, 0.05) * h * sc
                cap = (0.62, 0.30, 0.18, 1)
                if (not self._take_or_skip("Brown_Mushroom")
                        and not self._is_blocked(mx, my)):
                    items.append((my, lambda mx=mx, my=my, s=s, cap=cap:
                                  self._mushroom(mx, my, s, cap,
                                                 sprite=self._zs("mushroom"))))
        # Arbres + buissons PROCHES : GROS elements positionnes sur la GRILLE
        # 5x5 (les memes cases sont interdites a l'installation d'un objet :
        # impossible de mettre un feu de camp sous un arbre).
        for kind, rang, depth, tx, tb, jit in self._iter_nature_big():
            if kind == "nugget":
                items.extend(self._pepite_de_grille(rang, depth, tx, tb, jit))
                continue
            if kind == "tree":
                th = (1.00 - 0.58 * depth) * jit.uniform(0.85, 1.10) * h
                if jit.random() < 0.5:
                    tw = (0.11 - 0.05 * depth) * jit.uniform(0.85, 1.15) * w
                    items.append((tb, lambda tx=tx, tb=tb, tw=tw, th=th:
                                  self._pine(tx, tb, tw, th,
                                             (0.06, 0.15, 0.09, 1))))
                else:
                    sc = 1.0 - 0.6 * depth
                    items.append((tb, lambda tx=tx, tb=tb, th=th, sc=sc:
                                  self._forest_tree(tx, tb, th, sc)))
            else:                                     # buisson de sous-bois
                g2 = jit.uniform(0.0, 0.06)
                r = (0.13 - 0.06 * depth) * jit.uniform(0.85, 1.15) * h
                items.append((tb - self.DEBORD_BUISSON * r,
                              lambda bx=tx, by=tb, r=r, g2=g2:
                              self._bush(bx, by, r,
                                         (0.06 + g2, 0.16 + g2, 0.09, 1),
                                         sprite=self._zs("bush"))))
        # Ligne d'arbres DENSE a l'horizon (lointains et petits) : HORS grille
        # (au-dela de la zone d'installation), purement decorative.
        m = rng.randint(24, 32)
        for i in range(m):
            fx = min(0.999, max(0.001, i / (m - 1) + rng.uniform(-0.02, 0.02)))
            tb = floor_curve(fx) - rng.uniform(0.0, 0.03) * h
            tx = x0 + fx * w
            if rng.random() < 0.55:
                tw = rng.uniform(0.03, 0.06) * w
                th = rng.uniform(0.12, 0.22) * h
                items.append((tb, lambda tx=tx, tb=tb, tw=tw, th=th:
                              self._pine(tx, tb, tw, th, (0.09, 0.17, 0.11, 1),
                                         shadow=False)))
            else:
                th = rng.uniform(0.12, 0.20) * h
                items.append((tb, lambda tx=tx, tb=tb, th=th:
                              self._forest_tree(tx, tb, th, 0.4, shadow=False)))
        # (Les insectes sont desormais une couche ANIMEE separee : InsectLayer.)

        items += self._installed_items()     # feu de camp... a leur profondeur
        items += self._edge_items()          # la case d'a cote, qui deborde
        items.sort(key=lambda it: it[0], reverse=True)
        for _, fn in items:
            fn()

    # -- objets recoltables / insectes (details) ----------------------- #
    def _mushroom(self, cx, base, size, cap, sprite=None):
        self._shadow(cx, base + size * 0.10, size * 1.4)  # ombre au sol
        if self._sprite(sprite, cx, base, size * 1.45):
            return
        Color(0.92, 0.88, 0.78, 1)                       # tige
        Rectangle(pos=(cx - size * 0.18, base), size=(size * 0.36, size * 0.9))
        Color(0, 0, 0, 0.18)                             # ombre sous le chapeau
        Ellipse(pos=(cx - size * 0.55, base + size * 0.58),
                size=(size * 1.1, size * 0.28))
        Color(*cap)                                      # chapeau
        Ellipse(pos=(cx - size * 0.6, base + size * 0.62),
                size=(size * 1.2, size * 0.8))
        Color(1, 1, 1, 0.85)                             # points
        for dx in (-0.3, 0.05, 0.32):
            Ellipse(pos=(cx + dx * size, base + size * 0.85),
                    size=(size * 0.14, size * 0.14))

    def _berries(self, cx, cy, r):
        self._shadow(cx, cy - r * 0.2, r * 2.2)
        if self._sprite("berries_bush", cx, cy - r * 0.3, r * 2.0):
            return
        Color(0.10, 0.28, 0.13, 1)                       # buisson
        for off in (-0.6, 0.0, 0.6):
            Ellipse(pos=(cx + off * r - r * 0.6, cy - r * 0.3),
                    size=(r * 1.2, r * 1.0))
        Color(0.85, 0.16, 0.20, 1)                       # baies
        for dx, dy in ((-0.4, 0.2), (0.1, 0.45), (0.5, 0.15),
                       (-0.1, 0.0), (0.3, 0.5)):
            d = r * 0.32
            Ellipse(pos=(cx + dx * r - d / 2, cy + dy * r - d / 2), size=(d, d))

    @staticmethod
    def _ell_c(ex, ey, w, hh):
        """Ellipse CENTREE sur (ex, ey)."""
        Ellipse(pos=(ex - w / 2, ey - hh / 2), size=(w, hh))

    def _flower(self, cx, cy, size, color, petals=5, sprite=None):
        """Fleur : petales allonges disposes en etoile + coeur, au lieu d'un
        simple rond. `size` ~ rayon de la fleur."""
        if self._sprite(sprite, cx, cy - size * 0.6, size * 2.6):
            return
        r, g, b, a = color
        pw = size * 0.62                                   # largeur d'un petale
        pl = size * 1.25                                   # longueur d'un petale
        for k in range(petals):
            PushMatrix()
            Rotate(angle=360.0 * k / petals, origin=(cx, cy))
            Color(r * 0.78, g * 0.78, b * 0.78, a)         # bord du petale
            Ellipse(pos=(cx - pw / 2, cy + size * 0.10), size=(pw, pl))
            Color(r, g, b, a)                              # petale
            Ellipse(pos=(cx - pw * 0.4, cy + size * 0.16),
                    size=(pw * 0.8, pl * 0.88))
            Color(min(1, r + 0.18), min(1, g + 0.18), min(1, b + 0.18), a)
            Ellipse(pos=(cx - pw * 0.22, cy + size * 0.45),
                    size=(pw * 0.44, pl * 0.5))            # reflet clair
            PopMatrix()
        Color(0.85, 0.62, 0.16, 1)                         # coeur (contour)
        self._ell_c(cx, cy, size * 0.66, size * 0.66)
        Color(0.98, 0.82, 0.28, 1)                         # coeur (clair)
        self._ell_c(cx, cy, size * 0.44, size * 0.44)
        Color(0.78, 0.55, 0.14, 0.9)                       # grains au centre
        for dx, dy in ((-0.12, 0.08), (0.12, 0.06), (0.0, -0.12)):
            self._ell_c(cx + dx * size, cy + dy * size, size * 0.12, size * 0.12)

    # -- pepites de mineraux --------------------------------------------- #
    #
    # Elles sont dans TOUTES les zones, et c'est le meme code qui les pose
    # partout : une pierre est une pierre, la foret n'a pas les siennes.
    #
    # LEUR TAILLE SE MESURE SUR LE BUISSON DE PLAINE. C'est la reference
    # demandee, et c'est aussi le seul gros element qu'on trouve a toutes les
    # profondeurs : une pepite fait de -20 % a +20 % de sa hauteur, donc elle
    # grossit et retrecit avec la distance comme lui.
    RAYON_BUISSON_PLAINE = (0.17, 0.09)   # au premier plan, puis ce qu'il
    ECART_PEPITE = 0.20                   # perd au fond ; -20 % a +20 %

    # LARGEUR D'UNE PEPITE, en rayons. Elle vient d'une mesure, pas d'un
    # calcul : on dessine un buisson et une pepite au meme rayon, on releve
    # les deux boites, et on cherche le facteur qui leur donne la MEME
    # EMPRISE (largeur x hauteur).
    #
    # Pourquoi l'emprise et non la seule largeur : un buisson mesure 2,89 r de
    # large pour 1,51 r de haut, une pepite 2,89 r pour 2,33 r. A largeur
    # egale -- ce qu'on faisait -- la pierre etait donc une fois et demie plus
    # haute que le buisson, et elle ecrasait la scene comme un rocher. Le
    # facteur qui egalise les emprises vaut racine(1,51 / 2,33) = 0,81, d'ou
    # 2,89 x 0,81.
    LARGEUR_PEPITE = 2.35

    # UN CRAN TOUS LES N PIXELS a la base d'une pierre. Plus fin que le pas
    # du sol (quatorze) : le sol se dentelle sur toute la largeur de l'ecran,
    # une pierre sur deux cents pixels. Au pas du sol elle n'aurait eu que
    # huit crans -- des marches d'escalier, pas une dentelure.
    SEGMENT_CRAN = 8.0

    # DE COMBIEN SA COUPE EST DENTELEE, en part de sa LARGEUR. La frange du
    # sol se mesure a la tuile de la texture ; celle d'une pierre se mesure a
    # la pierre -- une petite pierre a de petits crans. A 3,5 %, une pierre de
    # 190 px en a de sept, soit l'ordre de grandeur de la frange du sol sur un
    # telephone : les deux bords se ressemblent, ce qui est le but.
    FRANGE_PEPITE = 0.035

    # DE COMBIEN ELLE EST ENTERREE, en part de sa hauteur. Une pierre posee
    # SUR le sol est une pierre qu'on vient d'y deposer : le decor en paraît
    # meuble. Enfoncee, elle a toujours ete la.
    ENFONCE_PEPITE = (0.25, 0.50)

    # LA TERRE DE CHAQUE ZONE, pour le bourrelet au pied de la pierre. C'est
    # la surface PROCHE de la zone -- celle sur laquelle reposent les elements
    # de la grille -- et non celle de l'horizon.
    #
    # Le lac reste de l'EAU. Un haut-fond de sable y avait ete essaye ; il
    # dessinait une galette brune autour de chaque pierre, et la pierre avait
    # l'air posee sur un radeau. L'eau, elle, ne se voit pas contre l'eau : il
    # ne reste que la ligne de flottaison sombre, qui est exactement ce qu'on
    # veut voir.
    SOL_DE_ZONE = {"Foret": "forest_floor", "Plaine": "grass",
                   "Montagne": "rock", "Lac": "water"}

    # TEINTE DE LA PIERRE, PAR ZONE. Les images sont des photos de granit :
    # mesure faite, elles sortent a 0,55 de luminosite pour 0,06 de saturation
    # -- un gris clair et parfaitement neutre. Le sol de foret, lui, est a
    # 0,12. La pierre etait donc de loin la chose la plus claire de l'ecran,
    # et sans la moindre couleur commune avec ce qui l'entoure : elle se
    # decollait de la scene comme un autocollant.
    #
    # Chaque zone la ramene donc a sa propre lumiere et lui prete un peu de sa
    # couleur -- vert sous les arbres, chaud dans l'herbe. C'est le meme
    # granit partout, vu sous plusieurs ciels.
    #
    # LES VALEURS NE SONT PAS CHOISIES A L'OEIL. Ce qui fait qu'un element
    # "sort" d'une scene n'est pas sa couleur en soi, c'est son ECART avec ce
    # qui l'entoure. On a donc mesure ce rapport sur le decor que le jeu
    # dessine DEJA -- c'est lui la direction artistique, pas une intuition :
    #
    #   gros rocher de montagne  0,90 x la luminosite de son sol
    #   buisson de foret         1,81 x
    #   buisson de plaine        0,66 x
    #
    # La pepite etait a 2,36 x en foret : plus de deux fois plus claire que le
    # sol, la chose la plus lumineuse de l'ecran. Les teintes ci-dessous la
    # ramenent a 1,35 x -- ENTRE les deux references que le jeu se donne. Plus
    # claire que le sol, parce qu'une pierre prend le jour du ciel ; moins
    # qu'un buisson, parce qu'elle n'est pas censee attirer l'oeil avant lui.
    #
    # LA FORET PREND LA MEME TEINTE QUE LA PLAINE, sur epreuve dans le jeu.
    # Calee a 1,35 x d'un sol aussi sombre, la pierre y devenait une tache
    # noire : la regle du rapport constant tenait sur le papier, pas devant
    # l'ecran. Et elle avait tort sur le fond -- la foret est sombre parce
    # qu'elle est A L'OMBRE DES ARBRES, alors qu'une pierre qui affleure
    # recoit le meme ciel qu'ailleurs. Une seule teinte pour les deux zones
    # dit exactement cela : c'est le meme granit, sous le meme ciel.
    #
    # Le rapport au sol n'est donc plus le meme partout. Le test l'affiche
    # toujours, mais comme un CONSTAT, plus comme une regle a tenir.
    #
    # L'entree du LAC ne sert plus : il n'y a plus de pepites dans l'eau (voir
    # world.SANS_PEPITES). Elle reste pour le jour ou il en reprendrait, mais
    # elle n'a PAS ete mesuree comme les autres.
    # LA TEINTE NE SUFFIT PAS, ET NE PEUT PAS SUFFIRE. Multiplier une image
    # change sa couleur mais JAMAIS son contraste : la photo garde des noirs
    # et des blancs que rien d'autre dans la scene ne possede, et la pierre
    # continue de se detacher comme un decoupage. Deux aplats poses par-dessus
    # sa silhouette corrigent cela (voir _etalonne_pepite) :
    #
    #  - un VOILE de la couleur du decor, d'autant plus epais que la pierre
    #    est loin : c'est l'air entre l'oeil et elle. Il rapproche ses tons de
    #    ceux du fond, donc il ecrase son contraste -- exactement ce qu'il
    #    faut ;
    #  - un DEGRADE sombre a son pied, qui s'eteint a mi-hauteur : la lumiere
    #    vient du ciel, le haut d'un caillou la recoit, son pied ne la recoit
    #    plus. C'est le signal de relief le plus fort dont on dispose sans
    #    carte de normales.
    #
    # L'HEURE n'entre pas ici : le voile de nuit passe sur TOUTE la scene une
    # fois celle-ci dessinee (voir daylight.veil_color et les ecrans). Teinter
    # la pierre une deuxieme fois l'aurait desynchronisee du reste.
    VOILE_PEPITE = (0.12, 0.34)    # epaisseur du voile : au plus pres, au fond
    PIED_PEPITE = 0.45             # noirceur au pied de la pierre
    PIED_HAUTEUR = 0.55            # sur quelle part de sa hauteur il s'eteint
    BANDES_PEPITE = 7              # en combien de marches (assez pour ne pas
    #                                se voir : mesure, 5 se voyaient)

    TEINTE_PEPITE = {"Foret": (0.815, 0.783, 0.661),   # la meme que la plaine
                     "Plaine": (0.815, 0.783, 0.661),
                     "Montagne": (0.858, 0.858, 0.879),
                     "Lac": (0.607, 0.644, 0.662)}

    def _pepite_de_grille(self, rang, depth, cx, base, jit):
        """Une pepite posee sur la grille 5x5, comme un arbre ou un buisson.

        Elle y a sa place pour deux raisons : on la voit alors dans l'ecran de
        PROXIMITE au meme titre que le reste du decor, et on ne peut plus
        installer un feu de camp dessus. Combien il y en a par case est decide
        par le monde (voir world.nature_blocked_cells) : ici, on ne fait que
        les dessiner.

        LE RANG REPARTIT LES MODELES : une case a cinq pepites en montre cinq
        differentes, au lieu de laisser le hasard des positions en repeter.
        Il est DECALE d'un cran tire de la graine de la case -- sans ce
        decalage, le premier modele sortait sur toutes les cases qui portent
        au moins une pepite et le cinquieme seulement sur celles qui en
        portent cinq : mesure, un contre huit."""
        a, b = self.RAYON_BUISSON_PLAINE
        r = (a - b * depth) * jit.uniform(1.0 - self.ECART_PEPITE,
                                          1.0 + self.ECART_PEPITE) * self.height
        decalage = random.Random("%s:variante" % self._seed).randrange(5)
        enfonce = jit.uniform(*self.ENFONCE_PEPITE)
        # LA PIERRE ET SON HERBE SONT DES ELEMENTS SEPARES pour le tri par
        # profondeur, et il le faut : une touffe qui pousse devant la pierre
        # doit passer devant elle, une touffe de cote derriere ce qui est plus
        # proche. Dessinees toutes ensemble a la cle de la pierre, elles
        # recouvraient ce qui etait devant -- mesure, jusqu'a 72 recouvrements
        # fautifs par scene de foret, dont des troncs d'arbres.
        return [(base - self.DEBORD_PEPITE * r,
                 lambda cx=cx, base=base, r=r, v=rang + decalage,
                 e=enfonce, d=depth: self._pepite(cx, base, r, v, e, d))] \
            + self._herbe_de_pepite(cx, base, r * self.LARGEUR_PEPITE, depth)

    def _pepite(self, cx, base, r, variante, enfonce=0.35, depth=0.0):
        """Une pepite : un bloc de pierre a demi enterre.

        Cent pour cent de pierre grise pour l'instant -- aucun minerai. Quand
        il y en aura, ils se distingueront ici et nulle part ailleurs : la
        pepite est un element du decor, pas un objet, et c'est le decor qui
        dit de quoi elle a l'air.

        TROIS CHOSES L'ANCRENT AU SOL, et il les faut toutes les trois : la
        part enterree n'est pas dessinee, la terre remonte contre elle, et
        elle est teintee de la lumiere de sa zone."""
        # ON LA POSE PAR SA LARGEUR, pas par sa hauteur : les cinq images
        # n'ont pas le meme aplatissement, et c'est la place prise AU SOL qui
        # doit rester la meme de l'une a l'autre.
        largeur = r * self.LARGEUR_PEPITE
        # UNE OMBRE PORTEE COURTE : la pierre est a demi enterree, elle n'a
        # plus grand-chose au-dessus du sol pour porter loin. A la taille
        # qu'elle avait quand la pierre etait POSEE, elle s'etalait autour
        # d'elle en flaque grise.
        self._shadow(cx, base - largeur * 0.02, largeur * 0.88, opacity=0.85)
        teinte = self.TEINTE_PEPITE.get(self._zone,
                                        self.TEINTE_PEPITE["Plaine"])
        # LES MEMES CRANS POUR L'IMAGE ET POUR SES VOILES : tires une seule
        # fois ici, puis passes aux deux. Chacun les tirant de son cote, le
        # voile aurait peint sa couleur dans les echancrures de la pierre.
        crans = self._crans_de_pepite(largeur, variante)
        if self._sprite("ore_nugget", cx, base, None, pick=variante,
                        width=largeur, teinte=teinte, coupe_bas=enfonce,
                        crans=crans):
            self._etalonne_pepite(cx, base, largeur, variante, enfonce, depth,
                                  crans)
            self._pied_de_pepite(cx, base, largeur, depth)
            return
        # Sans image : un bloc anguleux, plus sombre et plus trapu qu'un
        # galet, pour qu'on ne le confonde pas avec les pierres a ramasser.
        # Il est rogne du meme enfoncement, par le bas.
        w2 = largeur / 2.0
        plein = largeur * 0.78
        haut = plein * (1.0 - enfonce)

        def y(part):
            """La hauteur `part` du bloc entier, ramenee au-dessus du sol."""
            return base + max(0.0, plein * part - plein * enfonce)

        Color(0.34, 0.34, 0.37, 1)
        Quad(points=[cx - w2, base, cx + w2, base,
                     cx + w2 * 0.72, y(0.66), cx - w2 * 0.80, y(0.58)])
        Color(0.48, 0.48, 0.52, 1)
        Quad(points=[cx - w2 * 0.80, y(0.58), cx + w2 * 0.72, y(0.66),
                     cx + w2 * 0.18, base + haut,
                     cx - w2 * 0.52, base + haut * 0.92])
        self._pied_de_pepite(cx, base, largeur, depth)

    def _etalonne_pepite(self, cx, base, largeur, variante, enfonce, depth,
                         crans=None):
        """Rapproche la photo de pierre des couleurs de la scene.

        Voir VOILE_PEPITE : un voile de la couleur du decor, epaissi par la
        distance, puis un degrade sombre a son pied. Les deux sont poses sur
        sa SILHOUETTE -- un simple rectangle teinterait aussi le vide autour.

        Sans silhouette (pas d'image, ou image illisible), on ne fait rien :
        le repli geometrique porte deja ses propres couleurs."""
        sil = foliage.silhouette("ore_nugget", variante)
        if sil is None:
            return
        tw, th = sil.size
        if not tw or not th:
            return
        haut = largeur * (float(th) / float(tw)) * (1.0 - enfonce)
        gauche = cx - largeur / 2.0
        vu = 1.0 - enfonce          # la part de l'image qui sort de terre

        # LES BANDES SUIVENT LA COUPE DENTELEE, colonne par colonne. Posees a
        # plat, elles debordaient dans les crans : la ou la pierre remonte, la
        # silhouette est encore opaque, et le voile peignait donc sa couleur
        # sur le SOL, dans l'echancrure meme qu'on venait de creuser.
        h_pleine = largeur * (float(th) / float(tw))    # l'image entiere
        n_cols = len(crans) - 1 if crans else 1

        def bande(y0, y1, coul, alpha):
            """Un morceau de la silhouette, de y0 a y1 (0 = sol, 1 = sommet)."""
            if alpha <= 0.002 or y1 <= y0:
                return
            bas_nom, haut_nom = base + haut * y0, base + haut * y1
            Color(coul[0], coul[1], coul[2], alpha)
            verts, idx = [], []
            for i in range(n_cols + 1):
                u = i / n_cols
                x = gauche + u * largeur
                # Le bas de la colonne : le plus HAUT de la ligne nominale et
                # du cran. Borne par le haut de la bande, sinon elle
                # s'inverserait la ou le cran la depasse.
                cran = base + (crans[i] if crans else 0.0)
                bas = min(max(bas_nom, cran), haut_nom)
                # v DESCEND dans l'image quand l'ecran MONTE (voir
                # textures.py) : un pixel d'ecran vaut 1/h_pleine de v.
                verts += [x, bas, u, vu - (bas - base) / h_pleine]
                verts += [x, haut_nom, u, vu - (haut_nom - base) / h_pleine]
                if i:
                    p = (i - 1) * 2
                    idx += [p, p + 1, p + 2, p + 1, p + 3, p + 2]
            Mesh(vertices=verts, indices=idx, mode="triangles", texture=sil)

        # LA COULEUR REELLEMENT POSEE AU SOL, texture comprise -- pas celle du
        # repli. Les deux s'ecartent beaucoup des qu'une image existe (voir
        # textures.average_color), et c'est dans le sol tel qu'on le VOIT que
        # la pierre doit se fondre.
        decor = textures.average_color(self.SOL_DE_ZONE.get(self._zone, "rock"))
        pres, loin = self.VOILE_PEPITE
        bande(0.0, 1.0, decor, pres + (loin - pres) * max(0.0, min(1.0, depth)))

        # LE DEGRADE DU PIED, en marches : une Mesh ne sait pas donner une
        # couleur par sommet, et c'est la facon la plus simple d'obtenir un
        # fondu. Sept marches ne se voient pas ; cinq se voyaient.
        sombre = tuple(c * 0.35 for c in decor)
        n = self.BANDES_PEPITE
        for i in range(n):
            y0, y1 = i / n, (i + 1) / n
            t = (y0 + y1) / 2.0 / self.PIED_HAUTEUR
            if t >= 1.0:
                break
            bande(y0, y1, sombre, self.PIED_PEPITE * (1.0 - t) ** 2)

    # L'HERBE AU PIED DE LA PIERRE : combien de touffes, sur quelle largeur
    # (en part de la largeur de la pierre) et quelle hauteur.
    # Valeurs prises sur une planche d'essais (9 / 14 / 18 / 24 touffes) : a 9
    # le trait de coupe se lit encore entre les touffes, a 24 l'herbe avale la
    # pierre et fait une haie.
    TOUFFES_PEPITE = 14
    DEBORD_HERBE = 1.10
    HAUTEUR_HERBE = (0.16, 0.26)      # au milieu, puis sur les flancs

    # LA COULEUR DE L'HERBE DE CHAQUE ZONE, reprise de sa scene. La foret a
    # son vert sombre de sous-bois, la plaine son vert de pre, la montagne ses
    # touffes rases et grises. Le lac n'en a pas besoin : plus de pepites dans
    # l'eau.
    HERBE_DE_ZONE = {"Foret": (0.10, 0.20, 0.12, 1),
                     "Plaine": (0.20, 0.40, 0.14, 1),
                     "Montagne": (0.22, 0.34, 0.16, 1),
                     "Lac": (0.18, 0.34, 0.16, 1)}

    def _pied_de_pepite(self, cx, base, largeur, depth):
        """L'OMBRE DE CONTACT au pied de la pierre, dessinee avec elle.

        La terre au pied d'une pierre ne recoit plus le ciel. Sans ce lisere
        sombre, la pierre coupee net a la ligne du sol a l'air posee derriere
        un muret.

        ELLE RESTE SOUS LA PIERRE et s'amincit vers les flancs. Etalee plus
        largement -- ce qui avait ete fait d'abord -- elle debordait de part et
        d'autre en deux croissants sombres : la pierre portait une moustache.
        Une ombre de contact n'existe que la ou il y a contact.

        SA COURBE EST UN SOURIRE : on regarde d'en haut et de biais, le point
        du sol le plus PROCHE est celui droit devant la pierre, et le plus
        proche est le plus BAS a l'ecran ; les flancs, eux, sont plus loin
        donc plus hauts.

        L'herbe qui acheve de la raccorder au sol est ailleurs : elle se trie
        avec le reste du decor (voir _herbe_de_pepite)."""
        demi = largeur / 2.0
        creux_max = largeur * 0.065
        verts, idx, segs = [], [], 22
        for i in range(segs + 1):
            dx = -demi + 2.0 * demi * i / segs
            haut = base + creux_max * 0.35 * (dx / demi) ** 2
            creux = creux_max * (1.0 - (dx / demi) ** 2)
            for yy in (haut - creux, haut):
                verts += [cx + dx, yy, 0, 0]
            if i:
                p = (i - 1) * 2
                idx += [p, p + 1, p + 2, p + 1, p + 3, p + 2]
        Color(0.04, 0.04, 0.03, 0.30)
        Mesh(vertices=verts, indices=idx, mode="triangles", texture=None)

    def _herbe_de_pepite(self, cx, base, largeur, depth):
        """L'herbe qui pousse au pied de la pierre : [(cle de tri, dessin)].

        ON NE SOULEVE PLUS LE TERRAIN. Un bourrelet de terre etait dessine ici,
        avec la vraie matiere du sol : il faisait le travail, mais il ajoutait
        une bosse la ou il n'y en a pas, et cela se voyait des qu'on regardait.
        L'herbe fait mieux et ne ment pas : elle POUSSE au pied des pierres,
        c'est meme la qu'elle pousse le mieux -- a l'abri du pietinement. Et
        comme elle est deja partout dans la scene, rien ne signale qu'elle a
        ete mise la pour cacher quelque chose.

        CHAQUE TOUFFE EST TRIEE POUR ELLE-MEME, a sa propre profondeur : celle
        qui pousse devant la pierre passe devant elle, celle de cote passe
        derriere ce qui est plus proche.

        LES TOUFFES SONT PLUS HAUTES SUR LES FLANCS que droit devant, pour la
        meme raison que l'ombre dessine un sourire : les flancs sont plus loin,
        donc plus haut a l'ecran, donc il en faut davantage pour couvrir la
        coupe.

        Elles se balancent au vent comme toutes les autres (voir _grass_tuft) :
        c'est ce qui acheve de les faire passer pour de l'herbe de la scene et
        non pour un cache-misere fige."""
        col = self.HERBE_DE_ZONE.get(self._zone)
        if not col:
            return []
        demi = largeur / 2.0
        # Le hasard tient a la POSITION : la touffe ne change pas d'un
        # redessin a l'autre, comme tout le reste du decor.
        jit = random.Random("%s:%.1f:%.1f:herbe" % (self._seed, cx, base))
        h0, h1 = self.HAUTEUR_HERBE
        n = self.TOUFFES_PEPITE
        out = []
        for i in range(n):
            # Reparties sur la largeur, avec un peu de flou : alignees, elles
            # auraient fait une haie.
            t = (i + 0.5) / n + jit.uniform(-0.35, 0.35) / n
            dx = (t * 2.0 - 1.0) * demi * self.DEBORD_HERBE
            f = min(1.0, abs(dx) / demi)
            haut = largeur * (h0 + (h1 - h0) * f) * jit.uniform(0.75, 1.25)
            by = base + largeur * 0.055 * f ** 2 - largeur * 0.02
            g = jit.uniform(-0.03, 0.05)
            teinte = (max(0.0, col[0] + g), max(0.0, col[1] + g),
                      max(0.0, col[2] + g * 0.5), col[3])
            ech = (1.0 - 0.45 * depth) * jit.uniform(0.8, 1.2)
            out.append((by, lambda x=cx + dx, y=by, h=haut, c=teinte, e=ech:
                        self._grass_tuft(x, y, h, c, scale=e)))
        return out

    def _stone(self, cx, cy, r, sprite=None):
        self._shadow(cx, cy - r * 0.05, r * 2.1)          # ombre portee
        if self._sprite(sprite, cx, cy, r * 1.5):
            return
        Color(0.30, 0.31, 0.34, 1)                        # bas sombre
        Ellipse(pos=(cx - r, cy), size=(r * 2, r * 1.25))
        Color(0.46, 0.47, 0.51, 1)                        # corps
        Ellipse(pos=(cx - r * 0.95, cy + r * 0.18), size=(r * 1.9, r * 1.05))
        Color(0.60, 0.61, 0.66, 1)                        # reflet (haut-gauche)
        Ellipse(pos=(cx - r * 0.7, cy + r * 0.55), size=(r * 1.0, r * 0.6))
        Color(0.22, 0.22, 0.25, 0.5)                      # fissure
        Line(points=[cx - r * 0.3, cy + r * 0.2,
                     cx + r * 0.1, cy + r * 0.95], width=1.0)

    def _branch(self, cx, cy, length, sprite=None):
        wdt = max(1.5, length * 0.07)
        if self._sprite(sprite, cx, cy - wdt, length * 0.30):
            return
        Color(0, 0, 0, 0.14)                              # ombre
        Line(points=[cx - length / 2, cy - wdt * 0.6,
                     cx + length / 2, cy - wdt * 0.6 + length * 0.08],
             width=wdt)
        Color(0.34, 0.23, 0.13, 1)                        # bois
        Line(points=[cx - length / 2, cy, cx + length / 2, cy + length * 0.08],
             width=wdt)
        Color(0.30, 0.20, 0.11, 1)                        # ramures
        Line(points=[cx + length * 0.1, cy + length * 0.05,
                     cx + length * 0.28, cy + length * 0.20],
             width=max(1.0, wdt * 0.6))
        Line(points=[cx - length * 0.2, cy + length * 0.01,
                     cx - length * 0.34, cy + length * 0.16],
             width=max(1.0, wdt * 0.6))
        Color(0.48, 0.35, 0.21, 0.7)                      # reflet sur le dessus
        Line(points=[cx - length * 0.42, cy + wdt * 0.3,
                     cx + length * 0.42, cy + wdt * 0.3 + length * 0.08],
             width=max(1.0, wdt * 0.35))

    def _plant(self, cx, base, size, sprite=None):
        self._shadow(cx, base, size * 1.1, opacity=0.7)
        if self._sprite(sprite, cx, base, size * 1.05):
            return
        Color(0.18, 0.36, 0.16, 1)                       # tige
        Rectangle(pos=(cx - size * 0.06, base), size=(size * 0.12, size * 0.8))
        Color(0.24, 0.46, 0.20, 1)                       # feuilles
        Ellipse(pos=(cx - size * 0.55, base + size * 0.20),
                size=(size * 0.60, size * 0.30))
        Ellipse(pos=(cx - size * 0.05, base + size * 0.30),
                size=(size * 0.60, size * 0.30))
        Ellipse(pos=(cx - size * 0.22, base + size * 0.55),
                size=(size * 0.44, size * 0.50))

    def _hay(self, cx, base, height, scale):
        """Touffe de foin (graminees dorees)."""
        if self._sprite("hay", cx, base, height):
            return
        bw = max(1.5, self.width * 0.004 * scale)
        Color(0.74, 0.64, 0.30, 1)
        for off, sc in ((-1.5, 0.8), (-0.7, 1.0), (0.0, 0.9),
                        (0.7, 1.0), (1.5, 0.75)):
            bx = cx + off * bw
            Triangle(points=[bx - bw, base, bx + bw, base,
                             bx + off * bw * 0.15, base + height * sc])

    def _wheat(self, cx, base, height, scale):
        """Epi de cereale : tige + grains."""
        if self._sprite("wheat", cx, base, height):
            return
        Color(0.80, 0.70, 0.34, 1)
        Line(points=[cx, base, cx, base + height], width=max(1.0, 2.0 * scale))
        Color(0.87, 0.74, 0.34, 1)
        rr = max(2.0, 3.2 * scale)
        for i in range(4):
            yy = base + height * (0.56 + 0.11 * i)
            Ellipse(pos=(cx - rr, yy), size=(rr * 2, rr * 1.5))

    # UN SOMMET TOUS LES N PIXELS pour le bord du sol. C'est ce qui fixe la
    # FINESSE de la dentelure : on ne peut pas decrire un cran plus etroit que
    # deux segments. A quarante segments pour tout l'ecran -- l'ancienne
    # valeur, fixe -- le plus fin relief possible faisait cinquante pixels de
    # large sur un telephone : une ondulation, pas un bord.
    #
    # QUATORZE ET NON SIX. A six, la crete de montagne etait une scie : un
    # cran tous les douze pixels sur toute la largeur de l'ecran. Ce n'est pas
    # ainsi qu'un terrain se decoupe -- il a quelques accidents, pas cent.
    SEGMENT_FRANGE = 14.0

    # DE COMBIEN LE BORD S'EFFILOCHE, en part de la TUILE de la texture vue a
    # la crete. C'est ce qui l'accorde a la matiere : une frange se mesure a
    # la taille des brins, pas a la taille de l'ecran. Un sol a grosse maille
    # s'effiloche donc en gros morceaux, un sol fin en petits.
    FRANGE_TUILE = 0.06
    # ... et jamais plus que cela en part de la hauteur de l'ecran : sur un
    # telephone etroit, la tuile peut faire la moitie de l'image.
    FRANGE_MAX = 0.007

    # PART DU GRAIN FIN dans la frange (le reste est le grain large). Plus il
    # monte, plus le bord est herisse ; plus il baisse, plus il ondule.
    POIDS_FIN = 0.28

    def _frange(self, tex_name, tile_px, depth, segs):
        """Le decalage a ajouter au bord du sol, sommet par sommet.

        DEUX GRAINS SUPERPOSES, parce qu'un seul ne suffit pas : un bruit fin
        seul donne un peigne regulier, un bruit large seul une simple
        ondulation de plus. Ensemble ils font une frange -- des touffes
        irregulieres, chacune dentelee.

        LE BORD SE REFERME AUX DEUX BOUTS (la frange s'eteint sur les
        cinquante premiers et derniers pixels). Le sol est un ruban qui sort
        de l'ecran des deux cotes ; un cran au ras du bord se lirait comme un
        defaut d'affichage.

        Le hasard tient a la GRAINE de la case et au nom de la texture : la
        meme case garde sa frange d'un redessin a l'autre, et les deux bandes
        d'un meme sol (la proche et la lointaine) ne se decoupent pas
        pareil."""
        if segs < 2:
            return [0.0] * (segs + 1)
        # La tuile telle qu'on la voit A LA CRETE : c'est la que se trouve le
        # bord, et la texture y est deja resserree par la perspective.
        tuile = tile_px / max(1.0, float(depth))
        ampl = min(tuile * self.FRANGE_TUILE, self.height * self.FRANGE_MAX)
        rng = random.Random("%s:%s:frange" % (self._seed, tex_name))
        gros = [rng.uniform(-1.0, 1.0) for _ in range(segs // 12 + 2)]
        out = []
        for i in range(segs + 1):
            # Grain large, interpole : les touffes.
            u = i / segs * (len(gros) - 1)
            j = min(len(gros) - 2, int(u))
            f = u - j
            large = gros[j] * (1 - f) + gros[j + 1] * f
            # Grain fin, sommet par sommet : la dentelure.
            fin = rng.uniform(-1.0, 1.0)
            v = (1.0 - self.POIDS_FIN) * large + self.POIDS_FIN * fin
            # Extinction aux deux bouts.
            bord = min(1.0, (min(i, segs - i) / segs) * self.width / 50.0)
            out.append(v * ampl * bord)
        return out

    def _fill_curve(self, top_fn, tex_name, segs=None, tile_px=None,
                    depth=GROUND_DEPTH, rows=GROUND_ROWS, estompe=False,
                    frange=True):
        """Remplit du bas du widget jusqu'a la courbe top_fn(fx) (terrain).

        Habille avec la texture `tex_name` si elle existe (sinon couleur de
        repli), EN PERSPECTIVE : la tuile retrecit a mesure que le terrain
        s'eloigne (voir GROUND_DEPTH).

        `depth=1.0` redonne une repetition reguliere, sans profondeur.

        LE BORD DU HAUT EST DECHIQUETE, et c'est le point de ce dessin. La
        courbe est une somme de sinus : parfaitement lisse, elle tranchait la
        texture au rasoir et le sol se lisait comme une decoupe de papier
        posee sur le fond. Un sol ne finit jamais ainsi -- il s'effiloche en
        brins, en feuilles, en cailloux. Voir _frange.

        `frange=False` rend le bord LISSE. Le lac s'en sert : sa rive d'en
        face est une ligne d'eau, et l'eau ne s'effiloche pas -- elle a un
        niveau.

        `estompe` ajoute en plus un fondu de matiere au-dessus du bord. IL NE
        VAUT QUE LA OU LE SOL RENCONTRE UN AUTRE SOL -- la bande proche
        par-dessus la bande lointaine. Contre le CIEL il est nuisible, et cela
        s'est vu tout de suite : la crete de la montagne trainait une bavure
        grise en diagonale dans le ciel, et la rive du lac un halo bleu
        par-dessus la berge d'en face. Contre le ciel, la dentelure seule fait
        le travail -- c'est une silhouette qu'on veut, pas un degrade."""
        if tile_px is None:
            tile_px = textures.tile_for(tex_name)
        if segs is None:
            # Assez de sommets pour que la frange ait du grain : un segment
            # tous les quelques pixels. A quarante segments pour tout l'ecran
            # -- l'ancienne valeur -- le plus fin relief qu'on puisse decrire
            # fait vingt-cinq pixels de large, soit une ondulation, pas un
            # bord.
            segs = max(40, int(self.width / self.SEGMENT_FRANGE))
        x0, y0, w = self.x, self.y, self.width
        cx = x0 + w / 2.0                      # point de fuite : le milieu
        tex = paint(tex_name)
        self._bind_pbr(tex_name)

        depth = max(1.0, float(depth))
        rows = max(1, int(rows)) if depth > 1.0 else 1
        # a = part du chemin vers l'horizon reellement parcourue. k = 1/(1-a*t)
        # va donc de 1 (tout pres) a `depth` (au fond) quand t va de 0 a 1.
        a = 1.0 - 1.0 / depth

        # Bandes reparties uniformement en DISTANCE (donc resserrees a
        # l'ecran pres de la crete) : c'est la que la perspective se courbe
        # le plus, et donc la qu'il faut des sommets.
        ks = [1.0 + (depth - 1.0) * j / rows for j in range(rows + 1)]
        if a:
            ts = [(1.0 - 1.0 / k) / a for k in ks]
        else:
            # SANS PERSPECTIVE (depth = 1), les rangees se repartissent
            # simplement sur la hauteur. La formule ci-dessus divise par a,
            # qui vaut alors zero ; elle rendait 0 pour toutes les rangees, et
            # le maillage etait PLAT -- hauteur nulle, donc invisible.
            #
            # Le cas n'avait jamais servi : la documentation annoncait
            # "depth=1.0 redonne une repetition reguliere", et personne
            # n'avait essaye. Le jour ou la pente de montagne est passee par
            # ici, elle a disparu de l'ecran.
            ts = [j / rows for j in range(rows + 1)]

        frange = (self._frange(tex_name, tile_px, depth, segs) if frange
                  else [0.0] * (segs + 1))
        verts = []
        for i in range(segs + 1):
            fx = i / segs
            x = x0 + fx * w
            top = top_fn(fx) + frange[i]
            for k, t in zip(ks, ts):
                # A la distance k, l'ecran couvre k fois plus de terrain :
                # u s'ecarte du point de fuite, v s'enfonce. La tuile
                # retrecit donc des deux cotes a la fois (pas d'etirement).
                #
                # v SE DEDUIT DE LA HAUTEUR A L'ECRAN, pas de (k-1) : les deux
                # donnent le meme resultat quand il y a de la perspective
                # (span*(k-1) vaut exactement (y-y0)*k), mais seule celle-ci
                # garde un sens quand il n'y en a pas.
                yy = y0 + t * (top - y0)
                verts += [x, yy, (x - cx) * k / tile_px,
                          -(yy - y0) * k / tile_px]

        stride = rows + 1
        idx = []
        for i in range(segs):
            for j in range(rows):
                p = i * stride + j
                q = p + stride
                idx += [p, q, q + 1, p, q + 1, p + 1]
        Mesh(vertices=verts, indices=idx, mode="triangles", texture=tex)
        if estompe:
            self._estompe(top_fn, frange, tex, tex_name, tile_px, depth, segs)
        self._reset_pbr()

    # LA MECHE QUI S'EFFACE au-dessus du bord : sur quelle hauteur (en part de
    # la frange) et en combien de paliers.
    ESTOMPE_HAUTEUR = 2.2
    ESTOMPE_PALIERS = 4

    def _estompe(self, top_fn, frange, tex, tex_name, tile_px, depth, segs):
        """Prolonge le sol au-dessus de son bord, en s'effacant.

        POURQUOI CELA NE SUFFISAIT PAS DE DECHIQUETER LE BORD. Un bord
        dentele reste un BORD : la matiere s'y arrete net, a un pixel pres, et
        l'oeil lit toujours une decoupe -- une decoupe aux ciseaux cranteurs
        plutot qu'aux ciseaux droits. Ce qui enleve la coupure, c'est que la
        matiere s'ECLAIRCISSE en montant, comme un sol qui se perd dans la
        distance.

        C'est aussi ce qui accorde le bord a LA TEXTURE de la scene, au sens
        propre : ce qui deborde au-dessus n'est pas une couleur choisie, c'est
        le sol lui-meme, la meme image, a la meme echelle.

        EN PALIERS, parce qu'un maillage Kivy ne sait pas donner une opacite
        par sommet. Quatre suffisent : le degrade porte sur une vingtaine de
        pixels, et l'oeil n'y distingue pas les marches.

        Chaque palier a sa PROPRE dentelure, sinon les quatre se
        superposeraient exactement et le degrade redeviendrait un bord franc,
        juste plus epais."""
        n = self.ESTOMPE_PALIERS
        ampl = max(abs(v) for v in frange) if frange else 0.0
        if ampl <= 0.5 or n <= 0:
            return
        haut = ampl * self.ESTOMPE_HAUTEUR
        x0, y0, w = self.x, self.y, self.width
        cx = x0 + w / 2.0
        k = max(1.0, float(depth))
        rng = random.Random("%s:%s:estompe" % (self._seed, tex_name))
        bas = list(frange)
        for etage in range(n):
            # Opacite decroissante : 0.62, 0.42, 0.26, 0.13 pour quatre.
            alpha = 0.62 * (1.0 - etage / float(n)) ** 1.6
            dessus = [frange[i] + haut * (etage + 1) / n
                      + rng.uniform(-0.45, 0.45) * ampl
                      for i in range(segs + 1)]
            verts, idx = [], []
            for i in range(segs + 1):
                fx = i / segs
                x = x0 + fx * w
                for yy in (top_fn(fx) + bas[i], top_fn(fx) + dessus[i]):
                    verts += [x, yy, (x - cx) * k / tile_px, -(yy - y0) / tile_px]
                if i:
                    p = (i - 1) * 2
                    idx += [p, p + 1, p + 2, p + 1, p + 3, p + 2]
            if tex is not None:
                Color(1, 1, 1, alpha)
            else:
                r, g, b = textures.fallback(tex_name)[:3]
                Color(r, g, b, alpha)
            Mesh(vertices=verts, indices=idx, mode="triangles", texture=tex)
            bas = dessus

    def _plaine(self, rng):
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        hor = 0.55
        edge = hor - 0.06
        near = (0.20, 0.40, 0.14)
        far = (0.42, 0.55, 0.32)

        def green_at(t):
            return tuple(near[i] + (far[i] - near[i]) * t for i in range(3)) \
                + (1,)

        # Terrain ONDULE : deux courbes (sommes de sinus) pour un relief
        # naturel. horizon_curve = crete lointaine (l'horizon) ; field_curve =
        # surface du champ proche, ou reposent tous les elements.
        p1 = rng.uniform(0, 6.28)
        p2 = rng.uniform(0, 6.28)

        def horizon_curve(fx):
            return y0 + (edge + 0.035 * math.sin(fx * 6.28 * 1.4 + p1)
                         + 0.018 * math.sin(fx * 6.28 * 3.1 + p2)) * h

        def field_curve(fx):
            return y0 + ((edge - 0.13)
                         + 0.030 * math.sin(fx * 6.28 * 1.1 + p1 + 1.0)
                         + 0.014 * math.sin(fx * 6.28 * 2.5 + p2)) * h

        def place(maxt=1.0, fx=None, floor=0.0):
            if fx is None:
                fx = rng.uniform(0, 1)
            fx = min(0.999, max(0.001, fx))
            surf = (field_curve(fx) - y0) / h         # sommet du sol a cet x
            lo = min(floor, surf)              # plancher (jointures des mains)
            hi = surf * maxt
            if hi < lo:
                hi = lo
            fy = lo + (hi - lo) * rng.random()
            t = (fy / surf) if surf else 0.0
            return (x0 + fx * w, y0 + fy * h, 1.0 - 0.70 * t, t)

        # Distribution en AMAS : chaque type pousse autour de quelques foyers
        # (touffes d'herbe, tas de pierres, bosquets...) au lieu d'un saupoudrage
        # uniforme -> bien plus naturel.
        def clusters(count, spread):
            centers = [rng.uniform(0.05, 0.95) for _ in range(max(1, count))]
            return lambda: rng.choice(centers) + rng.gauss(0, spread)

        grass_pick = clusters(rng.randint(4, 6), 0.13)
        stone_pick = clusters(rng.randint(2, 3), 0.05)
        plant_pick = clusters(rng.randint(3, 4), 0.08)
        mush_pick = clusters(rng.randint(2, 3), 0.05)
        berry_pick = clusters(rng.randint(2, 3), 0.05)
        hay_pick = clusters(rng.randint(2, 3), 0.10)
        wheat_pick = clusters(rng.randint(2, 3), 0.10)


        # Ce qu'il y a AUTOUR, tout au fond, avant le moindre brin d'herbe.
        self._horizon(lambda fx: horizon_curve(fx) - 0.012 * h)

        # Collines : crete lointaine (clair) puis champ proche (fonce) ondules.
        self._fill_curve(horizon_curve, "grass_far")
        self._fill_curve(field_curve, "grass", estompe=True)

        # Petites fabriques de "fonctions de dessin" (pour differer le rendu).
        def f_grass(gx, gb, gh, col, sc, flower, fr):
            def fn():
                self._grass_tuft(gx, gb, gh, col, scale=sc)
                if flower:
                    fcol, fsprite = flower
                    self._flower(gx, gb + gh, fr * 2.4, fcol, sprite=fsprite)
            return fn

        # On collecte chaque element avec sa PROFONDEUR (= y de sa base), puis
        # on dessine du plus LOIN (base haute) au plus PROCHE (base basse) :
        # les elements proches recouvrent ceux du fond, de facon realiste.
        items = []   # (y_base, fonction)

        for _ in range(rng.randint(9, 13)):            # pierres (en tas) [Pierre]
            sx, sy, sc, t = place(1.0, fx=stone_pick(), floor=_HARVEST_FLOOR)
            r = rng.uniform(0.018, 0.045) * h * sc
            if not self._take_or_skip("Pierre") and not self._is_blocked(sx, sy):
                items.append((sy, lambda sx=sx, sy=sy, r=r:
                              self._stone(sx, sy, r,
                                          sprite=self._zs("stone"))))
        for _ in range(rng.randint(6, 9)):             # branches [Small_Stick]
            bx, by, sc, t = place(1.0, floor=_HARVEST_FLOOR)
            ln = rng.uniform(0.06, 0.12) * w * sc
            # Un baton est trie sur son BOIS, ombre comprise. Il l'etait
            # auparavant sur un biais fixe de 12 % de l'ecran, cense le faire
            # passer par-dessus l'herbe de sa profondeur ; mais c'etait sept
            # fois sa propre emprise, et cela le faisait aussi passer devant
            # des buissons et des arbres nettement plus proches que lui.
            if not self._take_or_skip("Small_Stick") and not self._is_blocked(bx, by):
                items.append((by - self.DEBORD_BRANCHE * ln,
                              lambda bx=bx, by=by, ln=ln:
                              self._branch(bx, by, ln,
                                           sprite=self._zs("branch"))))
        # Buissons (taille humaine) : GROS elements positionnes sur la GRILLE
        # 5x5 (cases interdites a l'installation d'un objet).
        for kind, rang, depth, bx, by, jit in self._iter_nature_big():
            if kind == "nugget":
                items.extend(self._pepite_de_grille(rang, depth, bx, by, jit))
                continue
            g = jit.uniform(0.0, 0.10)
            r = (0.17 - 0.09 * depth) * jit.uniform(0.85, 1.15) * h
            col = (0.12 + g, 0.30 + g, 0.15, 1)
            items.append((by - self.DEBORD_BUISSON * r,
                          lambda bx=bx, by=by, r=r, col=col:
                          self._bush(bx, by, r, col,
                                     sprite=self._zs("bush"))))
        for _ in range(105):                           # gazon (en touffes) [Herbe]
            fx = grass_pick() if rng.random() < 0.72 else None  # amas + un peu partout
            gx, gb, sc, t = place(fx=fx, floor=_HARVEST_FLOOR)
            gh = rng.uniform(0.05, 0.16) * h * sc
            fcol = rng.choice(_FLOWERS) if rng.random() < 0.10 else None
            fr = max(1.5, w * 0.004 * sc)
            if (not self._take_or_skip("Herbe")
                    and not self._is_blocked(gx, gb, gb + gh)):
                items.append((gb, f_grass(gx, gb, gh, green_at(t), sc, fcol, fr)))
        n = 125                                        # herbe d'horizon [Herbe]
        for i in range(n):
            fx = i / (n - 1)
            gx = x0 + fx * w + rng.uniform(-0.006, 0.006) * w
            gb = horizon_curve(fx) - rng.uniform(0.0, 0.03) * h  # sur la crete
            gh = rng.uniform(0.05, 0.11) * h
            if (not self._take_or_skip("Herbe")
                    and not self._is_blocked(gx, gb, gb + gh)):
                items.append((gb, f_grass(gx, gb, gh,
                                          green_at(rng.uniform(0.85, 1.0)),
                                          0.5, None, 0)))
        for _ in range(rng.randint(10, 14)):           # plantes feuillues (bosquets)
            px, py, sc, t = place(fx=plant_pick())
            s = rng.uniform(0.05, 0.09) * h * sc
            if self._is_blocked(px, py, py + s * 1.05):
                continue
            items.append((py, lambda px=px, py=py, s=s:
                          self._plant(px, py, s, sprite=self._zs("plant"))))

        # --- Plantes de champ OPTIONNELLES (tirage generatif) ---
        if rng.random() < 0.75:                        # foin (en parcelles)
            for _ in range(rng.randint(6, 12)):
                fx, fb, sc, t = place(0.95, fx=hay_pick())
                ht = rng.uniform(0.10, 0.20) * h * sc
                if self._is_blocked(fx, fb, fb + ht):
                    continue
                items.append((fb, lambda fx=fx, fb=fb, ht=ht, sc=sc:
                              self._hay(fx, fb, ht, sc)))
        if rng.random() < 0.65:                        # epis / graminees (parcelles)
            for _ in range(rng.randint(8, 16)):
                ex, eb, sc, t = place(0.95, fx=wheat_pick())
                ht = rng.uniform(0.10, 0.18) * h * sc
                if self._is_blocked(ex, eb, eb + ht):
                    continue
                items.append((eb, lambda ex=ex, eb=eb, ht=ht, sc=sc:
                              self._wheat(ex, eb, ht, sc)))
        # Pas de champignons en plaine (uniquement en foret pour l'instant).
        if rng.random() < 0.5:                         # baies (buissons) [Baie]
            for _ in range(rng.randint(3, 6)):
                bx, by, sc, t = place(1.0, fx=berry_pick(), floor=_HARVEST_FLOOR)
                r = rng.uniform(0.03, 0.045) * h * sc
                if not self._take_or_skip("Baie") and not self._is_blocked(bx, by):
                    items.append((by - self.DEBORD_BAIES * r,
                                  lambda bx=bx, by=by, r=r:
                                  self._berries(bx, by, r)))

        # (Les insectes sont desormais une couche ANIMEE separee : InsectLayer.)

        # Rendu trie : plus loin (base haute) d'abord, plus proche par-dessus.
        items += self._installed_items()     # feu de camp... a leur profondeur
        items += self._edge_items()          # la case d'a cote, qui deborde
        items.sort(key=lambda it: it[0], reverse=True)
        for _, fn in items:
            fn()

    def _montagne(self, rng):
        w, h, x0, y0 = self.width, self.height, self.x, self.y

        def surf(fx):                      # hauteur de la pente a la position fx
            return y0 + (0.60 + 0.36 * fx) * h

        # Paysages voisins : poses au POINT LE PLUS BAS de la pente, pas sur
        # la pente elle-meme. Une ligne d'arbres qui grimperait le long du
        # versant se lirait comme une foret accrochee a la montagne ; posee a
        # plat, elle reste ce qu'elle est -- le fond de vallee, que la pente
        # (dessinee juste apres) vient masquer a mesure qu'elle monte.
        self._horizon(lambda fx: surf(0.0))

        # Pente principale (remplit le cadre, monte vers la droite). Elle
        # passe par _fill_curve et non par un quadrilatere : sa crete est le
        # bord du SOL contre le ciel, et elle etait dessinee ici comme un
        # trait parfaitement droit -- une regle posee sur le paysage. Elle y
        # gagne la meme frange que les autres sols.
        #
        # depth=1.0 : la pente monte, elle ne s'enfonce pas vers un horizon.
        # Sa tuile ne doit donc pas se resserrer.
        self._fill_curve(lambda fx: surf(fx), "rock", depth=1.0)
        # Bas plus sombre (profondeur).
        self._tquad("rock_dark",
                    [x0, y0, x0 + w, y0, x0 + w, y0 + 0.22 * h, x0, y0 + 0.14 * h])
        # Rochers disperses sur la pente (vers le haut). [recoltable: Pierre]
        for _ in range(42):
            fx = rng.uniform(0, 1)
            sx = x0 + fx * w
            top = (surf(fx) - y0) / h
            lo = min(_HARVEST_FLOOR, top - 0.05)   # plancher (jointures)
            hi = max(lo + 0.02, top - 0.05)
            sy = y0 + rng.uniform(lo, hi) * h
            rr = rng.uniform(0.015, 0.05) * h
            s = rng.uniform(-0.06, 0.06)
            if not self._take_or_skip("Pierre") and not self._is_blocked(sx, sy):
                if not self._sprite(self._zs("stone"), sx, sy, rr * 1.5):
                    Color(0.45 + s, 0.44 + s, 0.49 + s, 1)
                    Ellipse(pos=(sx - rr, sy), size=(rr * 2.2, rr * 1.5))
        # Plaques de neige en haut de la pente.
        for _ in range(8):
            fx = rng.uniform(0.4, 1.0)
            sx = x0 + fx * w
            sy = surf(fx) - rng.uniform(0.02, 0.10) * h
            rr = rng.uniform(0.02, 0.05) * h
            if self._is_blocked(sx, sy, sy + rr * 1.2):
                continue
            if not self._sprite("snow_patch", sx, sy, rr * 1.2):
                Color(0.92, 0.95, 1.0, 1)
                Ellipse(pos=(sx - rr, sy), size=(rr * 2.4, rr * 1.2))
        # GROS rochers : elements FIXES positionnes sur la GRILLE 5x5 (cases
        # interdites a l'installation d'un objet). Non recoltables : la Pierre
        # se recolte sur les petits rochers de la pente. Ils sont tries AVEC
        # les objets installes : un feu de camp pose derriere un rocher passe
        # donc derriere lui.
        items = self._installed_items() + self._edge_items()
        # Touffes rares sur la pente basse. Elles etaient dessinees ici meme,
        # HORS du tri : elles passaient donc toujours derriere les rochers, et
        # surtout dans un ordre quelconque ENTRE ELLES -- une touffe lointaine
        # pouvait recouvrir une touffe proche. Elles rejoignent la liste.
        for _ in range(8):
            sx = x0 + rng.uniform(0, 1) * w
            sy = y0 + rng.uniform(0.03, 0.18) * h
            gh = rng.uniform(0.03, 0.06) * h
            if self._is_blocked(sx, sy, sy + gh):
                continue
            items.append((sy, lambda sx=sx, sy=sy, gh=gh:
                          self._grass_tuft(sx, sy, gh, (0.22, 0.34, 0.16, 1))))
        for kind, rang, depth, rx, ry, jit in self._iter_nature_big():
            if kind == "nugget":
                items.extend(self._pepite_de_grille(rang, depth, rx, ry, jit))
                continue
            rr = (0.085 - 0.045 * depth) * jit.uniform(0.85, 1.15) * h
            items.append((ry, lambda rx=rx, ry=ry, rr=rr:
                          self._big_rock(rx, ry, rr)))
        items.sort(key=lambda it: it[0], reverse=True)
        for _, fn in items:
            fn()

    def _big_rock(self, rx, ry, rr):
        self._shadow(rx, ry + rr * 0.15, rr * 2.4)
        if self._sprite("boulder", rx, ry, rr * 1.8):
            return
        Color(0.38, 0.37, 0.43, 1)
        Ellipse(pos=(rx - rr, ry), size=(rr * 2.4, rr * 1.8))

    def _lac(self, rng):
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        # Paysages voisins, derriere la berge d'en face.
        self._horizon(lambda fx: y0 + 0.70 * h)

        # COLLINES / BERGE D'EN FACE : c'est de l'HERBE, et c'est la meme que
        # celle de la plaine -- elle prend donc sa texture. Ces deux bandes
        # etaient deux ellipses d'un vert plat, et elles etaient devenues la
        # derniere grande surface unie du jeu.
        #
        # Deux plans, comme en plaine : le lointain assombri (grass_far), le
        # plus proche a pleine couleur. Chacun est dessine par _fill_curve,
        # qui repete la tuile en perspective -- sur une bande aussi lointaine,
        # l'herbe doit etre tres fine, et une ellipse texturee l'aurait
        # simplement etiree d'un bord a l'autre.
        def colline(cx, demi, bas, haut):
            """La silhouette d'une colline : l'arc de l'ellipse d'avant."""
            def f(fx):
                d = (fx - cx) / demi
                return y0 + h * (bas + haut * math.sqrt(max(0.0, 1.0 - d * d)))
            return f

        self._fill_curve(colline(0.55, 0.80, 0.58, 0.18), "grass_far",
                         frange=False)
        self._fill_curve(colline(0.52, 0.85, 0.54, 0.14), "grass",
                         frange=False)
        # Grande etendue d'eau (on est au bord), jusqu'a 0.60h.
        #
        # SANS FRANGE : l'eau ne s'effiloche pas, elle a un NIVEAU. Une rive
        # dentelee se lisait comme une cote decoupee vue d'avion, alors qu'on
        # regarde une surface plane par la tranche.
        # (Le bas est recouvert par la rive proche, juste apres : remplir
        # depuis y0 ne change rien a ce qu'on voit.)
        self._fill_curve(lambda fx: y0 + 0.60 * h, "water", depth=1.0,
                         frange=False)
        # Reflets clairs.
        Color(0.32, 0.56, 0.74, 1)
        for _ in range(11):
            ly = y0 + rng.uniform(0.13, 0.58) * h
            lx = x0 + rng.uniform(0, 0.6) * w
            Line(points=[lx, ly, lx + rng.uniform(0.2, 0.45) * w, ly],
                 width=1.4)
        # Rive proche (premier plan). Les galets recoltables sont remontes a
        # partir des jointures (rien en bas). [recoltable: Pierre]
        self._trect("sand", x0, y0, w, 0.12 * h)

        # Galets, roseaux et objets installes sont tries ENSEMBLE par
        # profondeur : un feu de camp pose au fond passe derriere les roseaux
        # du premier plan.
        items = self._installed_items() + self._edge_items()
        for _ in range(12):
            rx = x0 + rng.uniform(0, 1) * w
            ry = y0 + rng.uniform(_HARVEST_FLOOR, 0.28) * h
            rr = rng.uniform(0.012, 0.03) * h
            if not self._take_or_skip("Pierre") and not self._is_blocked(rx, ry):
                items.append((ry, lambda rx=rx, ry=ry, rr=rr:
                              self._pebble(rx, ry, rr)))
        # Roseaux (remontes a partir des jointures). [recoltable: Roseau]
        for _ in range(34):
            gx = x0 + rng.uniform(0, 1) * w
            gb = y0 + rng.uniform(_HARVEST_FLOOR, 0.30) * h
            gh = rng.uniform(0.08, 0.22) * h
            if (not self._take_or_skip("Roseau")
                    and not self._is_blocked(gx, gb, gb + gh)):
                items.append((gb, lambda gx=gx, gb=gb, gh=gh:
                              self._grass_tuft(gx, gb, gh,
                                               (0.18, 0.38, 0.20, 1),
                                               sprite="reed")))
        # Pepites de mineraux, sur la GRILLE comme partout ailleurs. C'est le
        # seul gros element du lac : il n'y pousse ni arbre ni buisson.
        for kind, rang, depth, px, pb, jit in self._iter_nature_big():
            if kind == "nugget":
                items.extend(self._pepite_de_grille(rang, depth, px, pb, jit))
        items.sort(key=lambda it: it[0], reverse=True)
        for _, fn in items:
            fn()

    def _pebble(self, rx, ry, rr):
        self._shadow(rx, ry + rr * 0.1, rr * 2.2, opacity=0.8)
        if self._sprite("pebble", rx, ry, rr * 1.4):
            return
        Color(0.42, 0.40, 0.32, 1)
        Ellipse(pos=(rx - rr, ry), size=(rr * 2.4, rr * 1.4))
