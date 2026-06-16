"""
Ecran de jeu.

Le jeu est de style "menu jouable" : le joueur choisit une action, chaque
action fait AVANCER LE TEMPS (qui ne s'arrete jamais) et modifie ses stats.
L'affichage se met a jour apres chaque action.

Sauvegarde automatique (gere ici, pour la partie en cours) :
- PERIODIQUE : toutes les `AUTOSAVE_SECONDS` secondes tant qu'on est en jeu.
- APRES CERTAINES ACTIONS : chaque action declenche une sauvegarde.
La sauvegarde "avant fermeture" est geree au niveau de l'app (voir game.py).

L'etat de la partie n'est PAS cree ici : il est prepare par le menu
(nouvelle partie ou chargement) puis depose dans `App.game_state`. Cet
ecran lit/modifie cet etat partage.
"""
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button

from src.widgets.animated_background import AnimatedBackground
from src.widgets.responsive import scale_font

# Intervalle de la sauvegarde automatique periodique (en secondes).
AUTOSAVE_SECONDS = 30

# Vitesse d'ecoulement du temps : combien de secondes de JEU passent pour
# chaque seconde reelle. 1 = temps reel. Augmenter pour accelerer l'horloge.
TIME_SCALE = 1

# Definition des actions : libelle, minutes de temps consommees, effets sur
# les stats, et une ambiance (couleur de fond) associee.
ACTIONS = [
    {"label": "Explorer",       "minutes": 90,  "energy": -15, "hunger": +10,
     "wood": 0, "food": +1, "mood": (0.20, 0.35, 0.40)},
    {"label": "Couper du bois", "minutes": 120, "energy": -20, "hunger": +12,
     "wood": +3, "food": 0,  "mood": (0.18, 0.30, 0.18)},
    {"label": "Chercher a manger", "minutes": 60, "energy": -10, "hunger": -5,
     "wood": 0, "food": +2, "mood": (0.30, 0.28, 0.15)},
    {"label": "Se reposer",     "minutes": 240, "energy": +35, "hunger": +8,
     "wood": 0, "food": 0,  "mood": (0.12, 0.10, 0.20)},
]


class GameScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._autosave_event = None
        self._tick_event = None

        root = FloatLayout()
        # Ciel pilote par l'horloge de la partie (time_scale=0 : pas
        # d'avance auto, on le cale via set_seconds dans refresh()).
        self.background = AnimatedBackground(time_scale=0, size_hint=(1, 1),
                                             pos_hint={"x": 0, "y": 0})
        root.add_widget(self.background)

        column = BoxLayout(orientation="vertical", padding=16, spacing=8,
                           size_hint=(0.92, 0.94),
                           pos_hint={"center_x": 0.5, "center_y": 0.5})

        # En-tete : temps + jour.
        self.header = scale_font(Label(text="", bold=True,
                            size_hint=(1, 0.1)), 0.026)
        column.add_widget(self.header)

        # Stats du joueur.
        self.stats = scale_font(Label(text="", halign="center",
                           size_hint=(1, 0.12)), 0.018)
        column.add_widget(self.stats)

        # Journal des dernieres actions.
        self.journal = scale_font(Label(text="", halign="center",
                             color=(0.85, 0.85, 0.85, 1), size_hint=(1, 0.22)),
                             0.016)
        column.add_widget(self.journal)

        # Boutons d'action (un par action definie).
        actions_box = BoxLayout(orientation="vertical", spacing=6,
                                size_hint=(1, 0.42))
        for action in ACTIONS:
            btn = scale_font(Button(text=action["label"]), 0.022)
            btn.bind(on_release=lambda _w, a=action: self.do_action(a))
            actions_box.add_widget(btn)
        column.add_widget(actions_box)

        # Retour au menu (sauvegarde avant de partir).
        back_btn = scale_font(Button(text="Menu (sauvegarde)",
                          size_hint=(1, 0.12)), 0.018)
        back_btn.bind(on_release=self.back_to_menu)
        column.add_widget(back_btn)

        root.add_widget(column)
        self.add_widget(root)

    # ------------------------------------------------------------------ #
    # Cycle de vie de l'ecran
    # ------------------------------------------------------------------ #
    def on_pre_enter(self):
        # L'etat a ete prepare par le menu : on rafraichit l'affichage.
        self.refresh()

    def on_enter(self):
        # Demarre la sauvegarde automatique periodique.
        self._autosave_event = Clock.schedule_interval(
            self._periodic_autosave, AUTOSAVE_SECONDS)
        # Demarre l'ecoulement continu du temps (1 fois par seconde).
        self._tick_event = Clock.schedule_interval(self._tick, 1.0)

    def on_leave(self):
        # Arrete la sauvegarde periodique quand on quitte l'ecran.
        if self._autosave_event is not None:
            self._autosave_event.cancel()
            self._autosave_event = None
        # Arrete l'horloge temps reel.
        if self._tick_event is not None:
            self._tick_event.cancel()
            self._tick_event = None

    def _tick(self, _dt):
        state = App.get_running_app().game_state
        if state is None:
            return
        state.tick(TIME_SCALE)
        self.refresh()

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #
    def do_action(self, action):
        state = App.get_running_app().game_state
        if state is None:
            return

        state.advance_time(action["minutes"])
        state.energy = _clamp(state.energy + action["energy"])
        state.hunger = _clamp(state.hunger + action["hunger"])
        state.wood += action["wood"]
        state.food += action["food"]
        state.action_count += 1
        state.add_log(f"Jour {state.day} {state.clock} - {action['label']}")

        self.refresh()
        # Sauvegarde APRES l'action.
        App.get_running_app().autosave()

    def back_to_menu(self, *_):
        App.get_running_app().autosave()
        self.manager.current = "menu"

    # ------------------------------------------------------------------ #
    # Affichage & sauvegarde periodique
    # ------------------------------------------------------------------ #
    def refresh(self):
        state = App.get_running_app().game_state
        if state is None:
            return
        self.header.text = f"Jour {state.day}   -   {state.clock}"
        self.stats.text = (
            f"Energie {state.energy}   Faim {state.hunger}\n"
            f"Bois {state.wood}   Nourriture {state.food}"
        )
        self.journal.text = "\n".join(state.log)
        # Le ciel suit l'heure de la partie (cycle jour/nuit).
        self.background.set_seconds(state.time_seconds)

    def _periodic_autosave(self, _dt):
        App.get_running_app().autosave()


def _clamp(value, low=0, high=100):
    return max(low, min(high, value))
