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
import math

from kivy.app import App
from kivy.clock import Clock
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
from src.widgets.item_info import show_item_info
from src.widgets.styled_button import StyledButton
from src.widgets.responsive import scale_font, dh

# Tolerance, en pixels, sous laquelle un toucher est un TAP et non un
# glisser. Un doigt bouge toujours un peu : sans cette marge, ouvrir une
# fiche d'objet serait une affaire de chance.
TAP_SLOP = dp(14)

# Couleur des textes secondaires (emplacement vide, explications).
_DIM = (0.62, 0.64, 0.70, 1)
_GOLD = (0.96, 0.82, 0.45, 1)

# Une case d'objet, dans le sac COMME dans l'equipement : un carre pour
# l'image, une legende dessous. L'equipement ajoute une legende AU-DESSUS
# (la partie du corps), d'ou sa hauteur plus grande.
# Tailles pensees pour une fenetre de 1080 de haut (cf. dh()).
_ICON_SIDE = 116        # cote du carre de l'image
_CELL_LABEL = 34        # hauteur de la legende du HAUT (partie du corps)
# La legende du BAS est plus haute : un sac y affiche son remplissage sur
# une deuxieme ligne, sous son nom.
_NAME_LABEL = 46
_CELL_W = 182           # largeur d'une case (celle d'une case du sac)
# Part de la largeur prise par la colonne des statistiques. Le reste est
# partage a egalite entre l'equipement et le sac, comme avant qu'elle
# existe. 0.26 laisse aux cases d'equipement la place de ne pas mordre sur
# la silhouette (voir _cell_size).
_STATS_SHARE = 0.26
_STAT_ROW = 120         # hauteur d'une ligne de statistique
_CELL_H = _ICON_SIDE + _CELL_LABEL + _NAME_LABEL
_BAG_CELL_H = _ICON_SIDE + _NAME_LABEL

# Silhouette : chaque emplacement est place VIS-A-VIS de la partie du corps
# qu'il habille, et relie a elle par un trait.
#   emplacement -> (x, y du cadre, x, y de la partie du corps)
# Coordonnees en fractions du panneau (y = 0 en bas). Les six cases forment
# deux colonnes de trois, de part et d'autre du corps.
_SLOT_LAYOUT = {
    "casque":    (0.22, 0.84, 0.50, 0.85),
    "chandail":  (0.22, 0.50, 0.50, 0.60),
    "gant":      (0.22, 0.16, 0.375, 0.45),
    "sac":       (0.78, 0.84, 0.58, 0.68),
    "pantalon":  (0.78, 0.50, 0.50, 0.28),
    "chaussure": (0.78, 0.16, 0.545, 0.08),
}


def _cell_size(panel):
    """Taille d'une case d'equipement.

    C'est celle d'une case du sac, mais ramenee si le panneau est trop
    etroit ou trop court : trois rangees doivent tenir sans se chevaucher,
    quelle que soit la forme de la fenetre."""
    if panel.width <= 1 or panel.height <= 1:
        return (dh(_CELL_W), dh(_CELL_H))
    # 0.24 en largeur : au-dela, les deux colonnes de cases mordraient sur la
    # silhouette (elles sont centrees a 0.22 et 0.78, le corps occupe le
    # milieu). 0.315 en hauteur : trois rangees, plus un peu d'air.
    width = min(dh(_CELL_W), panel.width * 0.24)
    # Le carre ne peut pas etre plus large que la case : sur un ecran etroit
    # on rabaisse la case, sinon elle serait haute avec un carre riquiqui.
    height = min(dh(_CELL_H), panel.height * 0.315,
                 width * _CELL_H / _ICON_SIDE)
    return (width, height)


def _panel(widget, alpha=0.45):
    with widget.canvas.before:
        Color(0, 0, 0, alpha)
        rect = RoundedRectangle(radius=[dp(12)])
    widget.bind(pos=lambda w, *_: setattr(rect, "pos", w.pos),
                size=lambda w, *_: setattr(rect, "size", w.size))


