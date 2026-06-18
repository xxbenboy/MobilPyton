"""
Insectes animes (papillons + abeilles) qui volent doucement dans la scene.

Couche legere redessinee a chaque frame (quelques insectes seulement). Tous
suivent LE MEME modele -> animation coherente :
- derive sinusoidale lente (vol nonchalant),
- battement d'ailes (papillon : ailes qui s'ouvrent/ferment ; abeille :
  bourdonnement des ailes).

A placer DEVANT le decor, mais derriere les mains / le voile de nuit / le HUD.
"""
import math
import random

from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse

_COLORS = [(0.85, 0.80, 0.40, 1), (0.70, 0.50, 0.30, 1),
           (0.90, 0.90, 0.95, 1), (0.60, 0.42, 0.92, 1),
           (0.95, 0.60, 0.20, 1)]


class InsectLayer(Widget):
    def __init__(self, count=5, **kwargs):
        super().__init__(**kwargs)
        self._t = 0.0
        self._count = count
        self._insects = []
        self._rng = random.Random()
        self._spawn()
        self._event = Clock.schedule_interval(self._tick, 1 / 60.0)

    def _spawn(self):
        rng = self._rng
        self._insects = []
        for _ in range(self._count):
            ax = rng.uniform(0.06, 0.16)
            ay = rng.uniform(0.04, 0.10)
            self._insects.append({
                "butterfly": rng.random() < 0.55,
                "fx": rng.uniform(0.05 + ax, 0.95 - ax),   # position de base
                "fy": rng.uniform(0.20 + ay, 0.72 - ay),
                "ax": ax, "ay": ay,                        # amplitude de derive
                "sx": rng.uniform(0.18, 0.45),             # vitesse de derive
                "sy": rng.uniform(0.30, 0.70),
                "phase": rng.uniform(0.0, 6.28),
                "flap": rng.uniform(7.0, 11.0),            # frequence des ailes
                "size": rng.uniform(0.013, 0.022),
                "col": rng.choice(_COLORS),
            })

    def _tick(self, dt):
        self._t += min(dt, 0.1)
        self._redraw()

    def _redraw(self):
        self.canvas.clear()
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        if w <= 0 or h <= 0:
            return
        t = self._t
        with self.canvas:
            for ins in self._insects:
                cx = x0 + (ins["fx"] + ins["ax"]
                           * math.sin(t * ins["sx"] + ins["phase"])) * w
                cy = y0 + (ins["fy"] + ins["ay"]
                           * math.sin(t * ins["sy"] + ins["phase"] * 1.7)) * h
                size = ins["size"] * h
                flap = 0.5 + 0.5 * abs(math.sin(t * ins["flap"] + ins["phase"]))
                if ins["butterfly"]:
                    self._butterfly(cx, cy, size, ins["col"], flap)
                else:
                    self._bee(cx, cy, size, flap)

    @staticmethod
    def _ell(ex, ey, ww, hh):
        Ellipse(pos=(ex - ww / 2, ey - hh / 2), size=(ww, hh))

    def _butterfly(self, cx, cy, size, color, flap):
        r, g, b, a = color
        ws = 0.30 + 0.70 * flap          # ouverture des ailes (battement)
        for sgn in (-1, 1):
            ux = cx + sgn * size * 0.52 * ws
            lx = cx + sgn * size * 0.44 * ws
            Color(r * 0.5, g * 0.5, b * 0.5, a)
            self._ell(ux, cy + size * 0.20, size * 1.04 * ws, size * 1.18)
            self._ell(lx, cy - size * 0.42, size * 0.82 * ws, size * 0.82)
            Color(r, g, b, a)
            self._ell(ux, cy + size * 0.20, size * 0.9 * ws, size * 1.02)
            self._ell(lx, cy - size * 0.42, size * 0.68 * ws, size * 0.68)
        Color(0.12, 0.10, 0.10, 1)
        self._ell(cx, cy - size * 0.05, size * 0.18, size * 1.28)    # corps
        self._ell(cx, cy + size * 0.58, size * 0.24, size * 0.32)    # tete

    def _bee(self, cx, cy, size, flap):
        Color(0.92, 0.95, 1.0, 0.30 + 0.40 * flap)     # ailes (bourdonnement)
        self._ell(cx - size * 0.16, cy + size * 0.40, size * 0.7, size * 0.46)
        self._ell(cx + size * 0.16, cy + size * 0.40, size * 0.7, size * 0.46)
        Color(0.96, 0.74, 0.12, 1)                     # corps dore
        self._ell(cx, cy, size * 1.32, size * 0.84)
        Color(0.12, 0.10, 0.08, 1)                     # rayures
        for dx, hsc in ((-0.30, 0.7), (0.02, 0.86), (0.34, 0.66)):
            self._ell(cx + dx * size, cy, size * 0.16, size * 0.84 * hsc)
        Color(0.16, 0.13, 0.10, 1)                     # tete
        self._ell(cx - size * 0.64, cy, size * 0.36, size * 0.52)

    def stop(self):
        if self._event is not None:
            self._event.cancel()
            self._event = None
