"""
GLISSER-DEPOSER des objets, partage par l'inventaire et le craft.

Deplacer un objet, c'est le prendre du doigt et le lacher ailleurs. La
mecanique vivait entierement dans l'ecran d'inventaire ; le craft, lui,
offrait des boutons ("Prendre main gauche", "Deposer"...) qui faisaient la
meme chose en moins direct. Ces boutons ont ete retires : il fallait donc que
le craft sache glisser, lui aussi.

Plutot que d'en ecrire une deuxieme version, l'ecran herite de ce melangeur.
Les deux ecrans partagent ainsi la MEME facon de deplacer un objet, jusqu'aux
messages de refus.

L'ecran doit fournir :
    drag_layer      couche par-dessus tout, ou vit l'objet suivi par le doigt
    hand_slots      les deux mains
    ground_scroll / _ground_cells      la colonne "a proximite"
    bag_scroll / _bag_cells            la colonne du sac
    _equip_slots    la silhouette -- LISTE VIDE si l'ecran n'en a pas
    hint            un libelle pour les messages (facultatif)
    refresh()       pour se redessiner apres un depot

Un TAP (doigt pose et releve sans bouger) n'est pas un glisser : il ouvre la
fiche de l'objet. C'est la meme geste au depart, seule la distance parcourue
les separe.
"""
import math

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.graphics import Color, Line
from kivy.metrics import dp

from src import items
from src.widgets.item_icon import ItemIcon
from src.widgets.item_info import show_item_info
from src.widgets.panels import panel

# Tolerance, en pixels, sous laquelle un toucher est un TAP et non un glisser.
# Un doigt bouge toujours un peu : sans cette marge, ouvrir une fiche d'objet
# serait une affaire de chance.
TAP_SLOP = dp(14)

# Cadence du clignotement des cibles, et sa vitesse.
PULSE_FPS = 30.0
PULSE_SPEED = 6.0


def hit(widget, touch):
    """Le doigt est-il sur ce widget, et ce widget est-il VISIBLE ?

    On passe par to_window() : un widget place dans un ScrollView a des
    coordonnees LOCALES (le ScrollView applique une translation a ses
    enfants), et collide_point() les comparerait a des coordonnees d'ecran.
    Le test echouait donc systematiquement pour les cases du sac.

    get_root_window() ecarte ce qui n'est PLUS A L'ECRAN. Changer de
    sous-menu remplace le panneau affiche : le panneau quitte l'arbre, mais
    ses cases gardent leur parent, et repondaient encore au doigt. On pouvait
    ainsi attraper une piece d'equipement en glissant sur la zone qu'elle
    occupait avant, alors que l'ecran montrait autre chose."""
    if widget is None or widget.parent is None:
        return False
    if widget.get_root_window() is None:
        return False
    x, y = widget.to_window(widget.x, widget.y)
    return (x <= touch.x <= x + widget.width
            and y <= touch.y <= y + widget.height)


def make_highlightable(widget):
    """Donne a un widget un cadre vert clignotant, eteint au repos.

    Sert a montrer OU un objet peut etre lache pendant un glisser. Le cadre
    est dans `canvas.after` pour passer par-dessus le contenu du widget."""
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


