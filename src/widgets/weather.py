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

# Duree du fondu d'une meteo a l'autre (secondes reelles) : on eteint d'abord
# la meteo en cours, puis on allume la nouvelle -> aucun changement brutal.
FADE_SECONDS = 2.5

# LA BRUME A SON PROPRE FONDU. Son epaisseur vient du jeu : elle monte apres
# le lever du soleil et se dissipe en fin de matinee (GameState.fog_level).
# Ce delai-ci ne fait que lisser ses sauts (changement de zone, fin de
# l'episode). Surtout, une brume qui se leve ne doit pas eteindre puis
# rallumer le voile gris du temps nuageux, comme le ferait un changement de
# meteo : le temps, lui, n'a pas change.
BRUME_FADE_SECONDS = 3.0

# Meteos ou l'on voit des eclairs.
_STORMY = ("orage", "blizzard")


class WeatherLayer(Widget):
    """Voile, precipitations et brouillard (sous le voile de nuit)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._t = 0.0
        self._kind = "clair"
        # La brume : epaisseur affichee (lissee) et visee, de 0 a 1.
        self._fog = 0.0
        self._fog_target = 0.0
        self._fog_shown = True        # ses formes ont-elles une taille ?
        # Fondu : intensite affichee (0 a 1) et meteo en attente. On descend
        # a 0 avant de basculer sur la nouvelle meteo, puis on remonte.
        self._intensity = 1.0
        self._pending = None
        self._alphas = []             # [(Color, opacite, de la brume ?), ...]
        self._built = None            # (meteo, largeur, hauteur)
        self._veil_rect = None
        self._fog_rect = None
        self._fog_bands = []          # [(Ellipse, fx, fy, fw, fh, vitesse)]
        self._drops = []              # [(Line, fx, phase, vitesse, long, biais)]
        self._flakes = []             # [(Ellipse, fx, phase, vit, amp, w, taille)]
        self._wind = 0.0
        self._rng = random.Random(20260803)
        self.bind(pos=self._invalidate, size=self._invalidate)
        self._event = Clock.schedule_interval(self._tick, 1 / 60.0)

    # ---- API ---------------------------------------------------------- #
    def set_weather(self, kind, fog=0.0):
        """Definit la meteo affichee et l'epaisseur de la brume (0 a 1 ; un
        booleen convient aussi).

        Un changement de METEO est PROGRESSIF : la meteo en cours s'efface
        d'abord, puis la nouvelle apparait (voir _tick). La BRUME, elle,
        s'epaissit ou se dissipe seule, sans toucher au reste. Appelable a
        chaque frame."""
        self._fog_target = max(0.0, min(1.0, float(fog)))
        if self._pending is not None:
            self._pending = kind          # la cible a encore change
        elif kind != self._kind:
            self._pending = kind

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
        self._fog_rect = None
        self._fog_bands = []
        self._drops = []
        self._flakes = []
        self._alphas = []
        rng = self._rng
        w, h = self.width, self.height
        kind = self._kind

        with self.canvas:
            # 1) Voile general de la meteo.
            veil = _VEIL.get(kind)
            if veil:
                self._alphas.append((Color(*veil), veil[3], False))
                self._veil_rect = Rectangle(pos=self.pos, size=self.size)

            # 2) Brume : voile clair + larges bandes qui derivent. TOUJOURS
            # construite, quelle que soit la meteo : c'est son epaisseur qui
            # la montre ou la cache (voir _tick).
            self._alphas.append((Color(0.82, 0.85, 0.88, 0.30), 0.30, True))
            self._fog_rect = Rectangle(pos=self.pos, size=self.size)
            self._alphas.append((Color(0.90, 0.92, 0.95, 0.16), 0.16, True))
            for _ in range(4):
                fy = rng.uniform(0.10, 0.70)
                fw = rng.uniform(0.7, 1.3)
                fh = rng.uniform(0.10, 0.22)
                speed = rng.uniform(0.010, 0.030)
                self._fog_bands.append(
                    [Ellipse(), rng.uniform(0.0, 1.0), fy, fw, fh, speed])
            self._fog_shown = True

            # 3) Precipitations.
            spec = _PRECIP.get(kind)
            self._wind = 0.0
            if spec:
                ptype, count, vfac, sfac, wind = spec
                self._wind = wind
                if ptype == "rain":
                    self._alphas.append((Color(*_RAIN_COLOR), _RAIN_COLOR[3],
                                         False))
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
                    self._alphas.append((Color(*_SNOW_COLOR), _SNOW_COLOR[3],
                                         False))
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

        self._built = (kind, w, h)

    # ---- Animation (chaque frame) ------------------------------------- #
    def _tick(self, dt):
        w, h = self.width, self.height
        if w <= 0 or h <= 0:
            return
        # Fondu progressif : on eteint la meteo en cours (intensite -> 0),
        # on bascule alors sur la nouvelle, puis on la rallume (-> 1).
        step = min(dt, 0.1) / FADE_SECONDS
        if self._pending is not None:
            self._intensity -= step
            if self._intensity <= 0.0:
                self._intensity = 0.0
                self._kind = self._pending
                self._pending = None
        elif self._intensity < 1.0:
            self._intensity = min(1.0, self._intensity + step)
        # La brume rejoint son epaisseur visee, a son propre rythme.
        pas = min(dt, 0.1) / BRUME_FADE_SECONDS
        if self._fog < self._fog_target:
            self._fog = min(self._fog_target, self._fog + pas)
        elif self._fog > self._fog_target:
            self._fog = max(self._fog_target, self._fog - pas)

        if self._built != (self._kind, w, h):
            self._build()
        self._t += min(dt, 0.1)
        t, x0, y0 = self._t, self.x, self.y

        # Opacites suivant le fondu en cours (et l'epaisseur de la brume).
        for col, base, brume in self._alphas:
            col.a = base * self._intensity * (self._fog if brume else 1.0)

        if self._veil_rect is not None:
            self._veil_rect.pos = self.pos
            self._veil_rect.size = self.size

        # Brume : bandes qui derivent lentement de gauche a droite. Absente,
        # ses formes sont ramenees a une taille nulle : invisibles de toute
        # facon, elles couvriraient encore l'ecran, pixel par pixel, pour
        # rien.
        if self._fog > 0.0:
            self._fog_rect.pos = self.pos
            self._fog_rect.size = self.size
            for band in self._fog_bands:
                ell, fx, fy, fw, fh, speed = band
                px = (fx + t * speed) % 1.6 - 0.3
                ell.size = (fw * w, fh * h)
                ell.pos = (x0 + px * w - fw * w / 2, y0 + fy * h - fh * h / 2)
            self._fog_shown = True
        elif self._fog_shown:
            self._fog_rect.size = (0, 0)
            for band in self._fog_bands:
                band[0].size = (0, 0)
            self._fog_shown = False

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
