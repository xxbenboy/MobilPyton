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
                           Mesh)

_ZONE_SEED = {"Foret": 1, "Plaine": 2, "Montagne": 3, "Lac": 4}


class ZoneScenery(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._zone = "Foret"
        self._seed = 0
        self.bind(pos=self._redraw, size=self._redraw)

    def set_scene(self, zone_type, seed=0):
        self._zone = zone_type
        self._seed = seed
        self._redraw()

    # ------------------------------------------------------------------ #
    def _redraw(self, *_):
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return
        draw = {
            "Foret": self._foret,
            "Plaine": self._plaine,
            "Montagne": self._montagne,
            "Lac": self._lac,
        }.get(self._zone, self._foret)
        rng = random.Random(_ZONE_SEED.get(self._zone, 0) * 100000 + self._seed)
        with self.canvas:
            draw(rng)

    # -- helpers -------------------------------------------------------- #
    def _pine(self, cx, base, tw, th, color):
        Color(*color)
        Triangle(points=[cx - tw / 2, base, cx + tw / 2, base,
                         cx, base + th * 0.72])
        Triangle(points=[cx - tw * 0.36, base + th * 0.32,
                         cx + tw * 0.36, base + th * 0.32, cx, base + th])

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
        Color(cr * 0.7, cg * 0.7, cb * 0.7, 1)            # masse sombre (bas)
        Ellipse(pos=(cx - r * 1.4, cy - r * 0.3), size=(r * 1.3, r * 1.0))
        Ellipse(pos=(cx + r * 0.2, cy - r * 0.3), size=(r * 1.3, r * 1.0))
        Ellipse(pos=(cx - r, cy - r * 0.4), size=(r * 2, r * 1.2))
        Color(cr, cg, cb, 1)                              # feuillage clair (haut)
        Ellipse(pos=(cx - r * 0.9, cy + r * 0.1), size=(r * 1.8, r * 1.0))
        Ellipse(pos=(cx - r * 1.2, cy), size=(r * 1.1, r * 0.8))
        Ellipse(pos=(cx + r * 0.2, cy), size=(r * 1.1, r * 0.8))

    def _tree(self, cx, base, th, leaf, trunk):
        tw = max(2.0, self.width * 0.006)
        Color(*trunk)
        Rectangle(pos=(cx - tw / 2, base), size=(tw, th * 0.5))
        Color(*leaf)
        r = th * 0.35
        Ellipse(pos=(cx - r, base + th * 0.32), size=(r * 2, r * 2))

    # -- scenes (plein cadre) ------------------------------------------- #
    def _foret(self, rng):
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        # Sol.
        Color(0.06, 0.14, 0.09, 1)
        Rectangle(pos=(x0, y0), size=(w, 0.15 * h))
        # Arbres du fond (clairs, moyens).
        for _ in range(18):
            fx = x0 + rng.uniform(-0.03, 1.03) * w
            self._pine(fx, y0 + rng.uniform(0.18, 0.34) * h,
                       rng.uniform(0.05, 0.09) * w, rng.uniform(0.34, 0.50) * h,
                       (0.10, 0.21, 0.13, 1))
        # Arbres du milieu.
        for _ in range(13):
            fx = x0 + rng.uniform(-0.03, 1.03) * w
            self._pine(fx, y0 + rng.uniform(0.06, 0.20) * h,
                       rng.uniform(0.08, 0.12) * w, rng.uniform(0.50, 0.72) * h,
                       (0.07, 0.17, 0.10, 1))
        # Grands arbres de premier plan.
        for _ in range(7):
            fx = x0 + rng.uniform(-0.03, 1.03) * w
            self._pine(fx, y0 + rng.uniform(-0.02, 0.08) * h,
                       rng.uniform(0.11, 0.16) * w, rng.uniform(0.72, 0.98) * h,
                       (0.04, 0.10, 0.07, 1))
        # Canopee en haut (remplit le ciel).
        Color(0.05, 0.12, 0.08, 1)
        for i in range(10):
            fx = x0 + (i / 9.0) * w + rng.uniform(-0.04, 0.04) * w
            r = rng.uniform(0.10, 0.16) * w
            Ellipse(pos=(fx - r, y0 + 0.82 * h), size=(r * 2.2, r * 1.5))
        # Sous-bois.
        for _ in range(6):
            bx = x0 + rng.uniform(0, 1) * w
            self._bush(bx, y0 + rng.uniform(0.04, 0.13) * h,
                       rng.uniform(0.03, 0.06) * h, (0.06, 0.16, 0.09, 1))

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

    def _butterfly(self, cx, cy, size, color):
        Color(*color)
        Ellipse(pos=(cx - size, cy - size * 0.45), size=(size, size * 0.9))
        Ellipse(pos=(cx, cy - size * 0.45), size=(size, size * 0.9))
        Color(0.1, 0.1, 0.1, 1)
        Ellipse(pos=(cx - size * 0.12, cy - size * 0.5),
                size=(size * 0.24, size))

    def _bee(self, cx, cy, size):
        Color(1, 1, 1, 0.6)                              # ailes
        Ellipse(pos=(cx - size * 0.2, cy + size * 0.1),
                size=(size * 0.5, size * 0.4))
        Color(0.95, 0.78, 0.15, 1)                       # corps
        Ellipse(pos=(cx - size * 0.6, cy - size * 0.4),
                size=(size * 1.2, size * 0.8))
        Color(0.12, 0.12, 0.12, 1)                       # rayures
        for dx in (-0.2, 0.2):
            Rectangle(pos=(cx + dx * size - size * 0.06, cy - size * 0.4),
                      size=(size * 0.12, size * 0.8))

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

    def _fill_curve(self, top_fn, color, segs=40):
        """Remplit du bas du widget jusqu'a la courbe top_fn(fx) (terrain)."""
        x0, y0, w = self.x, self.y, self.width
        Color(*color)
        verts = []
        for i in range(segs + 1):
            fx = i / segs
            x = x0 + fx * w
            verts += [x, y0, 0, 0, x, top_fn(fx), 0, 0]
        idx = list(range(len(verts) // 4))
        Mesh(vertices=verts, indices=idx, mode="triangle_strip")

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

        def place(maxt=1.0, fx=None):
            if fx is None:
                fx = rng.uniform(0, 1)
            fx = min(0.999, max(0.001, fx))
            surf = (field_curve(fx) - y0) / h         # sommet du sol a cet x
            fy = rng.random() * surf * maxt           # base toujours sur le sol
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
        self._fill_curve(horizon_curve, (0.36, 0.50, 0.26, 1))
        self._fill_curve(field_curve, (0.26, 0.42, 0.19, 1))

        # Petites fabriques de "fonctions de dessin" (pour differer le rendu).
        def f_grass(gx, gb, gh, col, sc, fcol, fr):
            def fn():
                self._grass_tuft(gx, gb, gh, col, scale=sc)
                if fcol:
                    Color(*fcol)
                    Ellipse(pos=(gx - fr, gb + gh - fr), size=(fr * 2, fr * 2))
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

        for _ in range(rng.randint(9, 13)):            # pierres (en tas)
            sx, sy, sc, t = place(0.85, fx=stone_pick())
            r = rng.uniform(0.018, 0.045) * h * sc
            items.append((sy, lambda sx=sx, sy=sy, r=r: self._stone(sx, sy, r)))
        for _ in range(rng.randint(6, 9)):             # branches
            bx, by, sc, t = place(0.82)
            ln = rng.uniform(0.06, 0.12) * w * sc
            # Un baton repose SUR l'herbe locale : on le rapproche (biais) pour
            # qu'il soit dessine par-dessus l'herbe de sa profondeur. Seule
            # l'herbe nettement plus proche (plus bas) passe devant.
            items.append((by - 0.12 * h, lambda bx=bx, by=by, ln=ln:
                          self._branch(bx, by, ln)))
        for _ in range(rng.randint(4, 6)):             # buissons (taille humaine)
            bx, by, sc, t = place(0.85)
            g = rng.uniform(0.0, 0.10)
            r = rng.uniform(0.11, 0.20) * h * sc
            col = (0.12 + g, 0.30 + g, 0.15, 1)
            items.append((by, lambda bx=bx, by=by, r=r, col=col:
                          self._bush(bx, by, r, col)))
        for _ in range(105):                           # gazon (en touffes)
            fx = grass_pick() if rng.random() < 0.72 else None  # amas + un peu partout
            gx, gb, sc, t = place(fx=fx)
            gh = rng.uniform(0.05, 0.16) * h * sc
            fcol = rng.choice(flowers) if rng.random() < 0.10 else None
            fr = max(1.5, w * 0.004 * sc)
            items.append((gb, f_grass(gx, gb, gh, green_at(t), sc, fcol, fr)))
        n = 125                                        # herbe d'horizon
        for i in range(n):
            fx = i / (n - 1)
            gx = x0 + fx * w + rng.uniform(-0.006, 0.006) * w
            gb = horizon_curve(fx) - rng.uniform(0.0, 0.03) * h  # sur la crete
            gh = rng.uniform(0.05, 0.11) * h
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
        if rng.random() < 0.6:                         # champignons (en cercles)
            for _ in range(rng.randint(5, 9)):
                mx, my, sc, t = place(0.82, fx=mush_pick())
                s = rng.uniform(0.03, 0.05) * h * sc
                cap = rng.choice([(0.80, 0.22, 0.20, 1), (0.72, 0.50, 0.30, 1)])
                items.append((my, lambda mx=mx, my=my, s=s, cap=cap:
                              self._mushroom(mx, my, s, cap)))
        if rng.random() < 0.5:                         # baies (en buissons groupes)
            for _ in range(rng.randint(3, 6)):
                bx, by, sc, t = place(0.80, fx=berry_pick())
                r = rng.uniform(0.03, 0.045) * h * sc
                items.append((by, lambda bx=bx, by=by, r=r:
                              self._berries(bx, by, r)))

        for _ in range(rng.randint(6, 9)):             # insectes
            ix = x0 + rng.uniform(0.05, 0.95) * w
            iy = y0 + rng.uniform(0.08, hor) * h
            sz = rng.uniform(0.014, 0.026) * h
            is_b = rng.random() < 0.6
            col = rng.choice([(0.95, 0.6, 0.2, 1), (0.6, 0.42, 0.92, 1),
                              (0.92, 0.92, 0.96, 1)])
            items.append((iy, f_insect(ix, iy, sz, is_b, col)))

        # Rendu trie : plus loin (base haute) d'abord, plus proche par-dessus.
        items.sort(key=lambda it: it[0], reverse=True)
        for _, fn in items:
            fn()

    def _montagne(self, rng):
        w, h, x0, y0 = self.width, self.height, self.x, self.y

        def surf(fx):                      # hauteur de la pente a la position fx
            return y0 + (0.60 + 0.36 * fx) * h

        # Pente principale (remplit le cadre, monte vers la droite).
        Color(0.42, 0.41, 0.46, 1)
        Quad(points=[x0, y0, x0 + w, y0, x0 + w, surf(1.0), x0, surf(0.0)])
        # Bas plus sombre (profondeur).
        Color(0.33, 0.32, 0.37, 1)
        Quad(points=[x0, y0, x0 + w, y0, x0 + w, y0 + 0.22 * h, x0, y0 + 0.14 * h])
        # Rochers disperses sur la pente.
        for _ in range(42):
            fx = rng.uniform(0, 1)
            sx = x0 + fx * w
            top = (surf(fx) - y0) / h
            sy = y0 + rng.uniform(0.04, max(0.06, top - 0.05)) * h
            rr = rng.uniform(0.015, 0.05) * h
            s = rng.uniform(-0.06, 0.06)
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
        # Gros rochers au premier plan.
        Color(0.38, 0.37, 0.43, 1)
        for _ in range(5):
            rx = x0 + rng.uniform(0, 1) * w
            rr = rng.uniform(0.05, 0.09) * h
            Ellipse(pos=(rx - rr, y0 - 0.02 * h), size=(rr * 2.4, rr * 1.8))

    def _lac(self, rng):
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        # Collines / berge lointaine (haut), pour reduire le ciel.
        Color(0.16, 0.30, 0.18, 1)
        Ellipse(pos=(x0 - 0.25 * w, y0 + 0.58 * h), size=(1.6 * w, 0.18 * h))
        Color(0.12, 0.24, 0.15, 1)
        Ellipse(pos=(x0 - 0.30 * w, y0 + 0.54 * h), size=(1.7 * w, 0.14 * h))
        # Grande etendue d'eau (on est au bord) : 0.10h -> 0.60h.
        Color(0.15, 0.38, 0.58, 1)
        Rectangle(pos=(x0, y0 + 0.10 * h), size=(w, 0.50 * h))
        # Reflets clairs.
        Color(0.32, 0.56, 0.74, 1)
        for _ in range(11):
            ly = y0 + rng.uniform(0.13, 0.58) * h
            lx = x0 + rng.uniform(0, 0.6) * w
            Line(points=[lx, ly, lx + rng.uniform(0.2, 0.45) * w, ly],
                 width=1.4)
        # Rive proche (premier plan) + galets.
        Color(0.32, 0.30, 0.22, 1)
        Rectangle(pos=(x0, y0), size=(w, 0.12 * h))
        Color(0.42, 0.40, 0.32, 1)
        for _ in range(12):
            rx = x0 + rng.uniform(0, 1) * w
            ry = y0 + rng.uniform(0.0, 0.10) * h
            rr = rng.uniform(0.012, 0.03) * h
            Ellipse(pos=(rx - rr, ry), size=(rr * 2.4, rr * 1.4))
        # Roseaux le long du bord (remplissent les bords).
        for _ in range(34):
            gx = x0 + rng.uniform(0, 1) * w
            gb = y0 + rng.uniform(0.06, 0.16) * h
            gh = rng.uniform(0.08, 0.22) * h
            self._grass_tuft(gx, gb, gh, (0.18, 0.38, 0.20, 1))
