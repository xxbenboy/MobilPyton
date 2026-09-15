"""
Ecran ATELIER : ce qu'on fabrique A L'ETABLI, avec ce qu'on y a pose.

Il ressemble au craft, et c'est voulu : trois colonnes aux memes mesures, la
bande des mains en bas, le meme glisser-deposer. On ne reapprend rien en y
entrant. Mais il obeit a une autre regle, et c'est toute sa raison d'etre :

    SEUL LE CONTENU DE L'ETABLI COMPTE. Ni les mains, ni le sac, ni ce qui
    traine autour. Il faut POSER sa matiere sur l'etabli avant de s'en servir.

Ce n'est pas une tracasserie. C'est ce qui separe le bricolage debout -- le
craft ordinaire, qui ratisse tout ce qu'on a a portee -- du travail d'atelier,
ou l'on s'installe. Et c'est ce qui donne un sens a l'endroit ou l'on a monte
l'atelier : sa matiere y reste, et le campement devient un lieu.

LA COLONNE DE DROITE A DEUX VOLETS, sac a dos et etabli, parce qu'il faut
constamment passer de l'un a l'autre pour charger l'etabli, et qu'ils ne
tiennent pas cote a cote sur un telephone. Le sac s'ouvre en premier : c'est
de la qu'on part quand on arrive les bras pleins.

On n'y entre que par le bouton Atelier de l'ecran de jeu, qui n'apparait que
s'il y a un atelier sur la case.
"""
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp

from src import items
from src.widgets.animated_background import AnimatedBackground, night_darkness
from src.widgets import daylight
from src.widgets.zone_scenery import ZoneScenery
from src.widgets.item_info import TappableIcon
from src.widgets.styled_button import StyledButton, TabButton
from src.widgets.panels import panel
from src.widgets.hand_slot import hands_row, item_text
from src.widgets.item_grid import fill_ground, fill_bag, fill_station
from src.widgets.drag_drop import DragDrop, make_highlightable
from src.widgets.responsive import (scale_font, dh, fit_text, TEXT_NORMAL,
                                    TEXT_SMALL, SIDE_SHARE, center_share,
                                    ROW_TITLE, ROW_BODY, ROW_HANDS, ROW_HINT,
                                    ROW_BACK, COL_TITLE, COL_LIST)

_DIM = (0.62, 0.64, 0.70, 1)


def _recipe_text_font(w, *_):
    """Texte d'une recette, renvoye a la ligne : voir craft_screen."""
    fit_text(w, TEXT_NORMAL, wrap=True)


def _fit_button_font(btn, *_):
    """Police d'un bouton aussi grande que possible sans deborder sa boite."""
    if btn.width <= 1 or btn.height <= 1:
        return
    f = btn.height * 0.42
    btn.text_size = (None, None)
    btn.font_size = f
    btn.texture_update()
    if btn.texture_size[0] > btn.width * 0.90:
        f = f * (btn.width * 0.90) / btn.texture_size[0]
    btn.font_size = max(10, f)


