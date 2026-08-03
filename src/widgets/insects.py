"""
Petite faune animee de la scene, selon l'heure :

- LE JOUR : papillons et abeilles (InsectLayer). Tous suivent le meme modele
  -> animation coherente : derive sinusoidale lente + battement d'ailes.
- LA NUIT : lucioles (FireflyLayer), qui clignotent et diffusent un halo de
  lumiere autour d'elles.

La bascule est PROGRESSIVE : `set_night(0..1)` fait disparaitre les insectes
de jour au fur et a mesure que la nuit tombe, et apparaitre les lucioles (et
l'inverse au lever du jour).

Placement des couches (important pour le rendu) :
- InsectLayer  : devant le decor mais DERRIERE le voile de nuit -> les
  insectes s'assombrissent naturellement au crepuscule ;
- FireflyLayer : DEVANT le voile de nuit (mais derriere le HUD) -> les
  lucioles eclairent vraiment au lieu d'etre assombries.
"""
import math
import random

from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse

_COLORS = [(0.85, 0.80, 0.40, 1), (0.70, 0.50, 0.30, 1),
           (0.90, 0.90, 0.95, 1), (0.60, 0.42, 0.92, 1),
           (0.95, 0.60, 0.20, 1)]

# En dessous de ce seuil de visibilite, une couche n'est plus dessinee du tout
# (evite de redessiner des elements totalement transparents).
_MIN_VISIBLE = 0.02


def _ell(ex, ey, ww, hh):
    """Ellipse CENTREE sur (ex, ey)."""
    Ellipse(pos=(ex - ww / 2, ey - hh / 2), size=(ww, hh))


class InsectLayer(Widget):
    """Papillons et abeilles du JOUR (s'effacent quand la nuit tombe)."""

    def __init__(self, count=5, **kwargs):
        super().__init__(**kwargs)
        self._t = 0.0
        self._count = count
        self._insects = []
        self._fade = 1.0          # visibilite globale (1 le jour, 0 la nuit)
        self._blank = False       # canvas deja vide : rien a refaire
        self._rng = random.Random()
        self._spawn()
        self._event = Clock.schedule_interval(self._tick, 1 / 60.0)

    def set_night(self, night):
        """0 = plein jour (insectes visibles), 1 = pleine nuit (disparus)."""
        self._fade = max(0.0, min(1.0, 1.0 - night))

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
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        # Nuit tombee : plus aucun insecte de jour a dessiner.
        if self._fade <= _MIN_VISIBLE or w <= 0 or h <= 0:
            if not self._blank:
                self.canvas.clear()
                self._blank = True
            return
        self.canvas.clear()
        self._blank = False
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

    def _col(self, r, g, b, a):
        """Couleur attenuee par la visibilite globale (fondu jour/nuit)."""
        Color(r, g, b, a * self._fade)

    def _butterfly(self, cx, cy, size, color, flap):
        r, g, b, a = color
        ws = 0.30 + 0.70 * flap          # ouverture des ailes (battement)
        for sgn in (-1, 1):
            ux = cx + sgn * size * 0.52 * ws
            lx = cx + sgn * size * 0.44 * ws
            self._col(r * 0.5, g * 0.5, b * 0.5, a)
            _ell(ux, cy + size * 0.20, size * 1.04 * ws, size * 1.18)
            _ell(lx, cy - size * 0.42, size * 0.82 * ws, size * 0.82)
            self._col(r, g, b, a)
            _ell(ux, cy + size * 0.20, size * 0.9 * ws, size * 1.02)
            _ell(lx, cy - size * 0.42, size * 0.68 * ws, size * 0.68)
        self._col(0.12, 0.10, 0.10, 1)
        _ell(cx, cy - size * 0.05, size * 0.18, size * 1.28)    # corps
        _ell(cx, cy + size * 0.58, size * 0.24, size * 0.32)    # tete

    def _bee(self, cx, cy, size, flap):
        self._col(0.92, 0.95, 1.0, 0.30 + 0.40 * flap)  # ailes (bourdonnement)
        _ell(cx - size * 0.16, cy + size * 0.40, size * 0.7, size * 0.46)
        _ell(cx + size * 0.16, cy + size * 0.40, size * 0.7, size * 0.46)
        self._col(0.96, 0.74, 0.12, 1)                  # corps dore
        _ell(cx, cy, size * 1.32, size * 0.84)
        self._col(0.12, 0.10, 0.08, 1)                  # rayures
        for dx, hsc in ((-0.30, 0.7), (0.02, 0.86), (0.34, 0.66)):
            _ell(cx + dx * size, cy, size * 0.16, size * 0.84 * hsc)
        self._col(0.16, 0.13, 0.10, 1)                  # tete
        _ell(cx - size * 0.64, cy, size * 0.36, size * 0.52)

    def stop(self):
        if self._event is not None:
            self._event.cancel()
            self._event = None


