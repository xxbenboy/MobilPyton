"""
LA BANDE DES MAINS, en bas de l'inventaire ET du craft.

Les deux ecrans se repondent par un titre a deux volets : on passe de l'un a
l'autre d'un seul toucher. Il faut donc que le bas de l'ecran ne bouge PAS a
la bascule -- meme forme, meme place, meme contenu. Le craft avait sa propre
version, avec ses boutons "Equiper" et "Deposer" ; on retrouvait donc deux
barres differentes selon l'ecran, et le regard devait se reorienter a chaque
aller-retour.

La barre vit desormais ici, en un seul exemplaire. Les actions (equiper,
deposer) appartiennent a l'inventaire, ou l'on fait glisser les objets : le
craft ne fait que MONTRER ce que tiennent les mains.
"""
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp

from src import items
from src.widgets.item_icon import ItemIcon
from src.widgets.panels import panel
from src.widgets.responsive import fit_text, TEXT_NORMAL

# Gris des textes secondaires (main vide).
DIM = (0.62, 0.64, 0.70, 1)
LIT = (0.92, 0.92, 0.95, 1)


def empty_slot(size_hint_x=1.0):
    """Emplacement vide : un cadre plutot qu'un trou.

    Une case vraiment vide se lit comme un bout de decor ; un cadre dit
    qu'il y a une place, et qu'elle attend quelque chose."""
    w = Widget(size_hint_x=size_hint_x)
    with w.canvas:
        Color(1, 1, 1, 0.10)
        rect = RoundedRectangle(radius=[dp(8)])

    def _sync(*_):
        s = min(w.width, w.height)
        rect.pos = (w.center_x - s / 2, w.center_y - s / 2)
        rect.size = (s, s)
    w.bind(pos=_sync, size=_sync)
    _sync()
    return w


def item_text(state, name, worn=False):
    """Nom de l'objet, avec le remplissage dessous s'il s'agit d'un sac.

    Un sac retire garde ce qu'il transportait : on affiche donc son contenu
    qu'il soit porte, tenu en main ou range."""
    if not name:
        return "Vide"
    text = items.display_name(name)
    fill = state.bag_fill(name, worn) if state is not None else None
    if fill and fill[0] > 0:
        text += f"\n{fill[0]}/{fill[1]}"
    return text


class HandSlot(BoxLayout):
    """Ce que tient une main.

    Dans l'inventaire, c'est aussi le point de DEPART du glisser-deposer :
    l'ecran lui greffe alors de quoi s'allumer quand on peut y lacher un
    objet (voir _make_highlightable). Le craft s'en sert tel quel, sans rien
    y brancher."""

    def __init__(self, hand, title, **kwargs):
        kwargs.setdefault("orientation", "horizontal")
        kwargs.setdefault("padding", dp(6))
        kwargs.setdefault("spacing", dp(6))
        super().__init__(**kwargs)
        self.hand = hand
        self.item = None
        panel(self, alpha=0.30)
        self._icon_box = BoxLayout(size_hint_x=0.34)
        self.add_widget(self._icon_box)
        self._text = Label(text="", color=LIT, halign="left",
                           valign="middle", size_hint_x=0.66)
        fit_text(self._text, TEXT_NORMAL)
        self.add_widget(self._text)
        self._title = title

    def set_item(self, name, text=None):
        self.item = name
        self._icon_box.clear_widgets()
        self._icon_box.add_widget(ItemIcon(name, show_name=False) if name
                                  else empty_slot(1.0))
        self._text.text = f"{self._title}\n{text or 'Vide'}"
        self._text.color = LIT if name else DIM


def hands_row(**kwargs):
    """Les deux mains cote a cote. Renvoie (rangee, [main gauche, main droite])."""
    kwargs.setdefault("orientation", "horizontal")
    kwargs.setdefault("spacing", dp(8))
    row = BoxLayout(**kwargs)
    slots = []
    for i, titre in enumerate(("Main gauche", "Main droite")):
        slot = HandSlot(i, titre)
        slots.append(slot)
        row.add_widget(slot)
    return row, slots
