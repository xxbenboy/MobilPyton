"""
Indicateur de statistique CIRCULAIRE.

Un anneau dont le REMPLISSAGE (arc colore, depart en haut, sens horaire)
represente la valeur de 0 a 100. Au centre, un LOGO qui represente la stat ;
sous le cercle, le NOM de la stat.

Remplace l'ancienne barre (StatBar) dans la section "Etat" du jeu.

Dessin : le fond (disque + anneau gris + logo + nom) n'est reconstruit que
quand la taille change ; la valeur (l'arc colore) est mise a jour seule a
chaque rafraichissement, ce qui reste fluide meme appele souvent.
"""
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.graphics import Color, Line, Ellipse
from kivy.metrics import dp

from src.widgets.icon_button import ICONS


class StatCircle(Widget):
    def __init__(self, name, color, icon, **kwargs):
        super().__init__(**kwargs)
        self._name = name
        self._color = color
        self._icon = icon
        self._value = 100.0

        # Reference vers l'arc colore (mis a jour quand la valeur change).
        self._arc = None
        self._geom = None       # (cx, cy, radius_arc) memorise pour l'arc

        self._label = Label(halign="center", valign="top", bold=True,
                            color=(1, 1, 1, 1))
        self.add_widget(self._label)

        self.bind(pos=self._rebuild, size=self._rebuild)

    def set_value(self, value):
        self._value = max(0.0, min(100.0, float(value)))
        self._update_arc()

    # ------------------------------------------------------------------ #
    def _rebuild(self, *_):
        """Reconstruit tout le dessin (appele quand la taille/pos change)."""
        self.canvas.before.clear()
        self.canvas.after.clear()
        self._arc = None
        if self.width <= 0 or self.height <= 0:
            return

        # Le bas du widget accueille le nom ; le reste, le cercle.
        name_h = self.height * 0.24
        circle_h = self.height - name_h
        diameter = min(self.width, circle_h) * 0.92
        radius = diameter / 2.0
        cx = self.center_x
        cy = self.y + name_h + circle_h / 2.0
        thickness = max(dp(3), radius * 0.20)
        radius_arc = radius - thickness / 2.0
        self._geom = (cx, cy, radius_arc, thickness)

        with self.canvas.before:
            # Disque de fond translucide.
            Color(0, 0, 0, 0.45)
            Ellipse(pos=(cx - radius, cy - radius), size=(diameter, diameter))
            # Anneau "vide" (gris) : repere visuel du maximum.
            Color(1, 1, 1, 0.16)
            Line(circle=(cx, cy, radius_arc), width=thickness)
            # Anneau de valeur (arc colore). Garde sous la main pour la maj.
            Color(*self._color)
            self._arc = Line(width=thickness, cap="round")

        # Logo au centre.
        fn = ICONS.get(self._icon)
        if fn:
            s = radius * 0.5
            with self.canvas.after:
                fn(cx, cy, s)

        # Nom sous le cercle.
        self._label.pos = (self.x, self.y)
        self._label.size = (self.width, name_h)
        self._label.text_size = (self.width, name_h)
        self._label.font_size = max(10, name_h * 0.55)
        self._label.text = self._name

        self._update_arc()

    def _update_arc(self):
        """Met a jour le seul arc colore selon la valeur (0 a 100)."""
        if self._arc is None or self._geom is None:
            return
        cx, cy, radius_arc, _ = self._geom
        sweep = 360.0 * (self._value / 100.0)
        # Arc depuis le haut (0 deg) dans le sens horaire.
        self._arc.circle = (cx, cy, radius_arc, 0, sweep)
