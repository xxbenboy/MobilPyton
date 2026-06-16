"""
Barre de statistique : un libelle + une barre coloree (0 a 100).

Sert a afficher vie / energie / sommeil / faim / soif dans la section "Etat".
Dessinee au canvas, avec un texte par-dessus. Responsive (taille de police et
barre suivent la taille du widget).
"""
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp


class StatBar(Widget):
    def __init__(self, name, color, **kwargs):
        super().__init__(**kwargs)
        self._name = name
        self._color = color
        self._value = 100.0

        with self.canvas.before:
            Color(0, 0, 0, 0.45)
            self._bg = RoundedRectangle(radius=[dp(5)])
            self._fill_c = Color(*color)
            self._fill = RoundedRectangle(radius=[dp(5)])

        self._label = Label(halign="left", valign="middle", bold=True,
                            color=(1, 1, 1, 1))
        self.add_widget(self._label)

        self.bind(pos=self._redraw, size=self._redraw)

    def set_value(self, value):
        self._value = max(0.0, min(100.0, float(value)))
        self._redraw()

    def _redraw(self, *_):
        if self.width <= 0:
            return
        r = dp(5)
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._bg.radius = [r]
        fw = self.width * (self._value / 100.0)
        self._fill.pos = self.pos
        self._fill.size = (fw, self.height)
        self._fill.radius = [r]
        self._label.pos = (self.x + dp(8), self.y)
        self._label.size = (self.width - dp(12), self.height)
        self._label.text_size = (self.width - dp(12), self.height)
        self._label.font_size = max(10, self.height * 0.55)
        self._label.text = f"{self._name}  {int(round(self._value))}"
