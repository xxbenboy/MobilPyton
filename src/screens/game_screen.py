"""
Ecran de jeu : exploration de la carte generative.

A gauche  : la mini-carte (25x25) + les infos de la zone courante.
A droite  : jour/heure, stats du joueur, une boussole de deplacement
            (Nord / Sud / Est / Ouest) et le retour au menu.

Se deplacer d'une case = parcourir 1 km : ca fait avancer le temps et coute un
peu d'energie. Le ciel suit l'heure de la partie.

Sauvegarde automatique : periodique, apres chaque deplacement, et avant la
fermeture (geree dans game.py).
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
TIME_SCALE = 1            # secondes de jeu par seconde reelle (ecoulement)

# Cout d'un deplacement d'une case (1 km a pied).
MOVE_MINUTES = 12
MOVE_ENERGY = -3
MOVE_HUNGER = 2


class GameScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._autosave_event = None
        self._tick_event = None

        root = FloatLayout()
        # Ciel pilote par l'horloge de la partie (cale via set_seconds).
        self.background = AnimatedBackground(time_scale=0, size_hint=(1, 1),
                                             pos_hint={"x": 0, "y": 0})
        root.add_widget(self.background)

        main = BoxLayout(orientation="horizontal", padding=12, spacing=12,
                         size_hint=(0.96, 0.96),
                         pos_hint={"center_x": 0.5, "center_y": 0.5})

        # ---- Gauche : mini-carte + infos de zone ----
        left = BoxLayout(orientation="vertical", spacing=8, size_hint_x=0.52)
        self.minimap = MiniMap(size_hint_y=0.74)
        left.add_widget(self.minimap)
        self.zone_label = scale_font(Label(text="", halign="center",
                                           valign="middle",
                                           size_hint_y=0.26), 0.02)
        self.zone_label.bind(size=lambda w, *_: setattr(
            w, "text_size", (w.width, None)))
        left.add_widget(self.zone_label)
        main.add_widget(left)

        # ---- Droite : temps, stats, boussole, retour ----
        right = BoxLayout(orientation="vertical", spacing=8, size_hint_x=0.48)

        self.header = scale_font(Label(text="", bold=True, size_hint_y=0.12),
                                 0.026)
        right.add_widget(self.header)

        self.stats = scale_font(Label(text="", halign="center",
                                      size_hint_y=0.16), 0.018)
        right.add_widget(self.stats)

        # Boussole : grille 3x3, N/S/E/O en croix.
        cross = GridLayout(cols=3, spacing=6, size_hint_y=0.5)
        self.btn_n = self._move_btn("N", 0, -1)
        self.btn_s = self._move_btn("S", 0, 1)
        self.btn_e = self._move_btn("E", 1, 0)
        self.btn_o = self._move_btn("O", -1, 0)
        cross.add_widget(Widget())
        cross.add_widget(self.btn_n)
        cross.add_widget(Widget())
        cross.add_widget(self.btn_o)
        cross.add_widget(Widget())
        cross.add_widget(self.btn_e)
        cross.add_widget(Widget())
        cross.add_widget(self.btn_s)
        cross.add_widget(Widget())
        right.add_widget(cross)

        back_btn = scale_font(StyledButton(text="Menu (sauvegarde)",
                              size_hint_y=0.12), 0.018)
        back_btn.bind(on_release=self.back_to_menu)
        right.add_widget(back_btn)

        main.add_widget(right)
        root.add_widget(main)
        self.add_widget(root)

    def _move_btn(self, label, dx, dy):
        btn = scale_font(StyledButton(text=label), 0.03)
        btn.bind(on_release=lambda _w: self.do_move(dx, dy))
        return btn

    # ------------------------------------------------------------------ #
    # Cycle de vie
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
        self.refresh_hud()          # met a jour heure + ciel (pas la carte)

    # ------------------------------------------------------------------ #
    # Deplacement
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

    def back_to_menu(self, *_):
        App.get_running_app().autosave()
        self.manager.current = "menu"

    # ------------------------------------------------------------------ #
    # Affichage
    # ------------------------------------------------------------------ #
    def refresh_hud(self):
        state = App.get_running_app().game_state
        if state is None:
            return
        zone = state.current_zone()
        self.header.text = f"Jour {state.day}   -   {state.clock}"
        self.stats.text = (
            f"Energie {state.energy}   Faim {state.hunger}\n"
            f"Bois {state.wood}   Nourriture {state.food}"
        )
        self.zone_label.text = (
            f"[b]{zone}[/b]\n{world.zone_desc(zone)}\n"
            f"Case ({state.player_x},{state.player_y}) - 1x1 km"
        )
        self.zone_label.markup = True
        # Boussole : on grise les directions hors carte.
        self.btn_n.disabled = not state.can_move(0, -1)
        self.btn_s.disabled = not state.can_move(0, 1)
        self.btn_e.disabled = not state.can_move(1, 0)
        self.btn_o.disabled = not state.can_move(-1, 0)
        # Ciel cale sur l'heure de la partie.
        self.background.set_seconds(state.time_seconds)

    def _periodic_autosave(self, _dt):
        App.get_running_app().autosave()


def _clamp(value, low=0, high=100):
    return max(low, min(high, value))
