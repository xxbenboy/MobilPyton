"""
TITRE A DEUX VOLETS : passer d'un ecran a son voisin d'un seul toucher.

L'inventaire et le craft montrent les memes objets sous deux angles : ce qu'on
porte d'un cote, ce qu'on peut en faire de l'autre. On passait par "Retour"
puis un autre bouton pour aller de l'un a l'autre. Ils partagent desormais un
titre unique, ou le volet OUVERT est en surbrillance et le volet FERME reste
sombre -- et cliquable pour y basculer.

    INVENTAIRE / craft      (sur l'ecran inventaire)
    CRAFT / inventaire      (sur l'ecran craft)

L'ecran ouvert se nomme donc toujours EN PREMIER : on lit d'abord ou l'on est,
puis ou l'on peut aller.
"""
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp

from src.widgets.responsive import scale_font

# Volet OUVERT : l'or deja utilise par les titres du jeu.
OPEN_COLOR = (0.96, 0.82, 0.45, 1)
# Volet FERME : nettement plus sombre, mais encore lisible -- il faut voir
# qu'il y a quelque chose a toucher.
CLOSED_COLOR = (0.52, 0.46, 0.36, 1)
# Barre oblique de separation, discrete.
SEP_COLOR = (0.45, 0.40, 0.32, 1)

# Fond de surbrillance du volet ouvert.
OPEN_BG = (0.96, 0.82, 0.45, 0.13)


def _fit(label):
    """Cale le texte dans sa boite (sans quoi halign ne sert a rien)."""
    def _update(*_):
        label.text_size = label.size
    label.bind(pos=_update, size=_update)
    _update()
    return label


class _Closed(ButtonBehavior, Label):
    """Volet FERME : on peut taper dessus pour ouvrir l'autre ecran.

    Herite de ButtonBehavior comme le reste du jeu : c'est lui qui sait deja
    distinguer un vrai tap d'un doigt qui glisse."""


class MenuToggle(BoxLayout):
    """Titre a deux volets. `other_screen` est le nom de l'ecran a ouvrir."""

    def __init__(self, screen, open_name, closed_name, other_screen, **kwargs):
        kwargs.setdefault("orientation", "horizontal")
        super().__init__(**kwargs)
        self.screen = screen
        self.other_screen = other_screen

        self._open = _fit(Label(text=open_name, bold=True, color=OPEN_COLOR,
                                halign="right", valign="middle",
                                size_hint_x=0.47))
        # Surbrillance du volet ouvert : une plaque douce derriere le texte.
        with self._open.canvas.before:
            Color(*OPEN_BG)
            self._open_bg = RoundedRectangle(radius=[dp(8)])
        # `texture_size` compte autant que la taille : la plaque epouse le
        # texte, qui n'est mesure qu'une fois la police calculee.
        self._open.bind(pos=self._sync_bg, size=self._sync_bg,
                        texture_size=self._sync_bg)

        sep = _fit(Label(text="/", color=SEP_COLOR, halign="center",
                         valign="middle", size_hint_x=0.06))

        self._closed = _fit(_Closed(text=closed_name, bold=True,
                                    color=CLOSED_COLOR, halign="left",
                                    valign="middle", size_hint_x=0.47))
        self._closed.bind(on_release=self._go)

        for lbl in (self._open, sep, self._closed):
            scale_font(lbl)
            self.add_widget(lbl)
        # Pose la plaque tout de suite : la laisser au seul jeu des liaisons
        # la laisserait sans taille tant que rien ne bouge.
        self._sync_bg()

    def _sync_bg(self, *_):
        """La plaque epouse le TEXTE, pas toute la moitie de l'ecran : sur un
        titre aligne a droite, un fond pleine largeur laisserait une grande
        zone eclairee et vide a gauche."""
        lbl = self._open
        tw, th = lbl.texture_size
        pad_x, pad_y = dp(14), dp(6)
        w = min(lbl.width, tw + pad_x * 2)
        h = min(lbl.height, th + pad_y * 2)
        # Aligne a droite, comme le texte du volet ouvert.
        self._open_bg.pos = (lbl.right - w, lbl.center_y - h / 2.0)
        self._open_bg.size = (w, h)

    def _go(self, *_):
        # `manager` est encore vide tant que l'ecran n'a pas ete ajoute au
        # gestionnaire : on ne bascule que s'il existe vraiment.
        if self.screen.manager is not None:
            self.screen.manager.current = self.other_screen
