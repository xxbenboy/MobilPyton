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
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.metrics import dp

from src import items
from src.widgets.animated_background import AnimatedBackground, night_darkness
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


def _btn_font(w, *_):
    """Taille de police d'un bouton, divisee par le nombre de lignes du texte."""
    lines = (w.text or "").count("\n") + 1
    w.font_size = max(9, w.height * 0.34 / lines)


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

        # Voile de NUIT : assombrit ciel + sol selon l'heure, comme dans
        # l'ecran de jeu et la carte. Ajoute AVANT le HUD (col) qui reste
        # lisible.
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
            # Voile de nuit synchronise sur l'heure.
            self._night_color.a = night_darkness(state.time_seconds)
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

        hand_names = ["Main gauche", "Main droite"]

        # Objets TENUS : un bouton "Deposer" par main occupee.
        for i, item in enumerate(state.hands):
            if item is None:
                continue
            row = BoxLayout(orientation="horizontal", spacing=dp(6),
                            size_hint_y=None, height=dh(140))
            row.add_widget(ItemIcon(item, size_hint_x=0.24))
            lbl = Label(text=hand_names[i], halign="left", valign="middle",
                        size_hint_x=0.38, color=(0.96, 0.82, 0.45, 1))
            lbl.bind(size=lambda w, *_: (
                setattr(w, "font_size", max(8, w.height * 0.4)),
                setattr(w, "text_size", (w.width, None))))
            row.add_widget(lbl)
            drop = StyledButton(text="Deposer", size_hint_x=0.38, bold=True)
            drop.bind(size=_btn_font)
            drop.bind(on_release=lambda _w, idx=i: self._drop(idx))
            row.add_widget(drop)
            self.inventory_box.add_widget(row)

        # Objets AU SOL : deux boutons -> prendre dans la main gauche / droite
        # (desactives si la main visee est deja occupee).
        ground = state.ground_here()
        for name, count in sorted(ground.items()):
            row = BoxLayout(orientation="horizontal", spacing=dp(6),
                            size_hint_y=None, height=dh(140))
            row.add_widget(ItemIcon(name, count, size_hint_x=0.24))
            lbl = Label(text="À proximité", halign="left", valign="middle",
                        size_hint_x=0.38, color=(0.96, 0.82, 0.45, 1))
            lbl.bind(size=lambda w, *_: (
                setattr(w, "font_size", max(8, w.height * 0.4)),
                setattr(w, "text_size", (w.width, None))))
            row.add_widget(lbl)
            # Deux boutons 2x moins larges : ensemble ils occupent la place d'un
            # seul bouton. Desactives si la main est occupee ou si l'objet ne
            # peut pas etre tenu en main.
            hand_ok = items.is_hand_collectable(name)
            for hand_idx, text in ((0, "Prendre\nmain gauche"),
                                   (1, "Prendre\nmain droite")):
                take = StyledButton(text=text, halign="center", size_hint_x=0.19,
                                    bold=True)
                take.bind(size=_btn_font)
                take.disabled = (state.hands[hand_idx] is not None) or not hand_ok
                take.bind(on_release=lambda _w, n=name, h=hand_idx:
                          self._take(n, h))
                row.add_widget(take)
            self.inventory_box.add_widget(row)

        # Rien dans les mains ni au sol.
        if all(h is None for h in state.hands) and not ground:
            lbl = scale_font(Label(text="Rien à proximité.",
                             color=(0.8, 0.8, 0.85, 1), size_hint_y=None,
                             height=dh(40)), 0.018)
            self.inventory_box.add_widget(lbl)

        # Recettes
        self.recipe_box.clear_widgets()
        pool = state.craft_pool()
        for recipe in items.RECIPES:
            # Ingredients : ecriture plus FONCEE si l'ingredient manque.
            parts = []
            for k, v in recipe["ingredients"].items():
                label = f"{items.display_name(k)} x{v}"
                if pool.get(k, 0) >= v:
                    parts.append(label)
                else:
                    parts.append(f"[color=777777]{label}[/color]")
            ing = ", ".join(parts)

            row = BoxLayout(orientation="horizontal", spacing=dp(6),
                            size_hint_y=None, height=dh(70))
            # Image du resultat a gauche (ou "?" si aucune image n'existe).
            row.add_widget(ItemIcon(recipe["result"], show_name=False,
                                    size_hint_x=0.18))
            txt = scale_font(Label(
                text=f"[b]{items.display_name(recipe['result'])}[/b]\n{ing}",
                markup=True, halign="left", valign="middle", size_hint_x=0.50),
                0.016)
            txt.bind(size=lambda w, *_: setattr(w, "text_size",
                                                (w.width, w.height)))
            row.add_widget(txt)
            btn = scale_font(StyledButton(text="Fabriquer", size_hint_x=0.32),
                             0.018)
            btn.disabled = not state.can_craft(recipe)
            btn.bind(on_release=lambda _w, r=recipe: self._craft(r))
            row.add_widget(btn)
            self.recipe_box.add_widget(row)

    # ------------------------------------------------------------------ #
    def _take(self, name, hand):
        App.get_running_app().game_state.take_from_ground(name, hand)
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
