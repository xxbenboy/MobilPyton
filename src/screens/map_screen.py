"""
Ecran CARTE : visualiser la carte et les infos de la zone.

Le DEPLACEMENT se fait depuis l'ecran de jeu (bouton "Deplacer"), plus ici.
On NE montre PAS l'heure. Le temps continue de s'ecouler normalement pendant
qu'on consulte la carte.
"""
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle

from src import world
from src.widgets.animated_background import AnimatedBackground, night_darkness
from src.widgets.zone_scenery import ZoneScenery
from src.widgets.minimap import MiniMap
from src.widgets.styled_button import StyledButton
from src.widgets.responsive import scale_font

AUTOSAVE_SECONDS = 30
TIME_SCALE = 144              # 24h en 10 min


class MapScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._autosave_event = None
        self._tick_event = None
        self._time_accum = 0.0

        root = FloatLayout()
        self.background = AnimatedBackground(time_scale=0, size_hint=(1, 1),
                                             pos_hint={"x": 0, "y": 0})
        root.add_widget(self.background)
        # Decor du sol de la zone courante en fond (au lieu du ciel seul).
        self.scenery = ZoneScenery(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.scenery)
        self._scene_key = None

        # Voile de NUIT : assombrit le ciel + le sol selon l'heure (comme
        # dans l'ecran de jeu). Ajoute APRES decor, AVANT le HUD : le HUD
        # (minimap, labels, boutons) reste lisible meme la nuit.
        self.night = Widget(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        with self.night.canvas:
            self._night_color = Color(0.03, 0.05, 0.12, 0.0)
            self._night_rect = Rectangle(pos=self.night.pos,
                                         size=self.night.size)

        def _sync_night(*_):
            self._night_rect.pos = self.night.pos
            self._night_rect.size = self.night.size
        self.night.bind(pos=_sync_night, size=_sync_night)
        root.add_widget(self.night)

        # Carte + infos seulement (le deplacement est dans l'ecran de jeu).
        col = BoxLayout(orientation="vertical", padding=12, spacing=12,
                        size_hint=(0.96, 0.96),
                        pos_hint={"center_x": 0.5, "center_y": 0.5})

        self.minimap = MiniMap(size_hint_y=0.70)
        col.add_widget(self.minimap)

        self.zone_label = scale_font(Label(text="", markup=True,
                                     halign="center", valign="middle",
                                     size_hint_y=0.18), 0.02)
        self.zone_label.bind(size=lambda w, *_: setattr(
            w, "text_size", (w.width, None)))
        col.add_widget(self.zone_label)

        self.quit_btn = scale_font(StyledButton(text="Quitter la carte",
                                   size_hint_y=0.12), 0.024)
        self.quit_btn.bind(on_release=lambda *_: setattr(self.manager,
                                                         "current", "game"))
        col.add_widget(self.quit_btn)

        root.add_widget(col)
        self.add_widget(root)

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
        self._time_accum += dt * TIME_SCALE
        whole = int(self._time_accum)
        self._time_accum -= whole
        if whole:
            state.tick(whole)
            state.advance_survival(whole)
        self.refresh_hud()

    # ------------------------------------------------------------------ #
    def refresh_hud(self):
        state = App.get_running_app().game_state
        if state is None:
            return
        zone = state.current_zone()
        self.zone_label.text = (
            f"[b]{zone}[/b]\n{world.zone_desc(zone)}\n"
            f"Case ({state.player_x},{state.player_y}) - 1x1 km"
        )
        self.background.set_seconds(state.time_seconds)
        # Voile de nuit synchronise sur l'heure (alpha 0 le jour, max nuit).
        self._night_color.a = night_darkness(state.time_seconds)
        # Fond = vue VERS LE BAS du sol de la zone (on regarde la carte/le sol).
        key = (zone, state.player_x, state.player_y)
        if key != self._scene_key:
            self.scenery.set_ground(zone, state.player_x * 131 + state.player_y)
            self._scene_key = key

    def _periodic_autosave(self, _dt):
        App.get_running_app().autosave()
