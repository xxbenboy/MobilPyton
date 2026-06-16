"""
Ecran CARTE : visualiser la carte et se deplacer.

A gauche : la mini-carte (25x25) + les infos de la zone courante.
A droite : une boussole Nord / Sud / Est / Ouest et un bouton pour revenir a
l'ecran de survie.

Se deplacer d'une case = parcourir 1 km : ca fait avancer le temps et coute un
peu d'energie. Le temps continue de s'ecouler tant qu'on est sur la carte.
"""
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label

from src import world
from src.widgets.animated_background import AnimatedBackground
from src.widgets.minimap import MiniMap
from src.widgets.styled_button import StyledButton
from src.widgets.responsive import scale_font

AUTOSAVE_SECONDS = 30
# 24h en 10 min => 86400 / 600 = 144 secondes de jeu par seconde reelle.
TIME_SCALE = 144

# Cout d'un deplacement d'une case (1 km a pied).
MOVE_MINUTES = 12
MOVE_ENERGY = -3
MOVE_HUNGER = 2


class MapScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._autosave_event = None
        self._tick_event = None

        root = FloatLayout()
        self.background = AnimatedBackground(time_scale=0, size_hint=(1, 1),
                                             pos_hint={"x": 0, "y": 0})
        root.add_widget(self.background)

        main = BoxLayout(orientation="horizontal", padding=12, spacing=12,
                         size_hint=(0.96, 0.96),
                         pos_hint={"center_x": 0.5, "center_y": 0.5})

        # ---- Gauche : mini-carte + infos zone ----
        left = BoxLayout(orientation="vertical", spacing=8, size_hint_x=0.56)
        self.minimap = MiniMap(size_hint_y=0.76)
        left.add_widget(self.minimap)
        self.zone_label = scale_font(Label(text="", markup=True,
                                     halign="center", valign="middle",
                                     size_hint_y=0.24), 0.02)
        self.zone_label.bind(size=lambda w, *_: setattr(
            w, "text_size", (w.width, None)))
        left.add_widget(self.zone_label)
        main.add_widget(left)

        # ---- Droite : heure, boussole, quitter ----
        right = BoxLayout(orientation="vertical", spacing=8, size_hint_x=0.44)

        self.header = scale_font(Label(text="", bold=True, size_hint_y=0.12),
                                 0.024)
        right.add_widget(self.header)

        cross = GridLayout(cols=3, spacing=6, size_hint_y=0.62)
        self.btn_n = self._move_btn("N", 0, -1)
        self.btn_s = self._move_btn("S", 0, 1)
        self.btn_e = self._move_btn("E", 1, 0)
        self.btn_o = self._move_btn("O", -1, 0)
        for w in (Widget(), self.btn_n, Widget(),
                  self.btn_o, Widget(), self.btn_e,
                  Widget(), self.btn_s, Widget()):
            cross.add_widget(w)
        right.add_widget(cross)

        quit_btn = scale_font(StyledButton(text="Quitter la carte",
                              size_hint_y=0.14), 0.02)
        quit_btn.bind(on_release=lambda *_: setattr(self.manager, "current",
                                                    "game"))
        right.add_widget(quit_btn)

        main.add_widget(right)
        root.add_widget(main)
        self.add_widget(root)

    def _move_btn(self, label, dx, dy):
        btn = scale_font(StyledButton(text=label), 0.03)
        btn.bind(on_release=lambda _w: self.do_move(dx, dy))
        return btn

    # ------------------------------------------------------------------ #
    def on_pre_enter(self):
        self.refresh_hud()
        self.minimap.refresh()

    def on_enter(self):
        self._autosave_event = Clock.schedule_interval(
            self._periodic_autosave, AUTOSAVE_SECONDS)
        self._tick_event = Clock.schedule_interval(self._tick, 1.0)

    def on_leave(self):
        for ev in ("_autosave_event", "_tick_event"):
            event = getattr(self, ev)
            if event is not None:
                event.cancel()
                setattr(self, ev, None)

    def _tick(self, _dt):
        state = App.get_running_app().game_state
        if state is None:
            return
        state.tick(TIME_SCALE)
        self.refresh_hud()          # heure + ciel (pas la carte)

    # ------------------------------------------------------------------ #
    def do_move(self, dx, dy):
        state = App.get_running_app().game_state
        if state is None or not state.move(dx, dy):
            return
        state.advance_time(MOVE_MINUTES)
        state.energy = _clamp(state.energy + MOVE_ENERGY)
        state.hunger = _clamp(state.hunger + MOVE_HUNGER)
        state.action_count += 1
        state.add_log(f"Jour {state.day} {state.clock} - "
                      f"{state.current_zone()} ({state.player_x},{state.player_y})")
        self.refresh_hud()
        self.minimap.refresh()
        App.get_running_app().autosave()

    # ------------------------------------------------------------------ #
    def refresh_hud(self):
        state = App.get_running_app().game_state
        if state is None:
            return
        zone = state.current_zone()
        self.header.text = f"Jour {state.day}   -   {state.clock}"
        self.zone_label.text = (
            f"[b]{zone}[/b]\n{world.zone_desc(zone)}\n"
            f"Case ({state.player_x},{state.player_y}) - 1x1 km"
        )
        self.btn_n.disabled = not state.can_move(0, -1)
        self.btn_s.disabled = not state.can_move(0, 1)
        self.btn_e.disabled = not state.can_move(1, 0)
        self.btn_o.disabled = not state.can_move(-1, 0)
        self.background.set_seconds(state.time_seconds)

    def _periodic_autosave(self, _dt):
        App.get_running_app().autosave()


def _clamp(value, low=0, high=100):
    return max(low, min(high, value))
