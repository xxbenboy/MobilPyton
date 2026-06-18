"""
Petite horloge animee (cadran + aiguilles) : l'aiguille des minutes tourne.

Utilisee au centre de l'ecran de transition pendant un deplacement, pour
signifier "le temps passe / deplacement en cours".
"""
import math

from kivy.uix.widget import Widget
from kivy.properties import NumericProperty
from kivy.animation import Animation
from kivy.graphics import Color, Line, Ellipse, PushMatrix, PopMatrix, Rotate


class ClockFace(Widget):
    angle = NumericProperty(0)      # rotation de l'aiguille des minutes (deg)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._anim = None
        self.bind(pos=self._redraw, size=self._redraw, angle=self._redraw)

    def start(self):
        """Lance la rotation continue de l'aiguille des minutes."""
        self.stop()
        self._anim = Animation(angle=360, duration=1.6)
        self._anim.repeat = True
        self._anim.start(self)

    def stop(self):
        Animation.cancel_all(self, "angle")
        self.angle = 0

    def _redraw(self, *_):
        self.canvas.clear()
        if self.width <= 1 or self.height <= 1:
            return
        cx, cy = self.center
        r = min(self.width, self.height) * 0.46
        with self.canvas:
            Color(0.96, 0.82, 0.45, 1)                 # cadran dore
            Line(circle=(cx, cy, r), width=max(1.5, r * 0.06))
            for a in (0, 90, 180, 270):                # graduations 12/3/6/9
                rad = math.radians(a)
                x1, y1 = cx + r * 0.82 * math.sin(rad), cy + r * 0.82 * math.cos(rad)
                x2, y2 = cx + r * math.sin(rad), cy + r * math.cos(rad)
                Line(points=[x1, y1, x2, y2], width=max(1.0, r * 0.04))
            Color(1, 1, 1, 1)                          # aiguille heures (fixe)
            Line(points=[cx, cy, cx, cy + r * 0.45], width=max(1.5, r * 0.07))
            PushMatrix()                               # aiguille minutes (tourne)
            Rotate(angle=-self.angle, origin=(cx, cy))
            Line(points=[cx, cy, cx, cy + r * 0.72], width=max(1.2, r * 0.05))
            PopMatrix()
            Color(0.96, 0.82, 0.45, 1)                 # moyeu central
            Ellipse(pos=(cx - r * 0.08, cy - r * 0.08), size=(r * 0.16, r * 0.16))
