"""
Silhouette de nature (decor).

Dessine en bas de l'ecran, au canvas (aucune image) :
- deux collines (ellipses) en degrade de verts,
- des sapins (triangles empiles) repartis dessus.

Couche purement decorative : a placer DERRIERE le contenu du menu, devant le
fond anime. Tout est en proportions => s'adapte a la taille de l'ecran.
"""
import random

from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse, Rectangle, Triangle


class NatureSilhouette(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        rng = random.Random(7)
        # Sapins : positions (fraction de largeur) + taille (fraction hauteur).
        self._back = [(rng.uniform(0.04, 0.96), rng.uniform(0.05, 0.08))
                      for _ in range(8)]
        self._front = [(rng.uniform(0.02, 0.98), rng.uniform(0.08, 0.13))
                       for _ in range(7)]
        self.bind(pos=self._redraw, size=self._redraw)

    def _pine(self, cx, base, tw, th, color):
        """Un sapin : deux triangles empiles."""
        Color(*color)
        Triangle(points=[cx - tw / 2, base, cx + tw / 2, base,
                         cx, base + th * 0.72])
        Triangle(points=[cx - tw * 0.36, base + th * 0.32,
                         cx + tw * 0.36, base + th * 0.32, cx, base + th])

    def _redraw(self, *_):
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        with self.canvas:
            # Colline arriere (plus claire = lointaine).
            Color(0.12, 0.22, 0.15, 0.85)
            Ellipse(pos=(x0 - 0.25 * w, y0 - 0.10 * h), size=(1.5 * w, 0.26 * h))
            # Sapins lointains.
            for fx, sh in self._back:
                self._pine(x0 + fx * w, y0 + 0.07 * h,
                           sh * 0.55 * h, sh * h * 1.5, (0.10, 0.19, 0.13, 0.9))

            # Colline avant (plus sombre = proche) + bande de sol.
            Color(0.05, 0.13, 0.09, 0.98)
            Ellipse(pos=(x0 - 0.3 * w, y0 - 0.14 * h), size=(1.6 * w, 0.24 * h))
            Rectangle(pos=(x0, y0), size=(w, 0.06 * h))
            # Sapins proches.
            for fx, sh in self._front:
                self._pine(x0 + fx * w, y0 + 0.04 * h,
                           sh * 0.5 * h, sh * h * 1.9, (0.04, 0.11, 0.07, 1))
