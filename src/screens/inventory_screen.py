"""Ecran INVENTAIRE : ce que le personnage PORTE et ce qu'il TRANSPORTE.

Deux colonnes :
- a gauche l'EQUIPEMENT, un emplacement par piece (casque, chandail, gants,
  pantalon, chaussures, sac a dos). Un emplacement vide reste affiche, pour
  qu'on voie tout de suite ce qui manque ;
- a droite le contenu du SAC A DOS. Sans sac, il n'y a aucune place : la
  colonne l'explique au lieu d'afficher une grille vide.

Au depart le personnage porte ses vetements de rescape (chandail, pantalon,
chaussures) et n'a pas de sac : il ne transporte donc que ce qu'il tient dans
ses mains.
"""
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import (Color, RoundedRectangle, Rectangle, Ellipse,
                           Line)
from kivy.metrics import dp

from src import items
from src.widgets.animated_background import AnimatedBackground, night_darkness
from src.widgets.zone_scenery import ZoneScenery
from src.widgets.item_icon import ItemIcon
from src.widgets.styled_button import StyledButton
from src.widgets.responsive import scale_font, dh

# Couleur des textes secondaires (emplacement vide, explications).
_DIM = (0.62, 0.64, 0.70, 1)
_GOLD = (0.96, 0.82, 0.45, 1)

# Silhouette : chaque emplacement est place VIS-A-VIS de la partie du corps
# qu'il habille, et relie a elle par un trait.
#   emplacement -> (x, y du cadre, x, y de la partie du corps)
# Coordonnees en fractions du panneau (y = 0 en bas).
_SLOT_LAYOUT = {
    "casque":    (0.19, 0.86, 0.50, 0.85),
    "chandail":  (0.19, 0.62, 0.50, 0.58),
    "gant":      (0.19, 0.38, 0.35, 0.47),
    "sac":       (0.81, 0.74, 0.60, 0.62),
    "pantalon":  (0.81, 0.50, 0.50, 0.30),
    "chaussure": (0.81, 0.22, 0.50, 0.08),
}
_SLOT_SIZE = (0.30, 0.19)


def _panel(widget, alpha=0.45):
    with widget.canvas.before:
        Color(0, 0, 0, alpha)
        rect = RoundedRectangle(radius=[dp(12)])
    widget.bind(pos=lambda w, *_: setattr(rect, "pos", w.pos),
                size=lambda w, *_: setattr(rect, "size", w.size))


def _row_font(w, *_):
    """Police d'une ligne d'inventaire, ramenee si le texte est trop large."""
    if w.width <= 1:
        return
    target = dh(70) * 0.46
    w.text_size = (None, None)
    w.font_size = target
    w.texture_update()
    if w.texture_size[0] > w.width:
        w.font_size = max(10, target * w.width / w.texture_size[0])
    w.text_size = (w.width, w.height)


def _label(text, color=(0.92, 0.92, 0.95, 1), halign="left", **kwargs):
    lbl = Label(text=text, color=color, halign=halign, valign="middle",
                **kwargs)
    lbl.bind(size=_row_font)
    _row_font(lbl)
    return lbl


class InventoryScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = FloatLayout()
        self.background = AnimatedBackground(time_scale=0, size_hint=(1, 1),
                                             pos_hint={"x": 0, "y": 0})
        root.add_widget(self.background)
        self.scenery = ZoneScenery(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.scenery)
        self._scene_key = None

        # Voile de nuit, comme les autres ecrans.
        self.night = Widget(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        with self.night.canvas:
            self._night_color = Color(0.03, 0.05, 0.12, 0.0)
            self._night_rect = Rectangle()

        def _sync_night(*_):
            self._night_rect.pos = self.night.pos
            self._night_rect.size = self.night.size
        self.night.bind(pos=_sync_night, size=_sync_night)
        root.add_widget(self.night)

        col = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8),
                        size_hint=(0.96, 0.96),
                        pos_hint={"center_x": 0.5, "center_y": 0.5})
        col.add_widget(scale_font(Label(text="INVENTAIRE", bold=True,
                       color=_GOLD, size_hint=(1, 0.08)), 0.03))

        body = BoxLayout(orientation="horizontal", spacing=dp(10),
                         size_hint=(1, 0.60))

        # ---- Gauche : equipement porte ----
        left = BoxLayout(orientation="vertical", spacing=dp(6), size_hint_x=0.5)
        left.add_widget(scale_font(Label(text="Equipement", bold=True,
                        size_hint=(1, 0.10)), 0.022))
        self.equip_box = _BodyPanel(size_hint=(1, 0.90))
        left.add_widget(self.equip_box)
        body.add_widget(left)

        # ---- Droite : contenu du sac ----
        right = BoxLayout(orientation="vertical", spacing=dp(6), size_hint_x=0.5)
        self.bag_title = scale_font(Label(text="Sac a dos", bold=True,
                                    size_hint=(1, 0.10)), 0.022)
        right.add_widget(self.bag_title)
        sc2 = ScrollView(size_hint=(1, 0.90))
        self.bag_box = BoxLayout(orientation="vertical", spacing=dp(4),
                                 size_hint_y=None)
        self.bag_box.bind(minimum_height=self.bag_box.setter("height"))
        sc2.add_widget(self.bag_box)
        right.add_widget(sc2)
        body.add_widget(right)

        col.add_widget(body)

        # ---- Les MAINS, en bas : source du glisser-deposer ----
        hands = BoxLayout(orientation="horizontal", spacing=dp(8),
                          size_hint=(1, 0.20))
        self.hand_slots = []
        for i, titre in enumerate(("Main gauche", "Main droite")):
            slot = _HandSlot(i, titre)
            self.hand_slots.append(slot)
            hands.add_widget(slot)
        col.add_widget(hands)

        # Message d'aide / refus (pourquoi un depot n'a pas marche).
        self.hint = _label("Glisse un objet d'une main vers son emplacement "
                           "ou vers le sac.", _DIM, halign="center",
                           size_hint=(1, 0.06))
        col.add_widget(self.hint)

        back = scale_font(StyledButton(text="Retour", size_hint=(1, 0.10)), 0.022)
        back.bind(on_release=lambda *_: setattr(self.manager, "current", "game"))
        col.add_widget(back)

        _panel(col)
        root.add_widget(col)

        # Couche du glisser-deposer : l'objet suivi par le doigt passe
        # AU-DESSUS de tout le reste.
        self.drag_layer = FloatLayout(size_hint=(1, 1),
                                      pos_hint={"x": 0, "y": 0})
        root.add_widget(self.drag_layer)
        self._drag = None
        # Cibles du glisser-deposer, reconstruites a chaque rafraichissement.
        self._equip_slots = []
        self._bag_cells = []
        self.add_widget(root)

    # ------------------------------------------------------------------ #
    def on_pre_enter(self):
        state = App.get_running_app().game_state
        if state is not None:
            self.background.set_seconds(state.time_seconds)
            self.background.set_weather(state.effective_weather())
            self._night_color.a = night_darkness(state.time_seconds)
            zone = state.current_zone()
            key = (zone, state.player_x, state.player_y)
            if key != self._scene_key:
                self.scenery.set_ground(zone,
                                        state.player_x * 131 + state.player_y)
                self._scene_key = key
        self.refresh()

    def refresh(self):
        state = App.get_running_app().game_state
        if state is None:
            return
        self._fill_equipment(state)
        self._fill_bag(state)
        for slot in self.hand_slots:
            slot.set_item(state.hands[slot.hand])

    # ------------------------------------------------------------------ #
    # Glisser-deposer
    # ------------------------------------------------------------------ #
    def on_touch_down(self, touch):
        if self._start_drag(touch):
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self._drag is not None:
            self._drag["ghost"].center = touch.pos
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if self._drag is not None:
            self._drop(touch)
            return True
        return super().on_touch_up(touch)

    def _start_drag(self, touch):
        """Saisit l'objet sous le doigt : une main, ou une case du sac."""
        source = None
        for slot in self.hand_slots:
            if slot.item and slot.collide_point(*touch.pos):
                source = ("hand", slot.hand, slot.item)
        for cell in self._bag_cells:
            if cell.item and cell.collide_point(*touch.pos):
                source = ("bag", cell.bag_index, cell.item)
        if source is None:
            return False
        name = source[2]
        size = (self.width * 0.09, self.height * 0.16)
        ghost = BoxLayout(size_hint=(None, None), size=size, padding=dp(4))
        _panel(ghost, alpha=0.55)
        ghost.add_widget(ItemIcon(name, show_name=False))
        ghost.center = touch.pos
        ghost.opacity = 0.9
        self.drag_layer.add_widget(ghost)
        self._drag = {"source": source, "ghost": ghost}
        self.hint.text = f"{items.display_name(name)}..."
        return True

    def _drop(self, touch):
        """Lache l'objet : on regarde ce qui se trouve sous le doigt."""
        drag, self._drag = self._drag, None
        self.drag_layer.remove_widget(drag["ghost"])
        kind, index, name = drag["source"]
        state = App.get_running_app().game_state
        if state is None:
            return
        message = self._apply_drop(state, kind, index, name, touch)
        self.hint.text = message
        App.get_running_app().autosave()
        self.refresh()

    def _apply_drop(self, state, kind, index, name, touch):
        """Effectue le depot et renvoie le message a afficher."""
        # ---- vers un emplacement d'EQUIPEMENT ----
        for widget in self._equip_slots:
            if not widget.collide_point(*touch.pos):
                continue
            if kind != "hand":
                return "Prends l'objet en main avant de le porter."
            good = items.equip_slot(name)
            if good is None:
                return f"{items.display_name(name)} ne se porte pas."
            if good != widget.slot:
                return (f"{items.display_name(name)} se porte a "
                        f"l'emplacement {items.EQUIP_SLOT_NAMES[good]}.")
            state.equip_from_hand(index)
            return f"{items.display_name(name)} equipe."
        # ---- vers le SAC ----
        if self.bag_box.collide_point(*touch.pos) or any(
                c.collide_point(*touch.pos) for c in self._bag_cells):
            if kind != "hand":
                return ""
            if state.bag_capacity() <= 0:
                return "Aucun sac a dos pour ranger cet objet."
            if state.bag_free() <= 0:
                return "Le sac est plein."
            state.bag_store(index)
            return f"{items.display_name(name)} range dans le sac."
        # ---- vers une MAIN (on ressort du sac) ----
        for slot in self.hand_slots:
            if not slot.collide_point(*touch.pos):
                continue
            if kind != "bag":
                return ""
            if state.hands[slot.hand] is not None:
                return "Cette main est deja occupee."
            state.bag_take(index, slot.hand)
            return f"{items.display_name(name)} repris en main."
        return ""

    def _fill_equipment(self, state):
        """Pose un cadre par emplacement, en face de sa partie du corps."""
        self.equip_box.clear_widgets()
        self._equip_slots = []
        for slot in items.EQUIP_SLOTS:
            sx, sy, _bx, _by = _SLOT_LAYOUT[slot]
            widget = _EquipSlot(slot, state.equipment.get(slot),
                                size_hint=_SLOT_SIZE,
                                pos_hint={"center_x": sx, "center_y": sy})
            self._equip_slots.append(widget)
            self.equip_box.add_widget(widget)

    def _fill_bag(self, state):
        self.bag_box.clear_widgets()
        self._bag_cells = []
        capacity = state.bag_capacity()
        if capacity <= 0:
            self.bag_title.text = "Sac a dos"
            msg = _label("Aucun sac a dos.\nTu ne transportes que ce que tu "
                         "tiens dans tes mains.", _DIM, halign="center",
                         size_hint_y=None, height=dh(220))
            self.bag_box.add_widget(msg)
            return
        self.bag_title.text = f"Sac a dos ({len(state.bag)}/{capacity})"
        grid = GridLayout(cols=2, spacing=dp(6), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        for i in range(capacity):
            name = state.bag[i] if i < len(state.bag) else None
            cell = BoxLayout(orientation="vertical", spacing=dp(2),
                             size_hint_y=None, height=dh(220))
            cell.bag_index = i
            cell.item = name
            self._bag_cells.append(cell)
            cell.add_widget(ItemIcon(name, show_name=False) if name
                            else _empty_slot(1.0))
            cell.add_widget(_label(items.display_name(name) if name
                                   else "Vide",
                                   (0.92, 0.92, 0.95, 1) if name else _DIM,
                                   halign="center",
                                   size_hint_y=None, height=dh(46)))
            grid.add_widget(cell)
        self.bag_box.add_widget(grid)


class _HandSlot(BoxLayout):
    """Ce que tient une main. Point de DEPART du glisser-deposer."""

    def __init__(self, hand, title, **kwargs):
        kwargs.setdefault("orientation", "horizontal")
        kwargs.setdefault("padding", dp(6))
        kwargs.setdefault("spacing", dp(6))
        super().__init__(**kwargs)
        self.hand = hand
        self.item = None
        _panel(self, alpha=0.30)
        self._icon_box = BoxLayout(size_hint_x=0.34)
        self.add_widget(self._icon_box)
        self._text = _label("", size_hint_x=0.66)
        self.add_widget(self._text)
        self._title = title

    def set_item(self, name):
        self.item = name
        self._icon_box.clear_widgets()
        self._icon_box.add_widget(ItemIcon(name, show_name=False) if name
                                  else _empty_slot(1.0))
        self._text.text = (f"{self._title}\n{items.display_name(name)}"
                           if name else f"{self._title}\nVide")
        self._text.color = (0.92, 0.92, 0.95, 1) if name else _DIM


class _BodyPanel(FloatLayout):
    """Silhouette humaine, avec un trait vers chaque emplacement d'equipement.

    Le corps est dessine dans `canvas.before` : les cadres d'equipement,
    ajoutes comme enfants, passent donc par-dessus."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_):
        self.canvas.before.clear()
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        if w <= 0 or h <= 0:
            return

        def px(fx, fy):
            return (x0 + fx * w, y0 + fy * h)

        with self.canvas.before:
            # Traits de correspondance, sous le corps : discrets.
            Color(1, 1, 1, 0.16)
            for slot, (sx, sy, bx, by) in _SLOT_LAYOUT.items():
                # On part du bord INTERIEUR du cadre, vers la partie du corps.
                edge = sx + (_SLOT_SIZE[0] / 2 if sx < 0.5
                             else -_SLOT_SIZE[0] / 2)
                Line(points=[*px(edge, sy), *px(bx, by)], width=1.2)

            Color(0.72, 0.76, 0.84, 0.55)
            head_r = h * 0.062
            hx, hy = px(0.50, 0.85)
            Ellipse(pos=(hx - head_r, hy - head_r),
                    size=(head_r * 2, head_r * 2))            # tete
            Rectangle(pos=px(0.475, 0.755), size=(w * 0.05, h * 0.04))  # cou
            # Torse : epaules larges, taille plus etroite.
            RoundedRectangle(pos=px(0.415, 0.44),
                             size=(w * 0.17, h * 0.32),
                             radius=[w * 0.03])
            # Bras, le long du torse, mains a hauteur des hanches.
            for dx in (0.365, 0.585):
                RoundedRectangle(pos=px(dx, 0.46), size=(w * 0.05, h * 0.28),
                                 radius=[w * 0.025])
            # Mains.
            for dx in (0.355, 0.595):
                Ellipse(pos=px(dx, 0.425), size=(w * 0.06, h * 0.05))
            # Jambes.
            for dx in (0.437, 0.505):
                RoundedRectangle(pos=px(dx, 0.10), size=(w * 0.058, h * 0.35),
                                 radius=[w * 0.025])
            # Pieds.
            for dx in (0.425, 0.493):
                RoundedRectangle(pos=px(dx, 0.055), size=(w * 0.082, h * 0.05),
                                 radius=[w * 0.02])


class _EquipSlot(BoxLayout):
    """Cadre d'un emplacement : le nom, et l'objet porte (ou "Aucun")."""

    def __init__(self, slot, worn, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("padding", dp(4))
        kwargs.setdefault("spacing", dp(2))
        super().__init__(**kwargs)
        # Un emplacement OCCUPE est plus dense et cercle d'or ; un emplacement
        # vide reste discret.
        edge = _GOLD[:3] + (0.45,) if worn else (1, 1, 1, 0.18)
        with self.canvas.before:
            Color(0.05, 0.07, 0.10, 0.62 if worn else 0.42)
            bg = RoundedRectangle(radius=[dp(8)])
            Color(*edge)
            border = Line(width=1.2)

        def _sync(*_):
            bg.pos = self.pos
            bg.size = self.size
            border.rounded_rectangle = (self.x, self.y, self.width,
                                        self.height, dp(8))
        self.bind(pos=_sync, size=_sync)
        _sync()

        top = BoxLayout(orientation="horizontal", spacing=dp(4),
                        size_hint_y=0.66)
        top.add_widget(ItemIcon(worn, show_name=False, size_hint_x=0.42)
                       if worn else _empty_slot(0.42))
        top.add_widget(_label(items.EQUIP_SLOT_NAMES[slot], _GOLD,
                              size_hint_x=0.58))
        self.add_widget(top)
        self.add_widget(_label(items.display_name(worn) if worn else "Aucun",
                               (0.92, 0.92, 0.95, 1) if worn else _DIM,
                               halign="center", size_hint_y=0.34))


def _empty_slot(size_hint_x):
    """Emplacement vide : un cadre en pointille plutot qu'un trou."""
    w = Widget(size_hint_x=size_hint_x)
    with w.canvas:
        Color(1, 1, 1, 0.10)
        rect = RoundedRectangle(radius=[dp(8)])
        Color(1, 1, 1, 0.22)

    def _sync(*_):
        s = min(w.width, w.height)
        rect.pos = (w.center_x - s / 2, w.center_y - s / 2)
        rect.size = (s, s)
    w.bind(pos=_sync, size=_sync)
    return w
