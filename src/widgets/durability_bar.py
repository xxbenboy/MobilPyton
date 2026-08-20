"""Barre de SOLIDITE d'un outil (hache, lance, couteau).

Une jauge plate et discrete : elle se glisse sous le nom de l'objet tenu sans
manger de place. Pleine et verte quand l'outil est neuf, elle se vide et
rougit a mesure qu'il s'use, pour qu'un coup d'oeil suffise a savoir s'il
tiendra encore quelques travaux.

`set_value(None)` masque la barre : les objets sans solidite (une pierre, une
branche) n'en affichent pas.
"""
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle


# Couleur de la jauge selon ce qu'il RESTE : verte tant que l'outil est bon,
# ambre quand il faudra bientot en refaire un, rouge quand il est en bout de
# course. Seuil = solidite minimale pour cette couleur.
_LEVELS = ((0.55, (0.42, 0.82, 0.40)),
           (0.25, (0.92, 0.75, 0.25)),
           (0.00, (0.90, 0.34, 0.28)))


def wear_color(health):
    for floor, rgb in _LEVELS:
        if health >= floor:
            return rgb
    return _LEVELS[-1][1]


class DurabilityBar(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._value = None
        with self.canvas:
            self._back_c = Color(0.10, 0.11, 0.13, 0.0)
            self._back = Rectangle()
            self._fill_c = Color(0.42, 0.82, 0.40, 0.0)
            self._fill = Rectangle()
        self.bind(pos=self._sync, size=self._sync)

    def set_value(self, health):
        """`health` : 1.0 = neuf, 0.0 = casse, None = pas d'outil (masquee)."""
        if health is not None:
            health = max(0.0, min(1.0, health))
        if health == self._value:
            return
        self._value = health
        self._sync()

    def _sync(self, *_):
        v = self._value
        if v is None or self.width <= 0 or self.height <= 0:
            self._back_c.a = self._fill_c.a = 0.0
            return
        self._back_c.a = 0.55
        self._fill_c.a = 0.95
        self._back.pos = self.pos
        self._back.size = self.size
        self._fill.pos = self.pos
        self._fill.size = (self.width * v, self.height)
        self._fill_c.rgb = wear_color(v)
