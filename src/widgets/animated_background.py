"""
Fond anime pilote par l'HEURE (cycle jour/nuit).

La couleur du ciel correspond en permanence a l'heure de la journee :
- nuit sombre,
- aube vers 5h (lueur chaude),
- 6h : plein jour ensoleille (le lever du soleil est termine),
- midi : ciel clair,
- ~19h : coucher (orange),
- ~20h : crepuscule, puis nuit.

Couches dessinees au canvas (aucune image) :
1. un degrade vertical dont la couleur suit l'heure ;
2. des etoiles, visibles seulement quand il fait sombre.

Deux usages :
- MENU : le temps avance tout seul (time_scale) -> cycle visible.
- JEU  : on appelle `set_seconds(...)` pour coller a l'horloge de la partie.
"""
import math
import random

from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, Ellipse
from kivy.graphics.texture import Texture
from kivy.metrics import dp

SECONDS_PER_DAY = 24 * 3600

# 24h en 4 minutes (240 s) => 360 secondes de jeu par seconde reelle.
MENU_TIME_SCALE = SECONDS_PER_DAY / 240.0

# Couleur du ciel (bas du degrade) selon l'heure. On interpole entre ces
# points. 0h et 24h sont identiques pour une boucle sans rupture.
_SKY_KEYS = [
    (0.0,  (0.05, 0.07, 0.12)),   # nuit
    (4.0,  (0.06, 0.08, 0.13)),   # nuit profonde -> bientot l'aube
    (5.0,  (0.34, 0.23, 0.25)),   # aube (lever du soleil)
    (6.0,  (0.42, 0.56, 0.72)),   # 6h : plein jour ensoleille
    (12.0, (0.52, 0.70, 0.92)),   # midi
    (17.0, (0.46, 0.62, 0.82)),   # apres-midi
    (19.0, (0.58, 0.36, 0.28)),   # coucher du soleil
    (20.0, (0.22, 0.18, 0.26)),   # crepuscule
    (22.0, (0.07, 0.09, 0.14)),   # nuit
    (24.0, (0.05, 0.07, 0.12)),   # = 0h
]


def sky_color(seconds):
    """Couleur du ciel pour un instant donne (en secondes de la journee)."""
    h = (seconds % SECONDS_PER_DAY) / 3600.0
    for i in range(len(_SKY_KEYS) - 1):
        h0, c0 = _SKY_KEYS[i]
        h1, c1 = _SKY_KEYS[i + 1]
        if h0 <= h <= h1:
            t = 0.0 if h1 == h0 else (h - h0) / (h1 - h0)
            return [c0[j] + (c1[j] - c0[j]) * t for j in range(3)]
    return list(_SKY_KEYS[-1][1])


class AnimatedBackground(Widget):
    def __init__(self, start_seconds=6 * 3600, time_scale=0.0, stars=28,
                 **kwargs):
        super().__init__(**kwargs)
        # Instant courant (en secondes de la journee) et vitesse d'ecoulement
        # (secondes de jeu par seconde reelle ; 0 = pilote de l'exterieur).
        self._seconds = float(start_seconds) % SECONDS_PER_DAY
        self.time_scale = float(time_scale)
        self._current = sky_color(self._seconds)
        self._t = 0.0
        self._frame = 0

        self._grad_tex = Texture.create(size=(1, 64), colorfmt="rgba")
        self._grad_tex.wrap = "clamp_to_edge"
        self._grad_tex.mag_filter = "linear"
        self._grad_tex.min_filter = "linear"

        with self.canvas.before:
            Color(1, 1, 1, 1)
            self._rect = Rectangle(texture=self._grad_tex,
                                   pos=self.pos, size=self.size)
            self._stars = []
            rng = random.Random(20240601)
            for _ in range(stars):
                col = Color(1, 1, 1, 0.0)
                ellipse = Ellipse()
                self._stars.append({
                    "col": col, "e": ellipse,
                    "fx": rng.uniform(0.02, 0.98),
                    "fy": rng.uniform(0.32, 0.98),
                    "size": dp(rng.uniform(1.5, 3.5)),
                    "base": rng.uniform(0.25, 0.75),
                    "phase": rng.uniform(0.0, 6.28),
                    "tw": rng.uniform(0.6, 1.8),
                })

        self._build_gradient()
        self.bind(pos=self._update_layout, size=self._update_layout)
        Clock.schedule_interval(self._tick, 1 / 60.0)

    # ------------------------------------------------------------------ #
    def set_seconds(self, seconds):
        """Cale le ciel sur un instant precis (ex. l'horloge de la partie)."""
        self._seconds = float(seconds) % SECONDS_PER_DAY

    def _update_layout(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        for s in self._stars:
            sz = s["size"]
            s["e"].size = (sz, sz)
            s["e"].pos = (self.x + s["fx"] * self.width - sz / 2,
                          self.y + s["fy"] * self.height - sz / 2)

    def _build_gradient(self):
        h = 64
        bot = self._current
        top = [c * 0.4 for c in self._current]
        buf = bytearray(h * 4)
        for i in range(h):
            t = i / (h - 1)
            buf[i * 4] = int((bot[0] * (1 - t) + top[0] * t) * 255)
            buf[i * 4 + 1] = int((bot[1] * (1 - t) + top[1] * t) * 255)
            buf[i * 4 + 2] = int((bot[2] * (1 - t) + top[2] * t) * 255)
            buf[i * 4 + 3] = 255
        self._grad_tex.blit_buffer(bytes(buf), colorfmt="rgba",
                                   bufferfmt="ubyte")

    def _night_factor(self):
        """1 quand il fait nuit (etoiles visibles), 0 en plein jour."""
        c = self._current
        lum = 0.3 * c[0] + 0.6 * c[1] + 0.1 * c[2]
        return max(0.0, min(1.0, (0.20 - lum) / 0.20))

    def _tick(self, dt):
        self._t += dt
        if self.time_scale:
            self._seconds = (self._seconds + dt * self.time_scale) \
                % SECONDS_PER_DAY
        self._current = sky_color(self._seconds)

        self._frame += 1
        if self._frame % 3 == 0:
            self._build_gradient()

        night = self._night_factor()
        for s in self._stars:
            twinkle = 0.35 + 0.65 * abs(math.sin(self._t * s["tw"] + s["phase"]))
            s["col"].a = s["base"] * twinkle * night
