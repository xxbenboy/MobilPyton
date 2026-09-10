"""
LE TITRE "CARTE / ZONE", partage par les deux ecrans du lieu.

La carte et la proximite repondent a la meme question -- OU SUIS-JE ? -- a
deux distances : le monde autour, et ce qu'on a sous la main. Elles se
partagent donc un titre a deux volets, comme l'inventaire et le craft (voir
menu_toggle).

CE MODULE EXISTE POUR QUE LA REGLE NE SOIT ECRITE QU'UNE FOIS. Les deux
ecrans doivent s'ouvrir l'un l'autre exactement de la meme facon, et deux
details s'y pretent mal a la copie :

- la ZONE n'est pas un ecran a elle : c'est l'ecran de placement regle sur un
  autre mode. L'ouvrir demande de le preparer, pas seulement d'y aller ;
- la CARTE ne s'ouvre pas sans en posseder une (sauf en mode debug). C'est la
  seule paire de volets du jeu dont un cote peut etre ferme a clef.

Si l'une des deux moities recopiait ces regles pour son compte, elles
finiraient par ne plus dire la meme chose.
"""
from kivy.app import App

from src import items
from src.widgets.menu_toggle import MenuToggle, PANES_LIEU


def carte_ouvrable():
    """La carte s'ouvre-t-elle ? Il faut en posseder une -- ou etre en debug."""
    state = App.get_running_app().game_state
    if state is None:
        return False
    return bool(state.debug or state.has_item(items.MAP_ITEM))


def ouvrir_zone(manager):
    """Passe a la ZONE : l'ecran de placement, regle pour SE SERVIR d'un objet
    pose plutot que pour choisir une case libre."""
    place = manager.get_screen("place")
    place._slot = None
    place.mode = "use"
    place._action_cell = None
    place._action_from_grid = True     # on arrive par la grille
    manager.current = "place"


def lieu_toggle(screen, current, **kwargs):
    """Le titre a deux volets, deja cable, pour l'un ou l'autre des ecrans."""
    def bascule(name):
        if name == "place":
            ouvrir_zone(screen.manager)
        else:
            screen.manager.current = name

    def dispo(name):
        return True if name == "place" else carte_ouvrable()

    return MenuToggle(screen, current, panes=PANES_LIEU, switch=bascule,
                      available=dispo, **kwargs)
