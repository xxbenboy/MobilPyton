"""
REGLAGES DE DEBUG : imposer l'heure et la meteo, depuis le menu pause.

Le decor a beaucoup de rendus qu'on ne voit qu'en attendant : la lumiere
dorée du matin, l'orange du couchant, le voile bleu de la nuit, la pluie,
le brouillard, les eclairs d'orage. Les attendre coute cher -- la meteo est
tiree au sort et un episode dure de 2 a 6 heures de jeu, et l'orage ne tombe
que 5 % du temps. On pouvait donc jouer longtemps sans jamais voir ce qu'on
venait de coder.

Ce panneau donne la main sur les deux. Il n'apparait QUE dans une partie de
debug (state.debug) : c'est un outil d'observation, pas une fonction de jeu.

DEUX VERROUS, sans lesquels les boutons seraient decoratifs :
- l'HEURE est figee (24 h de jeu passent en 10 minutes reelles : sans cela,
  "Soir" serait deja la nuit avant qu'on ait fini de regarder) ;
- la METEO est tenue (update_weather() rendrait la main au hasard des la fin
  de l'episode en cours).
Chaque groupe a donc son bouton "Auto" pour rendre la main au jeu.

Les deux verrous ne sont PAS sauvegardes (voir game_state) : rouvrir une
partie la rend toujours a son cours normal.
"""
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.metrics import dp

from src.widgets.styled_button import TabButton
from src.widgets.responsive import fit_text, TEXT_SMALL, TEXT_NORMAL

# Moments de la journee -> heure posee sur l'horloge. Ces heures ne sont pas
# prises au hasard : chacune tombe au COEUR d'un rendu, pas a sa frontiere,
# sinon on reglerait "Soir" pour tomber sur un ciel deja de nuit.
#   7 h  : l'or du matin est installe (le soleil se leve a 5 h)
#  12 h  : lumiere neutre, ombres les plus courtes
#  19 h  : le soleil se couche, c'est l'orange franc
#  23 h  : nuit pleine (elle commence a 20 h)
MOMENTS = (("Matin", 7.0), ("Midi", 12.0), ("Soir", 19.0), ("Nuit", 23.0))

# Meteos proposees -> (meteo du jeu, brouillard). Le brouillard n'est pas une
# meteo a lui seul dans le jeu : c'est un temps NUAGEUX auquel il s'ajoute.
# Le panneau en fait un choix a part entiere, parce que c'est ainsi qu'on le
# cherche quand on veut le regarder.
#
# A savoir : en MONTAGNE le jeu traduit de lui-meme la pluie en neige et
# l'orage en blizzard (effective_weather). Ces deux rendus-la se regardent
# donc en montant, avec les memes boutons.
METEOS = (("Clair", "clair", False), ("Pluie", "pluie", False),
          ("Brume", "nuageux", True), ("Orage", "orage", False))


def _titre(texte):
    lbl = Label(text=texte, halign="left", valign="middle",
                color=(0.72, 0.76, 0.84, 1), size_hint_y=0.09)
    fit_text(lbl, TEXT_SMALL)
    return lbl


def _grille(entrees, actif, choisir):
    """Un groupe de choix ou UN SEUL est allume (TabButton : vert / gris)."""
    grid = GridLayout(cols=2, spacing=dp(6), size_hint_y=0.30)
    boutons = []
    for entree in entrees:
        b = TabButton(text=entree[0])
        fit_text(b, TEXT_SMALL)
        b.selected = (entree[0] == actif)
        b.bind(on_release=lambda _b, e=entree: choisir(e))
        boutons.append(b)
        grid.add_widget(b)
    return grid, boutons


def _auto(texte, actif, relacher):
    """Le retour au jeu normal. Allume quand AUCUN reglage n'est impose :
    on voit ainsi d'un coup d'oeil si l'on regarde le jeu ou une mise en
    scene."""
    b = TabButton(text=texte, size_hint_y=0.13)
    fit_text(b, TEXT_SMALL)
    b.selected = actif
    b.bind(on_release=lambda *_: relacher())
    return b


def moment_actuel(state):
    """Nom du moment impose, ou None si l'horloge tourne librement."""
    if not state.time_frozen:
        return None
    heure = (state.time_seconds % 86400) / 3600.0
    for nom, h in MOMENTS:
        if abs(heure - h) < 0.5:
            return nom
    return None


def meteo_actuelle(state):
    """Nom de la meteo imposee, ou None si elle est laissee au hasard."""
    if not state.weather_locked:
        return None
    for nom, kind, fog in METEOS:
        if state.weather == kind and bool(state.fog) == fog:
            return nom
    return None


def debug_section(state, apres):
    """Construit le bloc de reglages. `apres` est rappele apres chaque choix
    (l'ecran s'y redessine et reconstruit le panneau, pour que le bouton qui
    vient d'etre touche s'allume)."""
    box = BoxLayout(orientation="vertical", spacing=dp(6))

    titre = Label(text="DEBUG", halign="left", valign="middle", bold=True,
                  color=(1.0, 0.86, 0.45, 1), size_hint_y=0.10)
    fit_text(titre, TEXT_NORMAL)
    box.add_widget(titre)

    def choisir_moment(entree):
        state.set_debug_hour(entree[1])
        apres()

    def choisir_meteo(entree):
        state.set_debug_weather(entree[1], entree[2])
        apres()

    box.add_widget(_titre("Moment"))
    grille, _ = _grille(MOMENTS, moment_actuel(state), choisir_moment)
    box.add_widget(grille)
    box.add_widget(_auto("Heure auto", not state.time_frozen,
                         lambda: (state.release_debug_time(), apres())))

    box.add_widget(_titre("Meteo"))
    grille, _ = _grille(METEOS, meteo_actuelle(state), choisir_meteo)
    box.add_widget(grille)
    box.add_widget(_auto("Meteo auto", not state.weather_locked,
                         lambda: (state.release_debug_weather(), apres())))
    return box


__all__ = ["debug_section", "MOMENTS", "METEOS", "moment_actuel",
           "meteo_actuelle"]