class DragDrop:
    """Melangeur : donne le glisser-deposer a un ecran.

    A placer AVANT Screen dans les bases, pour que ses on_touch_* passent en
    premier."""

    def init_drag(self):
        """A appeler une fois l'ecran construit."""
        self._drag = None
        self._drag_name = None
        self._info = None
        self._hl_widgets = []
        self._hl_event = None
        self._hl_t = 0.0

    # -- gestes --------------------------------------------------------- #
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

    # -- fiche d'objet -------------------------------------------------- #
    def _show_info(self, name):
        """Ouvre la fiche d'un objet, et retient qu'elle est ouverte."""
        if not name:
            return
        self._say("")
        self._info = show_item_info(self._root, name)
        self._info.bind(parent=self._forget_info)

    def _forget_info(self, panel_widget, parent):
        if parent is None and self._info is panel_widget:
            self._info = None

    def _say(self, message):
        """Ecrit un message, si l'ecran a de quoi l'afficher."""
        hint = getattr(self, "hint", None)
        if hint is not None:
            hint.text = message

    def _equip_widgets(self):
        """La silhouette, ou rien du tout si l'ecran n'en a pas."""
        return getattr(self, "_equip_slots", ())

    # -- prise ---------------------------------------------------------- #
    def _start_drag(self, touch):
        """Saisit l'objet sous le doigt.

        Quatre origines : le sol, une main, une case du sac, ou une piece
        PORTEE (on la retire alors de la silhouette)."""
        source = None
        for widget in self._equip_widgets():
            if widget.worn and hit(widget, touch):
                source = ("equip", widget.slot, widget.worn)
        for slot in self.hand_slots:
            if slot.item and hit(slot, touch):
                source = ("hand", slot.hand, slot.item)
        for cell in self._bag_cells:
            if cell.item and hit(cell, touch):
                source = ("bag", cell.bag_index, cell.item)
        for cell in self._ground_cells:
            if cell.item and hit(cell, touch):
                source = ("ground", cell.item, cell.item)
        if source is None:
            return False
        name = source[2]
        ghost = BoxLayout(size_hint=(None, None), padding=dp(4),
                          size=(self.width * 0.09, self.height * 0.16))
        panel(ghost, alpha=0.55)
        ghost.add_widget(ItemIcon(name, show_name=False))
        ghost.center = touch.pos
        ghost.opacity = 0.9
        self.drag_layer.add_widget(ghost)
        self._drag = {"source": source, "ghost": ghost, "start": touch.pos}
        self._drag_name = name
        # Montre OU cet objet peut aller : les cibles valables clignotent
        # tant que le doigt le tient.
        self._highlight_for(source[0], name)
        self._say(f"{items.display_name(name)}...")
        return True

    # -- cibles qui clignotent ------------------------------------------ #
    def _targets(self):
        """Tout ce qui peut clignoter, pour tout eteindre d'un coup."""
        return (list(self._equip_widgets()) + list(self.hand_slots)
                + [self.bag_scroll, self.ground_scroll])

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
            targets += [w for w in self._equip_widgets() if w.slot == slot]
        # Une main LIBRE : on sort du sac, ou on se deshabille.
        if kind != "hand":
            targets += [h for h in self.hand_slots
                        if state.hands[h.hand] is None]
        # Le sac, s'il existe et qu'il reste de la place. Un sac a dos ne
        # peut evidemment pas se ranger dans lui-meme.
        if (kind != "bag" and state.bag_free() > 0
                and not (kind == "equip" and slot == "sac")):
            targets.append(self.bag_scroll)
        # Le SOL accepte tout : on peut toujours poser un objet par terre.
        if kind != "ground":
            targets.append(self.ground_scroll)

        for widget in self._targets():
            widget.set_highlight(False)
        self._hl_widgets = targets
        if not targets:
            self._stop_highlight()
        elif self._hl_event is None:
            self._hl_t = 0.0
            self._hl_event = Clock.schedule_interval(self._pulse_highlight,
                                                     1 / PULSE_FPS)

    def _pulse_highlight(self, dt):
        self._hl_t += dt
        pulse = 0.5 + 0.5 * math.sin(self._hl_t * PULSE_SPEED)
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

    # -- depot ---------------------------------------------------------- #
    def _drop(self, touch):
        """Lache l'objet : on regarde ce qui se trouve sous le doigt."""
        drag, self._drag = self._drag, None
        self.drag_layer.remove_widget(drag["ghost"])
        self._stop_highlight()
        kind, index, name = drag["source"]
        state = App.get_running_app().game_state
        if state is None:
            return
        self._say(self._apply_drop(state, kind, index, name, touch))
        App.get_running_app().autosave()
        self.refresh()

    def _apply_drop(self, state, kind, index, name, touch):
        """Effectue le depot et renvoie le message a afficher."""
        label = items.display_name(name)
        # ---- vers un emplacement d'EQUIPEMENT ----
        for widget in self._equip_widgets():
            if not hit(widget, touch):
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
            if kind == "ground":
                # Depuis le SOL : la piece remplacee tombe a sa place.
                spilled = state.ground_equip(name)
                if spilled is None:
                    return ""
                return f"{label} ramasse et equipe."
            # Depuis le SAC : la piece remplacee prend sa place dedans.
            spilled = state.equip_from_bag(index)
            if spilled is None:
                return ""
            if spilled:
                return (f"{label} equipe — {spilled} objet(s) du sac "
                        f"tombent au sol.")
            return f"{label} equipe."
        # ---- vers le SAC ----
        if hit(self.bag_scroll, touch):
            if kind == "bag":
                return ""
            if kind == "equip" and index == "sac":
                return "Le sac a dos ne peut pas se ranger dans lui-meme."
            if state.bag_capacity() <= 0:
                return "Aucun sac a dos pour ranger cet objet."
            if state.bag_free() <= 0:
                return "Le sac est plein."
            if kind == "equip":
                state.unequip_to_bag(index)
                return f"{label} retire et range dans le sac."
            if kind == "ground":
                state.ground_to_bag(name)
                return f"{label} ramasse dans le sac."
            state.bag_store(index)
            return f"{label} range dans le sac."
        # ---- vers le SOL : on peut toujours poser un objet par terre ----
        if hit(self.ground_scroll, touch):
            if kind == "hand":
                state.drop_from_hands(index)
                return f"{label} pose au sol."
            if kind == "bag":
                state.bag_drop(index)
                return f"{label} sorti du sac, pose au sol."
            if kind == "equip":
                spilled = state.unequip_to_ground(index)
                if spilled is None:
                    return ""
                kept = state.bag_fill(name)
                if kept and kept[0] > 0:
                    return (f"{label} pose au sol — ses {kept[0]} objet(s) "
                            f"restent dedans.")
                return f"{label} retire et pose au sol."
            return ""
        # ---- vers une MAIN (on ressort du sac, ou on se deshabille) ----
        for slot in self.hand_slots:
            if not hit(slot, touch):
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
            if kind == "ground":
                state.take_from_ground(name, slot.hand)
                return f"{label} ramasse."
            if kind != "bag":
                return ""
            state.bag_take(index, slot.hand)
            return f"{label} repris en main."
        return ""
