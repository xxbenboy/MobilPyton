"""
LA COLONNE "A PROXIMITE", en bas de l'inventaire ET du craft.

Meme histoire que la bande des mains : les deux ecrans montrent la MEME chose
(state.ground_here()), mais chacun la dessinait a sa facon. L'inventaire en
faisait une grille compacte d'images ; le craft, une liste haute avec deux
boutons "Main G" / "Main D" pour ramasser. Passer d'un ecran a l'autre
changeait donc la colonne de forme, alors qu'elle contient exactement les
memes objets.

Les boutons de ramassage ont disparu : on prend un objet en le GLISSANT, dans
l'inventaire. La colonne n'a donc plus qu'a montrer ce qui traine, et une
seule facon de le faire suffit -- celle qui vit ici.

Les cases restent utilisables comme point de depart d'un glisser : chacune
porte `item` et `count`, ce dont l'inventaire a besoin pour savoir ce qu'on
vient d'attraper. Le craft, lui, ne branche rien dessus.
"""
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.metrics import dp

from src import items
from src.widgets.item_icon import ItemIcon
from src.widgets.responsive import dh, fit_text, TEXT_NORMAL

# Une case : le carre de l'image, puis sa legende dessous.
ICON_SIDE = 116
NAME_LABEL = 46
CELL_H = ICON_SIDE + NAME_LABEL

# Nombre de cases par rangee. La colonne est etroite (26 % de l'ecran) : au
#-dela de quatre, les images deviennent illisibles.
GROUND_COLS = 4

# Hauteur du message quand il n'y a rien : de quoi respirer, sans laisser un
# grand vide.
EMPTY_H = 120

DIM = (0.62, 0.64, 0.70, 1)
LIT = (0.92, 0.92, 0.95, 1)


def cell_label(text, color=LIT, height=None, **kwargs):
    """Legende d'une case, a la taille commune du jeu."""
    lbl = Label(text=text, color=color, halign="center", valign="middle",
                size_hint_y=None, height=height or dh(NAME_LABEL), **kwargs)
    fit_text(lbl, TEXT_NORMAL)
    return lbl


def item_cell(name, count=1):
    """Une case : l'image de l'objet et son nom (avec le nombre s'il y en a
    plusieurs). Porte `item` et `count` pour le glisser-deposer."""
    cell = BoxLayout(orientation="vertical", size_hint_y=None,
                     height=dh(CELL_H))
    cell.item = name
    cell.count = count
    cell.add_widget(ItemIcon(name, show_name=False))
    cell.name_label = cell_label(
        items.display_name(name) + (f" x{count}" if count > 1 else ""))
    cell.add_widget(cell.name_label)
    return cell


def fill_ground(box, title, state):
    """Remplit la colonne des objets AU SOL et renvoie ses cases.

    `title` est le libelle de la colonne : il porte le compte, pour qu'on
    sache d'un coup d'oeil s'il y a de quoi faire sans avoir a defiler."""
    box.clear_widgets()
    ground = state.ground_here() if state is not None else {}
    title.text = ("A proximite" if not ground
                  else f"A proximite ({sum(ground.values())})")
    if not ground:
        box.add_widget(fit_text(Label(
            text="Rien au sol ici.", color=DIM, halign="center",
            valign="middle", size_hint_y=None, height=dh(EMPTY_H)),
            wrap=True))
        return []
    grid = GridLayout(cols=GROUND_COLS, spacing=dp(3), size_hint_y=None)
    grid.bind(minimum_height=grid.setter("height"))
    cells = []
    for name, count in sorted(ground.items()):
        cell = item_cell(name, count)
        cells.append(cell)
        grid.add_widget(cell)
    box.add_widget(grid)
    return cells