def _row_font(w, *_):
    """Police d'une ligne d'inventaire, ramenee si le texte deborde.

    Le texte peut compter plusieurs lignes (un sac affiche son remplissage
    sous son nom) : la police est donc d'abord limitee par la hauteur
    DISPONIBLE PAR LIGNE, puis reduite encore si une ligne est trop large."""
    if w.width <= 1 or w.height <= 1:
        return
    lines = (w.text or "").count("\n") + 1
    target = min(dh(70) * 0.46, w.height * 0.82 / lines)
    w.text_size = (None, None)
    w.font_size = target
    w.texture_update()
    if w.texture_size[0] > w.width:
        w.font_size = max(9, target * w.width / w.texture_size[0])
    w.text_size = (w.width, w.height)


def _hit(widget, touch):
    """Le doigt est-il sur ce widget ?

    On passe par to_window() : un widget place dans un ScrollView a des
    coordonnees LOCALES (le ScrollView applique une translation a ses
    enfants), et collide_point() les comparerait a des coordonnees d'ecran.
    Le test echouait donc systematiquement pour les cases du sac."""
    if widget is None or widget.parent is None:
        return False
    x, y = widget.to_window(widget.x, widget.y)
    return (x <= touch.x <= x + widget.width
            and y <= touch.y <= y + widget.height)


def _make_highlightable(widget):
    """Donne a un widget un cadre vert clignotant, eteint au repos.

    Sert a montrer OU un objet peut etre lache pendant un glisser : les
    mains libres, le sac. Le cadre est dans `canvas.after` pour passer
    par-dessus le contenu du widget."""
    with widget.canvas.after:
        color = Color(0.45, 1.00, 0.62, 0.0)
        line = Line(width=1.6)

    def _sync(*_):
        line.rounded_rectangle = (widget.x, widget.y, widget.width,
                                  widget.height, dp(10))
    widget.bind(pos=_sync, size=_sync)
    _sync()

    def set_highlight(on, pulse=1.0):
        color.a = (0.40 + 0.60 * pulse) if on else 0.0

    widget.set_highlight = set_highlight
    return widget


