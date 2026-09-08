"""
Bouton stylise (dessine au canvas, sans image).

Quatre etats, qui doivent se distinguer AU PREMIER COUP D'OEIL sans lire le
texte :

    repos       fond plein + contour net       -> ca s'appuie
    appuye      fond eclairci + contour vif    -> le doigt a bien porte
    choisi      or, contour epais              -> c'est l'onglet ouvert
    desactive   gris terne, texte pali         -> ca ne repond pas

Le CONTOUR est ce qui delimite le bouton : il reste franc meme quand le fond
est presque transparent, sinon un bouton pose sur le decor se dissout dedans
et on ne sait plus ou appuyer.

"Choisi" n'est PAS "desactive". Les onglets se servaient de `disabled` pour
marquer celui qui est ouvert : l'onglet courant paraissait donc en panne. Un
etat separe dit "tu es ici" au lieu de "c'est cassé".

S'utilise comme un Button normal :
    btn = StyledButton(text="Jouer", size_hint=(1, 0.18))
et reste compatible avec scale_font() (qui ajuste juste la taille du texte).
"""
from kivy.properties import BooleanProperty
from kivy.uix.button import Button
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.metrics import dp

FILL_IDLE = (0.13, 0.24, 0.18, 0.92)     # repos (vert foret)
FILL_DOWN = (0.22, 0.40, 0.28, 0.97)     # appuye (vert clair)
FILL_OFF = (0.15, 0.15, 0.16, 0.55)      # desactive : gris NEUTRE, delave
BORDER = (0.62, 0.92, 0.68, 0.85)        # bordure verte lumineuse

# Etat CHOISI : l'or des titres du jeu, pour que "ouvert" se lise partout de
# la meme facon.
FILL_ON = (0.30, 0.25, 0.10, 0.95)
BORDER_ON = (0.96, 0.82, 0.45, 1.0)
TEXT_ON = (1.0, 0.92, 0.70, 1)

# Contour du bouton desactive : encore visible (on doit voir qu'il y a un
# bouton), mais sans eclat.
BORDER_OFF = (0.58, 0.58, 0.62, 0.32)

TEXT_IDLE = (0.95, 0.96, 1, 1)
TEXT_OFF = (0.62, 0.62, 0.66, 0.55)      # texte pali : le gris se lit de loin

# Epaisseurs de contour. Le bouton choisi est plus epais : c'est lui qu'on
# doit reperer sans chercher.
LINE_W = dp(2.0)
LINE_W_ON = dp(2.8)
RADIUS = dp(16)


class StyledButton(Button):
    # Onglet OUVERT / choix courant. Volontairement distinct de `disabled`.
    selected = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # On neutralise l'apparence par defaut de Kivy pour dessiner la notre.
        self.background_normal = ""
        self.background_down = ""
        self.background_disabled_normal = ""
        self.background_color = (0, 0, 0, 0)
        self.color = TEXT_IDLE
        # Kivy pali lui-meme le texte d'un bouton desactive : on lui donne
        # notre gris, sinon un libelle blanc vif reste parfaitement lisible et
        # rien ne dit que le bouton ne repond pas.
        self.disabled_color = TEXT_OFF
        self.bold = True

        # Couleurs surchargeables par les sous-classes (voir set_palette).
        self.fill_idle = FILL_IDLE
        self.fill_down = FILL_DOWN
        self.fill_off = FILL_OFF
        self.border_col = BORDER

        with self.canvas.before:
            self._fill = Color(*self.fill_idle)
            self._rect = RoundedRectangle(radius=[RADIUS])
            self._border = Color(*self.border_col)
            self._line = Line(width=LINE_W)

        self.bind(pos=self._redraw, size=self._redraw,
                  state=self._refresh, disabled=self._refresh,
                  selected=self._refresh)
        self._refresh()

    def set_palette(self, idle, down, off, border):
        self.fill_idle, self.fill_down = idle, down
        self.fill_off, self.border_col = off, border
        self._refresh()

    def _redraw(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._rect.radius = [RADIUS]
        self._line.rounded_rectangle = (self.x, self.y, self.width,
                                        self.height, RADIUS)

    def _refresh(self, *_):
        width = LINE_W
        if self.disabled:
            self._fill.rgba = self.fill_off
            self._border.rgba = BORDER_OFF
        elif self.selected:
            self._fill.rgba = FILL_ON
            self._border.rgba = BORDER_ON
            width = LINE_W_ON
        elif self.state == "down":
            self._fill.rgba = self.fill_down
            self._border.rgba = self.border_col[:3] + (1.0,)
        else:
            self._fill.rgba = self.fill_idle
            self._border.rgba = self.border_col
        self._line.width = width
        # Le texte suit l'etat : dore quand c'est l'onglet ouvert.
        self.color = TEXT_ON if (self.selected and not self.disabled) \
            else TEXT_IDLE
