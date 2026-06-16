"""
Ecran CARTE : visualiser la carte et se deplacer.

On NE montre PAS l'heure. Se deplacer d'une case = parcourir 1 km : le temps
passe en AVANCE RAPIDE pendant la duree du trajet (court instant), boutons
desactives, puis on peut de nouveau agir.
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
from src.widgets.zone_scenery import ZoneScenery
from src.widgets.minimap import MiniMap
from src.widgets.styled_button import StyledButton
from src.widgets.responsive import scale_font

AUTOSAVE_SECONDS = 30
TIME_SCALE = 144              # 24h en 10 min
FAST_FORWARD_SCALE = 3600     # avance rapide : 1h de jeu / s reelle

# Cout d'un deplacement d'une case (1 km a pied).
MOVE_MINUTES = 12
MOVE_ENERGY = -3
MOVE_HUNGER = 2


class MapScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._autosave_event = None
        self._tick_event = None
        self._time_accum = 0.0
        self._ff_active = False
        self._ff_remaining = 0.0

        root = FloatLayout()
        self.background = AnimatedBackground(time_scale=0, size_hint=(1, 1),
                                             pos_hint={"x": 0, "y": 0})
        root.add_widget(self.background)
        # Decor du sol de la zone courante en fond (au lieu du ciel seul).
        self.scenery = ZoneScenery(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.scenery)
        self._scene_key = None

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

        # ---- Droite : etat, boussole, quitter ----
        right = BoxLayout(orientation="vertical", spacing=8, size_hint_x=0.44)

        self.status = scale_font(Label(text="", bold=True,
                                 color=(0.96, 0.82, 0.45, 1),
                                 size_hint_y=0.12), 0.022)
        right.add_widget(self.status)

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

        self.quit_btn = scale_font(StyledButton(text="Quitter la carte",
                                   size_hint_y=0.14), 0.02)
        self.quit_btn.bind(on_release=lambda *_: setattr(self.manager,
                                                         "current", "game"))
        right.add_widget(self.quit_btn)

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
        dt = min(dt, 0.25)
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
            state.advance_survival(whole)
        if self._ff_active and self._ff_remaining <= 0:
            self._ff_active = False
            App.get_running_app().autosave()
        self.refresh_hud()

    # ------------------------------------------------------------------ #
    def do_move(self, dx, dy):
        state = App.get_running_app().game_state
        if state is None or self._ff_active or not state.move(dx, dy):
            return
        state.energy = _clamp(state.energy + MOVE_ENERGY)
        state.hunger = _clamp(state.hunger + MOVE_HUNGER)
        state.action_count += 1
        state.add_log(f"{state.current_zone()} "
                      f"({state.player_x},{state.player_y})")
        self._ff_active = True
        self._ff_remaining = MOVE_MINUTES * 60.0
        self._time_accum = 0.0
        self.refresh_hud()
        self.minimap.refresh()
        App.get_running_app().autosave()

    # ------------------------------------------------------------------ #
    def refresh_hud(self):
        state = App.get_running_app().game_state
        if state is None:
            return
        zone = state.current_zone()
        self.status.text = "Deplacement..." if self._ff_active else ""
        self.zone_label.text = (
            f"[b]{zone}[/b]\n{world.zone_desc(zone)}\n"
            f"Case ({state.player_x},{state.player_y}) - 1x1 km"
        )
        # Boussole : desactivee en avance rapide, ou hors carte.
        self.btn_n.disabled = self._ff_active or not state.can_move(0, -1)
        self.btn_s.disabled = self._ff_active or not state.can_move(0, 1)
        self.btn_e.disabled = self._ff_active or not state.can_move(1, 0)
        self.btn_o.disabled = self._ff_active or not state.can_move(-1, 0)
        self.quit_btn.disabled = self._ff_active
        self.background.set_seconds(state.time_seconds)
        # Fond = decor du sol de la zone courante (redessine si la case change).
        key = (zone, state.player_x, state.player_y)
        if key != self._scene_key:
            self.scenery.set_scene(zone, state.player_x * 131 + state.player_y)
            self._scene_key = key

    def _periodic_autosave(self, _dt):
        if not self._ff_active:
            App.get_running_app().autosave()


def _clamp(value, low=0, high=100):
    return max(low, min(high, value))
