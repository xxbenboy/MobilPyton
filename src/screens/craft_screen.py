"""
Ecran PROXIMITE & CRAFT.

- Mains : les 2 objets tenus (bouton "Deposer" pour les poser au sol).
- Au sol : les objets presents sur la case (avec leur nombre) ; bouton
  "Prendre" pour les ramasser (si les mains ne sont pas pleines).
- Recettes : ce qu'on peut fabriquer avec les objets en mains + au sol.

Les objets sont affiches via leur image (assets/items/<nom>.png) ou un "?".
"""
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp

from src import items
from src.game_state import HANDS_MAX
from src.widgets.animated_background import AnimatedBackground
from src.widgets.zone_scenery import ZoneScenery
from src.widgets.item_icon import ItemIcon
from src.widgets.styled_button import StyledButton
from src.widgets.responsive import scale_font, dh


def _panel(widget, alpha=0.45):
    with widget.canvas.before:
        Color(0, 0, 0, alpha)
        rect = RoundedRectangle(radius=[dp(12)])
    widget.bind(pos=lambda w, *_: setattr(rect, "pos", w.pos),
                size=lambda w, *_: setattr(rect, "size", w.size))


class CraftScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = FloatLayout()
        self.background = AnimatedBackground(time_scale=0, size_hint=(1, 1),
                                             pos_hint={"x": 0, "y": 0})
        root.add_widget(self.background)
        # Fond = vue VERS LE BAS du sol de la zone courante (comme la carte).
        self.scenery = ZoneScenery(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.scenery)
        self._scene_key = None

        col = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8),
                        size_hint=(0.96, 0.96),
                        pos_hint={"center_x": 0.5, "center_y": 0.5})

        col.add_widget(scale_font(Label(text="PROXIMITE & CRAFT", bold=True,
                       color=(0.96, 0.82, 0.45, 1), size_hint=(1, 0.08)), 0.03))

        body = BoxLayout(orientation="horizontal", spacing=dp(10),
                         size_hint=(1, 0.82))

        # ---- Gauche : sol + objets en main ----
        left = BoxLayout(orientation="vertical", spacing=dp(6), size_hint_x=0.5)
        left.add_widget(scale_font(Label(text="Inventaire", bold=True,
                        size_hint=(1, 0.10)), 0.022))
        sc1 = ScrollView(size_hint=(1, 0.90))
        self.inventory_box = BoxLayout(orientation="vertical", spacing=dp(4),
                                       size_hint_y=None)
        self.inventory_box.bind(minimum_height=self.inventory_box.setter("height"))
        sc1.add_widget(self.inventory_box)
        left.add_widget(sc1)
        body.add_widget(left)

        # ---- Droite : recettes ----
        right = BoxLayout(orientation="vertical", spacing=dp(6), size_hint_x=0.5)
        right.add_widget(scale_font(Label(text="Recettes", bold=True,
                         size_hint=(1, 0.10)), 0.022))
        sc2 = ScrollView(size_hint=(1, 0.90))
        self.recipe_box = BoxLayout(orientation="vertical", spacing=dp(6),
                                    size_hint_y=None)
        self.recipe_box.bind(minimum_height=self.recipe_box.setter("height"))
        sc2.add_widget(self.recipe_box)
        right.add_widget(sc2)
        body.add_widget(right)

        col.add_widget(body)

        back = scale_font(StyledButton(text="Retour", size_hint=(1, 0.10)), 0.022)
        back.bind(on_release=lambda *_: setattr(self.manager, "current", "game"))
        col.add_widget(back)

        _panel(col)
        root.add_widget(col)
        self.add_widget(root)

    # ------------------------------------------------------------------ #
    def on_pre_enter(self):
        state = App.get_running_app().game_state
        if state is not None:
            self.background.set_seconds(state.time_seconds)
            zone = state.current_zone()
            key = (zone, state.player_x, state.player_y)
            if key != self._scene_key:
                self.scenery.set_ground(zone, state.player_x * 131
                                        + state.player_y)
                self._scene_key = key
        self.refresh()

    def refresh(self):
        state = App.get_running_app().game_state
        if state is None:
            return

        # Inventaire (mains + sol)
        self.inventory_box.clear_widgets()
        
        # Afficher les objets en main
        if state.hands:
            hands_names = ["Main gauche", "Main droite"]
            for i, item in enumerate(state.hands):
                # Objet + Label + Bouton sur la même ligne
                row = BoxLayout(orientation="horizontal", spacing=dp(6),
                               size_hint_y=None, height=dh(140))
                row.add_widget(ItemIcon(item, size_hint_x=0.22))
                row.add_widget(Widget(size_hint_x=0.02))
                lbl = Label(text=hands_names[i], halign="left",
                                valign="middle", size_hint_x=0.51,
                                color=(0.96, 0.82, 0.45, 1))
                def _adjust_lbl_font(w, *_):
                    w.font_size = max(8, w.height * 0.4)
                lbl.bind(size=_adjust_lbl_font)
                lbl.bind(size=lambda w, *_: setattr(w, "text_size", (w.width, None)))
                row.add_widget(lbl)
                btn = scale_font(StyledButton(text="Deposer", size_hint_x=0.25),
                                0.008)
                def _adjust_btn_font(w, *_):
                    w.font_size = max(10, w.height * 0.35)
                btn.bind(size=_adjust_btn_font)
                btn.bind(on_release=lambda _w, idx=i: self._drop(idx))
                row.add_widget(btn)
                self.inventory_box.add_widget(row)
        
        # Afficher les objets au sol
        ground = state.ground_here()
        if ground:
            for name, count in sorted(ground.items()):
                row = BoxLayout(orientation="horizontal", spacing=dp(6),
                               size_hint_y=None, height=dh(140))
                row.add_widget(ItemIcon(name, count, size_hint_x=0.22))
                row.add_widget(Widget(size_hint_x=0.02))
                lbl = Label(text="À Proximité", halign="left",
                                valign="middle", size_hint_x=0.51,
                                color=(0.96, 0.82, 0.45, 1))
                def _adjust_lbl_font2(w, *_):
                    w.font_size = max(8, w.height * 0.4)
                lbl.bind(size=_adjust_lbl_font2)
                lbl.bind(size=lambda w, *_: setattr(w, "text_size", (w.width, None)))
                row.add_widget(lbl)
                take = scale_font(StyledButton(text="Prendre", size_hint_x=0.25),
                                 0.008)
                def _adjust_take_font(w, *_):
                    w.font_size = max(10, w.height * 0.35)
                take.bind(size=_adjust_take_font)
                take.disabled = state.hands_full()
                take.bind(on_release=lambda _w, n=name: self._take(n))
                row.add_widget(take)
                self.inventory_box.add_widget(row)
        elif not state.hands:
            lbl = scale_font(Label(text="Rien à proximité.",
                             color=(0.8, 0.8, 0.85, 1), size_hint_y=None,
                             height=dh(40)), 0.018)
            self.inventory_box.add_widget(lbl)

        # Recettes
        self.recipe_box.clear_widgets()
        for recipe in items.RECIPES:
            ing = ", ".join(f"{items.display_name(k)} x{v}"
                            for k, v in recipe["ingredients"].items())
            row = BoxLayout(orientation="horizontal", spacing=dp(6),
                            size_hint_y=None, height=dh(70))
            txt = scale_font(Label(
                text=f"[b]{items.display_name(recipe['result'])}[/b]\n{ing}",
                markup=True, halign="left", valign="middle", size_hint_x=0.62),
                0.016)
            txt.bind(size=lambda w, *_: setattr(w, "text_size",
                                                (w.width, w.height)))
            row.add_widget(txt)
            btn = scale_font(StyledButton(text="Fabriquer", size_hint_x=0.38),
                             0.018)
            btn.disabled = not state.can_craft(recipe)
            btn.bind(on_release=lambda _w, r=recipe: self._craft(r))
            row.add_widget(btn)
            self.recipe_box.add_widget(row)

    # ------------------------------------------------------------------ #
    def _take(self, name):
        App.get_running_app().game_state.take_from_ground(name)
        App.get_running_app().autosave()
        self.refresh()

    def _drop(self, index):
        App.get_running_app().game_state.drop_from_hands(index)
        App.get_running_app().autosave()
        self.refresh()

    def _craft(self, recipe):
        App.get_running_app().game_state.do_craft(recipe)
        App.get_running_app().autosave()
        self.refresh()
