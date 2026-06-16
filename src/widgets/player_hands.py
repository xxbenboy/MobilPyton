"""
Mains du joueur (vue a la premiere personne).

Deux avant-bras qui remontent du bas de l'ecran vers le centre, termines par
des mains ouvertes. Dessine en superposition, devant le decor. Pour l'instant
les mains sont VIDES (rien tenu) ; plus tard on pourra dessiner un objet entre
les deux mains.
"""
from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse, Quad


class PlayerHands(Widget):
    SKIN = (0.82, 0.64, 0.48, 1)
    SKIN_DK = (0.68, 0.52, 0.38, 1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_):
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return
        with self.canvas:
            self._arm(0.30, 0.43, 0.17, +1)      # main gauche
            self._arm(0.70, 0.57, 0.17, -1)      # main droite

    def _arm(self, base_fx, hand_fx, hand_fy, thumb_dir):
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        bx = x0 + base_fx * w
        hx = x0 + hand_fx * w
        hy = y0 + hand_fy * h
        armw = 0.060 * w
        wristw = 0.050 * w

        # Avant-bras (du bord bas jusqu'au poignet) : bord sombre + dessus clair.
        Color(*self.SKIN_DK)
        Quad(points=[bx - armw, y0, bx + armw, y0,
                     hx + wristw, hy, hx - wristw, hy])
        Color(*self.SKIN)
        Quad(points=[bx - armw * 0.65, y0, bx + armw * 0.65, y0,
                     hx + wristw * 0.65, hy, hx - wristw * 0.65, hy])

        # Paume.
        Color(*self.SKIN)
        Ellipse(pos=(hx - 0.055 * w, hy - 0.02 * h), size=(0.11 * w, 0.08 * h))
        # Doigts (4) vers le haut, teintes alternees pour les separer.
        for i in range(4):
            fx = hx + (i - 1.5) * 0.026 * w
            Color(*(self.SKIN if i % 2 == 0 else self.SKIN_DK))
            Ellipse(pos=(fx - 0.013 * w, hy + 0.03 * h),
                    size=(0.026 * w, 0.075 * h))
        # Pouce (vers le centre).
        Color(*self.SKIN)
        Ellipse(pos=(hx + thumb_dir * 0.05 * w - 0.012 * w, hy),
                size=(0.024 * w, 0.05 * h))
