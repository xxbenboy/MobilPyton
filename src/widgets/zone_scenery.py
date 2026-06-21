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
"""
import math
import random

from kivy.uix.widget import Widget
from kivy.graphics import (Color, Ellipse, Rectangle, Triangle, Line, Quad,
                           Mesh, RenderContext, PushMatrix, PopMatrix, Rotate)

from src.widgets import textures, pbr
from src.widgets.textures import paint, paint_color, tiled_coords

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
        self._ord = {}
        self._harvest_total = {}
        self._avail = {}            # {nom: nb recoltable} (aleatoire, par case)
        self.harvest_total = {}     # {nom: total visible dans la scene}
        self.harvest_max = {}       # {nom: nombre de recoltes possibles}
        # Eclairage par cartes de normales : actif seulement si des cartes
        # Normal existent (sinon canvas normal, aucun risque, rendu inchange).
        self._pbr = pbr.LIGHTING and textures.has_any_normal()
        if self._pbr:
            self.canvas = RenderContext(use_parent_projection=True,
                                        use_parent_modelview=True,
                                        use_parent_frag_modelview=True)
            pbr.setup(self.canvas)
        self.bind(pos=self._redraw, size=self._redraw)

    # -- liaison des cartes PBR (normal/packed) pour une surface ---------- #
    def _bind_pbr(self, name):
        if self._pbr:
            pbr.bind_maps(textures.normal_texture(name),
                          textures.packed_texture(name))

    def _reset_pbr(self):
        if self._pbr:
            pbr.reset_maps()

    def set_scene(self, zone_type, seed=0, taken=None):
        """Vue a l'horizon (sol en bas + ciel).

        `taken` = {nom: nombre deja recolte} pour masquer les objets recoltes."""
        self._zone = zone_type
        self._seed = seed
        self._mode = "scene"
        self._taken = dict(taken or {})
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
        # Reinitialise le comptage des objets recoltables pour cette passe.
        self._ord = {}
        self._harvest_total = {}
        self._avail = {}
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
                tc += [(points[i] - x0) / tile_px, (points[i + 1] - y0) / tile_px]
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
                self._stone(gx, gy, rng.uniform(0.015, 0.035) * h)
            for _ in range(rng.randint(5, 9)):          # fleurs (peu nombreuses)
                gx, gy = rnd()
                col = rng.choice([(1, 1, 0.9, 1), (0.96, 0.85, 0.28, 1),
                                  (0.9, 0.45, 0.55, 1), (0.72, 0.52, 0.92, 1)])
                r = rng.uniform(0.018, 0.032) * h
                self._flower(gx, gy, r, col, petals=rng.choice((5, 6)))
        elif zone == "Foret":
            leaves = [(0.45, 0.32, 0.14, 1), (0.36, 0.40, 0.16, 1),
                      (0.52, 0.38, 0.18, 1), (0.30, 0.26, 0.12, 1)]
            for _ in range(150):                       # litiere de feuilles
                gx, gy = rnd()
                self._leaf(gx, gy, rng.uniform(0.012, 0.024) * h,
                           rng.choice(leaves))
            for _ in range(rng.randint(10, 16)):       # brindilles
                gx, gy = rnd()
                self._branch(gx, gy, rng.uniform(0.05, 0.10) * w)
            for _ in range(45):                        # touffes sombres
                gx, gy = rnd()
                self._grass_tuft(gx, gy, rng.uniform(0.03, 0.07) * h,
                                 (0.12, 0.22, 0.13, 1), scale=0.7)
            for _ in range(rng.randint(8, 14)):        # pierres mousseuses
                gx, gy = rnd()
                self._stone(gx, gy, rng.uniform(0.02, 0.045) * h)
        else:                                          # Montagne (rocaille)
            for _ in range(rng.randint(45, 65)):       # rochers / galets
                gx, gy = rnd()
                self._stone(gx, gy, rng.uniform(0.02, 0.06) * h)
            for _ in range(rng.randint(8, 14)):        # touffes rares
                gx, gy = rnd()
                self._grass_tuft(gx, gy, rng.uniform(0.03, 0.06) * h,
                                 (0.22, 0.34, 0.16, 1), scale=0.7)

    # -- helpers -------------------------------------------------------- #
    def _pine(self, cx, base, tw, th, color):
        tex = paint_color("foliage", color)
        self._bind_pbr("foliage")
        Triangle(points=[cx - tw / 2, base, cx + tw / 2, base,
                         cx, base + th * 0.72], texture=tex)
        Triangle(points=[cx - tw * 0.36, base + th * 0.32,
                         cx + tw * 0.36, base + th * 0.32, cx, base + th],
                 texture=tex)
        self._reset_pbr()

    def _grass_tuft(self, cx, base, height, color, scale=1.0):
        bw = max(1.2, self.width * 0.0035 * scale)
        r, g, b, a = color
        # 5 brins fins en eventail, longueurs/inclinaisons/teintes variees.
        for off, hsc, lean in ((-1.3, 0.65, -0.55), (-0.6, 0.85, -0.25),
                               (0.0, 1.0, 0.08), (0.6, 0.88, 0.30),
                               (1.3, 0.70, 0.60)):
            bx = cx + off * bw
            tipx = bx + lean * bw * 2.4
            sh = 0.88 + 0.24 * ((off + 1.3) / 2.6)        # nuance par brin
            Color(min(1.0, r * sh), min(1.0, g * sh), min(1.0, b * sh), a)
            Triangle(points=[bx - bw, base, bx + bw, base,
                             tipx, base + height * hsc])

    def _bush(self, cx, cy, r, color):
        cr, cg, cb, ca = color
        Color(0, 0, 0, 0.16)                              # ombre au sol
        Ellipse(pos=(cx - r * 1.3, cy - r * 0.4), size=(r * 2.6, r * 0.6))
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

    def _tree(self, cx, base, th, leaf, trunk):
        tw = max(2.0, self.width * 0.006)
        btex = paint_color("bark", trunk)
        self._bind_pbr("bark")
        Rectangle(pos=(cx - tw / 2, base), size=(tw, th * 0.5), texture=btex)
        self._reset_pbr()
        ftex = paint_color("foliage", leaf)
        self._bind_pbr("foliage")
        r = th * 0.35
        Ellipse(pos=(cx - r, base + th * 0.32), size=(r * 2, r * 2), texture=ftex)
        self._reset_pbr()

    # -- scenes (plein cadre) ------------------------------------------- #
    def _leaf(self, cx, cy, size, color):
        """Feuille morte au sol (litiere)."""
        Color(*color)
        Ellipse(pos=(cx - size, cy - size * 0.4), size=(size * 2, size * 0.8))

    def _forest_tree(self, cx, base, th, scale):
        """Arbre feuillu : tronc conique + amas de feuillage sombre."""
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
        self._fill_curve(far_curve, "forest_floor_far")
        self._fill_curve(floor_curve, "forest_floor")

        GREENS = [(0.10, 0.20, 0.12), (0.08, 0.17, 0.10), (0.12, 0.24, 0.14)]
        LEAVES = [(0.45, 0.32, 0.14, 1), (0.36, 0.40, 0.16, 1),
                  (0.52, 0.38, 0.18, 1), (0.30, 0.26, 0.12, 1)]

        def f_grass(gx, gb, gh, col, sc):
            return lambda: self._grass_tuft(gx, gb, gh, col, scale=sc)

        def f_insect(ix, iy, sz, is_b, col):
            def fn():
                if is_b:
                    self._butterfly(ix, iy, sz, col)
                else:
                    self._bee(ix, iy, sz)
            return fn

        items = []   # (y_base, fonction) -> tri par profondeur

        # Litiere de feuilles mortes (beaucoup, en plaques). [recoltable: Feuille]
        for _ in range(100):
            fx = leaf_pick() if rng.random() < 0.8 else None
            lx, ly, sc, t = place(fx=fx, floor=_HARVEST_FLOOR)
            s = rng.uniform(0.010, 0.022) * h * sc
            col = rng.choice(LEAVES)
            if not self._take_or_skip("Feuille"):
                items.append((ly, lambda lx=lx, ly=ly, s=s, col=col:
                              self._leaf(lx, ly, s, col)))
        # Pierres mousseuses (en tas). [recoltable: Pierre]
        for _ in range(rng.randint(6, 10)):
            sx, sy, sc, t = place(1.0, fx=stone_pick(), floor=_HARVEST_FLOOR)
            r = rng.uniform(0.02, 0.05) * h * sc
            if not self._take_or_skip("Pierre"):
                items.append((sy, lambda sx=sx, sy=sy, r=r:
                              self._stone(sx, sy, r)))
        # Branches au sol. [recoltable: Small_Stick]
        for _ in range(rng.randint(7, 11)):
            bx, by, sc, t = place(1.0, floor=_HARVEST_FLOOR)
            ln = rng.uniform(0.06, 0.13) * w * sc
            if not self._take_or_skip("Small_Stick"):
                items.append((by - 0.12 * h, lambda bx=bx, by=by, ln=ln:
                              self._branch(bx, by, ln)))
        # Herbe de sous-bois (sombre), en touffes (dense).
        for _ in range(130):
            fx = grass_pick() if rng.random() < 0.72 else None
            gx, gb, sc, t = place(fx=fx)
            gh = rng.uniform(0.05, 0.13) * h * sc
            items.append((gb, f_grass(gx, gb, gh, rng.choice(GREENS) + (1,), sc)))
        # Fougeres / plantes (bosquets).
        for _ in range(rng.randint(8, 12)):
            px, py, sc, t = place(fx=fern_pick())
            s = rng.uniform(0.05, 0.10) * h * sc
            items.append((py, lambda px=px, py=py, s=s: self._plant(px, py, s)))
        # Buissons de sous-bois.
        for _ in range(rng.randint(5, 8)):
            bx, by, sc, t = place(0.85)
            g = rng.uniform(0.0, 0.06)
            r = rng.uniform(0.06, 0.13) * h * sc
            items.append((by, lambda bx=bx, by=by, r=r, g=g:
                          self._bush(bx, by, r, (0.06 + g, 0.16 + g, 0.09, 1))))
        # Champignons : tres peu dans la foret (uniquement bruns pour
        # l'instant). [recoltable: Brown_Mushroom]
        if rng.random() < 0.25:
            for _ in range(rng.randint(1, 3)):
                mx, my, sc, t = place(1.0, fx=mush_pick(), floor=_HARVEST_FLOOR)
                s = rng.uniform(0.03, 0.05) * h * sc
                cap = (0.62, 0.30, 0.18, 1)
                if not self._take_or_skip("Brown_Mushroom"):
                    items.append((my, lambda mx=mx, my=my, s=s, cap=cap:
                                  self._mushroom(mx, my, s, cap)))
        # Arbres : coniferes + feuillus. Ce sont leurs feuillages qui
        # remplissent le haut (plus de fausse canopee).
        def add_tree(tx, tb, sc, big=False):
            th = (rng.uniform(0.85, 1.15) if big
                  else rng.uniform(0.45, 1.05) * (0.5 + 0.5 * sc)) * h
            if rng.random() < 0.5:
                tw = rng.uniform(0.07, 0.14) * w * (0.55 + 0.45 * sc)
                items.append((tb, lambda tx=tx, tb=tb, tw=tw, th=th:
                              self._pine(tx, tb, tw, th, (0.06, 0.15, 0.09, 1))))
            else:
                items.append((tb, lambda tx=tx, tb=tb, th=th, sc=sc:
                              self._forest_tree(tx, tb, th, sc)))

        # Toujours des arbres AUTOUR du joueur : gros, proches, gauche/droite.
        for fxc in (0.05, 0.18, 0.82, 0.95):
            tx, tb, sc, t = place(0.40, fx=fxc + rng.uniform(-0.04, 0.04))
            add_tree(tx, tb, sc, big=True)
        # Beaucoup d'arbres repartis sur toute la profondeur.
        for _ in range(rng.randint(16, 22)):
            tx, tb, sc, t = place(0.97)
            add_tree(tx, tb, sc)
        # Ligne d'arbres DENSE a l'horizon (lointains et petits).
        m = rng.randint(24, 32)
        for i in range(m):
            fx = min(0.999, max(0.001, i / (m - 1) + rng.uniform(-0.02, 0.02)))
            tb = floor_curve(fx) - rng.uniform(0.0, 0.03) * h
            tx = x0 + fx * w
            if rng.random() < 0.55:
                tw = rng.uniform(0.03, 0.06) * w
                th = rng.uniform(0.12, 0.22) * h
                items.append((tb, lambda tx=tx, tb=tb, tw=tw, th=th:
                              self._pine(tx, tb, tw, th, (0.09, 0.17, 0.11, 1))))
            else:
                th = rng.uniform(0.12, 0.20) * h
                items.append((tb, lambda tx=tx, tb=tb, th=th:
                              self._forest_tree(tx, tb, th, 0.4)))
        # (Les insectes sont desormais une couche ANIMEE separee : InsectLayer.)

        items.sort(key=lambda it: it[0], reverse=True)
        for _, fn in items:
            fn()

    # -- objets recoltables / insectes (details) ----------------------- #
    def _mushroom(self, cx, base, size, cap):
        Color(0, 0, 0, 0.16)                             # ombre au sol
        Ellipse(pos=(cx - size * 0.7, base - size * 0.04),
                size=(size * 1.4, size * 0.28))
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

    def _butterfly(self, cx, cy, size, color):
        r, g, b, a = color
        # 2 paires d'ailes (superieure grande + inferieure petite) par cote,
        # avec un liisere sombre, la couleur, puis une tache claire (motif).
        for sgn in (-1, 1):
            ux = cx + sgn * size * 0.52
            lx = cx + sgn * size * 0.44
            Color(r * 0.5, g * 0.5, b * 0.5, a)                 # liisere sombre
            self._ell_c(ux, cy + size * 0.20, size * 1.04, size * 1.18)
            self._ell_c(lx, cy - size * 0.42, size * 0.82, size * 0.82)
            Color(r, g, b, a)                                   # membrane coloree
            self._ell_c(ux, cy + size * 0.20, size * 0.9, size * 1.02)
            self._ell_c(lx, cy - size * 0.42, size * 0.68, size * 0.68)
            Color(min(1, r + 0.32), min(1, g + 0.32), min(1, b + 0.32), a)
            self._ell_c(cx + sgn * size * 0.66, cy + size * 0.34,
                        size * 0.3, size * 0.34)               # tache claire
        Color(0.12, 0.10, 0.10, 1)                              # corps
        self._ell_c(cx, cy - size * 0.05, size * 0.18, size * 1.28)
        self._ell_c(cx, cy + size * 0.58, size * 0.24, size * 0.32)   # tete
        wd = max(1.0, size * 0.05)                              # antennes
        Line(points=[cx, cy + size * 0.66, cx - size * 0.24, cy + size * 1.0],
             width=wd)
        Line(points=[cx, cy + size * 0.66, cx + size * 0.24, cy + size * 1.0],
             width=wd)
        self._ell_c(cx - size * 0.24, cy + size * 1.0, size * 0.1, size * 0.1)
        self._ell_c(cx + size * 0.24, cy + size * 1.0, size * 0.1, size * 0.1)

    def _bee(self, cx, cy, size):
        Color(0, 0, 0, 0.14)                              # petite ombre
        self._ell_c(cx, cy - size * 0.5, size * 1.2, size * 0.3)
        Color(0.92, 0.95, 1.0, 0.55)                      # 2 ailes translucides
        self._ell_c(cx - size * 0.16, cy + size * 0.4, size * 0.7, size * 0.46)
        self._ell_c(cx + size * 0.16, cy + size * 0.4, size * 0.7, size * 0.46)
        Color(0.96, 0.74, 0.12, 1)                        # corps dore (ovale)
        self._ell_c(cx, cy, size * 1.32, size * 0.84)
        Color(0.12, 0.10, 0.08, 1)                        # rayures noires
        for dx, hsc in ((-0.30, 0.7), (0.02, 0.86), (0.34, 0.66)):
            self._ell_c(cx + dx * size, cy, size * 0.16, size * 0.84 * hsc)
        Color(0.16, 0.13, 0.10, 1)                        # tete
        self._ell_c(cx - size * 0.64, cy, size * 0.36, size * 0.52)
        Color(0.30, 0.26, 0.20, 1)                        # dard
        Line(points=[cx + size * 0.66, cy, cx + size * 0.9, cy],
             width=max(1.0, size * 0.05))

    def _flower(self, cx, cy, size, color, petals=5):
        """Fleur : petales allonges disposes en etoile + coeur, au lieu d'un
        simple rond. `size` ~ rayon de la fleur."""
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

    def _stone(self, cx, cy, r):
        Color(0, 0, 0, 0.18)                              # ombre portee
        Ellipse(pos=(cx - r * 1.05, cy - r * 0.35), size=(r * 2.1, r * 0.6))
        Color(0.30, 0.31, 0.34, 1)                        # bas sombre
        Ellipse(pos=(cx - r, cy), size=(r * 2, r * 1.25))
        Color(0.46, 0.47, 0.51, 1)                        # corps
        Ellipse(pos=(cx - r * 0.95, cy + r * 0.18), size=(r * 1.9, r * 1.05))
        Color(0.60, 0.61, 0.66, 1)                        # reflet (haut-gauche)
        Ellipse(pos=(cx - r * 0.7, cy + r * 0.55), size=(r * 1.0, r * 0.6))
        Color(0.22, 0.22, 0.25, 0.5)                      # fissure
        Line(points=[cx - r * 0.3, cy + r * 0.2,
                     cx + r * 0.1, cy + r * 0.95], width=1.0)

    def _branch(self, cx, cy, length):
        wdt = max(1.5, length * 0.07)
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

    def _plant(self, cx, base, size):
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
        bw = max(1.5, self.width * 0.004 * scale)
        Color(0.74, 0.64, 0.30, 1)
        for off, sc in ((-1.5, 0.8), (-0.7, 1.0), (0.0, 0.9),
                        (0.7, 1.0), (1.5, 0.75)):
            bx = cx + off * bw
            Triangle(points=[bx - bw, base, bx + bw, base,
                             bx + off * bw * 0.15, base + height * sc])

    def _wheat(self, cx, base, height, scale):
        """Epi de cereale : tige + grains."""
        Color(0.80, 0.70, 0.34, 1)
        Line(points=[cx, base, cx, base + height], width=max(1.0, 2.0 * scale))
        Color(0.87, 0.74, 0.34, 1)
        rr = max(2.0, 3.2 * scale)
        for i in range(4):
            yy = base + height * (0.56 + 0.11 * i)
            Ellipse(pos=(cx - rr, yy), size=(rr * 2, rr * 1.5))

    def _fill_curve(self, top_fn, tex_name, segs=40, tile_px=None):
        """Remplit du bas du widget jusqu'a la courbe top_fn(fx) (terrain).

        Habille avec la texture `tex_name` (repetee) si elle existe, sinon avec
        la couleur de repli correspondante."""
        if tile_px is None:
            tile_px = textures.tile_for(tex_name)
        x0, y0, w = self.x, self.y, self.width
        tex = paint(tex_name)
        self._bind_pbr(tex_name)
        verts = []
        for i in range(segs + 1):
            fx = i / segs
            x = x0 + fx * w
            top = top_fn(fx)
            u = (x - x0) / tile_px
            verts += [x, y0, u, 0.0, x, top, u, (top - y0) / tile_px]
        idx = list(range(len(verts) // 4))
        Mesh(vertices=verts, indices=idx, mode="triangle_strip", texture=tex)
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

        flowers = [(1, 1, 0.92, 1), (0.96, 0.85, 0.28, 1),
                   (0.92, 0.42, 0.52, 1), (0.72, 0.52, 0.92, 1)]

        # Collines : crete lointaine (clair) puis champ proche (fonce) ondules.
        self._fill_curve(horizon_curve, "grass_far")
        self._fill_curve(field_curve, "grass")

        # Petites fabriques de "fonctions de dessin" (pour differer le rendu).
        def f_grass(gx, gb, gh, col, sc, fcol, fr):
            def fn():
                self._grass_tuft(gx, gb, gh, col, scale=sc)
                if fcol:
                    self._flower(gx, gb + gh, fr * 2.4, fcol)
            return fn

        def f_insect(ix, iy, sz, is_b, col):
            def fn():
                if is_b:
                    self._butterfly(ix, iy, sz, col)
                else:
                    self._bee(ix, iy, sz)
            return fn

        # On collecte chaque element avec sa PROFONDEUR (= y de sa base), puis
        # on dessine du plus LOIN (base haute) au plus PROCHE (base basse) :
        # les elements proches recouvrent ceux du fond, de facon realiste.
        items = []   # (y_base, fonction)

        for _ in range(rng.randint(9, 13)):            # pierres (en tas) [Pierre]
            sx, sy, sc, t = place(1.0, fx=stone_pick(), floor=_HARVEST_FLOOR)
            r = rng.uniform(0.018, 0.045) * h * sc
            if not self._take_or_skip("Pierre"):
                items.append((sy, lambda sx=sx, sy=sy, r=r:
                              self._stone(sx, sy, r)))
        for _ in range(rng.randint(6, 9)):             # branches [Small_Stick]
            bx, by, sc, t = place(1.0, floor=_HARVEST_FLOOR)
            ln = rng.uniform(0.06, 0.12) * w * sc
            # Un baton repose SUR l'herbe locale : on le rapproche (biais) pour
            # qu'il soit dessine par-dessus l'herbe de sa profondeur. Seule
            # l'herbe nettement plus proche (plus bas) passe devant.
            if not self._take_or_skip("Small_Stick"):
                items.append((by - 0.12 * h, lambda bx=bx, by=by, ln=ln:
                              self._branch(bx, by, ln)))
        for _ in range(rng.randint(4, 6)):             # buissons (taille humaine)
            bx, by, sc, t = place(0.85)
            g = rng.uniform(0.0, 0.10)
            r = rng.uniform(0.11, 0.20) * h * sc
            col = (0.12 + g, 0.30 + g, 0.15, 1)
            items.append((by, lambda bx=bx, by=by, r=r, col=col:
                          self._bush(bx, by, r, col)))
        for _ in range(105):                           # gazon (en touffes) [Herbe]
            fx = grass_pick() if rng.random() < 0.72 else None  # amas + un peu partout
            gx, gb, sc, t = place(fx=fx, floor=_HARVEST_FLOOR)
            gh = rng.uniform(0.05, 0.16) * h * sc
            fcol = rng.choice(flowers) if rng.random() < 0.10 else None
            fr = max(1.5, w * 0.004 * sc)
            if not self._take_or_skip("Herbe"):
                items.append((gb, f_grass(gx, gb, gh, green_at(t), sc, fcol, fr)))
        n = 125                                        # herbe d'horizon [Herbe]
        for i in range(n):
            fx = i / (n - 1)
            gx = x0 + fx * w + rng.uniform(-0.006, 0.006) * w
            gb = horizon_curve(fx) - rng.uniform(0.0, 0.03) * h  # sur la crete
            gh = rng.uniform(0.05, 0.11) * h
            if not self._take_or_skip("Herbe"):
                items.append((gb, f_grass(gx, gb, gh,
                                          green_at(rng.uniform(0.85, 1.0)),
                                          0.5, None, 0)))
        for _ in range(rng.randint(10, 14)):           # plantes feuillues (bosquets)
            px, py, sc, t = place(fx=plant_pick())
            s = rng.uniform(0.05, 0.09) * h * sc
            items.append((py, lambda px=px, py=py, s=s: self._plant(px, py, s)))

        # --- Plantes de champ OPTIONNELLES (tirage generatif) ---
        if rng.random() < 0.75:                        # foin (en parcelles)
            for _ in range(rng.randint(6, 12)):
                fx, fb, sc, t = place(0.95, fx=hay_pick())
                ht = rng.uniform(0.10, 0.20) * h * sc
                items.append((fb, lambda fx=fx, fb=fb, ht=ht, sc=sc:
                              self._hay(fx, fb, ht, sc)))
        if rng.random() < 0.65:                        # epis / graminees (parcelles)
            for _ in range(rng.randint(8, 16)):
                ex, eb, sc, t = place(0.95, fx=wheat_pick())
                ht = rng.uniform(0.10, 0.18) * h * sc
                items.append((eb, lambda ex=ex, eb=eb, ht=ht, sc=sc:
                              self._wheat(ex, eb, ht, sc)))
        if rng.random() < 0.6:                         # champignons [Brown]
            for _ in range(rng.randint(5, 9)):
                mx, my, sc, t = place(1.0, fx=mush_pick(), floor=_HARVEST_FLOOR)
                s = rng.uniform(0.03, 0.05) * h * sc
                cap = (0.72, 0.50, 0.30, 1)
                if not self._take_or_skip("Brown_Mushroom"):
                    items.append((my, lambda mx=mx, my=my, s=s, cap=cap:
                                  self._mushroom(mx, my, s, cap)))
        if rng.random() < 0.5:                         # baies (buissons) [Baie]
            for _ in range(rng.randint(3, 6)):
                bx, by, sc, t = place(1.0, fx=berry_pick(), floor=_HARVEST_FLOOR)
                r = rng.uniform(0.03, 0.045) * h * sc
                if not self._take_or_skip("Baie"):
                    items.append((by, lambda bx=bx, by=by, r=r:
                                  self._berries(bx, by, r)))

        # (Les insectes sont desormais une couche ANIMEE separee : InsectLayer.)

        # Rendu trie : plus loin (base haute) d'abord, plus proche par-dessus.
        items.sort(key=lambda it: it[0], reverse=True)
        for _, fn in items:
            fn()

    def _montagne(self, rng):
        w, h, x0, y0 = self.width, self.height, self.x, self.y

        def surf(fx):                      # hauteur de la pente a la position fx
            return y0 + (0.60 + 0.36 * fx) * h

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
            if not self._take_or_skip("Pierre"):
                Color(0.45 + s, 0.44 + s, 0.49 + s, 1)
                Ellipse(pos=(sx - rr, sy), size=(rr * 2.2, rr * 1.5))
        # Plaques de neige en haut de la pente.
        Color(0.92, 0.95, 1.0, 1)
        for _ in range(8):
            fx = rng.uniform(0.4, 1.0)
            sx = x0 + fx * w
            sy = surf(fx) - rng.uniform(0.02, 0.10) * h
            rr = rng.uniform(0.02, 0.05) * h
            Ellipse(pos=(sx - rr, sy), size=(rr * 2.4, rr * 1.2))
        # Touffes rares sur la pente basse.
        for _ in range(8):
            sx = x0 + rng.uniform(0, 1) * w
            self._grass_tuft(sx, y0 + rng.uniform(0.03, 0.18) * h,
                             rng.uniform(0.03, 0.06) * h, (0.22, 0.34, 0.16, 1))
        # Gros rochers (a partir des jointures, vers le haut). [recoltable: Pierre]
        for _ in range(5):
            rx = x0 + rng.uniform(0, 1) * w
            rr = rng.uniform(0.05, 0.09) * h
            ry = y0 + rng.uniform(_HARVEST_FLOOR, 0.34) * h
            if not self._take_or_skip("Pierre"):
                Color(0.38, 0.37, 0.43, 1)
                Ellipse(pos=(rx - rr, ry), size=(rr * 2.4, rr * 1.8))

    def _lac(self, rng):
        w, h, x0, y0 = self.width, self.height, self.x, self.y
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
        for _ in range(12):
            rx = x0 + rng.uniform(0, 1) * w
            ry = y0 + rng.uniform(_HARVEST_FLOOR, 0.28) * h
            rr = rng.uniform(0.012, 0.03) * h
            if not self._take_or_skip("Pierre"):
                Color(0.42, 0.40, 0.32, 1)
                Ellipse(pos=(rx - rr, ry), size=(rr * 2.4, rr * 1.4))
        # Roseaux (remontes a partir des jointures). [recoltable: Roseau]
        for _ in range(34):
            gx = x0 + rng.uniform(0, 1) * w
            gb = y0 + rng.uniform(_HARVEST_FLOOR, 0.30) * h
            gh = rng.uniform(0.08, 0.22) * h
            if not self._take_or_skip("Roseau"):
                self._grass_tuft(gx, gb, gh, (0.18, 0.38, 0.20, 1))
