"""
Ecran CRAFT : ce qu'on peut FABRIQUER avec ce qu'on a sous la main.

- A portee : les 2 objets tenus (bouton "Deposer" pour les poser au sol) et
  les objets presents sur la case (avec leur nombre ; bouton "Prendre" pour
  les ramasser, si les mains ne sont pas pleines).
- Recettes : ce qu'on peut fabriquer avec les objets en mains + au sol.

Le titre est un TITRE A DEUX VOLETS partage avec l'inventaire : les deux
ecrans montrent les memes objets sous deux angles, on passe de l'un a l'autre
en tapant le volet sombre (voir src/widgets/menu_toggle.py).

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
from src.widgets import daylight
from src.widgets.zone_scenery import ZoneScenery
from src.widgets.item_info import show_item_info, TappableIcon
from src.widgets.durability_bar import DurabilityBar
from src.widgets.styled_button import StyledButton, TabButton
from src.widgets.panels import panel
from src.widgets.responsive import (scale_font, dh, fit_text, TEXT_NORMAL,
                                    TEXT_TITLE, TEXT_SMALL, SIDE_SHARE,
                                    center_share, ROW_TITLE, ROW_BODY,
                                    ROW_HANDS, ROW_HINT, ROW_BACK,
                                    COL_TITLE, COL_LIST)
from src.widgets.menu_toggle import MenuToggle

# Gris des textes secondaires, comme dans l'inventaire.
_DIM = (0.62, 0.64, 0.70, 1)
# Hauteur d'une case du sol : l'image et son nom, puis les deux boutons.
_GROUND_CELL_H = 236
_BAG_CELL_H = 170


def _panel(widget, alpha=0.45):
    return panel(widget, alpha=alpha)


def _btn_font(w, *_):
    """Taille de police d'un bouton, divisee par le nombre de lignes du texte."""
    lines = (w.text or "").count("\n") + 1
    w.font_size = max(9, w.height * 0.34 / lines)


def _recipe_text_font(w, *_):
    """Texte d'une recette : la taille courante du jeu (voir fit_text)."""
    fit_text(w, TEXT_NORMAL)


def _fit_button_font(btn, *_):
    """Police d'un bouton aussi grande que possible SANS deborder sa boite,
    limitee a la fois par la hauteur ET par la largeur du texte.

    Necessaire car la rangee des recettes est plus haute : un calcul base
    seulement sur la hauteur ferait deborder le texte en largeur."""
    if btn.width <= 1 or btn.height <= 1:
        return
    f = btn.height * 0.42
    btn.text_size = (None, None)
    btn.font_size = f
    btn.texture_update()
    if btn.texture_size[0] > btn.width * 0.90:
        f = f * (btn.width * 0.90) / btn.texture_size[0]
    btn.font_size = max(10, f)