def _item_text(state, name, worn=False):
    """Nom de l'objet, avec le remplissage dessous s'il s'agit d'un sac.

    Un sac retire garde ce qu'il transportait : on affiche donc son contenu
    qu'il soit porte, tenu en main ou range."""
    if not name:
        return "Vide"
    text = items.display_name(name)
    fill = state.bag_fill(name, worn) if state is not None else None
    if fill and fill[0] > 0:
        text += f"\n{fill[0]}/{fill[1]}"
    return text


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
                       color=_GOLD, size_hint=(1, 0.07)), 0.03))

        # Les cases d'equipement occupent trois rangees : cette section a
        # besoin de hauteur, elle en prend sur les mains et le bas d'ecran.
        body = BoxLayout(orientation="horizontal", spacing=dp(10),
                         size_hint=(1, 0.76))

        # ---- Gauche : les statistiques cumulees ----
        # Une simple liste : elle a besoin de moins de largeur que les deux
        # autres, qui gardent entre elles leur proportion d'avant (moitie
        # moitie).
        stats = BoxLayout(orientation="vertical", spacing=dp(6),
                          size_hint_x=_STATS_SHARE)
        stats.add_widget(scale_font(Label(text="Statistiques", bold=True,
                         size_hint=(1, 0.09)), 0.022))
        sc0 = ScrollView(size_hint=(1, 0.91))
        self.stats_box = BoxLayout(orientation="vertical", spacing=dp(6),
                                   size_hint_y=None)
        self.stats_box.bind(minimum_height=self.stats_box.setter("height"))
        sc0.add_widget(self.stats_box)
        stats.add_widget(sc0)
        body.add_widget(stats)

        # ---- Milieu : equipement porte ----
        rest = (1.0 - _STATS_SHARE) / 2.0
        left = BoxLayout(orientation="vertical", spacing=dp(6),
                         size_hint_x=rest)
        left.add_widget(scale_font(Label(text="Equipement", bold=True,
                        size_hint=(1, 0.09)), 0.022))
        self.equip_box = _BodyPanel(size_hint=(1, 0.91))
        left.add_widget(self.equip_box)
        body.add_widget(left)

        # ---- Droite : contenu du sac ----
        right = BoxLayout(orientation="vertical", spacing=dp(6),
                          size_hint_x=rest)
        self.bag_title = scale_font(Label(text="Sac a dos", bold=True,
                                    size_hint=(1, 0.09)), 0.022)
        right.add_widget(self.bag_title)
        sc2 = self.bag_scroll = _make_highlightable(ScrollView(
            size_hint=(1, 0.91)))
        self.bag_box = BoxLayout(orientation="vertical", spacing=dp(4),
                                 size_hint_y=None)
        self.bag_box.bind(minimum_height=self.bag_box.setter("height"))
        sc2.add_widget(self.bag_box)
        right.add_widget(sc2)
        body.add_widget(right)

        col.add_widget(body)

        # ---- Les MAINS, en bas : source du glisser-deposer ----
        hands = BoxLayout(orientation="horizontal", spacing=dp(8),
                          size_hint=(1, 0.16))
        self.hand_slots = []
        for i, titre in enumerate(("Main gauche", "Main droite")):
            slot = _HandSlot(i, titre)
            self.hand_slots.append(slot)
            hands.add_widget(slot)
        col.add_widget(hands)

        # Message d'aide / refus (pourquoi un depot n'a pas marche).
        self.hint = _label("Glisse un objet entre tes mains, ton sac et ton "
                           "equipement : les cases ou tu peux le lacher "
                           "clignotent.", _DIM, halign="center",
                           size_hint=(1, 0.05))
        col.add_widget(self.hint)

        back = scale_font(StyledButton(text="Retour", size_hint=(1, 0.09)), 0.022)
        back.bind(on_release=lambda *_: setattr(self.manager, "current", "game"))
        col.add_widget(back)

        _panel(col)
        root.add_widget(col)

        # Couche du glisser-deposer : l'objet suivi par le doigt passe
        # AU-DESSUS de tout le reste.
        self.drag_layer = FloatLayout(size_hint=(1, 1),
                                      pos_hint={"x": 0, "y": 0})
        root.add_widget(self.drag_layer)
        self._root = root
        self._drag = None
        self._drag_name = None
        # Fiche d'objet ouverte (un simple tap l'ouvre), ou None.
        self._info = None
        # Cibles du glisser-deposer, reconstruites a chaque rafraichissement.
        self._equip_slots = []
        self._bag_cells = []
        # Emplacement mis en valeur pendant un glisser, et son clignotement.
        # Cibles qui clignotent pendant un glisser.
        self._hl_widgets = []
        self._hl_event = None
        self._hl_t = 0.0
        # Les cases d'equipement ont une taille FIXE (celle d'une case du
        # sac) : il faut la recalculer quand le panneau change de taille.
        self.equip_box.bind(size=self._size_equip_slots)
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

    def on_leave(self):
        """Ne laisse ni clignotement ni fiche ouverte sur un ecran qu'on quitte."""
        self._cancel_drag()
        if self._info is not None:
            self._info.close()

    def refresh(self):
        state = App.get_running_app().game_state
        if state is None:
            return
        self._fill_stats(state)
        self._fill_equipment(state)
        self._fill_bag(state)
        # Apres les DEUX colonnes : la mise a l'echelle touche les cases de
        # l'equipement comme celles du sac, qui viennent d'etre recreees.
        self._size_equip_slots()
        for slot in self.hand_slots:
            name = state.hands[slot.hand]
            slot.set_item(name, _item_text(state, name))

    # ------------------------------------------------------------------ #
    # Glisser-deposer
    # ------------------------------------------------------------------ #
    def on_touch_down(self, touch):
        # Une fiche d'objet ouverte prend la main : le glisser attendra.
        if self._info is not None:
            return super().on_touch_down(touch)
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
            # Doigt pose et releve sans bouger : ce n'etait pas un glisser
            # mais un simple TAP, qui ouvre la fiche de l'objet.
            start = self._drag["start"]
            moved = max(abs(touch.x - start[0]), abs(touch.y - start[1]))
            if moved <= TAP_SLOP:
                self._cancel_drag()
                self._show_info(self._drag_name)
            else:
                self._drop(touch)
            return True
        return super().on_touch_up(touch)

    # ------------------------------------------------------------------ #
    def _show_info(self, name):
        """Ouvre la fiche d'un objet, et retient qu'elle est ouverte."""
        if not name:
            return
        self.hint.text = ""
        self._info = show_item_info(self._root, name)
        self._info.bind(parent=self._forget_info)

    def _forget_info(self, panel, parent):
        if parent is None and self._info is panel:
            self._info = None

    def _start_drag(self, touch):
        """Saisit l'objet sous le doigt.

        Trois origines possibles : une main, une case du sac, ou une piece
        PORTEE (on la retire alors de la silhouette)."""
        source = None
        for widget in self._equip_slots:
            if widget.worn and _hit(widget, touch):
                source = ("equip", widget.slot, widget.worn)
        for slot in self.hand_slots:
            if slot.item and _hit(slot, touch):
                source = ("hand", slot.hand, slot.item)
        for cell in self._bag_cells:
            if cell.item and _hit(cell, touch):
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
        self._drag = {"source": source, "ghost": ghost, "start": touch.pos}
        self._drag_name = name
        # Montre OU cet objet peut aller : les cibles valables clignotent
        # tant que le doigt le tient.
        self._highlight_for(source[0], name)
        self.hint.text = f"{items.display_name(name)}..."
        return True

    def _targets(self):
        """Tout ce qui peut clignoter, pour tout eteindre d'un coup."""
        return list(self._equip_slots) + list(self.hand_slots) + [self.bag_scroll]

    def _highlight_for(self, kind, name):
        """Fait clignoter TOUTES les destinations possibles de l'objet saisi.

        Le joueur voit donc d'un coup d'oeil ou il a le droit de lacher :
        une main libre, le sac, l'emplacement du corps qui convient."""
        state = App.get_running_app().game_state
        if state is None:
            return
        targets = []
        slot = items.equip_slot(name) if name else None

        # L'emplacement du corps qui accepte l'objet, sauf si on l'y prend.
        if kind != "equip" and slot is not None:
            targets += [w for w in self._equip_slots if w.slot == slot]
        # Une main LIBRE : on sort du sac, ou on se deshabille.
        if kind != "hand":
            targets += [h for h in self.hand_slots
                        if state.hands[h.hand] is None]
        # Le sac, s'il existe et qu'il reste de la place. Un sac a dos ne
        # peut evidemment pas se ranger dans lui-meme.
        if (kind != "bag" and state.bag_free() > 0
                and not (kind == "equip" and slot == "sac")):
            targets.append(self.bag_scroll)

        for widget in self._targets():
            widget.set_highlight(False)
        self._hl_widgets = targets
        if not targets:
            self._stop_highlight()
        elif self._hl_event is None:
            self._hl_t = 0.0
            self._hl_event = Clock.schedule_interval(self._pulse_highlight,
                                                     1 / 30.0)

    def _pulse_highlight(self, dt):
        self._hl_t += dt
        pulse = 0.5 + 0.5 * math.sin(self._hl_t * 6.0)
        for widget in self._hl_widgets:
            widget.set_highlight(True, pulse)

    def _stop_highlight(self):
        """Eteint le clignotement et rend leur aspect aux cibles."""
        if self._hl_event is not None:
            self._hl_event.cancel()
            self._hl_event = None
        self._hl_widgets = []
        for widget in self._targets():
            widget.set_highlight(False)

    def _cancel_drag(self):
        """Abandonne le glisser en cours sans rien deplacer."""
        drag, self._drag = self._drag, None
        if drag is not None:
            self.drag_layer.remove_widget(drag["ghost"])
        self._stop_highlight()

    def _drop(self, touch):
        """Lache l'objet : on regarde ce qui se trouve sous le doigt."""
        drag, self._drag = self._drag, None
        self.drag_layer.remove_widget(drag["ghost"])
        self._stop_highlight()
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
        label = items.display_name(name)
        # ---- vers un emplacement d'EQUIPEMENT ----
        for widget in self._equip_slots:
            if not _hit(widget, touch):
                continue
            if kind == "equip":
                # Repose sur son propre emplacement : rien n'a bouge.
                return "" if widget.slot == index else (
                    f"Prends {label} en main avant de le porter ailleurs.")
            good = items.equip_slot(name)
            if good is None:
                return f"{label} ne se porte pas."
            if good != widget.slot:
                return (f"{label} se porte a "
                        f"l'emplacement {items.EQUIP_SLOT_NAMES[good]}.")
            if kind == "hand":
                state.equip_from_hand(index)
                return f"{label} equipe."
            # Depuis le SAC : la piece remplacee prend sa place dedans.
            spilled = state.equip_from_bag(index)
            if spilled is None:
                return ""
            if spilled:
                return (f"{label} equipe — {spilled} objet(s) du sac "
                        f"tombent au sol.")
            return f"{label} equipe."
        # ---- vers le SAC ----
        if _hit(self.bag_scroll, touch):
            if kind == "equip":
                if index == "sac":
                    return "Le sac a dos ne peut pas se ranger dans lui-meme."
                if state.bag_capacity() <= 0:
                    return "Aucun sac a dos pour ranger cet objet."
                if state.bag_free() <= 0:
                    return "Le sac est plein."
                state.unequip_to_bag(index)
                return f"{label} retire et range dans le sac."
            if kind != "hand":
                return ""
            if state.bag_capacity() <= 0:
                return "Aucun sac a dos pour ranger cet objet."
            if state.bag_free() <= 0:
                return "Le sac est plein."
            state.bag_store(index)
            return f"{label} range dans le sac."
        # ---- vers une MAIN (on ressort du sac, ou on se deshabille) ----
        for slot in self.hand_slots:
            if not _hit(slot, touch):
                continue
            if state.hands[slot.hand] is not None:
                return "Cette main est deja occupee."
            if kind == "equip":
                spilled = state.unequip_to_hand(index, slot.hand)
                if spilled is None:
                    return ""
                kept = state.bag_fill(name)
                if kept and kept[0] > 0:
                    # Un sac retire garde ce qu'il transportait : rien ne
                    # tombe, tout revient quand on le remet.
                    return (f"{label} retire — ses {kept[0]} objet(s) "
                            f"restent dedans.")
                if spilled:
                    return (f"{label} retire — {spilled} objet(s) tombent "
                            f"au sol.")
                return f"{label} retire, en main."
            if kind != "bag":
                return ""
            state.bag_take(index, slot.hand)
            return f"{label} repris en main."
        return ""

    def _fill_stats(self, state):
        """Une ligne par statistique : le total, puis son detail."""
        self.stats_box.clear_widgets()
        totals = state.stats_total()
        for key in items.STAT_ORDER:
            base, gear = totals.get(key, (0, 0))
            unit = items.STAT_UNITS.get(key)
            row = BoxLayout(orientation="vertical", size_hint_y=None,
                            height=dh(_STAT_ROW), padding=(dp(10), dp(4)))
            with row.canvas.before:
                Color(0.05, 0.07, 0.10, 0.42)
                bg = RoundedRectangle(radius=[dp(8)])
            row.bind(pos=lambda w, *_, r=bg: setattr(r, "pos", w.pos),
                     size=lambda w, *_, r=bg: setattr(r, "size", w.size))

            head = BoxLayout(orientation="horizontal", size_hint_y=0.55)
            head.add_widget(_label(items.STAT_NAMES.get(key, key), _GOLD,
                                   size_hint_x=0.60))
            total = base + gear
            head.add_widget(_label(f"{total}" + (f" {unit}" if unit else ""),
                                   halign="right", size_hint_x=0.40))
            row.add_widget(head)

            # Le detail : sans lui, un total ne dit pas ce qu'on gagnerait a
            # mieux s'habiller.
            detail = f"base {base}" + (f"  +{gear} porte" if gear else "")
            row.add_widget(_label(detail, _DIM, size_hint_y=0.45))
            self.stats_box.add_widget(row)

        note = _label("Seul le rangement agit deja sur le jeu ; les autres "
                      "sont indicatifs.", _DIM, halign="center",
                      size_hint_y=None, height=dh(_STAT_ROW))
        self.stats_box.add_widget(note)

    def _fill_equipment(self, state):
        """Pose une case par emplacement, en face de sa partie du corps."""
        self.equip_box.clear_widgets()
        self._equip_slots = []
        for slot in items.EQUIP_SLOTS:
            sx, sy, _bx, _by = _SLOT_LAYOUT[slot]
            worn = state.equipment.get(slot)
            widget = _EquipSlot(slot, worn,
                                _item_text(state, worn, worn=True),
                                pos_hint={"center_x": sx, "center_y": sy})
            self._equip_slots.append(widget)
            self.equip_box.add_widget(widget)

    def _size_equip_slots(self, *_):
        """Accorde la taille des cases des DEUX colonnes.

        Le carre d'un objet doit faire exactement la meme taille dans le sac
        et dans l'equipement. Chaque colonne a sa propre contrainte : trois
        rangees a caser pour l'equipement, six cases de front pour le sac.
        C'est la plus SERREE des deux qui decide, sinon les carres
        finiraient par ne plus se ressembler sur les fenetres etroites."""
        width, height = _cell_size(self.equip_box)
        side = height * (_ICON_SIDE / _CELL_H)
        column = (self.bag_scroll.width - 5 * dp(3)) / 6.0
        if column > 1:
            side = min(side, column)
            height = side * (_CELL_H / _ICON_SIDE)
            width = min(width, height * (_CELL_W / _CELL_H))
        for widget in self._equip_slots:
            widget.size = (width, height)
        icon = side
        label = height * (_NAME_LABEL / _CELL_H)
        for cell in self._bag_cells:
            cell.name_label.height = label
            cell.height = icon + label

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
        grid = GridLayout(cols=6, spacing=dp(3), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        for i in range(capacity):
            name = state.bag[i] if i < len(state.bag) else None
            cell = BoxLayout(orientation="vertical", size_hint_y=None,
                             height=dh(_BAG_CELL_H))
            cell.bag_index = i
            cell.item = name
            self._bag_cells.append(cell)
            cell.add_widget(ItemIcon(name, show_name=False) if name
                            else _empty_slot(1.0))
            cell.name_label = _label(_item_text(state, name),
                                     (0.92, 0.92, 0.95, 1) if name else _DIM,
                                     halign="center",
                                     size_hint_y=None, height=dh(_NAME_LABEL))
            cell.add_widget(cell.name_label)
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
        _make_highlightable(self)   # cible d'un glisser (on se deshabille)
        self._icon_box = BoxLayout(size_hint_x=0.34)
        self.add_widget(self._icon_box)
        self._text = _label("", size_hint_x=0.66)
        self.add_widget(self._text)
        self._title = title

    def set_item(self, name, text=None):
        self.item = name
        self._icon_box.clear_widgets()
        self._icon_box.add_widget(ItemIcon(name, show_name=False) if name
                                  else _empty_slot(1.0))
        self._text.text = f"{self._title}\n{text or 'Vide'}"
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

        # Demi-largeur d'une case, en fraction du panneau : les traits doivent
        # partir du bord de la case, pas de son centre.
        half = _cell_size(self)[0] / (2.0 * w)

        with self.canvas.before:
            # Traits de correspondance, sous le corps : discrets.
            Color(1, 1, 1, 0.16)
            for slot, (sx, sy, bx, by) in _SLOT_LAYOUT.items():
                # On part du bord INTERIEUR de la case, vers la partie du corps.
                edge = sx + (half if sx < 0.5 else -half)
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
    """Une case d'equipement, batie comme une case du sac.

    De haut en bas : la PARTIE DU CORPS, le carre de l'objet (meme cote que
    dans le sac), puis le NOM de l'objet porte (ou "Aucun")."""

    def __init__(self, slot, worn, text, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("size", (dh(_CELL_W), dh(_CELL_H)))
        super().__init__(**kwargs)
        self.slot = slot          # cible du glisser-deposer
        self.worn = worn

        # 1. la partie du corps, au-dessus
        self.add_widget(_label(items.EQUIP_SLOT_NAMES[slot], _GOLD,
                               halign="center",
                               size_hint_y=_CELL_LABEL / _CELL_H))

        # 2. le carre de l'objet
        square = BoxLayout(size_hint_y=_ICON_SIDE / _CELL_H)
        # Un emplacement OCCUPE est plus dense et cercle d'or ; un emplacement
        # vide reste discret. Les couleurs sont memorisees pour pouvoir
        # ILLUMINER l'emplacement pendant un glisser, puis le rendre a son
        # aspect normal.
        self._base_bg = (0.05, 0.07, 0.10, 0.62 if worn else 0.42)
        self._base_edge = _GOLD[:3] + (0.45,) if worn else (1, 1, 1, 0.18)
        with square.canvas.before:
            self._bg_color = Color(*self._base_bg)
            bg = RoundedRectangle(radius=[dp(8)])
            self._edge_color = Color(*self._base_edge)
            border = Line(width=1.2)

        def _sync(*_):
            # Le cadre est CARRE et centre : c'est la meme forme que la case
            # vide d'un objet dans le sac.
            side = min(square.width, square.height)
            x = square.center_x - side / 2
            y = square.center_y - side / 2
            bg.pos = (x, y)
            bg.size = (side, side)
            border.rounded_rectangle = (x, y, side, side, dp(8))
        square.bind(pos=_sync, size=_sync)
        _sync()
        if worn:
            square.add_widget(ItemIcon(worn, show_name=False))
        self.add_widget(square)

        # 3. le nom de l'objet, en dessous (et son remplissage si c'est un sac)
        self.add_widget(_label(text if worn else "Aucun",
                               (0.92, 0.92, 0.95, 1) if worn else _DIM,
                               halign="center",
                               size_hint_y=_NAME_LABEL / _CELL_H))

    def set_highlight(self, on, pulse=1.0):
        """Allume l'emplacement pendant un glisser (ou le rend a son aspect).

        `pulse` va de 0 a 1 : c'est lui qui fait CLIGNOTER le cadre, pour
        attirer l'oeil sans etre agressif."""
        if not on:
            self._bg_color.rgba = self._base_bg
            self._edge_color.rgba = self._base_edge
            return
        self._bg_color.rgba = (0.12, 0.34, 0.20, 0.45 + 0.25 * pulse)
        self._edge_color.rgba = (0.45, 1.00, 0.62, 0.40 + 0.60 * pulse)


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
