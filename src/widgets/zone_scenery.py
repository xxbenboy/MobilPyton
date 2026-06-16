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

    def _grass_tuft(self, cx, base, height, color):
        bw = max(2.0, self.width * 0.004)
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

    def _plaine(self, rng):
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        # Collines jusqu'a un horizon haut (sky reduit en haut).
        Color(0.40, 0.55, 0.30, 1)
        Ellipse(pos=(x0 - 0.30 * w, y0 + 0.45 * h), size=(1.7 * w, 0.30 * h))
        Color(0.34, 0.50, 0.26, 1)
        Ellipse(pos=(x0 - 0.25 * w, y0 + 0.18 * h), size=(1.6 * w, 0.42 * h))
        Color(0.28, 0.44, 0.20, 1)
        Ellipse(pos=(x0 - 0.30 * w, y0 - 0.05 * h), size=(1.7 * w, 0.45 * h))
        Color(0.24, 0.40, 0.18, 1)
        Rectangle(pos=(x0, y0), size=(w, 0.25 * h))
        # Arbres sur l'horizon.
        for _ in range(rng.randint(2, 4)):
            tx = x0 + rng.uniform(0.1, 0.9) * w
            self._tree(tx, y0 + 0.50 * h, rng.uniform(0.10, 0.16) * h,
                       (0.18, 0.34, 0.16, 1), (0.26, 0.18, 0.10, 1))
        # Buissons.
        for _ in range(rng.randint(5, 7)):
            bx = x0 + rng.uniform(0.02, 0.98) * w
            by = y0 + rng.uniform(0.06, 0.22) * h
            g = rng.uniform(0.0, 0.10)
            self._bush(bx, by, rng.uniform(0.03, 0.06) * h,
                       (0.12 + g, 0.30 + g, 0.15, 1))
        # Hautes herbes denses (jusqu'a ~0.7h), + fleurs.
        greens = [(0.20, 0.40, 0.14, 1), (0.26, 0.46, 0.16, 1),
                  (0.32, 0.52, 0.18, 1), (0.30, 0.48, 0.22, 1)]
        flowers = [(1, 1, 0.92, 1), (0.96, 0.85, 0.28, 1),
                   (0.92, 0.42, 0.52, 1), (0.72, 0.52, 0.92, 1)]
        for _ in range(130):
            gx = x0 + rng.uniform(0, 1) * w
            gb = y0 + rng.uniform(0.0, 0.45) * h
            gh = rng.uniform(0.08, 0.24) * h
            self._grass_tuft(gx, gb, gh, rng.choice(greens))
            if rng.random() < 0.12:
                Color(*rng.choice(flowers))
                fr = max(2.0, w * 0.004)
                Ellipse(pos=(gx - fr, gb + gh - fr), size=(fr * 2, fr * 2))

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
