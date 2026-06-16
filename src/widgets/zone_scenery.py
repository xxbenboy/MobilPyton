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
import random

from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse, Rectangle, Triangle, Line, Quad

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
        bw = max(1.5, self.width * 0.004 * scale)
        Color(*color)
        for off, sc in ((-1.0, 0.7), (0.0, 1.0), (1.0, 0.8)):
            bx = cx + off * bw
            Triangle(points=[bx - bw, base, bx + bw, base,
                             bx + bw * 0.4, base + height * sc])

    def _bush(self, cx, cy, r, color):
        Color(*color)
        Ellipse(pos=(cx - r, cy - r * 0.5), size=(r * 2, r * 1.3))
        Ellipse(pos=(cx - r * 1.4, cy - r * 0.3), size=(r * 1.2, r * 0.9))
        Ellipse(pos=(cx + r * 0.3, cy - r * 0.3), size=(r * 1.2, r * 0.9))

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
        Color(0.92, 0.88, 0.78, 1)                       # tige
        Rectangle(pos=(cx - size * 0.18, base), size=(size * 0.36, size * 0.9))
        Color(*cap)                                      # chapeau
        Ellipse(pos=(cx - size * 0.6, base + size * 0.65),
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

    def _plaine(self, rng):
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        # Champ a perte de vue : on remplit presque tout le cadre de vert,
        # plus clair vers le haut (effet de distance). Fin liseré de ciel.
        bands = [(0.00, 0.32, (0.22, 0.38, 0.16)),
                 (0.32, 0.60, (0.27, 0.43, 0.19)),
                 (0.60, 0.80, (0.34, 0.49, 0.25)),
                 (0.80, 0.95, (0.44, 0.57, 0.34))]
        for a, b, col in bands:
            Color(*col, 1)
            Rectangle(pos=(x0, y0 + a * h), size=(w, (b - a) * h))

        near = (0.20, 0.40, 0.14)
        far = (0.46, 0.58, 0.36)

        def green_at(fy):
            return tuple(near[i] + (far[i] - near[i]) * fy for i in range(3)) \
                + (1,)

        flowers = [(1, 1, 0.92, 1), (0.96, 0.85, 0.28, 1),
                   (0.92, 0.42, 0.52, 1), (0.72, 0.52, 0.92, 1)]

        # Buissons repartis sur toute la hauteur.
        for _ in range(rng.randint(8, 12)):
            fy = rng.random() * 0.85
            sc = 1.0 - 0.7 * fy
            g = rng.uniform(0.0, 0.10)
            self._bush(x0 + rng.uniform(0.0, 1.0) * w, y0 + fy * h,
                       rng.uniform(0.03, 0.06) * h * sc,
                       (0.12 + g, 0.30 + g, 0.15, 1))

        # Hautes herbes PARTOUT (haut compris), plus petites en hauteur.
        for _ in range(190):
            fy = rng.random() * 0.90
            sc = 1.0 - 0.72 * fy
            gx = x0 + rng.uniform(0, 1) * w
            gb = y0 + fy * h
            gh = rng.uniform(0.08, 0.22) * h * sc
            self._grass_tuft(gx, gb, gh, green_at(fy), scale=sc)
            if rng.random() < 0.12:                       # fleur au sommet
                Color(*rng.choice(flowers))
                fr = max(1.5, w * 0.004 * sc)
                Ellipse(pos=(gx - fr, gb + gh - fr), size=(fr * 2, fr * 2))

        # Champignons (recoltables).
        for _ in range(rng.randint(7, 11)):
            fy = rng.random() * 0.8
            sc = 1.0 - 0.7 * fy
            self._mushroom(x0 + rng.uniform(0, 1) * w, y0 + fy * h,
                           rng.uniform(0.035, 0.06) * h * sc,
                           rng.choice([(0.80, 0.22, 0.20, 1),
                                       (0.72, 0.50, 0.30, 1)]))
        # Baies (recoltables).
        for _ in range(rng.randint(5, 8)):
            fy = rng.random() * 0.75
            sc = 1.0 - 0.7 * fy
            self._berries(x0 + rng.uniform(0, 1) * w, y0 + fy * h,
                          rng.uniform(0.03, 0.05) * h * sc)

        # Insectes (papillons, abeilles).
        for _ in range(rng.randint(6, 10)):
            ix = x0 + rng.uniform(0.05, 0.95) * w
            iy = y0 + rng.uniform(0.15, 0.88) * h
            sz = rng.uniform(0.014, 0.028) * h
            if rng.random() < 0.6:
                self._butterfly(ix, iy, sz,
                                rng.choice([(0.95, 0.6, 0.2, 1),
                                            (0.6, 0.42, 0.92, 1),
                                            (0.92, 0.92, 0.96, 1)]))
            else:
                self._bee(ix, iy, sz)

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
