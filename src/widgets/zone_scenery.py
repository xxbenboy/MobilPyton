"""
Decor de premier plan selon le TYPE de zone.

Dessine au canvas (aucune image) une scene differente en bas de l'ecran selon
la zone ou se trouve le joueur :
- Foret    : collines + sapins,
- Champ    : collines douces + brins d'herbe,
- Montagne : pics rocheux avec neige,
- Lac      : etendue d'eau + ondulations.

`set_scene(zone_type, seed)` change la scene (le seed varie selon la case, pour
que chaque endroit ait un petit air different). Redessine seulement quand la
zone change (pas a chaque frame).
"""
import random

from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse, Rectangle, Triangle, Line

# Graine de base par type (pour un rendu deterministe, sans hash() aleatoire).
_ZONE_SEED = {"Foret": 1, "Champ": 2, "Montagne": 3, "Lac": 4}


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
            "Champ": self._champ,
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

    # -- scenes --------------------------------------------------------- #
    def _foret(self, rng):
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        Color(0.12, 0.22, 0.15, 0.9)
        Ellipse(pos=(x0 - 0.25 * w, y0 - 0.10 * h), size=(1.5 * w, 0.26 * h))
        for _ in range(8):
            fx = rng.uniform(0.04, 0.96); sh = rng.uniform(0.05, 0.08)
            self._pine(x0 + fx * w, y0 + 0.07 * h, sh * 0.55 * h, sh * h * 1.5,
                       (0.10, 0.19, 0.13, 0.9))
        Color(0.05, 0.13, 0.09, 1)
        Ellipse(pos=(x0 - 0.3 * w, y0 - 0.14 * h), size=(1.6 * w, 0.24 * h))
        Rectangle(pos=(x0, y0), size=(w, 0.06 * h))
        for _ in range(7):
            fx = rng.uniform(0.02, 0.98); sh = rng.uniform(0.08, 0.13)
            self._pine(x0 + fx * w, y0 + 0.04 * h, sh * 0.5 * h, sh * h * 1.9,
                       (0.04, 0.11, 0.07, 1))

    def _champ(self, rng):
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        Color(0.30, 0.40, 0.18, 1)
        Ellipse(pos=(x0 - 0.30 * w, y0 - 0.16 * h), size=(1.6 * w, 0.30 * h))
        Color(0.42, 0.52, 0.22, 1)
        Ellipse(pos=(x0 - 0.20 * w, y0 - 0.18 * h), size=(1.4 * w, 0.24 * h))
        Color(0.36, 0.46, 0.20, 1)
        Rectangle(pos=(x0, y0), size=(w, 0.09 * h))
        # Brins d'herbe.
        for _ in range(48):
            gx = x0 + rng.uniform(0, 1) * w
            gb = y0 + rng.uniform(0.0, 0.10) * h
            gh = rng.uniform(0.02, 0.05) * h
            gw = max(2.0, w * 0.004)
            Color(0.22, 0.36, 0.14, 1)
            Triangle(points=[gx - gw, gb, gx + gw, gb, gx, gb + gh])

    def _montagne(self, rng):
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        # Crete lointaine.
        Color(0.32, 0.32, 0.37, 1)
        for _ in range(4):
            cx = x0 + rng.uniform(0, 1) * w
            pw = rng.uniform(0.25, 0.4) * w
            ph = rng.uniform(0.22, 0.34) * h
            Triangle(points=[cx - pw / 2, y0 + 0.05 * h, cx + pw / 2,
                             y0 + 0.05 * h, cx, y0 + 0.05 * h + ph])
        # Pics proches + neige.
        for _ in range(3):
            cx = x0 + rng.uniform(0.1, 0.9) * w
            pw = rng.uniform(0.30, 0.5) * w
            ph = rng.uniform(0.34, 0.5) * h
            base = y0
            apex = base + ph
            Color(0.42, 0.41, 0.45, 1)
            Triangle(points=[cx - pw / 2, base, cx + pw / 2, base, cx, apex])
            # Calotte de neige.
            Color(0.93, 0.95, 1.0, 1)
            cw = pw * 0.22
            cap_base = apex - ph * 0.18
            Triangle(points=[cx - cw / 2, cap_base, cx + cw / 2, cap_base,
                             cx, apex])
        Color(0.30, 0.29, 0.31, 1)
        Rectangle(pos=(x0, y0), size=(w, 0.05 * h))

    def _lac(self, rng):
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        # Berge lointaine.
        Color(0.10, 0.20, 0.13, 1)
        Ellipse(pos=(x0 - 0.2 * w, y0 + 0.22 * h), size=(1.4 * w, 0.10 * h))
        # Etendue d'eau.
        Color(0.16, 0.40, 0.60, 1)
        Rectangle(pos=(x0, y0 + 0.03 * h), size=(w, 0.26 * h))
        # Ondulations.
        for _ in range(6):
            ly = y0 + rng.uniform(0.05, 0.26) * h
            lx = x0 + rng.uniform(0.0, 0.5) * w
            Color(0.45, 0.65, 0.80, 0.45)
            Line(points=[lx, ly, lx + rng.uniform(0.2, 0.4) * w, ly],
                 width=1.3)
        # Rive proche.
        Color(0.30, 0.34, 0.22, 1)
        Rectangle(pos=(x0, y0), size=(w, 0.05 * h))
