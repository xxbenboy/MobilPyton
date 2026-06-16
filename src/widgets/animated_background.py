"""
Fond anime d'ambiance (plus elabore).

Trois couches dessinees au canvas (aucune image necessaire) :
1. un DEGRADE vertical (haut sombre -> bas couleur d'ambiance) qui change
   lentement de teinte en boucle (aube -> jour -> crepuscule -> nuit...),
   pour donner la sensation que le temps passe ;
2. des ETOILES qui scintillent doucement ;
3. (le jeu peut appeler `set_mood(...)` pour orienter l'ambiance selon
   l'action en cours).
"""
import math
import random

from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, Ellipse
from kivy.graphics.texture import Texture
from kivy.metrics import dp


# Palette d'ambiances parcourue en boucle (couleur "du bas" du degrade).
# Teintes naturelles : foret, sous-bois, vert d'eau, terre au crepuscule.
MOODS = [
    (0.09, 0.15, 0.12),  # nuit en foret
    (0.18, 0.28, 0.16),  # sous-bois / aube
    (0.16, 0.34, 0.30),  # jour, vert d'eau
    (0.28, 0.22, 0.13),  # crepuscule terreux
]

# Ambiance "6h du matin" : lueur chaude et douce de l'aube.
MORNING_6H = (0.40, 0.30, 0.30)


class AnimatedBackground(Widget):
    def __init__(self, speed=0.15, stars=28, cycle=True, mood=None, **kwargs):
        super().__init__(**kwargs)
        self.speed = speed
        # cycle=False : le fond reste sur une ambiance fixe (ex. 6h du matin).
        self.cycle = cycle
        self._mood_index = 0
        if mood is not None:
            self._current = list(mood)
            self._target = list(mood)
        else:
            self._current = list(MOODS[0])
            self._target = list(MOODS[1])
        self._t = 0.0
        self._frame = 0

        # Texture 1xN qui contient le degrade vertical (mise a jour au fil du
        # temps quand la couleur change).
        self._grad_tex = Texture.create(size=(1, 64), colorfmt="rgba")
        self._grad_tex.wrap = "clamp_to_edge"
        self._grad_tex.mag_filter = "linear"
        self._grad_tex.min_filter = "linear"

        with self.canvas.before:
            # Couche 1 : le degrade.
            Color(1, 1, 1, 1)
            self._rect = Rectangle(texture=self._grad_tex,
                                   pos=self.pos, size=self.size)
            # Couche 2 : les etoiles.
            self._stars = []
            rng = random.Random(20240601)
            for _ in range(stars):
                col = Color(1, 1, 1, 0.5)
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
    def _update_layout(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        for s in self._stars:
            sz = s["size"]
            s["e"].size = (sz, sz)
            s["e"].pos = (self.x + s["fx"] * self.width - sz / 2,
                          self.y + s["fy"] * self.height - sz / 2)

    def _build_gradient(self):
        """Recree la texture du degrade a partir de la couleur courante."""
        h = 64
        bot = self._current
        top = [c * 0.4 for c in self._current]  # haut plus sombre
        buf = bytearray(h * 4)
        for i in range(h):
            t = i / (h - 1)            # 0 = bas, 1 = haut
            buf[i * 4] = int((bot[0] * (1 - t) + top[0] * t) * 255)
            buf[i * 4 + 1] = int((bot[1] * (1 - t) + top[1] * t) * 255)
            buf[i * 4 + 2] = int((bot[2] * (1 - t) + top[2] * t) * 255)
            buf[i * 4 + 3] = 255
        self._grad_tex.blit_buffer(bytes(buf), colorfmt="rgba",
                                   bufferfmt="ubyte")

    def set_mood(self, rgb):
        """Oriente l'ambiance vers une couleur (ex. selon l'action)."""
        self._target = list(rgb)

    def _tick(self, dt):
        self._t += dt

        # Transition douce de la couleur d'ambiance.
        done = True
        for i in range(3):
            diff = self._target[i] - self._current[i]
            if abs(diff) > 0.001:
                self._current[i] += diff * self.speed * dt
                done = False
        if done and self.cycle:
            self._mood_index = (self._mood_index + 1) % len(MOODS)
            self._target = list(MOODS[self._mood_index])

        # Degrade : reconstruit 15 fois/seconde (suffisant, et leger).
        self._frame += 1
        if self._frame % 4 == 0:
            self._build_gradient()

        # Scintillement des etoiles.
        for s in self._stars:
            s["col"].a = s["base"] * (0.35 + 0.65 *
                                      abs(math.sin(self._t * s["tw"] + s["phase"])))