class WorkbenchScreen(DragDrop, Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Quel volet de la colonne de droite est ouvert : "bag" ou "station".
        self._right = "bag"

        root = FloatLayout()
        self.background = AnimatedBackground(time_scale=0, size_hint=(1, 1),
                                             pos_hint={"x": 0, "y": 0})
        root.add_widget(self.background)
        self.scenery = ZoneScenery(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.scenery)
        self._scene_key = None

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

        # LE NOM DE L'ETABLI, en haut. Il n'y en a qu'un pour l'instant, mais
        # il y en aura d'autres : savoir DEVANT LEQUEL on est dit du meme coup
        # pourquoi la liste des recettes est celle-la et pas une autre.
        self.title = scale_font(Label(text="Atelier", bold=True,
                                color=(0.96, 0.82, 0.45, 1),
                                size_hint=(1, ROW_TITLE)), 0.030)
        col.add_widget(self.title)

        # TROIS COLONNES aux mesures du craft : rien ne se deplace d'un ecran
        # a l'autre.
        body = BoxLayout(orientation="horizontal", spacing=dp(10),
                         size_hint=(1, ROW_BODY))

        # ---- Gauche : ce qui traine A PROXIMITE ----
        near = BoxLayout(orientation="vertical", spacing=dp(6),
                         size_hint_x=SIDE_SHARE)
        self.near_title = scale_font(Label(text="A proximite", bold=True,
                                     size_hint=(1, COL_TITLE)), 0.022)
        near.add_widget(self.near_title)
        sc0 = self.ground_scroll = make_highlightable(
            ScrollView(size_hint=(1, COL_LIST)))
        self.ground_box = BoxLayout(orientation="vertical", spacing=dp(4),
                                    size_hint_y=None)
        self.ground_box.bind(minimum_height=self.ground_box.setter("height"))
        sc0.add_widget(self.ground_box)
        near.add_widget(sc0)
        body.add_widget(near)

        rest = center_share()

        # ---- Milieu : les RECETTES DE CET ATELIER ----
        center = BoxLayout(orientation="vertical", spacing=dp(6),
                           size_hint_x=rest)
        self.recipe_title = scale_font(Label(text="Recettes", bold=True,
                                       size_hint=(1, COL_TITLE)), 0.022)
        center.add_widget(self.recipe_title)
        sc1 = ScrollView(size_hint=(1, COL_LIST))
        self.recipe_box = BoxLayout(orientation="vertical", spacing=dp(6),
                                    size_hint_y=None)
        self.recipe_box.bind(minimum_height=self.recipe_box.setter("height"))
        sc1.add_widget(self.recipe_box)
        center.add_widget(sc1)
        body.add_widget(center)

        # ---- Droite : SAC A DOS ou ETABLI, au choix ----
        right = BoxLayout(orientation="vertical", spacing=dp(6),
                          size_hint_x=rest)
        onglets = BoxLayout(orientation="horizontal", spacing=dp(4),
                            size_hint=(1, COL_TITLE))
        self.tab_bag = TabButton(text="Sac a dos", bold=True)
        self.tab_bag.bind(size=_fit_button_font, text=_fit_button_font)
        self.tab_bag.bind(on_release=lambda *_: self._show_right("bag"))
        self.tab_station = TabButton(text="Etabli", bold=True)
        self.tab_station.bind(size=_fit_button_font, text=_fit_button_font)
        self.tab_station.bind(
            on_release=lambda *_: self._show_right("station"))
        onglets.add_widget(self.tab_bag)
        onglets.add_widget(self.tab_station)
        right.add_widget(onglets)

        # Les deux panneaux existent des le depart ; un seul est DANS l'arbre
        # a la fois. C'est ce qui empeche le glisser-deposer d'attraper une
        # case du panneau cache : `hit` ecarte ce qui n'est plus a l'ecran.
        self.bag_scroll = make_highlightable(
            ScrollView(size_hint=(1, COL_LIST)))
        self.bag_box = BoxLayout(orientation="vertical", spacing=dp(4),
                                 size_hint_y=None)
        self.bag_box.bind(minimum_height=self.bag_box.setter("height"))
        self.bag_scroll.add_widget(self.bag_box)

        self.station_scroll = make_highlightable(
            ScrollView(size_hint=(1, COL_LIST)))
        self.station_box = BoxLayout(orientation="vertical", spacing=dp(4),
                                     size_hint_y=None)
        self.station_box.bind(
            minimum_height=self.station_box.setter("height"))
        self.station_scroll.add_widget(self.station_box)

        self.right_slot = BoxLayout(size_hint=(1, COL_LIST))
        right.add_widget(self.right_slot)
        body.add_widget(right)

        # Les deux titres de colonne vivent dans les onglets : fill_bag et
        # fill_station y ecrivent leur compte.
        self.bag_title = self.tab_bag
        self.station_title = self.tab_station

        col.add_widget(body)

        row, self.hand_slots = hands_row(size_hint=(1, ROW_HANDS))
        for slot in self.hand_slots:
            make_highlightable(slot)
        col.add_widget(row)

        self.hint = fit_text(Label(
            text="A l'etabli, seule compte la matiere POSEE dessus : glisse-y "
                 "ce qu'il te faut.", color=_DIM, halign="center",
            valign="middle", size_hint=(1, ROW_HINT)), TEXT_SMALL, wrap=True)
        col.add_widget(self.hint)

        back = scale_font(StyledButton(text="Retour",
                                       size_hint=(1, ROW_BACK)), 0.022)
        back.bind(on_release=lambda *_: setattr(self.manager,
                                                "current", "game"))
        col.add_widget(back)

        panel(col, alpha=0.45)
        root.add_widget(col)

        self.drag_layer = FloatLayout(size_hint=(1, 1),
                                      pos_hint={"x": 0, "y": 0})
        root.add_widget(self.drag_layer)
        self._root = root
        self._equip_slots = []
        self._bag_cells = []
        self._ground_cells = []
        self._station_cells = []
        self.init_drag()
        self.add_widget(root)
        self._show_right("bag")

    # ------------------------------------------------------------------ #
    def station_anchor(self):
        """(gx, gy) de l'atelier de la case, ou None. Lu par le melangeur."""
        state = App.get_running_app().game_state
        station = state.station_here() if state is not None else None
        return None if station is None else (station[1], station[2])

    def _show_right(self, which):
        """Bascule la colonne de droite entre le sac et l'etabli."""
        self._right = which
        self.right_slot.clear_widgets()
        self.right_slot.add_widget(self.bag_scroll if which == "bag"
                                   else self.station_scroll)
        self.tab_bag.selected = which == "bag"
        self.tab_station.selected = which == "station"
        # Un glisser en cours pointait peut-etre sur le panneau qu'on vient de
        # retirer : on l'abandonne plutot que de le laisser viser dans le vide.
        self._cancel_drag()

    # ------------------------------------------------------------------ #
    def on_pre_enter(self):
        state = App.get_running_app().game_state
        if state is not None:
            self.background.set_seconds(state.time_seconds)
            self.background.set_weather(state.effective_weather())
            self.scenery.set_wind(state.effective_weather())
            self._night_color.rgb = daylight.veil_color(state.time_seconds)
            self._night_color.a = night_darkness(state.time_seconds)
            self.scenery.set_daylight(state.time_seconds)
            zone = state.current_zone()
            key = (zone, state.player_x, state.player_y)
            if key != self._scene_key:
                self.scenery.set_ground(zone, state.player_x * 131
                                        + state.player_y)
                self._scene_key = key
        self.refresh()

    def on_leave(self):
        self._cancel_drag()
        if self._info is not None:
            self._info.close()

    def refresh(self):
        state = App.get_running_app().game_state
        if state is None:
            return
        station = state.station_here()
        if station is None:
            # L'atelier a disparu sous nos pieds (partie relue autrement,
            # bouton reste affiche...) : on ne montre pas un etabli vide, on
            # repart.
            self.manager.current = "game"
            return
        self.title.text = items.display_name(station[0])
        for slot in self.hand_slots:
            name = state.hands[slot.hand]
            slot.set_item(name, item_text(state, name))
        self._ground_cells = fill_ground(self.ground_box,
                                         self.near_title, state)
        self._bag_cells = fill_bag(self.bag_box, self.bag_title, state)
        self._station_cells = fill_station(self.station_box,
                                           self.station_title, state)
        self._fill_recipes(state, station)

    def _fill_recipes(self, state, station):
        """Les recettes de CET atelier, et rien d'autre.

        Pas de categories repliables ici : il n'y en a qu'une poignee, et les
        replier aurait cache la seule chose que l'ecran a a montrer."""
        self.recipe_box.clear_widgets()
        nom, gx, gy = station
        recettes = items.station_recipes(nom)
        prets = sum(1 for r in recettes if state.can_craft_at(r, gx, gy))
        self.recipe_title.text = "Recettes (%d/%d)" % (prets, len(recettes))
        if not recettes:
            self.recipe_box.add_widget(fit_text(Label(
                text="Cet atelier n'ouvre encore aucune recette.",
                color=_DIM, halign="center", valign="middle",
                size_hint_y=None, height=dh(120)), wrap=True))
            return
        pool = state.station_pool(gx, gy)
        for recipe in recettes:
            self.recipe_box.add_widget(self._recipe_row(state, recipe, pool,
                                                        gx, gy))

    def _recipe_row(self, state, recipe, pool, gx, gy):
        """Une rangee de recette. Ce qui manque SUR L'ETABLI est grise."""
        parts = []
        for k, v in recipe["ingredients"].items():
            label = f"{items.display_name(k)} x{v}"
            parts.append(label if pool.get(k, 0) >= v
                         else f"[color=777777]{label}[/color]")
        alts = recipe.get("any_of")
        if alts:
            label = " ou ".join(items.display_name(a) for a in alts)
            parts.append(label if state.station_choice(recipe, gx, gy)
                         else f"[color=777777]{label}[/color]")
        tool = recipe.get("tool")
        if tool:
            cost = int(round(recipe.get("tool_wear", 0.0) * 100))
            label = f"{items.display_name(tool)} (-{cost} %)"
            parts.append(label if pool.get(tool, 0) > 0
                         else f"[color=777777]{label}[/color]")
        minutes = int(recipe.get("minutes", 0))
        if minutes:
            parts.append("[color=c8b48c]%s[/color]"
                         % items.duree_texte(minutes))
        ing = ", ".join(parts)

        row = BoxLayout(orientation="horizontal", spacing=dp(6),
                        size_hint_y=None, height=dh(200))
        row.add_widget(TappableIcon(recipe["result"], self._show_info,
                                    show_name=False, size_hint_x=0.30))
        txt = Label(
            text=f"[b]{items.display_name(recipe['result'])}[/b]\n{ing}",
            markup=True, halign="left", valign="middle", size_hint_x=0.44)
        _recipe_text_font(txt)
        row.add_widget(txt)
        btn = StyledButton(text="Fabriquer", size_hint_x=0.26)
        btn.bind(size=_fit_button_font, text=_fit_button_font)
        btn.disabled = not state.can_craft_at(recipe, gx, gy)
        btn.bind(on_release=lambda _w, r=recipe: self._craft(r, gx, gy))
        row.add_widget(btn)
        return row

    def _craft(self, recipe, gx, gy):
        state = App.get_running_app().game_state
        if state is None or not state.do_craft_at(recipe, gx, gy):
            return
        App.get_running_app().autosave()
        # UN DEPOSABLE SORT DE L'ATELIER SANS ETRE UN OBJET : il attend sa
        # place, et le joueur tranche tout de suite -- exactement comme
        # depuis l'etabli du craft ordinaire.
        if state.pending_item() is not None:
            pose = self.manager.get_screen("place")
            pose._slot = None
            pose.mode = "place"
            pose._action_cell = None
            self.manager.current = "place"
            return
        self.refresh()