def _inv_label_font(w, *_):
    """Libelle d'une main : un cran au-dessus du texte courant."""
    fit_text(w, TEXT_TITLE)


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

        # Titre a deux volets : "inventaire / CRAFT". Les deux mots gardent
        # toujours la meme place, seule la surbrillance change d'ecran.
        col.add_widget(MenuToggle(self, "craft", size_hint=(1, ROW_TITLE)))

        # TROIS COLONNES, aux memes mesures que l'inventaire (gabarit commun
        # dans responsive.py) : a proximite / recettes / sac a dos. Basculer
        # d'un ecran a l'autre ne deplace donc aucune colonne -- on retrouve
        # chaque chose exactement ou on l'avait laissee.
        body = BoxLayout(orientation="horizontal", spacing=dp(10),
                         size_hint=(1, ROW_BODY))

        # ---- Gauche : ce qui traine A PROXIMITE ----
        near = BoxLayout(orientation="vertical", spacing=dp(6),
                         size_hint_x=SIDE_SHARE)
        self.near_title = scale_font(Label(text="A proximite", bold=True,
                                     size_hint=(1, COL_TITLE)), 0.022)
        near.add_widget(self.near_title)
        sc0 = ScrollView(size_hint=(1, COL_LIST))
        self.ground_box = BoxLayout(orientation="vertical", spacing=dp(4),
                                    size_hint_y=None)
        self.ground_box.bind(minimum_height=self.ground_box.setter("height"))
        sc0.add_widget(self.ground_box)
        near.add_widget(sc0)
        body.add_widget(near)

        rest = center_share()

        # ---- Milieu : les RECETTES ----
        center = BoxLayout(orientation="vertical", spacing=dp(6),
                           size_hint_x=rest)
        center.add_widget(scale_font(Label(text="Recettes", bold=True,
                                     size_hint=(1, COL_TITLE)), 0.022))
        sc1 = ScrollView(size_hint=(1, COL_LIST))
        self.recipe_box = BoxLayout(orientation="vertical", spacing=dp(6),
                                    size_hint_y=None)
        self.recipe_box.bind(minimum_height=self.recipe_box.setter("height"))
        sc1.add_widget(self.recipe_box)
        center.add_widget(sc1)
        body.add_widget(center)

        # ---- Droite : le SAC A DOS ----
        # Il compte comme matiere premiere (voir GameState.craft_pool) : ce
        # qu'on transporte se fabrique sans avoir a le poser par terre. Ses
        # cases n'ont donc pas de bouton -- il n'y a rien a en sortir.
        right = BoxLayout(orientation="vertical", spacing=dp(6),
                          size_hint_x=rest)
        self.bag_title = scale_font(Label(text="Sac a dos", bold=True,
                                    size_hint=(1, COL_TITLE)), 0.022)
        right.add_widget(self.bag_title)
        sc2 = ScrollView(size_hint=(1, COL_LIST))
        self.bag_box = BoxLayout(orientation="vertical", spacing=dp(4),
                                 size_hint_y=None)
        self.bag_box.bind(minimum_height=self.bag_box.setter("height"))
        sc2.add_widget(self.bag_box)
        right.add_widget(sc2)
        body.add_widget(right)

        col.add_widget(body)

        # ---- En bas : les MAINS, a la meme place que dans l'inventaire ----
        self.hands_row = BoxLayout(orientation="horizontal", spacing=dp(8),
                                   size_hint=(1, ROW_HANDS))
        col.add_widget(self.hands_row)

        self.hint = fit_text(Label(
            text="Le sac compte comme matiere : pas besoin d'en sortir les "
                 "objets pour fabriquer.", color=_DIM, halign="center",
            valign="middle", size_hint=(1, ROW_HINT)), TEXT_SMALL, wrap=True)
        col.add_widget(self.hint)

        back = scale_font(StyledButton(text="Retour",
                                       size_hint=(1, ROW_BACK)), 0.022)
        back.bind(on_release=lambda *_: setattr(self.manager, "current", "game"))
        col.add_widget(back)

        # Categories de recettes actuellement DEPLIEES.
        self._open_cats = set()

        _panel(col)
        root.add_widget(col)
        self._root = root
        self.add_widget(root)

    # ------------------------------------------------------------------ #
    def on_pre_enter(self):
        # A chaque ouverture de l'ecran, toutes les categories sont repliees.
        self._open_cats = set()
        state = App.get_running_app().game_state
        if state is not None:
            self.background.set_seconds(state.time_seconds)
            self.background.set_weather(state.effective_weather())
            self.scenery.set_wind(state.effective_weather())
            # Le voile de nuit prend AUSSI la teinte de l'heure, et le decor
            # suit le soleil (couleur de la lumiere, ombres portees).
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

    def refresh(self):
        state = App.get_running_app().game_state
        if state is None:
            return
        self._fill_hands(state)
        self._fill_ground(state)
        self._fill_bag(state)
        self._fill_recipes(state)

    # ------------------------------------------------------------------ #
    def _fill_hands(self, state):
        """Les deux mains, en bas de l'ecran : deposer, equiper.

        Elles etaient melangees aux objets du sol dans une seule colonne. Ici
        elles occupent la meme bande que dans l'inventaire : d'un ecran a
        l'autre, la main gauche reste la main gauche, au meme endroit."""
        self.hands_row.clear_widgets()
        for i, titre in enumerate(("Main gauche", "Main droite")):
            cell = BoxLayout(orientation="horizontal", spacing=dp(6),
                             padding=(dp(8), dp(4)))
            _panel(cell, alpha=0.30)
            item = state.hands[i]
            if item is None:
                vide = Label(text=f"{titre}\nvide", halign="center",
                             valign="middle", color=_DIM)
                _inv_label_font(vide)
                cell.add_widget(vide)
                self.hands_row.add_widget(cell)
                continue
            # Pour un OUTIL, l'image est surmontee de sa barre de solidite.
            health = state.tool_health(i)
            if health is None:
                cell.add_widget(TappableIcon(item, self._info,
                                             size_hint_x=0.34))
            else:
                box = BoxLayout(orientation="vertical", spacing=dp(3),
                                size_hint_x=0.34)
                box.add_widget(TappableIcon(item, self._info))
                bar = DurabilityBar(size_hint_y=None, height=dh(14))
                bar.set_value(health)
                box.add_widget(bar)
                cell.add_widget(box)
            lbl = Label(text=titre, halign="left", valign="middle",
                        size_hint_x=0.28, color=(0.96, 0.82, 0.45, 1))
            _inv_label_font(lbl)
            cell.add_widget(lbl)
            # Boutons empiles : la bande est basse et large, deux boutons
            # cote a cote y seraient des timbres-poste.
            btns = BoxLayout(orientation="vertical", spacing=dp(3),
                             size_hint_x=0.38)
            if state.can_equip(i):
                eq = StyledButton(text="Equiper", bold=True)
                eq.bind(size=_btn_font)
                eq.bind(on_release=lambda _w, idx=i: self._equip(idx))
                btns.add_widget(eq)
            drop = StyledButton(text="Deposer", bold=True)
            drop.bind(size=_btn_font)
            drop.bind(on_release=lambda _w, idx=i: self._drop(idx))
            btns.add_widget(drop)
            cell.add_widget(btns)
            self.hands_row.add_widget(cell)

    def _fill_ground(self, state):
        """Ce qui traine sur la case. Meme source que l'inventaire
        (state.ground_here()) : les deux listes ne peuvent pas diverger."""
        self.ground_box.clear_widgets()
        ground = state.ground_here()
        self.near_title.text = ("A proximite" if not ground
                                else f"A proximite ({sum(ground.values())})")
        if not ground:
            self.ground_box.add_widget(fit_text(Label(
                text="Rien au sol ici.", color=_DIM, halign="center",
                valign="middle", size_hint_y=None, height=dh(120)),
                wrap=True))
            return
        for name, count in sorted(ground.items()):
            cell = BoxLayout(orientation="vertical", spacing=dp(2),
                             size_hint_y=None, height=dh(_GROUND_CELL_H))
            cell.add_widget(TappableIcon(name, self._info, count=count))
            # Deux boutons pour prendre en main. Desactives si la main visee
            # est occupee, ou si l'objet ne se tient pas en main.
            hand_ok = items.is_hand_collectable(name)
            row = BoxLayout(orientation="horizontal", spacing=dp(3),
                            size_hint_y=None, height=dh(56))
            for hand_idx, text in ((0, "Main G"), (1, "Main D")):
                take = StyledButton(text=text, bold=True)
                take.bind(size=_btn_font)
                take.disabled = ((state.hands[hand_idx] is not None)
                                 or not hand_ok)
                take.bind(on_release=lambda _w, n=name, h=hand_idx:
                          self._take(n, h))
                row.add_widget(take)
            cell.add_widget(row)
            self.ground_box.add_widget(cell)

    def _fill_bag(self, state):
        """Le sac a dos. Ses objets servent de matiere premiere tels quels :
        aucun bouton, il n'y a rien a en sortir pour fabriquer."""
        self.bag_box.clear_widgets()
        capacity = state.bag_capacity()
        if capacity <= 0:
            self.bag_title.text = "Sac a dos"
            self.bag_box.add_widget(fit_text(Label(
                text="Aucun sac a dos. Tu ne transportes que ce que tu "
                     "tiens dans tes mains.", color=_DIM, halign="center",
                valign="middle", size_hint_y=None, height=dh(170)),
                wrap=True))
            return
        self.bag_title.text = f"Sac a dos ({len(state.bag)}/{capacity})"
        if not state.bag:
            self.bag_box.add_widget(fit_text(Label(
                text="Sac vide.", color=_DIM, halign="center",
                valign="middle", size_hint_y=None, height=dh(120)),
                wrap=True))
            return
        grid = GridLayout(cols=3, spacing=dp(3), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        for name in state.bag:
            grid.add_widget(TappableIcon(name, self._info, size_hint_y=None,
                                         height=dh(_BAG_CELL_H)))
        self.bag_box.add_widget(grid)

    def _fill_recipes(self, state):
        """Recettes, rangees par CATEGORIE repliable. Tout est replie a
        l'ouverture de l'ecran : la liste tient alors en quelques lignes, et
        le joueur deplie seulement ce qui l'interesse."""
        self.recipe_box.clear_widgets()
        pool = state.craft_pool()
        for category in items.RECIPE_CATEGORIES:
            group = [r for r in items.RECIPES
                     if r.get("category") == category]
            if not group:
                continue
            ready = sum(1 for r in group if state.can_craft(r))
            opened = category in self._open_cats
            head = TabButton(
                text=f"{'-' if opened else '+'}  {category}   "
                     f"({ready}/{len(group)})",
                halign="left", bold=True, size_hint_y=None, height=dh(84))
            head.bind(size=_btn_font)
            head.bind(on_release=lambda _w, c=category: self._toggle_cat(c))
            head.selected = opened          # categorie depliee = allumee
            self.recipe_box.add_widget(head)
            if not opened:
                continue
            self._add_recipes(state, pool, group)

    def _toggle_cat(self, category):
        """Deplie la categorie, ou la replie si elle l'etait deja."""
        if category in self._open_cats:
            self._open_cats.discard(category)
        else:
            self._open_cats.add(category)
        self.refresh()

    def _add_recipes(self, state, pool, group):
        for recipe in group:
            # Ingredients : ecriture plus FONCEE si l'ingredient manque.
            parts = []
            for k, v in recipe["ingredients"].items():
                label = f"{items.display_name(k)} x{v}"
                if pool.get(k, 0) >= v:
                    parts.append(label)
                else:
                    parts.append(f"[color=777777]{label}[/color]")
            # Matiere au CHOIX : "Feuille ou Herbe", une seule est consommee.
            alts = recipe.get("any_of")
            if alts:
                label = " ou ".join(items.display_name(a) for a in alts)
                if state.recipe_choice(recipe) is not None:
                    parts.append(label)
                else:
                    parts.append(f"[color=777777]{label}[/color]")
            # OUTIL requis : pas consomme, mais il s'use.
            tool = recipe.get("tool")
            if tool:
                cost = int(round(recipe.get("tool_wear", 0.0) * 100))
                label = f"{items.display_name(tool)} (-{cost} %)"
                if state.recipe_tool_ok(recipe):
                    parts.append(label)
                else:
                    parts.append(f"[color=777777]{label}[/color]")
            ing = ", ".join(parts)

            # Rangee bien plus HAUTE qu'avant : l'image (qui garde son ratio)
            # etait limitee par la hauteur de la rangee -> on la fait grandir.
            row = BoxLayout(orientation="horizontal", spacing=dp(6),
                            size_hint_y=None, height=dh(200))
            # Image du resultat a gauche, AGRANDIE au maximum : rangee plus
            # haute + boite plus large (ou "?" si aucune image n'existe).
            row.add_widget(TappableIcon(recipe["result"], self._info,
                                        show_name=False, size_hint_x=0.30))
            txt = Label(
                text=f"[b]{items.display_name(recipe['result'])}[/b]\n{ing}",
                markup=True, halign="left", valign="middle", size_hint_x=0.44)
            _recipe_text_font(txt)
            row.add_widget(txt)
            btn = StyledButton(text="Fabriquer", size_hint_x=0.26)
            btn.bind(size=_fit_button_font, text=_fit_button_font)
            btn.disabled = not state.can_craft(recipe)
            btn.bind(on_release=lambda _w, r=recipe: self._craft(r))
            row.add_widget(btn)
            self.recipe_box.add_widget(row)

    # ------------------------------------------------------------------ #
    def _info(self, name):
        """Ouvre la fiche de l'objet sur lequel on vient de taper."""
        show_item_info(self._root, name)

    def _take(self, name, hand):
        App.get_running_app().game_state.take_from_ground(name, hand)
        App.get_running_app().autosave()
        self.refresh()

    def _equip(self, index):
        """Porte l'objet tenu : il quitte la main pour son emplacement."""
        if App.get_running_app().game_state.equip_from_hand(index):
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
