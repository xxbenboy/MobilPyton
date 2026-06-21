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
from kivy.animation import Animation
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.metrics import dp

from src.game_state import _clamp100
from src.widgets.animated_background import AnimatedBackground, night_darkness
from src.widgets.zone_scenery import ZoneScenery

from src import items
from src.widgets.player_hands import PlayerHands
from src.widgets.insects import InsectLayer
from src.widgets.icon_button import IconButton
from src.widgets.styled_button import StyledButton
from src.widgets.item_icon import ItemIcon
from src.widgets.stat_circle import StatCircle
from src.widgets.clock_face import ClockFace
from src.widgets.responsive import scale_font

AUTOSAVE_SECONDS = 30
TIME_SCALE = 144              # 24h en 10 min
FAST_FORWARD_SCALE = 3600     # avance rapide : 1h de jeu / s reelle

# Cout d'un deplacement d'une case (1 km a pied).
MOVE_MINUTES = 12
MOVE_ENERGY = -3
MOVE_HUNGER = 2

# Actions : effets ponctuels (la faim/soif/sommeil derivent en plus avec le
# temps). "requires_sleep" => possible seulement si on est assez fatigue.
ACTIONS = [
    {"label": "Explorer", "icon": "explore", "name": "Explorer",
     "minutes": 90, "energy": -10, "type": "explore"},
    {"label": "Couper du bois", "icon": "wood", "name": "Couper\ndu bois",
     "minutes": 120, "energy": -15, "wood": 3, "need_axe": True},
    {"label": "Chercher a manger", "icon": "food", "name": "Chercher\na manger",
     "minutes": 60, "energy": -5, "hunger": -25, "food": 2},
    {"label": "Boire", "icon": "drink", "name": "Boire",
     "minutes": 10, "thirst": -40, "type": "drink"},
    {"label": "Remplir gourde", "icon": "fill", "name": "Remplir\ngourde",
     "minutes": 15, "type": "fill", "need_gourde": True},
    {"label": "Se reposer", "icon": "rest", "name": "Se\nreposer",
     "minutes": 240, "energy": 35, "sleep": 50, "requires_sleep": True},
]


def _action_reason(state, action):
    """Raison (texte court) pour laquelle l'action est indisponible, ou None.

    Sert a la fois a griser le bouton et a expliquer au joueur, quand il appuie,
    pourquoi l'action n'est pas possible.
    """
    if action.get("requires_sleep") and not state.can_sleep():
        return "Pas assez fatigue\npour te reposer."
    if action.get("type") == "drink" and not (state.has_water_source()
                                               or state.water > 0):
        return "Pas d'eau ici,\nni dans la gourde."
    if action.get("type") == "fill" and not state.has_water_source():
        return "Aucun ruisseau ici\npour remplir la gourde."
    if action.get("type") == "explore" and state.hands_full():
        return "Mains occupees.\nVide une main pour explorer."
    return None


def _action_available(state, action):
    """Une action est-elle realisable ? (raccourci sur _action_reason)"""
    return _action_reason(state, action) is None


def _add_panel(widget, alpha=0.34):
    """Ajoute un panneau translucide arrondi derriere un widget."""
    with widget.canvas.before:
        Color(0, 0, 0, alpha)
        rect = RoundedRectangle(radius=[dp(14)])

    def _sync(*_):
        rect.pos = widget.pos
        rect.size = widget.size
    widget.bind(pos=_sync, size=_sync)


def _button_label(text):
    """Etiquette d'un bouton (son nom) avec un fond noir arrondi AJUSTE au texte.

    Le nom reste TOUJOURS entierement visible et horizontal, le fond epouse sa
    taille (au lieu d'occuper toute la cellule), et les noms sur deux lignes
    (ex. "Couper\\ndu bois") sont centres.

    Methode : a chaque changement de police/taille, on mesure d'abord la largeur
    NATURELLE du texte (sans contrainte), puis on fige cette largeur pour centrer
    les lignes. Mesurer sans contrainte a chaque fois evite que le texte reste
    coince sur une largeur trop petite (ce qui l'afficherait verticalement).
    """
    lbl = Label(text=text, halign="center", valign="middle",
                size_hint=(1, 0.34), color=(1, 1, 1, 1))
    with lbl.canvas.before:
        Color(0, 0, 0, 0.75)
        bg = RoundedRectangle(radius=[dp(4)])

    busy = {"v": False}

    def _refit(*_):
        if busy["v"]:
            return
        busy["v"] = True
        # 1) largeur libre -> largeur reelle du texte.
        lbl.text_size = (None, None)
        lbl.texture_update()
        natural_w = lbl.texture_size[0]
        # 2) on fige cette largeur -> centrage des lignes, sans elargir.
        lbl.text_size = (natural_w, None)
        lbl.texture_update()
        busy["v"] = False
        tw, th = lbl.texture_size
        bw, bh = tw + dp(10), th + dp(6)
        bg.pos = (lbl.center_x - bw / 2.0, lbl.center_y - bh / 2.0)
        bg.size = (bw, bh)

    lbl.bind(pos=_refit, size=_refit, font_size=_refit, text=_refit)
    scale_font(lbl)
    return lbl


