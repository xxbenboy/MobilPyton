"""
Bouton-ICONE : un StyledButton sans texte, avec un petit logo dessine au
canvas (selon l'action). Le nom de l'action s'ecrit a cote, sous le bouton
(gere par l'ecran).
"""
from kivy.graphics import (Color, Ellipse, Rectangle, RoundedRectangle,
                           Triangle, Line)

from src.widgets.styled_button import StyledButton


def _zed(x, y, sz, wd):                              # petit "Z" (sommeil)
    Line(points=[x, y + sz, x + sz, y + sz, x, y, x + sz, y], width=wd)


def _explore(cx, cy, s):                             # loupe
    Color(0.95, 0.96, 1, 1)
    Line(circle=(cx - s * 0.18, cy + s * 0.18, s * 0.5), width=max(1.5, s * 0.13))
    Line(points=[cx + s * 0.16, cy - s * 0.16, cx + s * 0.62, cy - s * 0.62],
         width=max(1.5, s * 0.16))


def _wood(cx, cy, s):                                # hache
    Color(0.74, 0.54, 0.34, 1)
    Line(points=[cx - s * 0.5, cy - s * 0.6, cx + s * 0.35, cy + s * 0.6],
         width=max(2.0, s * 0.18))
    Color(0.85, 0.88, 0.92, 1)
    Triangle(points=[cx + s * 0.12, cy + s * 0.35, cx + s * 0.72, cy + s * 0.72,
                     cx + s * 0.6, cy + s * 0.05])


def _food(cx, cy, s):                                # pomme
    Color(0.85, 0.22, 0.22, 1)
    Ellipse(pos=(cx - s * 0.45, cy - s * 0.55), size=(s * 0.9, s * 1.0))
    Color(0.40, 0.28, 0.12, 1)
    Line(points=[cx, cy + s * 0.35, cx + s * 0.12, cy + s * 0.7],
         width=max(1.0, s * 0.09))
    Color(0.30, 0.60, 0.25, 1)
    Ellipse(pos=(cx + s * 0.1, cy + s * 0.5), size=(s * 0.4, s * 0.24))


def _drink(cx, cy, s):                               # goutte d'eau
    Color(0.30, 0.60, 0.92, 1)
    Ellipse(pos=(cx - s * 0.4, cy - s * 0.6), size=(s * 0.8, s * 0.8))
    Triangle(points=[cx - s * 0.34, cy + s * 0.02, cx + s * 0.34, cy + s * 0.02,
                     cx, cy + s * 0.72])


def _fill(cx, cy, s):                                # gourde
    Color(0.85, 0.88, 0.92, 1)
    Rectangle(pos=(cx - s * 0.12, cy + s * 0.35), size=(s * 0.24, s * 0.3))
    Color(0.40, 0.70, 0.95, 1)
    RoundedRectangle(pos=(cx - s * 0.38, cy - s * 0.6),
                     size=(s * 0.76, s * 1.0), radius=[s * 0.16])


def _rest(cx, cy, s):                                # Zzz
    Color(0.95, 0.96, 1, 1)
    wd = max(1.3, s * 0.1)
    _zed(cx - s * 0.12, cy - s * 0.12, s * 0.5, wd)
    _zed(cx + s * 0.28, cy + s * 0.28, s * 0.36, wd)


def _map(cx, cy, s):                                 # carte
    Color(0.90, 0.85, 0.60, 1)
    RoundedRectangle(pos=(cx - s * 0.62, cy - s * 0.46),
                     size=(s * 1.24, s * 0.92), radius=[s * 0.08])
    Color(0.45, 0.50, 0.30, 1)
    Line(points=[cx - s * 0.2, cy - s * 0.46, cx - s * 0.2, cy + s * 0.46],
         width=max(1.0, s * 0.07))
    Line(points=[cx + s * 0.2, cy - s * 0.46, cx + s * 0.2, cy + s * 0.46],
         width=max(1.0, s * 0.07))


def _home(cx, cy, s):                                # maison (menu)
    Color(0.90, 0.90, 0.95, 1)
    Triangle(points=[cx - s * 0.62, cy + s * 0.05, cx + s * 0.62, cy + s * 0.05,
                     cx, cy + s * 0.62])
    Rectangle(pos=(cx - s * 0.42, cy - s * 0.52), size=(s * 0.84, s * 0.6))
    Color(0.30, 0.25, 0.20, 1)
    Rectangle(pos=(cx - s * 0.13, cy - s * 0.52), size=(s * 0.26, s * 0.34))


ICONS = {"explore": _explore, "wood": _wood, "food": _food, "drink": _drink,
         "fill": _fill, "rest": _rest, "map": _map, "home": _home}


class IconButton(StyledButton):
    def __init__(self, icon="", **kwargs):
        super().__init__(**kwargs)
        self.icon = icon
        self.text = ""                              # pas de texte sur le bouton
        self.bind(pos=self._draw_icon, size=self._draw_icon)

    def _draw_icon(self, *_):
        self.canvas.after.clear()
        if self.width <= 0 or self.height <= 0:
            return
        fn = ICONS.get(self.icon)
        if not fn:
            return
        cx, cy = self.center_x, self.center_y
        s = min(self.width, self.height) * 0.42
        with self.canvas.after:
            fn(cx, cy, s)
