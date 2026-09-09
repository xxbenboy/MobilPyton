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

from src import world
from src.widgets import textures, pbr, foliage, daylight
from src.widgets import horizon
from src.widgets.textures import paint, paint_color, tiled_coords
from src.widgets.installed_layer import grid_to_screen

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
            blocked_grid = [(gx, gy) for _n, gx, gy, _l, _v in self._installed]
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

    def _compute_blocked_bboxes(self):
        """Reconstruit les rectangles d'ecran couverts par les objets installes
        (feu de camp, ...) a partir des cellules 5x5 (_blocked_grid)."""
        self._blocked_bboxes = []
        if not self._blocked_grid or self.width <= 0 or self.height <= 0:
            return
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        for (gx, gy) in self._blocked_grid:
            fx, fy, size = grid_to_screen(gx, gy)
            cx = x0 + fx * w
            cy = y0 + fy * h
            # Meme forme aplatie que le cercle de roche (h = w * 0.55) +
            # petite marge (15 %) pour bien couvrir les objets qui debordent.
            hw = size * w * 0.5 * 1.15
            hh = size * w * 0.55 * 0.5 * 1.15
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

        Genere (kind, depth, tx, tb, jit) : type ("tree"/"bush"/"rock"),
        profondeur 0..1, position ecran de la base, et un rng stable pour les
        variations (taille...). Les cases occupees par un objet INSTALLE sont
        sautees (l'objet installe a la priorite d'affichage)."""
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
            gfx, gfy, _gs = grid_to_screen(ggx, ggy)
            jit = random.Random(f"{self._seed}:{ggx}:{ggy}:big")
            depth = ggy / 4.0
            # AUCUN decalage : l'element est pose EXACTEMENT au centre de sa
            # case, comme un objet installe. C'est ce qui permet de retrouver
            # la meme position dans la grille de placement et dans le jeu.
            tx = x0 + gfx * w
            tb = y0 + gfy * h
            yield kind, depth, tx, tb, jit

    def _installed_items(self):
        """Objets INSTALLES, prets a etre tries avec le reste du decor.

        Renvoie [(y_base, fonction_de_dessin), ...] : la meme forme que les
        elements du decor, donc le tri par profondeur les melange correctement
        (ce qui est plus PROCHE est dessine par-dessus)."""
        out = []
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        for name, gx, gy, lit, level in self._installed:
            fx, fy, size = grid_to_screen(gx, gy)
            cx = x0 + fx * w
            cy = y0 + fy * h
            if name == "Feu_de_camp":
                out.append((cy, lambda cx=cx, cy=cy, s=size * w, lit=lit,
                            lv=level: self._fire_pit(cx, cy, s, lit, lv)))
        return out

    def _fire_pit(self, cx, cy, w, lit=False, level="grand"):
        """Foyer de pierres vu en angle (cercle aplati + anneau de pierres).

        Allume, il montre ses braises et ses flammes, d'autant plus hautes
        qu'il lui reste du combustible (voir _FLAME_SCALE). C'est la MEME
        scene qui sert au jeu et au fond de l'ecran de proximite : le feu a
        donc partout le meme aspect."""
        h = w * 0.55
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

    def _sprite(self, name, cx, base, height):
        """Dessine l'IMAGE de cet element, posee par son BAS sur (cx, base).

        Renvoie Vrai si une image existait et a ete dessinee ; Faux si aucune
        image n'a ete fournie, auquel cas l'appelant garde son dessin
        geometrique d'origine. C'est ce qui rend les images facultatives : le
        jeu tourne a l'identique sans elles, et s'habille au fur et a mesure
        qu'on en depose.

        La VARIANTE est deduite de la position : deux elements voisins ne
        prennent pas la meme image, et un element garde la sienne quand la
        scene est redessinee."""
        if not name:
            return False
        tex = foliage.sprite(name, int(abs(cx) * 7.13 + abs(base) * 3.71))
        if tex is None:
            return False
        w, h = foliage.size_for(tex, height)
        Color(1, 1, 1, 1)
        Rectangle(pos=(cx - w / 2.0, base), size=(w, h), texture=tex)
        return True

    def set_ground(self, zone_type, seed=0):
        """Vue VERS LE BAS : on regarde le sol, qui remplit tout l'ecran."""
        self._zone = zone_type
        self._seed = seed
        self._mode = "ground"
        self._redraw()

    # ------------------------------------------------------------------ #
    def _redraw(self, *_):
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return
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
        graine = self._seed
        for cote in sorted(self._neighbours):
            graine = graine * 31 + hash(self._neighbours[cote]) % 9973
        horizon.draw(self._neighbours, self.x, self.width, crest,
                     self.height, random.Random(graine))

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

        if zone == "Plaine":
            greens = [(0.22, 0.42, 0.16, 1), (0.28, 0.48, 0.18, 1),
                      (0.18, 0.38, 0.14, 1)]
            for _ in range(110):                       # gazon partout
                gx, gy = rnd()
                self._grass_tuft(gx, gy, rng.uniform(0.04, 0.09) * h,
                                 rng.choice(greens), scale=0.8)
            for _ in range(rng.randint(8, 14)):        # petites pierres
                gx, gy = rnd()
                self._stone(gx, gy, rng.uniform(0.015, 0.035) * h,
                            sprite=self._zs("stone"))
            for _ in range(rng.randint(5, 9)):          # fleurs (peu nombreuses)
                gx, gy = rnd()
                col, fsprite = rng.choice(_FLOWERS)
                r = rng.uniform(0.018, 0.032) * h
                self._flower(gx, gy, r, col, petals=rng.choice((5, 6)),
                             sprite=fsprite)
        elif zone == "Foret":
            leaves = [(0.45, 0.32, 0.14, 1), (0.36, 0.40, 0.16, 1),
                      (0.52, 0.38, 0.18, 1), (0.30, 0.26, 0.12, 1)]
            for _ in range(150):                       # litiere de feuilles
                gx, gy = rnd()
                self._leaf(gx, gy, rng.uniform(0.012, 0.024) * h,
                           rng.choice(leaves))
            for _ in range(rng.randint(10, 16)):       # brindilles
                gx, gy = rnd()
                self._branch(gx, gy, rng.uniform(0.05, 0.10) * w,
                             sprite=self._zs("branch"))
            for _ in range(45):                        # touffes sombres
                gx, gy = rnd()
                self._grass_tuft(gx, gy, rng.uniform(0.03, 0.07) * h,
                                 (0.12, 0.22, 0.13, 1), scale=0.7)
            for _ in range(rng.randint(8, 14)):        # pierres mousseuses
                gx, gy = rnd()
                self._stone(gx, gy, rng.uniform(0.02, 0.045) * h,
                            sprite=self._zs("stone"))
        else:                                          # Montagne (rocaille)
            for _ in range(rng.randint(45, 65)):       # rochers / galets
                gx, gy = rnd()
                self._stone(gx, gy, rng.uniform(0.02, 0.06) * h,
                            sprite=self._zs("stone"))
            for _ in range(rng.randint(8, 14)):        # touffes rares
                gx, gy = rnd()
                self._grass_tuft(gx, gy, rng.uniform(0.03, 0.06) * h,
                                 (0.22, 0.34, 0.16, 1), scale=0.7)

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
        self._fill_curve(floor_curve, "forest_floor")

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
                items.append((ly, lambda lx=lx, ly=ly, s=s, col=col:
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
                items.append((by - 0.12 * h, lambda bx=bx, by=by, ln=ln:
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
        for kind, depth, tx, tb, jit in self._iter_nature_big():
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
                items.append((tb, lambda bx=tx, by=tb, r=r, g2=g2:
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

    def _fill_curve(self, top_fn, tex_name, segs=40, tile_px=None,
                    depth=GROUND_DEPTH, rows=GROUND_ROWS):
        """Remplit du bas du widget jusqu'a la courbe top_fn(fx) (terrain).

        Habille avec la texture `tex_name` si elle existe (sinon couleur de
        repli), EN PERSPECTIVE : la tuile retrecit a mesure que le terrain
        s'eloigne (voir GROUND_DEPTH).

        `depth=1.0` redonne une repetition reguliere, sans profondeur."""
        if tile_px is None:
            tile_px = textures.tile_for(tex_name)
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
        ts = [(1.0 - 1.0 / k) / a if a else 0.0 for k in ks]

        verts = []
        for i in range(segs + 1):
            fx = i / segs
            x = x0 + fx * w
            top = top_fn(fx)
            # Facteur qui garde la MEME finesse de texture au premier plan
            # qu'une repetition reguliere : seul le fond se resserre.
            span = (top - y0) / a if a else (top - y0)
            for k, t in zip(ks, ts):
                # A la distance k, l'ecran couvre k fois plus de terrain :
                # u s'ecarte du point de fuite, v s'enfonce. La tuile
                # retrecit donc des deux cotes a la fois (pas d'etirement).
                verts += [x, y0 + t * (top - y0),
                          (x - cx) * k / tile_px,
                          -span * (k - 1.0) / tile_px]

        stride = rows + 1
        idx = []
        for i in range(segs):
            for j in range(rows):
                p = i * stride + j
                q = p + stride
                idx += [p, q, q + 1, p, q + 1, p + 1]
        Mesh(vertices=verts, indices=idx, mode="triangles", texture=tex)
        self._reset_pbr()

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
        self._fill_curve(field_curve, "grass")

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
            # Un baton repose SUR l'herbe locale : on le rapproche (biais) pour
            # qu'il soit dessine par-dessus l'herbe de sa profondeur. Seule
            # l'herbe nettement plus proche (plus bas) passe devant.
            if not self._take_or_skip("Small_Stick") and not self._is_blocked(bx, by):
                items.append((by - 0.12 * h, lambda bx=bx, by=by, ln=ln:
                              self._branch(bx, by, ln,
                                           sprite=self._zs("branch"))))
        # Buissons (taille humaine) : GROS elements positionnes sur la GRILLE
        # 5x5 (cases interdites a l'installation d'un objet).
        for kind, depth, bx, by, jit in self._iter_nature_big():
            g = jit.uniform(0.0, 0.10)
            r = (0.17 - 0.09 * depth) * jit.uniform(0.85, 1.15) * h
            col = (0.12 + g, 0.30 + g, 0.15, 1)
            items.append((by, lambda bx=bx, by=by, r=r, col=col:
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
                    items.append((by, lambda bx=bx, by=by, r=r:
                                  self._berries(bx, by, r)))

        # (Les insectes sont desormais une couche ANIMEE separee : InsectLayer.)

        # Rendu trie : plus loin (base haute) d'abord, plus proche par-dessus.
        items += self._installed_items()     # feu de camp... a leur profondeur
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

        # Pente principale (remplit le cadre, monte vers la droite).
        self._tquad("rock", [x0, y0, x0 + w, y0, x0 + w, surf(1.0), x0, surf(0.0)])
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
        # Touffes rares sur la pente basse.
        for _ in range(8):
            sx = x0 + rng.uniform(0, 1) * w
            sy = y0 + rng.uniform(0.03, 0.18) * h
            gh = rng.uniform(0.03, 0.06) * h
            if self._is_blocked(sx, sy, sy + gh):
                continue
            self._grass_tuft(sx, sy, gh, (0.22, 0.34, 0.16, 1))
        # GROS rochers : elements FIXES positionnes sur la GRILLE 5x5 (cases
        # interdites a l'installation d'un objet). Non recoltables : la Pierre
        # se recolte sur les petits rochers de la pente. Ils sont tries AVEC
        # les objets installes : un feu de camp pose derriere un rocher passe
        # donc derriere lui.
        items = self._installed_items()
        for kind, depth, rx, ry, jit in self._iter_nature_big():
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

        # Collines / berge lointaine (haut), pour reduire le ciel.
        Color(0.16, 0.30, 0.18, 1)
        Ellipse(pos=(x0 - 0.25 * w, y0 + 0.58 * h), size=(1.6 * w, 0.18 * h))
        Color(0.12, 0.24, 0.15, 1)
        Ellipse(pos=(x0 - 0.30 * w, y0 + 0.54 * h), size=(1.7 * w, 0.14 * h))
        # Grande etendue d'eau (on est au bord) : 0.10h -> 0.60h.
        self._trect("water", x0, y0 + 0.10 * h, w, 0.50 * h)
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
        items = self._installed_items()
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
        items.sort(key=lambda it: it[0], reverse=True)
        for _, fn in items:
            fn()

    def _pebble(self, rx, ry, rr):
        self._shadow(rx, ry + rr * 0.1, rr * 2.2, opacity=0.8)
        if self._sprite("pebble", rx, ry, rr * 1.4):
            return
        Color(0.42, 0.40, 0.32, 1)
        Ellipse(pos=(rx - rr, ry), size=(rr * 2.4, rr * 1.4))