def _fit_text_to_height(lbl, fill=0.92):
    """Agrandit le texte d'un Label pour REMPLIR la hauteur de son conteneur
    (selon le nombre de lignes), sans depasser sa largeur. Texte centre.

    Permet d'avoir un texte aussi GROS que possible dans une fenetre de taille
    fixe (la police est limitee par la hauteur, ou par la largeur si une ligne
    est trop longue)."""
    def _fit(*_):
        if lbl.width <= 1 or lbl.height <= 1:
            return
        lines = (lbl.text or "").count("\n") + 1
        bw, bh = lbl.width, lbl.height
        # Candidat base sur la hauteur disponible.
        font = max(8, bh * fill / lines)
        lbl.text_size = (None, None)
        lbl.font_size = font
        lbl.texture_update()
        tw = lbl.texture_size[0]
        # Si une ligne deborde en largeur, on reduit pour qu'elle tienne.
        if tw > bw * 0.98:
            font = max(8, font * (bw * 0.98) / tw)
            lbl.font_size = font
        # Centre les lignes horizontalement (la police tient deja en largeur).
        lbl.text_size = (bw, None)
    lbl.bind(size=_fit, text=_fit)
    return lbl


class _Fader(FloatLayout):
    """Voile plein ecran qui absorbe les touches pendant la transition."""
    def on_touch_down(self, touch):
        return True

    def on_touch_move(self, touch):
        return True

    def on_touch_up(self, touch):
        return True


class _ModalOverlay(FloatLayout):
    """Overlay modal : transmet les touches a ses enfants (panneau) mais bloque
    celles destinees au jeu derriere (renvoie toujours True)."""
    def on_touch_down(self, touch):
        super().on_touch_down(touch)
        return True

    def on_touch_move(self, touch):
        super().on_touch_move(touch)
        return True

    def on_touch_up(self, touch):
        super().on_touch_up(touch)
        return True


class GameScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._autosave_event = None
        self._tick_event = None
        self._time_accum = 0.0
        self._ff_active = False
        self._ff_remaining = 0.0
        self._ff_total = 0.0          # duree initiale (pour l'animation)
        self._ff_label = ""
        # Transition de deplacement (fondu noir + horloge).
        self._moving = False
        self._fader = None
        self._fader_clock = None
        self._pending_move = None
        self._move_event = None
        self._found_item = None        # objet decouvert a la fin d'une exploration
        self._did_explore = False      # vient-on d'explorer ? (pour le message)
        self._scene_key = None

        root = FloatLayout()
        self.root_layout = root
        self._toast = None
        self.background = AnimatedBackground(time_scale=0, size_hint=(1, 1),
                                             pos_hint={"x": 0, "y": 0})
        root.add_widget(self.background)
        self.scenery = ZoneScenery(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.scenery)
        # Insectes animes (papillons / abeilles) qui volent dans la scene.
        self.insects = InsectLayer(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.insects)
        # Mains du joueur (vue 1re personne), devant le decor.
        self.hands = PlayerHands(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.hands)

        # Voile de NUIT : assombrit tout le decor (ciel, sol, mains) selon
        # l'heure, SANS toucher le HUD (ajoute APRES, donc par-dessus ce voile).
        self.night = Widget(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        with self.night.canvas:
            self._night_color = Color(0.03, 0.05, 0.12, 0.0)   # bleu nuit
            self._night_rect = Rectangle(pos=self.night.pos, size=self.night.size)

        def _sync_night(*_):
            self._night_rect.pos = self.night.pos
            self._night_rect.size = self.night.size
        self.night.bind(pos=_sync_night, size=_sync_night)
        root.add_widget(self.night)

        # ---- Section ZONE (haut centre) ----
        zone_box = BoxLayout(orientation="vertical", padding=dp(10), spacing=4,
                             size_hint=(0.20, 0.16),
                             pos_hint={"center_x": 0.5, "top": 0.98})
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

        # ---- Section ETAT : cercles de stats colles a droite, empiles ----
        # Chaque stat = un anneau qui se remplit (logo au centre, nom dessous).
        # La colonne est plaquee sur le bord droit et n'occupe pas le bas droit
        # (reserve au bouton "Menu").
        stats_col = BoxLayout(orientation="vertical", padding=(dp(2), dp(6)),
                              spacing=dp(6), size_hint=(0.07, 0.80),
                              pos_hint={"right": 0.998, "top": 0.99})
        _add_panel(stats_col, alpha=0.28)
        self.stat_health = StatCircle("Vie", (0.85, 0.30, 0.30), "health")
        self.stat_energy = StatCircle("Energie", (0.95, 0.80, 0.30), "energy")
        self.stat_sleep = StatCircle("Sommeil", (0.45, 0.55, 0.95), "sleep")
        self.stat_hunger = StatCircle("Faim", (0.85, 0.55, 0.25), "hunger")
        self.stat_thirst = StatCircle("Soif", (0.30, 0.70, 0.92), "thirst")
        for circle in (self.stat_health, self.stat_energy, self.stat_sleep,
                       self.stat_hunger, self.stat_thirst):
            stats_col.add_widget(circle)
        root.add_widget(stats_col)

        # ---- Etat d'action (sous la zone) ----
        self.status = scale_font(Label(text="", bold=True,
                                 color=(0.96, 0.82, 0.45, 1),
                                 size_hint=(0.20, 0.07),
                                 pos_hint={"center_x": 0.5, "top": 0.80}), 0.022)
        root.add_widget(self.status)

        # ---- Boutons d'action (haut gauche) ----
        # Disposition : colonne de gauche = Explorer / Se reposer / Craft, le
        # reste rempli normalement (remplissage haut->bas puis colonne suivante).
        # La grille est RECONSTRUITE selon l'etat : "Couper du bois" n'apparait
        # qu'avec une hache en main, "Remplir gourde" qu'avec une gourde.
        self.grid = GridLayout(rows=3, orientation="tb-lr",
                               spacing=[dp(2), dp(12)], size_hint=(None, 0.50),
                               pos_hint={"x": 0.004, "top": 0.96})
        self.grid.bind(minimum_width=self.grid.setter("width"))
        root.add_widget(self.grid)
        self._action_buttons = []   # (bouton, action)
        self.craft_btn = None
        self._action_visible = None  # cle des actions visibles (pour rebuild)

        # ---- Bouton CARTE (bas a gauche) ----
        # Cellule ETROITE, plaquee au bord : le logo (taille basee sur la
        # HAUTEUR) ne change pas, mais se rapproche du bord de l'ecran.
        map_cell = BoxLayout(orientation="vertical", spacing=2, size_hint=(0.06, 0.16),
                             pos_hint={"x": 0.006, "y": 0.012})
        map_area = AnchorLayout(size_hint=(1, 0.66))
        self.map_btn = IconButton(icon="map", size_hint=(None, None))
        def _map_square(a, *_):
            s = a.height * 0.94
            self.map_btn.size = (s, s)
        map_area.bind(size=_map_square)
        self.map_btn.bind(on_release=self._open_map)
        map_area.add_widget(self.map_btn)
        map_cell.add_widget(map_area)
        map_cell.add_widget(_button_label("Carte"))
        root.add_widget(map_cell)

        # ---- Bouton MENU (bas a droite) ----
        menu_cell = BoxLayout(orientation="vertical", spacing=2, size_hint=(0.06, 0.16),
                              pos_hint={"right": 0.994, "y": 0.012})
        self.menu_cell = menu_cell
        menu_area = AnchorLayout(size_hint=(1, 0.66))
        self.back_btn = IconButton(icon="home", size_hint=(None, None))
        def _menu_square(a, *_):
            s = a.height * 0.94
            self.back_btn.size = (s, s)
        menu_area.bind(size=_menu_square)
        self.back_btn.bind(on_release=self._toggle_pause_menu)
        menu_area.add_widget(self.back_btn)
        menu_cell.add_widget(menu_area)
        self.menu_label = _button_label("Menu")
        menu_cell.add_widget(self.menu_label)
        root.add_widget(menu_cell)

        # ---- Boutons "Deposer" (vis-a-vis de chaque main, au-dessus) ----
        # Permettent de poser l'objet tenu sans passer par le menu Craft. Au-
        # dessus, un libelle montre le NOM de l'objet tenu. Masques (bouton +
        # libelle) quand la main est vide (gere dans refresh()).
        # X (cx) : aligne sur les centres des mains dans HandHUD.png.
        # Y : place AU-DESSUS de la zone des mains (qui occupe le bas ~8 %
        # de l'ecran) pour ne pas chevaucher les mains visuellement.
        self.drop_btns = []
        self.drop_labels = []
        for slot, cx in enumerate(PlayerHands.HAND_FX):
            # Bouton Deposer COLLE en bas. Label juste au-dessus.
            name_lbl = _button_label("")
            name_lbl.size_hint = (0.16, 0.05)
            name_lbl.pos_hint = {"center_x": cx, "y": 0.080}
            root.add_widget(name_lbl)
            self.drop_labels.append(name_lbl)

            db = scale_font(StyledButton(text="Deposer", size_hint=(0.13, 0.07),
                            pos_hint={"center_x": cx, "y": 0.005}), 0.02)
            # Fond plus transparent (alpha 0.40 au lieu de 0.92) pour ne pas
            # masquer les mains/decor derriere.
            db.set_palette(idle=(0.13, 0.24, 0.18, 0.40),
                           down=(0.22, 0.40, 0.28, 0.55),
                           off=(0.12, 0.14, 0.12, 0.30),
                           border=(0.55, 0.85, 0.60, 0.45))
            db.bind(on_release=lambda _w, s=slot: self._drop_hand(s))
            root.add_widget(db)
            self.drop_btns.append(db)

        # ---- Bouton DEPLACER (bas a droite, a gauche du Menu) ----
        # Meme style que Carte/Menu : un logo + le nom dessous.
        move_cell = BoxLayout(orientation="vertical", spacing=2,
                              size_hint=(0.06, 0.16),
                              pos_hint={"right": 0.90, "y": 0.012})
        move_area = AnchorLayout(size_hint=(1, 0.66))
        self.move_btn = IconButton(icon="move", size_hint=(None, None))
        def _move_square(a, *_):
            s = a.height * 0.94
            self.move_btn.size = (s, s)
        move_area.bind(size=_move_square)
        self.move_btn.bind(on_release=self._open_move_menu)
        move_area.add_widget(self.move_btn)
        move_cell.add_widget(move_area)
        move_cell.add_widget(_button_label("Deplacer"))
        root.add_widget(move_cell)
        self._move_menu = None      # overlay du menu de deplacement (ou None)
        self._pause_menu = None     # overlay du menu pause (Menu) (ou None)

        self.add_widget(root)

    # ------------------------------------------------------------------ #
    def on_pre_enter(self):
        self.refresh()

    def on_enter(self):
        self._autosave_event = Clock.schedule_interval(
            self._periodic_autosave, AUTOSAVE_SECONDS)
        self._tick_event = Clock.schedule_interval(self._tick, 1 / 60.0)

    def on_leave(self):
        self._close_move_menu()
        self._close_pause_menu()
        # Annule une transition de deplacement en cours et nettoie.
        if self._move_event is not None:
            self._move_event.cancel()
            self._move_event = None
        if self._pending_move is not None:
            self._move_apply()              # applique le deplacement en attente
        self._move_done()
        for ev in ("_autosave_event", "_tick_event"):
            event = getattr(self, ev)
            if event is not None:
                event.cancel()
                setattr(self, ev, None)

    def _tick(self, dt):
        state = App.get_running_app().game_state
        if state is None or self._moving:
            # Pendant la transition (ecran noir), le temps est gere a part.
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
        # Animation des mains pendant l'exploration : on alterne entre
        # HandEx1 (1/3 debut), HandEx2 (1/3 milieu), HandEx1 (1/3 fin).
        if self._ff_active and self._ff_label == "Explorer":
            frac = 1.0 - (self._ff_remaining / max(0.01, self._ff_total))
            if frac < 1.0 / 3.0 or frac >= 2.0 / 3.0:
                self.hands.set_state('ex1')
            else:
                self.hands.set_state('ex2')
        else:
            self.hands.set_state('haut')
        if self._ff_active and self._ff_remaining <= 0:
            self._finish_action()
        self.refresh()

    # ------------------------------------------------------------------ #
    # Construction (dynamique) de la grille des boutons d'action
    # ------------------------------------------------------------------ #
    def _action_visible_key(self, state):
        """Cle resumant quels boutons conditionnels sont visibles."""
        return (items.AXE_ITEM in state.hands,
                any(state.has_item(g) for g in items.GOURDE_ITEMS))

    def _build_action_grid(self, state):
        self.grid.clear_widgets()
        self._action_buttons = []
        cells = []          # (cell, btn, lbl) -> pour egaliser les largeurs

        def _fit_cells(*_):
            if not cells:
                return
            # Largeur UNIFORME = la cellule la plus large -> logos alignes, et
            # rien ne se chevauche (les noms non plus).
            w = max(max(btn.width, lbl.texture_size[0])
                    for _c, btn, lbl in cells) + dp(6)
            for cell, _b, _l in cells:
                cell.width = w

        def add_cell(icon, name, on_release):
            cell = BoxLayout(orientation="vertical", spacing=2, size_hint_x=None)
            area = AnchorLayout(size_hint=(1, 0.66))
            btn = IconButton(icon=icon, size_hint=(None, None))

            def _square(a, *_, _btn=btn):
                s = a.height * 0.94
                _btn.size = (s, s)
            area.bind(size=_square)
            btn.bind(on_release=on_release)
            area.add_widget(btn)
            lbl = _button_label(name)
            cell.add_widget(area)
            cell.add_widget(lbl)
            cells.append((cell, btn, lbl))
            btn.bind(size=_fit_cells)
            lbl.bind(texture_size=_fit_cells)
            self.grid.add_widget(cell)
            return btn

        has_axe = items.AXE_ITEM in state.hands
        has_gourde = any(state.has_item(g) for g in items.GOURDE_ITEMS)
        by_label = {a["label"]: a for a in ACTIONS}
        # Ordre voulu : colonne gauche = Explorer / Se reposer / Craft (3 lignes),
        # puis les autres remplissent les colonnes suivantes. None = Craft.
        order = ["Explorer", "Se reposer", None,
                 "Couper du bois", "Chercher a manger", "Boire", "Remplir gourde"]
        for label in order:
            if label is None:
                self.craft_btn = add_cell(
                    "craft", "Craft",
                    lambda *_: setattr(self.manager, "current", "craft"))
                continue
            action = by_label[label]
            if action.get("need_axe") and not has_axe:
                continue            # pas de hache -> bouton retire
            if action.get("need_gourde") and not has_gourde:
                continue            # pas de gourde -> bouton retire
            btn = add_cell(action["icon"], action["name"],
                           lambda _w, a=action: self.do_action(a))
            self._action_buttons.append((btn, action))

    # ------------------------------------------------------------------ #
    def do_action(self, action):
        state = App.get_running_app().game_state
        if state is None or self._ff_active or self._moving:
            return
        reason = _action_reason(state, action)
        if reason is not None:
            # Bouton grise : on explique pourquoi l'action est impossible.
            self._show_message(reason)
            return
        atype = action.get("type")
        # Plus rien a trouver si plus aucun objet recoltable n'est visible.
        if atype == "explore" and not self._can_find():
            self._show_find_toast(None)
            return
        # Eau : remplir la gourde au ruisseau ; boire consomme la gourde sauf
        # si on boit directement a un ruisseau.
        if atype == "fill":
            state.water += 3
        elif atype == "drink" and not state.has_water_source():
            state.water = max(0, state.water - 1)
        elif atype == "explore":
            # La trouvaille et le retrait du decor se font a la FIN du trajet
            # (cf. _finish_action) ; ici on lance juste l'exploration.
            state.reveal_zone(state.player_x, state.player_y)
            self._did_explore = True

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
        self._ff_total = action["minutes"] * 60.0
        self._ff_remaining = self._ff_total
        self._ff_label = action["label"]
        self._time_accum = 0.0
        self.refresh()
        App.get_running_app().autosave()

    def _finish_action(self):
        self._ff_active = False
        self._ff_label = ""
        self.hands.set_state('haut')
        if self._did_explore:
            self._did_explore = False
            # La trouvaille et le RETRAIT de l'objet du decor se font ICI, a la
            # fin du trajet (et non au moment d'appuyer sur Explorer).
            item = self._explore_find()
            if item:
                # En main (droite en priorite) ; au sol si non ramassable.
                dest = App.get_running_app().game_state.auto_take(item)
                self._show_find_toast(item, dest)
            else:
                self._show_find_toast(None)
        App.get_running_app().autosave()

    def _show_message(self, text):
        """Petit message d'information bref (1.2 s puis fondu), au centre haut.

        Sert a expliquer pourquoi une action grisee est impossible (ex. mains
        pleines)."""
        if self._toast is not None and self._toast.parent:
            self._toast.parent.remove_widget(self._toast)

        toast = BoxLayout(orientation="vertical", padding=dp(6),
                          size_hint=(0.30, 0.16),
                          pos_hint={"center_x": 0.5, "top": 0.81})
        _add_panel(toast, alpha=0.6)
        msg = Label(text=text, halign="center", valign="middle",
                    color=(1, 1, 1, 1), size_hint=(1, 1))
        _fit_text_to_height(msg)
        toast.add_widget(msg)
        self.root_layout.add_widget(toast)
        self._toast = toast

        from kivy.animation import Animation

        def _remove(*_):
            if toast.parent:
                toast.parent.remove_widget(toast)
            if self._toast is toast:
                self._toast = None

        anim = Animation(opacity=1, duration=1.2) + Animation(opacity=0,
                                                              duration=0.8)
        anim.bind(on_complete=_remove)
        anim.start(toast)

    def _show_find_toast(self, item, dest=None):
        """Message bref (1 s puis fondu). Si `item` est fourni : montre l'objet
        trouve (en main si `dest` est 0/1, sinon au sol). Si None : case epuisee."""
        # On enleve un eventuel message precedent.
        if self._toast is not None and self._toast.parent:
            self._toast.parent.remove_widget(self._toast)

        toast = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(4),
                          size_hint=(0.28, 0.26),
                          pos_hint={"center_x": 0.5, "top": 0.97})
        _add_panel(toast, alpha=0.6)
        if item:
            toast.add_widget(ItemIcon(item, size_hint=(1, 0.66)))
            place = "(au sol)" if dest is None else "(dans la main)"
            text = "Trouve : " + items.display_name(item) + "\n" + place
        else:
            text = "Tu ne trouves\nplus rien ici."
        msg = scale_font(Label(
            text=text, halign="center", valign="middle", color=(1, 1, 1, 1),
            size_hint=(1, 0.34 if item else 1.0)), 0.018)
        msg.bind(size=lambda w, *_: setattr(w, "text_size", (w.width, w.height)))
        toast.add_widget(msg)

        self.root_layout.add_widget(toast)
        self._toast = toast

        from kivy.animation import Animation

        def _remove(*_):
            if toast.parent:
                toast.parent.remove_widget(toast)
            if self._toast is toast:
                self._toast = None

        # Affiche 1 s, puis fondu doux de 0.8 s.
        anim = Animation(opacity=1, duration=1.0) + Animation(opacity=0,
                                                              duration=0.8)
        anim.bind(on_complete=_remove)
        anim.start(toast)
        self.refresh()

    def _drop_hand(self, slot):
        """Depose au sol l'objet tenu dans la main donnee (0=gauche, 1=droite)."""
        state = App.get_running_app().game_state
        if state is None or self._ff_active or self._moving:
            return
        if state.drop_from_hands(slot):
            App.get_running_app().autosave()
            self.refresh()

    # ------------------------------------------------------------------ #
    # Recolte (exploration) : basee sur les objets VISIBLES de la scene
    # ------------------------------------------------------------------ #
    def _remaining_harvest(self, state):
        """{nom: nombre de recoltes restantes} pour la case actuelle."""
        taken = state.harvested_here()
        rem = {}
        for name, mx in self.scenery.harvest_max.items():
            left = mx - taken.get(name, 0)
            if left > 0:
                rem[name] = left
        return rem

    def _can_find(self):
        state = App.get_running_app().game_state
        return bool(self._remaining_harvest(state))

    def _explore_find(self):
        """Choisit au hasard un objet recoltable visible, le retire de la scene
        et renvoie son nom (ou None s'il n'y a plus rien)."""
        import random as _random
        state = App.get_running_app().game_state
        rem = self._remaining_harvest(state)
        if not rem:
            return None
        names = list(rem.keys())
        weights = list(rem.values())
        name = _random.choices(names, weights=weights, k=1)[0]
        taken = state.harvested_here()
        taken[name] = taken.get(name, 0) + 1
        self.scenery.set_taken(taken)       # retire l'objet du decor
        return name

    # ------------------------------------------------------------------ #
    # Carte
    # ------------------------------------------------------------------ #
    def _open_map(self, *_):
        """Ouvre la carte, seulement si le joueur possede une CARTE."""
        state = App.get_running_app().game_state
        if state is None or self._ff_active or self._moving:
            return
        if not state.has_item(items.MAP_ITEM):
            self._show_message("Il te faut une carte\npour l'ouvrir.")
            return
        self.manager.current = "map"

    # ------------------------------------------------------------------ #
    # Deplacement (depuis l'ecran de jeu)
    # ------------------------------------------------------------------ #
    def _open_move_menu(self, *_):
        """Affiche le choix de direction (relatif, ou cardinal avec boussole)."""
        state = App.get_running_app().game_state
        if state is None or self._ff_active or self._moving:
            return
        self._close_move_menu()

        # Slots de la croix : (libelle, vecteur absolu). Avec boussole = points
        # cardinaux fixes ; sinon RELATIFS a l'orientation du joueur (en face =
        # direction regardee) -> apres le deplacement, l'origine est derriere.
        if state.has_item(items.COMPASS_ITEM):
            top, bottom = ("Nord", (0, -1)), ("Sud", (0, 1))
            left, right = ("Ouest", (-1, 0)), ("Est", (1, 0))
        else:
            top = ("En face", state.dir_vector(0))
            right = ("A droite", state.dir_vector(1))
            bottom = ("Derriere", state.dir_vector(2))
            left = ("A gauche", state.dir_vector(3))

        overlay = FloatLayout(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        panel = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10),
                          size_hint=(0.5, 0.52),
                          pos_hint={"center_x": 0.5, "center_y": 0.5})
        _add_panel(panel, alpha=0.9)
        panel.add_widget(scale_font(Label(text="Se deplacer", bold=True,
                         color=(0.96, 0.82, 0.45, 1), size_hint=(1, 0.16)), 0.03))

        cross = GridLayout(cols=3, spacing=dp(8), size_hint=(1, 0.62))

        def mk(slot):
            label, (dx, dy) = slot
            b = scale_font(StyledButton(text=label), 0.024)
            b.disabled = not state.can_move(dx, dy)
            b.bind(on_release=lambda _w, ddx=dx, ddy=dy: self._do_move(ddx, ddy))
            return b

        for w in (Widget(), mk(top), Widget(),
                  mk(left), Widget(), mk(right),
                  Widget(), mk(bottom), Widget()):
            cross.add_widget(w)
        panel.add_widget(cross)

        close = scale_font(StyledButton(text="Rester ici", size_hint=(1, 0.18)),
                           0.022)
        close.bind(on_release=lambda *_: self._close_move_menu())
        panel.add_widget(close)

        overlay.add_widget(panel)
        self.root_layout.add_widget(overlay)
        self._move_menu = overlay

    def _close_move_menu(self, *_):
        if self._move_menu is not None:
            if self._move_menu.parent:
                self._move_menu.parent.remove_widget(self._move_menu)
            self._move_menu = None

    def _move_message(self, dx, dy, state):
        """Texte du deplacement : cardinal si boussole, sinon RELATIF a
        l'orientation actuelle du joueur."""
        if state.has_item(items.COMPASS_ITEM):
            d = {(0, -1): "vers le Nord", (0, 1): "vers le Sud",
                 (1, 0): "vers l'Est", (-1, 0): "vers l'Ouest"}[(dx, dy)]
        else:
            d = {0: "en face", 1: "vers votre droite",
                 2: "vers l'arriere", 3: "vers votre gauche"}[state.turn_of(dx, dy)]
        return "Deplacement\n" + d + "\nen cours..."

    def _do_move(self, dx, dy):
        state = App.get_running_app().game_state
        if (state is None or self._ff_active or self._moving
                or not state.can_move(dx, dy)):
            return
        self._close_move_menu()
        self._moving = True
        self._pending_move = (dx, dy)

        # Voile noir plein ecran (opacite animee) + horloge + message au centre.
        fader = _Fader(size_hint=(1, 1), pos_hint={"x": 0, "y": 0}, opacity=0)
        with fader.canvas.before:
            Color(0, 0, 0, 1)
            rect = Rectangle()

        def _sync(*_):
            rect.pos = fader.pos
            rect.size = fader.size
        fader.bind(pos=_sync, size=_sync)
        _sync()

        box = BoxLayout(orientation="vertical", spacing=dp(12),
                        size_hint=(0.5, 0.45),
                        pos_hint={"center_x": 0.5, "center_y": 0.5})
        clock = ClockFace(size_hint=(1, 0.62))
        box.add_widget(clock)
        msg = Label(text=self._move_message(dx, dy, state), halign="center",
                    valign="middle", color=(1, 1, 1, 1), size_hint=(1, 0.38))
        msg.bind(size=lambda w, *_: setattr(w, "text_size", (w.width, w.height)))
        scale_font(msg)
        box.add_widget(msg)
        fader.add_widget(box)

        self.root_layout.add_widget(fader)
        self._fader = fader
        self._fader_clock = clock
        clock.start()

        # Fondu vers le noir (1 s) -> a la fin, on effectue le deplacement.
        a_in = Animation(opacity=1, duration=1.0)
        a_in.bind(on_complete=lambda *_: self._move_apply())
        a_in.start(fader)
        # Au bout de 3 s (fondu inclus) -> fondu retour vers normal.
        self._move_event = Clock.schedule_once(lambda _dt: self._move_fade_out(),
                                               3.0)

    def _move_apply(self):
        """Effectue le deplacement (ecran noir) une fois le fondu termine."""
        state = App.get_running_app().game_state
        if state is None or self._pending_move is None:
            return
        dx, dy = self._pending_move
        self._pending_move = None
        if not state.move(dx, dy):
            return
        # On regarde desormais dans la direction du deplacement (l'origine se
        # retrouve derriere nous).
        state.face(dx, dy)
        state.reveal_zone(state.player_x, state.player_y)
        state.energy = _clamp100(state.energy + MOVE_ENERGY)
        state.hunger = _clamp100(state.hunger + MOVE_HUNGER)
        state.tick(MOVE_MINUTES * 60)               # le temps du trajet passe
        state.advance_survival(MOVE_MINUTES * 60)
        state.action_count += 1
        state.add_log(f"{state.current_zone()} "
                      f"({state.player_x},{state.player_y})")
        self.refresh()
        App.get_running_app().autosave()

    def _move_fade_out(self):
        """Fondu noir -> normal (1 s), puis nettoyage."""
        self._move_event = None
        if self._fader is None:
            return
        a_out = Animation(opacity=0, duration=1.0)
        a_out.bind(on_complete=lambda *_: self._move_done())
        a_out.start(self._fader)

    def _move_done(self):
        if self._fader_clock is not None:
            self._fader_clock.stop()
        if self._fader is not None and self._fader.parent:
            self._fader.parent.remove_widget(self._fader)
        self._fader = None
        self._fader_clock = None
        self._moving = False
        self.refresh()

    # ------------------------------------------------------------------ #
    # Menu pause (bouton "Menu")
    # ------------------------------------------------------------------ #
    def _toggle_pause_menu(self, *_):
        """Le bouton Menu ouvre/ferme le panneau (et change de nom)."""
        if self._pause_menu is not None:
            self._close_pause_menu()
        else:
            self._open_pause_menu()

    def _open_pause_menu(self, *_):
        """Panneau lateral droit : Parametres / Statistiques / Quitter.
        Le bouton "Menu" devient "Continuer" tant que le panneau est ouvert."""
        if self._ff_active or self._moving:
            return
        self._close_pause_menu()

        overlay = _ModalOverlay(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        with overlay.canvas.before:
            Color(0, 0, 0, 0.35)
            rect = Rectangle()

        def _sync(*_):
            rect.pos = overlay.pos
            rect.size = overlay.size
        overlay.bind(pos=_sync, size=_sync)
        _sync()

        panel = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(14),
                          size_hint=(0.30, 1), pos_hint={"right": 1, "y": 0})
        _add_panel(panel, alpha=0.85)

        def mk(text, cb):
            b = scale_font(StyledButton(text=text, size_hint=(1, 0.13)), 0.026)
            b.bind(on_release=cb)
            return b

        panel.add_widget(mk("Parametres", lambda *_: self._go_settings()))
        panel.add_widget(mk("Statistiques", lambda *_: self._go_stats()))
        panel.add_widget(mk("Quitter", self.back_to_menu))
        panel.add_widget(Widget())                  # espace vide en bas

        overlay.add_widget(panel)
        self.root_layout.add_widget(overlay)
        self._pause_menu = overlay
        self.menu_label.text = "Continuer"
        # Le bouton "Menu" (devenu "Continuer") doit rester AU-DESSUS du panneau
        # pour rester visible et cliquable -> on le replace au sommet.
        self.root_layout.remove_widget(self.menu_cell)
        self.root_layout.add_widget(self.menu_cell)

    def _close_pause_menu(self, *_):
        if self._pause_menu is not None:
            if self._pause_menu.parent:
                self._pause_menu.parent.remove_widget(self._pause_menu)
            self._pause_menu = None
        self.menu_label.text = "Menu"

    def _go_settings(self):
        self._close_pause_menu()
        self.manager.get_screen("settings").return_to = "game"
        self.manager.current = "settings"

    def _go_stats(self):
        self._close_pause_menu()
        self.manager.get_screen("stats").return_to = "game"
        self.manager.current = "stats"

    def back_to_menu(self, *_):
        self._close_move_menu()
        self._close_pause_menu()
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

        self.stat_health.set_value(state.health)
        self.stat_energy.set_value(state.energy)
        self.stat_sleep.set_value(state.sleep)
        self.stat_hunger.set_value(state.hunger)
        self.stat_thirst.set_value(state.thirst)

        # Pendant l'exploration, on CACHE l'objet tenu, le bouton Deposer
        # et le label (animation des mains uniquement, sans distractions).
        exploring = self._ff_active and self._ff_label == "Explorer"

        # Objets tenus -> affiches dans les mains, sauf pendant l'exploration.
        if exploring:
            self.hands.set_items(None, None)
        else:
            self.hands.set_items(state.hands[0], state.hands[1])

        # Boutons "Deposer" + nom de l'objet tenu : visibles seulement si la
        # main correspondante tient un objet, et NON pendant l'exploration.
        for slot, db in enumerate(self.drop_btns):
            item = state.hands[slot]
            occupied = item is not None
            visible = occupied and not exploring
            db.opacity = 1 if visible else 0
            db.disabled = (not occupied) or self._ff_active
            lbl = self.drop_labels[slot]
            lbl.opacity = 1 if visible else 0
            if visible:
                lbl.text = items.display_name(item)

        # (Re)construit la grille des boutons si l'outillage a change (hache /
        # gourde) : ces boutons apparaissent / disparaissent completement.
        vk = self._action_visible_key(state)
        if vk != self._action_visible:
            self._action_visible = vk
            self._build_action_grid(state)

        # Boutons d'action : verrouilles pendant une avance rapide. Sinon, ils
        # restent CLIQUABLES mais grises si l'action est indisponible, pour
        # qu'un appui puisse en expliquer la raison (cf. do_action).
        for btn, action in self._action_buttons:
            if self._ff_active:
                btn.disabled = True
                btn.opacity = 1.0
            else:
                btn.disabled = False
                btn.opacity = 0.45 if _action_reason(state, action) else 1.0
        # Carte : grisee (mais cliquable) tant que le joueur n'a pas de carte ;
        # un appui explique alors qu'il en faut une.
        if self._ff_active:
            self.map_btn.disabled = True
            self.map_btn.opacity = 1.0
        else:
            self.map_btn.disabled = False
            self.map_btn.opacity = 1.0 if state.has_item(items.MAP_ITEM) else 0.45
        self.craft_btn.disabled = self._ff_active
        self.back_btn.disabled = self._ff_active
        self.move_btn.disabled = self._ff_active

        self.background.set_seconds(state.time_seconds)
        # Assombrit le decor selon l'heure (voile de nuit).
        self._night_color.a = night_darkness(state.time_seconds)
        key = (zone, state.player_x, state.player_y)
        if key != self._scene_key:
            # On passe les objets deja recoltes pour masquer ceux pris ici.
            self.scenery.set_scene(zone, state.player_x * 131 + state.player_y,
                                   taken=state.harvested_here())
            self._scene_key = key

    def _periodic_autosave(self, _dt):
        if not self._ff_active:
            App.get_running_app().autosave()
