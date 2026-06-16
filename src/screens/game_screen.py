"""
Ecran de SURVIE (menu de jeu principal).

Sections :
- en haut a gauche : la ZONE actuelle (type + description) ;
- en haut a droite : l'ETAT du joueur (vie, energie, sommeil, faim, soif)
  + les ressources ;
- en bas a gauche : les boutons d'action (petits).

L'heure n'est pas affichee. Une action lance une AVANCE RAPIDE pendant sa
duree (boutons verrouilles). "Se reposer" est interdit si l'energie est trop
haute (pas assez fatigue pour dormir).
"""
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp

from src.game_state import _clamp100
from src.widgets.animated_background import AnimatedBackground
from src.widgets.zone_scenery import ZoneScenery
from src.widgets.player_hands import PlayerHands
from src.widgets.styled_button import StyledButton
from src.widgets.stat_bar import StatBar
from src.widgets.responsive import scale_font

AUTOSAVE_SECONDS = 30
TIME_SCALE = 144              # 24h en 10 min
FAST_FORWARD_SCALE = 3600     # avance rapide : 1h de jeu / s reelle

# Actions : effets ponctuels (la faim/soif/sommeil derivent en plus avec le
# temps). "requires_sleep" => possible seulement si on est assez fatigue.
ACTIONS = [
    {"label": "Explorer",          "minutes": 90,  "energy": -10, "food": 1},
    {"label": "Couper du bois",    "minutes": 120, "energy": -15, "wood": 3},
    {"label": "Chercher a manger", "minutes": 60,  "energy": -5,
     "hunger": -25, "food": 2},
    {"label": "Boire",             "minutes": 10,  "thirst": -40,
     "type": "drink"},
    {"label": "Remplir gourde",    "minutes": 15,  "type": "fill"},
    {"label": "Se reposer",        "minutes": 240, "energy": 35, "sleep": 50,
     "requires_sleep": True},
]


def _action_available(state, action):
    """Une action est-elle realisable dans l'etat / la zone actuels ?"""
    if action.get("requires_sleep") and not state.can_sleep():
        return False
    if action.get("type") == "drink":
        # Boire : il faut un ruisseau ici OU de l'eau dans la gourde.
        return state.has_water_source() or state.water > 0
    if action.get("type") == "fill":
        # Remplir la gourde : seulement a un ruisseau.
        return state.has_water_source()
    return True


def _add_panel(widget, alpha=0.34):
    """Ajoute un panneau translucide arrondi derriere un widget."""
    with widget.canvas.before:
        Color(0, 0, 0, alpha)
        rect = RoundedRectangle(radius=[dp(14)])

    def _sync(*_):
        rect.pos = widget.pos
        rect.size = widget.size
    widget.bind(pos=_sync, size=_sync)


class GameScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._autosave_event = None
        self._tick_event = None
        self._time_accum = 0.0
        self._ff_active = False
        self._ff_remaining = 0.0
        self._ff_label = ""
        self._scene_key = None

        root = FloatLayout()
        self.background = AnimatedBackground(time_scale=0, size_hint=(1, 1),
                                             pos_hint={"x": 0, "y": 0})
        root.add_widget(self.background)
        self.scenery = ZoneScenery(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.scenery)
        # Mains du joueur (vue 1re personne), devant le decor.
        self.hands = PlayerHands(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.hands)

        # ---- Section ZONE (haut gauche) ----
        zone_box = BoxLayout(orientation="vertical", padding=dp(10), spacing=4,
                             size_hint=(0.42, 0.22),
                             pos_hint={"x": 0.02, "top": 0.98})
        _add_panel(zone_box)
        zone_box.add_widget(scale_font(Label(text="ZONE", bold=True,
                            color=(0.96, 0.82, 0.45, 1), size_hint=(1, 0.35)),
                            0.02))
        self.zone_name = scale_font(Label(text="", bold=True,
                                    size_hint=(1, 0.35)), 0.028)
        zone_box.add_widget(self.zone_name)
        self.zone_desc = scale_font(Label(text="", halign="center",
                                    valign="middle",
                                    color=(0.85, 0.88, 0.9, 1),
                                    size_hint=(1, 0.30)), 0.016)
        self.zone_desc.bind(size=lambda w, *_: setattr(
            w, "text_size", (w.width, None)))
        zone_box.add_widget(self.zone_desc)
        root.add_widget(zone_box)

        # ---- Section ETAT / stats (haut droite) ----
        stats_box = BoxLayout(orientation="vertical", padding=dp(10),
                              spacing=dp(5), size_hint=(0.40, 0.56),
                              pos_hint={"right": 0.98, "top": 0.98})
        _add_panel(stats_box)
        stats_box.add_widget(scale_font(Label(text="ETAT", bold=True,
                             color=(0.96, 0.82, 0.45, 1), size_hint_y=0.7),
                             0.02))
        self.bar_health = StatBar("Vie", (0.85, 0.30, 0.30))
        self.bar_energy = StatBar("Energie", (0.95, 0.80, 0.30))
        self.bar_sleep = StatBar("Sommeil", (0.45, 0.55, 0.95))
        self.bar_hunger = StatBar("Faim", (0.85, 0.55, 0.25))
        self.bar_thirst = StatBar("Soif", (0.30, 0.70, 0.92))
        for bar in (self.bar_health, self.bar_energy, self.bar_sleep,
                    self.bar_hunger, self.bar_thirst):
            stats_box.add_widget(bar)
        self.resources = scale_font(Label(text="", halign="center",
                                    color=(0.85, 0.88, 0.9, 1), size_hint_y=0.7),
                                    0.016)
        stats_box.add_widget(self.resources)
        root.add_widget(stats_box)

        # ---- Etat d'action (haut centre) ----
        self.status = scale_font(Label(text="", bold=True,
                                 color=(0.96, 0.82, 0.45, 1),
                                 size_hint=(0.5, 0.08),
                                 pos_hint={"center_x": 0.5, "top": 0.99}), 0.022)
        root.add_widget(self.status)

        # ---- Boutons (bas gauche, petits) ----
        buttons = BoxLayout(orientation="vertical", spacing=4,
                            size_hint=(0.30, 0.56),
                            pos_hint={"x": 0.02, "y": 0.03})
        self._action_buttons = []   # (bouton, action)
        for action in ACTIONS:
            btn = scale_font(StyledButton(text=action["label"]), 0.016)
            btn.bind(on_release=lambda _w, a=action: self.do_action(a))
            buttons.add_widget(btn)
            self._action_buttons.append((btn, action))

        self.map_btn = scale_font(StyledButton(text="Carte"), 0.016)
        self.map_btn.bind(on_release=lambda *_: setattr(self.manager, "current",
                                                        "map"))
        buttons.add_widget(self.map_btn)

        self.back_btn = scale_font(StyledButton(text="Menu"), 0.016)
        self.back_btn.bind(on_release=self.back_to_menu)
        buttons.add_widget(self.back_btn)
        root.add_widget(buttons)

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
            state.advance_survival(whole)   # faim/soif/sommeil/vie derivent
        if self._ff_active and self._ff_remaining <= 0:
            self._finish_action()
        self.refresh()

    # ------------------------------------------------------------------ #
    def do_action(self, action):
        state = App.get_running_app().game_state
        if state is None or self._ff_active:
            return
        if not _action_available(state, action):
            return
        atype = action.get("type")
        # Eau : remplir la gourde au ruisseau ; boire consomme la gourde sauf
        # si on boit directement a un ruisseau.
        if atype == "fill":
            state.water += 3
        elif atype == "drink" and not state.has_water_source():
            state.water = max(0, state.water - 1)

        state.health = _clamp100(state.health + action.get("health", 0))
        state.energy = _clamp100(state.energy + action.get("energy", 0))
        state.sleep = _clamp100(state.sleep + action.get("sleep", 0))
        state.hunger = _clamp100(state.hunger + action.get("hunger", 0))
        state.thirst = _clamp100(state.thirst + action.get("thirst", 0))
        state.wood += action.get("wood", 0)
        state.food += action.get("food", 0)
        state.action_count += 1
        state.add_log(action["label"])
        self._ff_active = True
        self._ff_remaining = action["minutes"] * 60.0
        self._ff_label = action["label"]
        self._time_accum = 0.0
        self.refresh()
        App.get_running_app().autosave()

    def _finish_action(self):
        self._ff_active = False
        self._ff_label = ""
        App.get_running_app().autosave()

    def back_to_menu(self, *_):
        App.get_running_app().autosave()
        self.manager.current = "menu"

    # ------------------------------------------------------------------ #
    def refresh(self):
        state = App.get_running_app().game_state
        if state is None:
            return
        zone = state.current_zone()
        self.zone_name.text = zone
        from src import world
        desc = world.zone_desc(zone)
        if state.has_water_source():
            desc += "\nUn ruisseau d'eau potable coule ici."
        self.zone_desc.text = desc
        self.status.text = f"{self._ff_label}..." if self._ff_active else ""

        self.bar_health.set_value(state.health)
        self.bar_energy.set_value(state.energy)
        self.bar_sleep.set_value(state.sleep)
        self.bar_hunger.set_value(state.hunger)
        self.bar_thirst.set_value(state.thirst)
        self.resources.text = (f"Bois {state.wood}   Nourriture {state.food}"
                               f"   Eau {state.water}")

        # Boutons : tout verrouille en avance rapide ; sinon selon la zone /
        # l'etat (dormir, boire, remplir la gourde).
        for btn, action in self._action_buttons:
            btn.disabled = self._ff_active or not _action_available(state, action)
        self.map_btn.disabled = self._ff_active
        self.back_btn.disabled = self._ff_active

        self.background.set_seconds(state.time_seconds)
        key = (zone, state.player_x, state.player_y)
        if key != self._scene_key:
            self.scenery.set_scene(zone, state.player_x * 131 + state.player_y)
            self._scene_key = key

    def _periodic_autosave(self, _dt):
        if not self._ff_active:
            App.get_running_app().autosave()
