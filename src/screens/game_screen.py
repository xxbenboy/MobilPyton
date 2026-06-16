"""
Ecran de SURVIE (le "menu jouable").

On NE montre PAS l'heure : on la devine au ciel. Quand on lance une action,
le temps ne saute pas d'un coup : il passe en AVANCE RAPIDE pendant la duree
de l'action (un court instant), boutons desactives. A la fin, on peut de
nouveau agir.

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
# Ecoulement normal du temps : 24h en 10 min => 144 s de jeu / s reelle.
TIME_SCALE = 144
# Avance rapide pendant une action : 1 heure de jeu par seconde reelle.
# (une action de 90 min passe donc en ~1,5 s ; 4h de repos en ~4 s)
FAST_FORWARD_SCALE = 3600

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
        self._time_accum = 0.0
        # Avance rapide en cours ?
        self._ff_active = False
        self._ff_remaining = 0.0       # secondes de jeu restantes a passer
        self._ff_label = ""

        root = FloatLayout()
        self.background = AnimatedBackground(time_scale=0, size_hint=(1, 1),
                                             pos_hint={"x": 0, "y": 0})
        root.add_widget(self.background)
        self.scenery = ZoneScenery(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.scenery)
        self._scene_key = None

        column = BoxLayout(orientation="vertical", padding=16, spacing=8,
                           size_hint=(0.92, 0.94),
                           pos_hint={"center_x": 0.5, "center_y": 0.5})

        # Ligne d'etat : vide au repos, "Action en cours..." en avance rapide.
        self.status = scale_font(Label(text="", bold=True,
                                 color=(0.96, 0.82, 0.45, 1),
                                 size_hint=(1, 0.1)), 0.024)
        column.add_widget(self.status)

        self.stats = scale_font(Label(text="", halign="center",
                                      size_hint=(1, 0.14)), 0.018)
        column.add_widget(self.stats)

        self.journal = scale_font(Label(text="", halign="center",
                                  color=(0.85, 0.88, 0.9, 1),
                                  size_hint=(1, 0.2)), 0.016)
        column.add_widget(self.journal)

        actions_box = BoxLayout(orientation="vertical", spacing=6,
                                size_hint=(1, 0.34))
        self._action_buttons = []
        for action in ACTIONS:
            btn = scale_font(StyledButton(text=action["label"]), 0.02)
            btn.bind(on_release=lambda _w, a=action: self.do_action(a))
            actions_box.add_widget(btn)
            self._action_buttons.append(btn)
        column.add_widget(actions_box)

        self.map_btn = scale_font(StyledButton(text="Carte", size_hint=(1, 0.1)),
                                  0.022)
        self.map_btn.bind(on_release=lambda *_: setattr(self.manager, "current",
                                                        "map"))
        column.add_widget(self.map_btn)

        self.back_btn = scale_font(StyledButton(text="Menu (sauvegarde)",
                                   size_hint=(1, 0.1)), 0.018)
        self.back_btn.bind(on_release=self.back_to_menu)
        column.add_widget(self.back_btn)

        root.add_widget(column)
        self.add_widget(root)

    # ------------------------------------------------------------------ #
    def on_pre_enter(self):
        self.refresh()

    def on_enter(self):
        self._autosave_event = Clock.schedule_interval(
            self._periodic_autosave, AUTOSAVE_SECONDS)
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
        dt = min(dt, 0.25)             # independant du framerate + anti-bond
        scale = FAST_FORWARD_SCALE if self._ff_active else TIME_SCALE
        self._time_accum += dt * scale
        whole = int(self._time_accum)
        self._time_accum -= whole
        if self._ff_active:
            rem = int(self._ff_remaining)
            if whole > rem:
                whole = rem
            self._ff_remaining -= whole
        if whole:
            state.tick(whole)
        if self._ff_active and self._ff_remaining <= 0:
            self._finish_action()
        self.refresh()

    # ------------------------------------------------------------------ #
    def do_action(self, action):
        state = App.get_running_app().game_state
        if state is None or self._ff_active:
            return
        # Effets appliques tout de suite (robuste si l'app est coupee).
        state.energy = _clamp(state.energy + action["energy"])
        state.hunger = _clamp(state.hunger + action["hunger"])
        state.wood += action["wood"]
        state.food += action["food"]
        state.action_count += 1
        state.add_log(action["label"])
        # Demarre l'avance rapide pendant la duree de l'action.
        self._ff_active = True
        self._ff_remaining = action["minutes"] * 60.0
        self._ff_label = action["label"]
        self._time_accum = 0.0
        self._set_locked(True)
        self.refresh()
        App.get_running_app().autosave()

    def _finish_action(self):
        self._ff_active = False
        self._ff_label = ""
        self._set_locked(False)
        App.get_running_app().autosave()

    def _set_locked(self, locked):
        for b in self._action_buttons:
            b.disabled = locked
        self.map_btn.disabled = locked
        self.back_btn.disabled = locked

    def back_to_menu(self, *_):
        App.get_running_app().autosave()
        self.manager.current = "menu"

    # ------------------------------------------------------------------ #
    def refresh(self):
        state = App.get_running_app().game_state
        if state is None:
            return
        self.status.text = f"{self._ff_label}..." if self._ff_active else ""
        self.stats.text = (
            f"Energie {state.energy}   Faim {state.hunger}\n"
            f"Bois {state.wood}   Nourriture {state.food}"
        )
        self.journal.text = "\n".join(state.log)
        self.background.set_seconds(state.time_seconds)
        key = (state.current_zone(), state.player_x, state.player_y)
        if key != self._scene_key:
            self.scenery.set_scene(state.current_zone(),
                                   state.player_x * 131 + state.player_y)
            self._scene_key = key

    def _periodic_autosave(self, _dt):
        if not self._ff_active:        # on ne sauvegarde pas en plein milieu
            App.get_running_app().autosave()


def _clamp(value, low=0, high=100):
    return max(low, min(high, value))
