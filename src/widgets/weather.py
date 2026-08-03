"""
Rendu de la METEO (voir game_state : clair / nuageux / pluie / orage, et
leurs equivalents montagnards neige / blizzard, plus le brouillard).

Deux couches, a placer a des profondeurs differentes :

- `WeatherLayer`   : voile de couleur, precipitations et brouillard. A poser
  DEVANT le decor et les mains, mais DERRIERE le voile de nuit -> la pluie
  et la neige s'assombrissent naturellement la nuit.
- `LightningLayer` : eclairs (orage / blizzard). A poser DEVANT le voile de
  nuit pour qu'ils ILLUMINENT reellement la scene.

Performance : les instructions graphiques sont creees UNE FOIS (a chaque
changement de meteo ou de taille), puis seules leurs positions sont mises a
jour a chaque frame. On evite ainsi de reconstruire le canvas 60 fois par
seconde, ce qui compte avec une centaine de flocons.
"""
import math
import random

from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, Ellipse, Line

# Voile de couleur pose sur toute la scene, par meteo : (r, v, b, opacite).
_VEIL = {
    "nuageux": (0.55, 0.57, 0.62, 0.16),      # gris doux
    "pluie": (0.35, 0.40, 0.48, 0.26),        # gris bleute
    "orage": (0.14, 0.16, 0.24, 0.42),        # tres sombre
    "neige": (0.72, 0.78, 0.88, 0.16),        # blanc froid
    "blizzard": (0.70, 0.75, 0.85, 0.36),     # blanc dense
}

# Precipitations : (type, nombre, vitesse, echelle, vent lateral)
_PRECIP = {
    "pluie": ("rain", 55, 1.0, 1.0, 0.0),
    "orage": ("rain", 90, 1.45, 1.3, 0.0),
    "neige": ("snow", 45, 1.0, 1.0, 0.0),
    "blizzard": ("snow", 95, 3.0, 1.0, 0.30),
}

_RAIN_COLOR = (0.78, 0.86, 0.98, 0.55)
_SNOW_COLOR = (1.0, 1.0, 1.0, 0.90)

# Meteos ou l'on voit des eclairs.
_STORMY = ("orage", "blizzard")


