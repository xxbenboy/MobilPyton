"""
Ecran de SURVIE (le "menu jouable").

Affiche jour/heure, stats du joueur, un journal, et des actions qui font
avancer le temps. Un bouton "Carte" ouvre l'ecran de carte (deplacement), un
bouton "Menu" revient a l'accueil. Le ciel suit l'horloge de la partie.

Sauvegarde automatique : periodique, apres chaque action, et avant la
fermeture (geree dans game.py).
"""
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

from src.widgets.animated_background import AnimatedBackground
from src.widgets.zone_scenery import ZoneScenery
from src.widgets.styled_button import StyledButton
from src.widgets.responsive import scale_font

AUTOSAVE_SECONDS = 30
# Vitesse du temps en partie : 24h en 10 min => 86400 / 600 = 144 secondes de
# jeu par seconde reelle.
TIME_SCALE = 144

# Actions de survie : libelle, minutes consommees, effets sur les stats.
ACTIONS = [
    {"label": "Explorer",          "minutes": 90,  "energy": -15, "hunger": 10,
     "wood": 0, "food": 1},
    {"label": "Couper du bois",    "minutes": 120, "energy": -20, "hunger": 12,
     "wood": 3, "food": 0},
    {"label": "Chercher a manger", "minutes": 60,  "energy": -10, "hunger": -5,
     "wood": 0, "food": 2},
    {"label": "Se reposer",        "minutes": 240, "energy": 35,  "hunger": 8,
     "wood": 0, "food": 0},
]


class GameScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._autosave_event = None
        self._tick_event = None
        self._time_accum = 0.0        # secondes de jeu en attente (fluide)

        root = FloatLayout()
        self.background = AnimatedBackground(time_scale=0, size_hint=(1, 1),
                                             pos_hint={"x": 0, "y": 0})
        root.add_widget(self.background)
        # Decor de premier plan selon la zone (foret, champ, montagne, lac).
        self.scenery = ZoneScenery(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.scenery)
        self._scene_key = None

        column = BoxLayout(orientation="vertical", padding=16, spacing=8,
                           size_hint=(0.92, 0.94),
                           pos_hint={"center_x": 0.5, "center_y": 0.5})

        self.header = scale_font(Label(text="", bold=True, size_hint=(1, 0.1)),
                                 0.026)
        column.add_widget(self.header)

        self.stats = scale_font(Label(text="", halign="center",
                                      size_hint=(1, 0.12)), 0.018)
        column.add_widget(self.stats)

        self.journal = scale_font(Label(text="", halign="center",
                                  color=(0.85, 0.88, 0.9, 1),
                                  size_hint=(1, 0.2)), 0.016)
        column.add_widget(self.journal)

        actions_box = BoxLayout(orientation="vertical", spacing=6,
                                size_hint=(1, 0.36))
        for action in ACTIONS:
            btn = scale_font(StyledButton(text=action["label"]), 0.02)
            btn.bind(on_release=lambda _w, a=action: self.do_action(a))
            actions_box.add_widget(btn)
        column.add_widget(actions_box)

        map_btn = scale_font(StyledButton(text="Carte", size_hint=(1, 0.1)),
                             0.022)
        map_btn.bind(on_release=lambda *_: setattr(self.manager, "current",
                                                   "map"))
        column.add_widget(map_btn)

        back_btn = scale_font(StyledButton(text="Menu (sauvegarde)",
                              size_hint=(1, 0.1)), 0.018)
        back_btn.bind(on_release=self.back_to_menu)
        column.add_widget(back_btn)

        root.add_widget(column)
        self.add_widget(root)

    # ------------------------------------------------------------------ #
    def on_pre_enter(self):
        self.refresh()

    def on_enter(self):
        self._autosave_event = Clock.schedule_interval(
            self._periodic_autosave, AUTOSAVE_SECONDS)
        # 60 fps : ecoulement du temps fluide (comme le fond du menu).
        self._tick_event = Clock.schedule_interval(self._tick, 1 / 60.0)

    def on_leave(self):
        for ev in ("_autosave_event", "_tick_event"):
            event = getattr(self, ev)
            if event is not None:
                event.cancel()
                setattr(self, ev, None)

    def _tick(self, dt):
        state = App.get_running_app().game_state
        if state is None:
            return
        # Independant du framerate : on se base sur le temps REEL ecoule (dt).
        # On plafonne dt pour eviter un bond apres un ralentissement / reveil.
        dt = min(dt, 0.25)
        # On accumule le temps reel * vitesse, et on n'ajoute que des secondes
        # entieres a l'horloge (pas de perte, et le rendu reste fluide).
        self._time_accum += dt * TIME_SCALE
        whole = int(self._time_accum)
        if whole:
            state.tick(whole)
            self._time_accum -= whole
        self.refresh()

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
        App.get_running_app().autosave()

    def back_to_menu(self, *_):
        App.get_running_app().autosave()
        self.manager.current = "menu"

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
        self.background.set_seconds(state.time_seconds)
        # Decor selon la zone : redessine seulement si la case a change.
        key = (state.current_zone(), state.player_x, state.player_y)
        if key != self._scene_key:
            self.scenery.set_scene(state.current_zone(),
                                   state.player_x * 131 + state.player_y)
            self._scene_key = key

    def _periodic_autosave(self, _dt):
        App.get_running_app().autosave()


def _clamp(value, low=0, high=100):
    return max(low, min(high, value))
