"""
Fond anime pilote par l'HEURE (cycle jour/nuit) avec astres et nuages.

Couches (canvas, aucune image) :
1. degrade du ciel dont la couleur suit l'heure ;
2. etoiles, visibles seulement quand il fait sombre ;
3. SOLEIL et LUNE qui montent puis descendent selon l'heure (arc dans le ciel) ;
4. NUAGES qui derivent lentement.

Usages :
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

_SKY_KEYS = [
    (0.0,  (0.05, 0.07, 0.12)),
    (4.0,  (0.06, 0.08, 0.13)),
    (5.0,  (0.34, 0.23, 0.25)),
    (6.0,  (0.42, 0.56, 0.72)),
    (12.0, (0.52, 0.70, 0.92)),
    (17.0, (0.46, 0.62, 0.82)),
    (19.0, (0.58, 0.36, 0.28)),
    (20.0, (0.22, 0.18, 0.26)),
    (22.0, (0.07, 0.09, 0.14)),
    (24.0, (0.05, 0.07, 0.12)),
]


def sky_color(seconds):
    h = (seconds % SECONDS_PER_DAY) / 3600.0
    for i in range(len(_SKY_KEYS) - 1):
        h0, c0 = _SKY_KEYS[i]
        h1, c1 = _SKY_KEYS[i + 1]
        if h0 <= h <= h1:
            t = 0.0 if h1 == h0 else (h - h0) / (h1 - h0)
            return [c0[j] + (c1[j] - c0[j]) * t for j in range(3)]
    return list(_SKY_KEYS[-1][1])


def _clamp01(v):
    return max(0.0, min(1.0, v))


class AnimatedBackground(Widget):
    def __init__(self, start_seconds=6 * 3600, time_scale=0.0, stars=28,
                 **kwargs):
        super().__init__(**kwargs)
        self._seconds = float(start_seconds) % SECONDS_PER_DAY
        self.time_scale = float(time_scale)
        self._current = sky_color(self._seconds)
        self._t = 0.0
        self._grad_accum = 0.0

        self._grad_tex = Texture.create(size=(1, 64), colorfmt="rgba")
        self._grad_tex.wrap = "clamp_to_edge"
        self._grad_tex.mag_filter = "linear"
        self._grad_tex.min_filter = "linear"

        with self.canvas.before:
            # 1. Ciel (degrade).
            Color(1, 1, 1, 1)
            self._rect = Rectangle(texture=self._grad_tex,
                                   pos=self.pos, size=self.size)

            # 2. Etoiles.
            self._stars = []
            rng = random.Random(20240601)
            for _ in range(stars):
                col = Color(1, 1, 1, 0.0)
                self._stars.append({
                    "col": col, "e": Ellipse(),
                    "fx": rng.uniform(0.02, 0.98),
                    "fy": rng.uniform(0.40, 0.98),
                    "size": dp(rng.uniform(1.5, 3.5)),
                    "base": rng.uniform(0.25, 0.75),
                    "phase": rng.uniform(0.0, 6.28),
                    "tw": rng.uniform(0.6, 1.8),
                })

            # 3. Soleil (avec halo) et Lune.
            self._sun_glow_c = Color(1.0, 0.92, 0.55, 0.0)
            self._sun_glow = Ellipse()
            self._sun_c = Color(1.0, 0.95, 0.6, 0.0)
            self._sun = Ellipse()
            self._moon_c = Color(0.92, 0.94, 1.0, 0.0)
            self._moon = Ellipse()

            # 4. Nuages : chaque cumulus a sa PROPRE forme aleatoire (aucun
            #    identique). Base plate et grisee (volume) + bouffees blanches.
            #    4 couches par nuage (de l'arriere vers l'avant) :
            #    halo doux -> base ombree (dessous plat) -> bouffees blanches
            #    -> reflets clairs (cote eclaire). Les Color/Ellipse sont crees
            #    dans cet ORDRE pour respecter la profondeur.
            self._clouds = []
            crng = random.Random(777)
            for _ in range(6):
                nha = crng.randint(2, 3)
                halo_shape = [(crng.uniform(-1.2, 1.2),
                               crng.uniform(0.05, 0.45),
                               crng.uniform(1.8, 2.6),
                               crng.uniform(1.0, 1.4)) for _ in range(nha)]
                nb = crng.randint(4, 6)
                base_shape = [((k / (nb - 1) - 0.5) * 2.7,
                               crng.uniform(-0.04, 0.04),
                               crng.uniform(1.05, 1.55),
                               crng.uniform(0.45, 0.6)) for k in range(nb)]
                nt = crng.randint(6, 8)
                top_shape = [(crng.uniform(-1.1, 1.1),
                              crng.uniform(0.16, 0.66),
                              crng.uniform(0.8, 1.5),
                              crng.uniform(0.7, 1.1)) for _ in range(nt)]
                nl = crng.randint(3, 4)
                hi_shape = [(crng.uniform(-0.85, 0.55),
                             crng.uniform(0.5, 0.92),
                             crng.uniform(0.5, 0.95),
                             crng.uniform(0.5, 0.85)) for _ in range(nl)]
                self._clouds.append({
                    "c_halo": Color(0.95, 0.97, 1.0, 0.0),
                    "halo_ell": [Ellipse() for _ in halo_shape],
                    "halo_shape": halo_shape,
                    "c_base": Color(0.74, 0.78, 0.86, 0.0),
                    "base_ell": [Ellipse() for _ in base_shape],
                    "base_shape": base_shape,
                    "c_top": Color(0.97, 0.98, 1.0, 0.0),
                    "top_ell": [Ellipse() for _ in top_shape],
                    "top_shape": top_shape,
                    "c_hi": Color(1, 1, 1, 0.0),
                    "hi_ell": [Ellipse() for _ in hi_shape],
                    "hi_shape": hi_shape,
                    "fy": crng.uniform(0.55, 0.90),
                    "scale": crng.uniform(0.10, 0.20),
                    "speed": crng.uniform(0.005, 0.016),
                    "base": crng.uniform(0.0, 1.0),
                })

        self._build_gradient()
        self.bind(pos=self._update_layout, size=self._update_layout)
        Clock.schedule_interval(self._tick, 1 / 60.0)

    # ------------------------------------------------------------------ #
    def set_seconds(self, seconds):
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

    def _lum(self):
        c = self._current
        return 0.3 * c[0] + 0.6 * c[1] + 0.1 * c[2]

    def _place_disc(self, ellipse, cx, cy, r):
        ellipse.size = (r * 2, r * 2)
        ellipse.pos = (cx - r, cy - r)

    def _tick(self, dt):
        # Independant du framerate : tout se base sur dt (temps reel), avec un
        # plafond pour eviter un bond apres un ralentissement / reveil.
        dt = min(dt, 0.25)
        self._t += dt
        if self.time_scale:
            self._seconds = (self._seconds + dt * self.time_scale) \
                % SECONDS_PER_DAY
        self._current = sky_color(self._seconds)

        # Redessin du degrade a cadence fixe (~20/s), quel que soit le fps.
        self._grad_accum += dt
        if self._grad_accum >= 0.05:
            self._grad_accum = 0.0
            self._build_gradient()

        w, h, x0, y0 = self.width, self.height, self.x, self.y
        if w <= 0 or h <= 0:
            return
        hour = (self._seconds % SECONDS_PER_DAY) / 3600.0
        lum = self._lum()
        sun_a = _clamp01((lum - 0.10) / 0.25)     # 1 en plein jour
        night = _clamp01((0.20 - lum) / 0.18)     # 1 la nuit

        # Etoiles.
        for s in self._stars:
            twinkle = 0.35 + 0.65 * abs(math.sin(self._t * s["tw"] + s["phase"]))
            s["col"].a = s["base"] * twinkle * night

        radius = min(w, h) * 0.055

        # Soleil : arc de 5h a 19h (gauche -> droite).
        sp = _clamp01((hour - 5.0) / 14.0)
        sx = x0 + w * (0.12 + 0.76 * sp)
        sy = y0 + h * (0.45 + 0.42 * math.sin(math.pi * sp))
        self._sun_c.a = sun_a
        self._place_disc(self._sun, sx, sy, radius)
        self._sun_glow_c.a = sun_a * 0.35
        self._place_disc(self._sun_glow, sx, sy, radius * 2.1)

        # Lune : arc de 19h a 5h (la nuit).
        nh = (hour - 19.0) % 24.0
        mp = _clamp01(nh / 10.0)
        mx = x0 + w * (0.12 + 0.76 * mp)
        my = y0 + h * (0.45 + 0.42 * math.sin(math.pi * mp))
        self._moon_c.a = night
        self._place_disc(self._moon, mx, my, radius * 0.85)

        # Nuages (cumulus) : halo doux, dessous ombre, bouffees blanches,
        # reflets clairs du cote eclaire.
        cloud_a = 0.55 * (0.30 + 0.70 * sun_a)

        def place(ellipses, shapes, cx, cy, s):
            for ell, (dx, dy, sw, sh) in zip(ellipses, shapes):
                ell.size = (sw * s, sh * s)
                ell.pos = (cx + dx * s - sw * s / 2, cy + dy * s)

        for cl in self._clouds:
            fx = (cl["base"] + self._t * cl["speed"]) % 1.4 - 0.2
            cx = x0 + fx * w
            cy = y0 + cl["fy"] * h
            s = w * cl["scale"]
            cl["c_halo"].a = cloud_a * 0.22
            place(cl["halo_ell"], cl["halo_shape"], cx, cy, s)
            cl["c_base"].a = cloud_a * 0.85
            place(cl["base_ell"], cl["base_shape"], cx, cy, s)
            cl["c_top"].a = cloud_a
            place(cl["top_ell"], cl["top_shape"], cx, cy, s)
            cl["c_hi"].a = cloud_a * 0.85
            place(cl["hi_ell"], cl["hi_shape"], cx, cy, s)