class FireflyLayer(Widget):
    """Lucioles de la NUIT : vol errant, clignotement et halo lumineux.

    A placer DEVANT le voile de nuit pour qu'elles eclairent la scene."""

    # Halo : cercles concentriques, du plus large/diffus au plus serre.
    # (multiplicateur du diametre du coeur, opacite de base)
    _HALO = ((7.0, 0.035), (4.6, 0.06), (3.0, 0.10), (1.9, 0.20))

    def __init__(self, count=9, **kwargs):
        super().__init__(**kwargs)
        self._t = 0.0
        self._count = count
        self._flies = []
        self._alpha = 0.0         # visibilite globale (0 le jour, 1 la nuit)
        self._blank = False
        self._rng = random.Random()
        self._spawn()
        self._event = Clock.schedule_interval(self._tick, 1 / 60.0)

    def set_night(self, night):
        """0 = plein jour (aucune luciole), 1 = pleine nuit (bien visibles)."""
        self._alpha = max(0.0, min(1.0, night))

    def _spawn(self):
        rng = self._rng
        self._flies = []
        for _ in range(self._count):
            ax = rng.uniform(0.05, 0.14)
            ay = rng.uniform(0.04, 0.11)
            self._flies.append({
                "fx": rng.uniform(0.05 + ax, 0.95 - ax),
                "fy": rng.uniform(0.16 + ay, 0.62 - ay),
                "ax": ax, "ay": ay,
                "sx": rng.uniform(0.12, 0.32),          # derive lente
                "sy": rng.uniform(0.20, 0.50),
                "phase": rng.uniform(0.0, 6.28),
                "blink": rng.uniform(0.8, 2.0),         # rythme du clignotement
                "size": rng.uniform(0.005, 0.009),      # diametre du coeur
            })

    def _tick(self, dt):
        self._t += min(dt, 0.1)
        self._redraw()

    def _redraw(self):
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        # Plein jour : aucune luciole.
        if self._alpha <= _MIN_VISIBLE or w <= 0 or h <= 0:
            if not self._blank:
                self.canvas.clear()
                self._blank = True
            return
        self.canvas.clear()
        self._blank = False
        t = self._t
        with self.canvas:
            for f in self._flies:
                ph = f["phase"]
                # Vol errant : deux sinus de periodes differentes -> trajectoire
                # irreguliere (moins mecanique qu'un simple va-et-vient).
                cx = x0 + (f["fx"]
                           + f["ax"] * math.sin(t * f["sx"] + ph)
                           + f["ax"] * 0.3 * math.sin(t * f["sx"] * 2.7
                                                      + ph * 1.4)) * w
                cy = y0 + (f["fy"]
                           + f["ay"] * math.sin(t * f["sy"] + ph * 1.7)
                           + f["ay"] * 0.3 * math.sin(t * f["sy"] * 3.1
                                                      + ph)) * h
                # Clignotement : pulsation adoucie puis accentuee (au carre)
                # -> longs temps faibles, breves montees lumineuses.
                p = 0.5 + 0.5 * math.sin(t * f["blink"] + ph)
                glow = 0.15 + 0.85 * p * p
                self._firefly(cx, cy, f["size"] * h, glow)

    def _firefly(self, cx, cy, size, glow):
        a = self._alpha
        # Halo lumineux (vert-jaune), du plus diffus au plus dense.
        for mult, ha in self._HALO:
            Color(0.72, 1.0, 0.38, ha * glow * a)
            _ell(cx, cy, size * mult, size * mult)
        # Coeur : presque blanc quand la luciole brille.
        Color(0.95, 1.0, 0.70, (0.45 + 0.55 * glow) * a)
        _ell(cx, cy, size, size)

    def stop(self):
        if self._event is not None:
            self._event.cancel()
            self._event = None
