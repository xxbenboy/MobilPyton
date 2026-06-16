"""
Bouton stylise (dessine au canvas, sans image).

- coins arrondis + bordure lumineuse,
- couleur qui reagit a l'appui (effet "pressed"),
- etat desactive grise (utilise par ex. pour "Charger" quand il n'y a aucune
  partie).

S'utilise comme un Button normal :
    btn = StyledButton(text="Jouer", size_hint=(1, 0.18))
et reste compatible avec scale_font() (qui ajuste juste la taille du texte).
"""
from kivy.uix.button import Button
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.metrics import dp

FILL_IDLE = (0.13, 0.24, 0.18, 0.92)     # repos (vert foret)
FILL_DOWN = (0.22, 0.40, 0.28, 0.97)     # appuye (vert clair)
FILL_OFF = (0.12, 0.14, 0.12, 0.70)      # desactive
BORDER = (0.55, 0.85, 0.60, 0.55)        # bordure verte lumineuse


class StyledButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # On neutralise l'apparence par defaut de Kivy pour dessiner la notre.
        self.background_normal = ""
        self.background_down = ""
        self.background_disabled_normal = ""
        self.background_color = (0, 0, 0, 0)
        self.color = (0.95, 0.96, 1, 1)
        self.bold = True

        with self.canvas.before:
            self._fill = Color(*FILL_IDLE)
            self._rect = RoundedRectangle(radius=[dp(16)])
            self._border = Color(*BORDER)
            self._line = Line(width=dp(1.2))

        self.bind(pos=self._redraw, size=self._redraw,
                  state=self._refresh, disabled=self._refresh)

    def _redraw(self, *_):
        r = dp(16)
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._rect.radius = [r]
        self._line.rounded_rectangle = (self.x, self.y, self.width,
                                        self.height, r)

    def _refresh(self, *_):
        if self.disabled:
            self._fill.rgba = FILL_OFF
            self._border.a = 0.18
        elif self.state == "down":
            self._fill.rgba = FILL_DOWN
            self._border.a = 0.95
        else:
            self._fill.rgba = FILL_IDLE
            self._border.a = BORDER[3]
