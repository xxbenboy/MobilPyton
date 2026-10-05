"""
Ecran CARTE : visualiser la carte et les infos de la zone.

Le DEPLACEMENT se fait depuis l'ecran de jeu (bouton "Deplacer"), plus ici.
On NE montre PAS l'heure. Le temps continue de s'ecouler normalement pendant
qu'on consulte la carte.

DERRIERE LA CARTE, LA CASE A 360 DEGRES (voir widgets/vue360.py) : le meme
tour que le jeu, qu'on fait tourner en glissant le doigt hors de la carte et
des boutons. On regarde ainsi autour de soi en lisant la carte.
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
from src.widgets.animated_background import night_darkness
from src.widgets import daylight
from src.widgets.vue360 import Vue360
from src.widgets.minimap import MiniMap
from src.widgets.styled_button import StyledButton
from src.widgets.responsive import scale_font
from src.widgets.lieu_toggle import lieu_toggle

AUTOSAVE_SECONDS = 30
TIME_SCALE = 144              # 24h en 10 min


class MapScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._autosave_event = None
        self._tick_event = None
        self._time_accum = 0.0

        root = FloatLayout()
        # La case en fond, sur tout le tour, comme dans le jeu (voir
        # refresh_hud) : elle tourne au doigt.
        self.vue = Vue360(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.vue)

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

        # Titre a deux volets : "CARTE / zone". Le volet sombre mene a ce
        # qu'on a sous la main, sans repasser par l'ecran de jeu.
        self.toggle = lieu_toggle(self, "map", size_hint_y=0.10)
        col.add_widget(self.toggle)

        self.minimap = MiniMap(size_hint_y=0.60)
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
        # On regarde d'abord ou l'on regardait dans le jeu.
        state = App.get_running_app().game_state
        if state is not None:
            self.vue.regarde(state.facing * 90.0, 0.0)
        self.minimap.regard = self.vue.lacet
        self.refresh_hud()
        self.minimap.refresh()
        self.toggle.refresh()

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

    # -- le doigt qui fait tourner la vue -------------------------------- #
    def on_touch_down(self, touch):
        if super().on_touch_down(touch):
            return True                 # un bouton, le volet...
        return self.vue.commence(touch)

    def on_touch_move(self, touch):
        if self.vue.glisse(touch):
            # La fleche de la carte suit le regard.
            self.minimap.set_regard(self.vue.lacet)
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if self.vue.leve(touch):
            return True
        return super().on_touch_up(touch)

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
        # Le voile de nuit prend AUSSI la teinte de l'heure.
        self._night_color.rgb = daylight.veil_color(state.time_seconds)
        self._night_color.a = night_darkness(state.time_seconds)
        # FOND : LA CASE, telle qu'elle est -- la meme que le jeu, par la
        # meme methode, a l'heure et au temps qu'il fait. Rien n'est
        # redessine d'une image a l'autre tant que la case ne change pas
        # (voir montre_la_case).
        self.vue.montre(state)

    def _periodic_autosave(self, _dt):
        App.get_running_app().autosave()
