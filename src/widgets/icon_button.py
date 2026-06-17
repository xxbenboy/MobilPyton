"""
Bouton-ICONE : un StyledButton sans texte, avec un petit logo.

Le logo est soit une IMAGE personnalisee (assets/buttons/<nom>.png, voir
assets/buttons/LISEZMOI.txt), soit, si l'image n'existe pas, un logo dessine
au canvas. Le nom de l'action s'ecrit sous le bouton (gere par l'ecran).
"""
import os

from kivy.core.image import Image as CoreImage
from kivy.graphics import (Color, Ellipse, Rectangle, RoundedRectangle,
                           Triangle, Line)

from src.widgets.styled_button import StyledButton

_HERE = os.path.dirname(os.path.abspath(__file__))
BUTTONS_DIR = os.path.abspath(os.path.join(_HERE, "..", "..", "assets",
                                           "buttons"))
_TEX_CACHE = {}


def button_image_path(name):
    """Chemin de l'image personnalisee du bouton si elle existe, sinon None."""
    for ext in (".png", ".jpg", ".jpeg"):
        p = os.path.join(BUTTONS_DIR, name + ext)
        if os.path.isfile(p):
            return p
    return None


def _texture(path):
    """Charge (et met en cache) la texture d'une image."""
    if path not in _TEX_CACHE:
        try:
            _TEX_CACHE[path] = CoreImage(path).texture
        except Exception:
            _TEX_CACHE[path] = None
    return _TEX_CACHE[path]


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


def _craft(cx, cy, s):                               # marteau
    Color(0.62, 0.45, 0.28, 1)                       # manche
    Line(points=[cx - s * 0.05, cy - s * 0.6, cx + s * 0.2, cy + s * 0.35],
         width=max(2.0, s * 0.16))
    Color(0.80, 0.82, 0.86, 1)                       # tete
    Rectangle(pos=(cx - s * 0.15, cy + s * 0.28), size=(s * 0.7, s * 0.32))


ICONS = {"explore": _explore, "wood": _wood, "food": _food, "drink": _drink,
         "fill": _fill, "rest": _rest, "map": _map, "home": _home,
         "craft": _craft}


class IconButton(StyledButton):
    def __init__(self, icon="", **kwargs):
        super().__init__(**kwargs)
        # Boutons noir / gris : les logos colores ressortent mieux.
        self.set_palette(idle=(0.11, 0.11, 0.12, 0.96),
                         down=(0.32, 0.32, 0.35, 0.98),
                         off=(0.07, 0.07, 0.08, 0.75),
                         border=(0.65, 0.65, 0.70, 0.55))
        self.icon = icon
        self.text = ""                              # pas de texte sur le bouton
        self.bind(pos=self._draw_icon, size=self._draw_icon)

    def _draw_icon(self, *_):
        self.canvas.after.clear()
        if self.width <= 0 or self.height <= 0:
            return
        # 1) Image personnalisee (assets/buttons/<nom>.png) si elle existe.
        path = button_image_path(self.icon)
        if path:
            tex = _texture(path)
            if tex is not None:
                s = min(self.width, self.height) * 0.80
                with self.canvas.after:
                    Color(1, 1, 1, 1)
                    Rectangle(texture=tex,
                              pos=(self.center_x - s / 2, self.center_y - s / 2),
                              size=(s, s))
                return
        # 2) Sinon : logo dessine au canvas.
        fn = ICONS.get(self.icon)
        if not fn:
            return
        cx, cy = self.center_x, self.center_y
        s = min(self.width, self.height) * 0.42
        with self.canvas.after:
            fn(cx, cy, s)