class WeatherLayer(Widget):
    """Voile, precipitations et brouillard (sous le voile de nuit)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._t = 0.0
        self._kind = "clair"
        self._fog = False
        self._built = None            # (meteo, brouillard, largeur, hauteur)
        self._veil_rect = None
        self._fog_bands = []          # [(Ellipse, fx, fy, fw, fh, vitesse)]
        self._drops = []              # [(Line, fx, phase, vitesse, long, biais)]
        self._flakes = []             # [(Ellipse, fx, phase, vit, amp, w, taille)]
        self._wind = 0.0
        self._rng = random.Random(20260803)
        self.bind(pos=self._invalidate, size=self._invalidate)
        self._event = Clock.schedule_interval(self._tick, 1 / 60.0)

    # ---- API ---------------------------------------------------------- #
    def set_weather(self, kind, fog=False):
        """Definit la meteo affichee et la presence de brouillard."""
        if kind == self._kind and bool(fog) == self._fog:
            return
        self._kind = kind
        self._fog = bool(fog)

    def stop(self):
        if self._event is not None:
            self._event.cancel()
            self._event = None

    # ---- Construction (rare) ------------------------------------------ #
    def _invalidate(self, *_):
        self._built = None

    def _build(self):
        self.canvas.clear()
        self._veil_rect = None
        self._fog_bands = []
        self._drops = []
        self._flakes = []
        rng = self._rng
        w, h = self.width, self.height
        kind = self._kind

        with self.canvas:
            # 1) Voile general de la meteo.
            veil = _VEIL.get(kind)
            if veil:
                Color(*veil)
                self._veil_rect = Rectangle(pos=self.pos, size=self.size)

            # 2) Brouillard : voile clair + larges bandes qui derivent.
            if self._fog:
                Color(0.82, 0.85, 0.88, 0.30)
                Rectangle(pos=self.pos, size=self.size)
                Color(0.90, 0.92, 0.95, 0.16)
                for _ in range(4):
                    fy = rng.uniform(0.10, 0.70)
                    fw = rng.uniform(0.7, 1.3)
                    fh = rng.uniform(0.10, 0.22)
                    speed = rng.uniform(0.010, 0.030)
                    self._fog_bands.append(
                        [Ellipse(), rng.uniform(0.0, 1.0), fy, fw, fh, speed])

            # 3) Precipitations.
            spec = _PRECIP.get(kind)
            self._wind = 0.0
            if spec:
                ptype, count, vfac, sfac, wind = spec
                self._wind = wind
                if ptype == "rain":
                    Color(*_RAIN_COLOR)
                    for _ in range(count):
                        self._drops.append([
                            Line(width=1.1),
                            rng.uniform(-0.05, 1.05),          # fx
                            rng.uniform(0.0, 1.0),             # phase
                            rng.uniform(1.1, 1.8) * vfac,      # vitesse
                            rng.uniform(0.05, 0.10) * sfac,    # longueur
                            rng.uniform(0.10, 0.22),           # biais lateral
                        ])
                else:
                    Color(*_SNOW_COLOR)
                    for _ in range(count):
                        self._flakes.append([
                            Ellipse(),
                            rng.uniform(0.0, 1.0),             # fx
                            rng.uniform(0.0, 1.0),             # phase
                            rng.uniform(0.10, 0.22) * vfac,    # vitesse
                            rng.uniform(0.010, 0.040),         # amplitude
                            rng.uniform(0.5, 1.4),             # vitesse ondul.
                            rng.uniform(0.004, 0.009),         # taille
                        ])

        self._built = (kind, self._fog, w, h)

    # ---- Animation (chaque frame) ------------------------------------- #
    def _tick(self, dt):
        w, h = self.width, self.height
        if w <= 0 or h <= 0:
            return
        if self._built != (self._kind, self._fog, w, h):
            self._build()
        self._t += min(dt, 0.1)
        t, x0, y0 = self._t, self.x, self.y

        if self._veil_rect is not None:
            self._veil_rect.pos = self.pos
            self._veil_rect.size = self.size

        # Brouillard : bandes qui derivent lentement de gauche a droite.
        for band in self._fog_bands:
            ell, fx, fy, fw, fh, speed = band
            px = (fx + t * speed) % 1.6 - 0.3
            ell.size = (fw * w, fh * h)
            ell.pos = (x0 + px * w - fw * w / 2, y0 + fy * h - fh * h / 2)

        # Pluie : traits inclines qui tombent et se repetent en boucle.
        for d in self._drops:
            line, fx, phase, speed, length, slant = d
            yy = (phase - t * speed) % 1.0
            px = x0 + fx * w
            py = y0 + yy * h
            ln = length * h
            line.points = [px, py, px - slant * ln, py + ln]

        # Neige : flocons lents, avec ondulation laterale (et vent en blizzard).
        for f in self._flakes:
            ell, fx, phase, speed, amp, wsp, size = f
            yy = (phase - t * speed) % 1.0
            drift = amp * math.sin(t * wsp + phase * 6.28)
            px = (fx + drift + t * self._wind) % 1.2 - 0.1
            d = size * min(w, h)
            ell.size = (d, d)
            ell.pos = (x0 + px * w - d / 2, y0 + yy * h - d / 2)


class LightningLayer(Widget):
    """Eclairs d'orage / blizzard : bref embrasement de tout l'ecran.

    A placer DEVANT le voile de nuit pour eclairer vraiment la scene."""

    # Enveloppe d'un eclair : (instant de fin, opacite). Deux flashs
    # rapproches, puis extinction douce -> lecture "coup de foudre".
    _STEPS = ((0.06, 0.55), (0.12, 0.10), (0.20, 0.45))
    _FADE_END = 0.45

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._t = 0.0
        self._kind = "clair"
        self._flash_start = None
        self._next_flash = 3.0
        self._rng = random.Random(777)
        with self.canvas:
            self._color = Color(0.85, 0.90, 1.0, 0.0)
            self._rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._sync, size=self._sync)
        self._event = Clock.schedule_interval(self._tick, 1 / 60.0)

    def set_weather(self, kind):
        if kind == self._kind:
            return
        self._kind = kind
        # On repart proprement : pas d'eclair en cours hors orage.
        self._flash_start = None
        self._color.a = 0.0
        self._next_flash = self._t + self._rng.uniform(2.0, 6.0)

    def stop(self):
        if self._event is not None:
            self._event.cancel()
            self._event = None

    def _sync(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def _tick(self, dt):
        self._t += min(dt, 0.1)
        if self._kind not in _STORMY:
            if self._color.a:
                self._color.a = 0.0
            return
        t = self._t
        if self._flash_start is None:
            if t >= self._next_flash:
                self._flash_start = t
            else:
                return
        e = t - self._flash_start
        alpha = 0.0
        for end, a in self._STEPS:
            if e < end:
                alpha = a
                break
        else:
            if e < self._FADE_END:
                last_end = self._STEPS[-1][0]
                k = (e - last_end) / (self._FADE_END - last_end)
                alpha = self._STEPS[-1][1] * (1.0 - k)
            else:
                # Eclair termine : on programme le suivant.
                self._flash_start = None
                self._next_flash = t + self._rng.uniform(4.0, 13.0)
        self._color.a = alpha
