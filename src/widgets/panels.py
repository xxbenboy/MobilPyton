"""
PANNEAUX : le cadre sombre sur lequel se posent les menus.

Chaque ecran redessinait le sien, et aucun n'avait de contour : un panneau
n'etait qu'un voile noir translucide. Pose sur le decor -- une foret sombre,
une nuit -- il s'y fondait, et on ne voyait plus ou commencait le menu.

Un panneau a donc desormais un CONTOUR net. C'est lui qui delimite la zone,
pas le fond : le fond peut rester tres transparent (on veut voir le paysage
derriere) sans que le menu cesse d'etre lisible.
"""
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.metrics import dp

# Fond : noir translucide. `alpha` reste reglable par appelant, certains
# panneaux devant laisser passer plus de decor que d'autres.
FILL = (0, 0, 0)

# Contour : un gris clair discret mais franc. Assez pale pour ne pas attirer
# l'oeil, assez net pour dessiner le bord sur n'importe quel fond.
BORDER = (0.72, 0.75, 0.82, 0.42)
BORDER_W = dp(1.1)
RADIUS = dp(12)


def panel(widget, alpha=0.45, radius=RADIUS, border=BORDER,
          border_width=BORDER_W):
    """Pose un fond arrondi + un contour derriere `widget`, et les tient
    colles a lui quand il bouge ou change de taille."""
    with widget.canvas.before:
        Color(*FILL, alpha)
        rect = RoundedRectangle(radius=[radius])
        Color(*border)
        line = Line(width=border_width)

    def _sync(w, *_):
        rect.pos = w.pos
        rect.size = w.size
        line.rounded_rectangle = (w.x, w.y, w.width, w.height, radius)

    widget.bind(pos=_sync, size=_sync)
    _sync(widget)
    return widget
