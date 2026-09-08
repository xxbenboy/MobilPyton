"""
TITRE A DEUX VOLETS : passer d'un ecran a son voisin d'un seul toucher.

L'inventaire et le craft montrent les memes objets sous deux angles : ce qu'on
porte d'un cote, ce qu'on peut en faire de l'autre. Ils partagent donc un titre
unique, ou le volet OUVERT est en surbrillance et le volet FERME reste sombre
-- et cliquable pour y basculer.

    INVENTAIRE / craft      sur l'ecran inventaire
    inventaire / CRAFT      sur l'ecran craft

Les deux mots ne bougent JAMAIS de place : "inventaire" est toujours a gauche,
"craft" toujours a droite. Seule la surbrillance se deplace. C'est ce qui
permet de faire l'aller-retour sans reflechir -- si les mots echangeaient leur
position a chaque bascule, le doigt taperait sur le mot qu'on vient de
quitter, et on reviendrait sur ses pas.
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

# Les deux volets, DANS L'ORDRE D'AFFICHAGE : (nom d'ecran, libelle).
# L'ordre est fixe une fois pour toutes -- c'est tout l'interet.
PANES = (("inventory", "INVENTAIRE"), ("craft", "CRAFT"))


class _Half(ButtonBehavior, Label):
    """Un volet du titre.

    Herite de ButtonBehavior comme le reste du jeu : c'est lui qui sait deja
    distinguer un vrai tap d'un doigt qui glisse."""


class MenuToggle(BoxLayout):
    """Titre a deux volets. `current` = nom de l'ecran ouvert."""

    def __init__(self, screen, current, **kwargs):
        kwargs.setdefault("orientation", "horizontal")
        super().__init__(**kwargs)
        self.screen = screen
        self.current = current

        # La plaque de surbrillance vit dans le canvas du TITRE, pas dans
        # celui d'un volet : elle doit pouvoir glisser de l'un a l'autre.
        with self.canvas.before:
            Color(*OPEN_BG)
            self._bg = RoundedRectangle(radius=[dp(8)])

        self._halves = {}
        for i, (name, text) in enumerate(PANES):
            first = (i == 0)
            lbl = _Half(text=text, bold=True, size_hint_x=0.47,
                        halign="right" if first else "left", valign="middle")
            lbl.bind(on_release=lambda _w, n=name: self._go(n))
            self._halves[name] = lbl
            if not first:
                self.add_widget(self._sep())
            self.add_widget(lbl)
            self._fit(lbl)

        for lbl in self._halves.values():
            scale_font(lbl)
        self._apply()

    def _sep(self):
        sep = Label(text="/", color=SEP_COLOR, halign="center",
                    valign="middle", size_hint_x=0.06)
        self._fit(sep)
        scale_font(sep)
        return sep

    def _fit(self, label):
        """Cale le texte dans sa boite (sans quoi halign ne sert a rien)."""
        def _update(*_):
            label.text_size = label.size
            self._sync_bg()
        label.bind(pos=_update, size=_update, texture_size=_update)
        _update()

    def set_current(self, current):
        """Change le volet ouvert sans reconstruire le titre."""
        self.current = current
        self._apply()

    def _apply(self):
        for name, lbl in self._halves.items():
            lbl.color = OPEN_COLOR if name == self.current else CLOSED_COLOR
        self._sync_bg()

    def _sync_bg(self):
        """La plaque epouse le TEXTE du volet ouvert, pas toute sa moitie.

        Sur un titre aligne contre le milieu, une plaque pleine largeur
        laisserait une grande zone eclairee et vide du cote du bord."""
        lbl = self._halves.get(self.current)
        if lbl is None:
            return
        tw, th = lbl.texture_size
        pad_x, pad_y = dp(14), dp(6)
        w = min(lbl.width, tw + pad_x * 2)
        h = min(lbl.height, th + pad_y * 2)
        # La plaque suit l'alignement du texte : contre le milieu du titre.
        x = lbl.right - w if lbl.halign == "right" else lbl.x
        self._bg.pos = (x, lbl.center_y - h / 2.0)
        self._bg.size = (w, h)

    def _go(self, name):
        # Le volet OUVERT ne mene nulle part : on est deja dessus.
        # `manager` est encore vide tant que l'ecran n'a pas ete ajoute au
        # gestionnaire -- on ne bascule que s'il existe vraiment.
        if name != self.current and self.screen.manager is not None:
            self.screen.manager.current = name
