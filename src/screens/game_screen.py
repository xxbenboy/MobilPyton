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
import math

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp

from src.game_state import _clamp100
from src.widgets.animated_background import AnimatedBackground
from src.widgets.zone_scenery import ZoneScenery

from src import items
from src.widgets.player_hands import PlayerHands
from src.widgets.icon_button import IconButton
from src.widgets.styled_button import StyledButton
from src.widgets.item_icon import ItemIcon
from src.widgets.stat_circle import StatCircle
from src.widgets.responsive import scale_font

AUTOSAVE_SECONDS = 30
TIME_SCALE = 144              # 24h en 10 min
FAST_FORWARD_SCALE = 3600     # avance rapide : 1h de jeu / s reelle

# Actions : effets ponctuels (la faim/soif/sommeil derivent en plus avec le
# temps). "requires_sleep" => possible seulement si on est assez fatigue.
ACTIONS = [
    {"label": "Explorer", "icon": "explore", "name": "Explorer",
     "minutes": 90, "energy": -10, "type": "explore"},
    {"label": "Couper du bois", "icon": "wood", "name": "Couper\ndu bois",
     "minutes": 120, "energy": -15, "wood": 3},
    {"label": "Chercher a manger", "icon": "food", "name": "Chercher\na manger",
     "minutes": 60, "energy": -5, "hunger": -25, "food": 2},
    {"label": "Boire", "icon": "drink", "name": "Boire",
     "minutes": 10, "thirst": -40, "type": "drink"},
    {"label": "Remplir gourde", "icon": "fill", "name": "Remplir\ngourde",
     "minutes": 15, "type": "fill"},
    {"label": "Se reposer", "icon": "rest", "name": "Se\nreposer",
     "minutes": 240, "energy": 35, "sleep": 50, "requires_sleep": True},
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
    if action.get("type") == "explore" and state.hands_full():
        # Explorer : interdit si les deux mains sont pleines (l'objet trouve
        # doit pouvoir aller dans une main).
        return False
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


class GameScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._autosave_event = None
        self._tick_event = None
        self._time_accum = 0.0
        self._ff_active = False
        self._ff_remaining = 0.0
        self._ff_label = ""
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
        # Mains du joueur (vue 1re personne), devant le decor.
        self.hands = PlayerHands(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.hands)

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

        # ---- Boutons d'action : icones CARREES, confinees EN HAUT A GAUCHE.
        # La zone est fixe ; ajouter des boutons augmente le nombre de
        # colonnes/lignes et donc REDUIT la taille des boutons (jamais la zone).
        n_btn = len(ACTIONS) + 1                  # actions + Craft
        cols = max(1, int(math.ceil(n_btn ** 0.5)))
        # Grille resserree, plaquee a gauche. La LARGEUR n'est pas fixee : chaque
        # colonne s'ajuste a son contenu le plus large (en general le NOM), et la
        # grille prend exactement cette largeur -> boutons aussi colles que
        # possible mais qui ne se chevauchent JAMAIS (les noms non plus).
        grid = GridLayout(cols=cols, spacing=[dp(2), dp(12)],
                          size_hint=(None, 0.50),
                          pos_hint={"x": 0.004, "top": 0.96})
        grid.bind(minimum_width=grid.setter("width"))
        self._action_buttons = []   # (bouton, action)
        action_cells = []           # (cell, btn, lbl) : pour egaliser les largeurs

        def _fit_cells(*_):
            if not action_cells:
                return
            # Largeur UNIFORME = la cellule la plus large (en general "Explorer",
            # dont le nom est le plus long). Toutes les cellules identiques -> les
            # logos (centres) sont tous alignes, et rien ne se chevauche.
            w = max(max(btn.width, lbl.texture_size[0])
                    for _c, btn, lbl in action_cells) + dp(6)
            for cell, _b, _l in action_cells:
                cell.width = w

        def add_cell(icon, name, on_release):
            # Largeur de la cellule pilotee par le contenu (jamais d'overlap),
            # puis egalisee entre toutes les cellules (voir _fit_cells).
            cell = BoxLayout(orientation="vertical", spacing=2, size_hint_x=None)
            area = AnchorLayout(size_hint=(1, 0.66))
            btn = IconButton(icon=icon, size_hint=(None, None))

            def _square(a, *_):                      # bouton carre = taille logo
                s = a.height * 0.94
                btn.size = (s, s)
            area.bind(size=_square)
            btn.bind(on_release=on_release)
            area.add_widget(btn)

            # Nom du bouton : fond noir ajuste a la taille du texte (comme les
            # boutons Carte/Menu). Logo inchange (taille basee sur la hauteur).
            lbl = _button_label(name)
            cell.add_widget(area)
            cell.add_widget(lbl)

            action_cells.append((cell, btn, lbl))
            btn.bind(size=_fit_cells)
            lbl.bind(texture_size=_fit_cells)

            grid.add_widget(cell)
            return btn

        for action in ACTIONS:
            btn = add_cell(action["icon"], action["name"],
                           lambda _w, a=action: self.do_action(a))
            self._action_buttons.append((btn, action))
        self.craft_btn = add_cell("craft", "Craft",
                                  lambda *_: setattr(self.manager,
                                                     "current", "craft"))
        root.add_widget(grid)

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
        self.map_btn.bind(on_release=lambda *_: setattr(self.manager, "current", "map"))
        map_area.add_widget(self.map_btn)
        map_cell.add_widget(map_area)
        map_cell.add_widget(_button_label("Carte"))
        root.add_widget(map_cell)

        # ---- Bouton MENU (bas a droite) ----
        menu_cell = BoxLayout(orientation="vertical", spacing=2, size_hint=(0.06, 0.16),
                              pos_hint={"right": 0.994, "y": 0.012})
        menu_area = AnchorLayout(size_hint=(1, 0.66))
        self.back_btn = IconButton(icon="home", size_hint=(None, None))
        def _menu_square(a, *_):
            s = a.height * 0.94
            self.back_btn.size = (s, s)
        menu_area.bind(size=_menu_square)
        self.back_btn.bind(on_release=self.back_to_menu)
        menu_area.add_widget(self.back_btn)
        menu_cell.add_widget(menu_area)
        menu_cell.add_widget(_button_label("Menu"))
        root.add_widget(menu_cell)

        # ---- Boutons "Deposer" (bas, vis-a-vis de chaque main) ----
        # Permettent de poser l'objet tenu sans passer par le menu Craft.
        # Masques quand la main est vide (gere dans refresh()).
        self.drop_btns = []
        for slot, cx in ((0, 0.31), (1, 0.69)):     # 0=gauche, 1=droite
            db = scale_font(StyledButton(text="Deposer", size_hint=(0.13, 0.07),
                            pos_hint={"center_x": cx, "y": 0.015}), 0.02)
            db.bind(on_release=lambda _w, s=slot: self._drop_hand(s))
            root.add_widget(db)
            self.drop_btns.append(db)

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
        # Verifier si la zone est epuisee AVANT de lancer l'exploration
        if atype == "explore" and not state.can_find():
            self._show_find_toast(None)
            return
        # Eau : remplir la gourde au ruisseau ; boire consomme la gourde sauf
        # si on boit directement a un ruisseau.
        if atype == "fill":
            state.water += 3
        elif atype == "drink" and not state.has_water_source():
            state.water = max(0, state.water - 1)
        elif atype == "explore":
            # Trouvaille ponderee par la rarete ; None si la case est epuisee
            # (stock de 5 a 15 trouvailles par case). Affiche a la fin du trajet.
            self._found_item = state.try_find()
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
        self._ff_remaining = action["minutes"] * 60.0
        self._ff_label = action["label"]
        self._time_accum = 0.0
        self.refresh()
        App.get_running_app().autosave()

    def _finish_action(self):
        self._ff_active = False
        self._ff_label = ""
        if self._found_item:
            item = self._found_item
            self._found_item = None
            # L'objet trouve va dans une main (droite en priorite) ; s'il n'est
            # pas ramassable a la main, il reste au sol.
            dest = App.get_running_app().game_state.auto_take(item)
            self._show_find_toast(item, dest)
        elif self._did_explore:
            # Exploration sans resultat : la case n'a plus rien a offrir.
            self._show_find_toast(None)
        self._did_explore = False
        App.get_running_app().autosave()

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
        if state is None or self._ff_active:
            return
        if state.drop_from_hands(slot):
            App.get_running_app().autosave()
            self.refresh()

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

        self.stat_health.set_value(state.health)
        self.stat_energy.set_value(state.energy)
        self.stat_sleep.set_value(state.sleep)
        self.stat_hunger.set_value(state.hunger)
        self.stat_thirst.set_value(state.thirst)

        # Objets tenus -> affiches dans les mains du joueur (1re personne).
        self.hands.set_items(state.hands[0], state.hands[1])

        # Boutons "Deposer" : visibles seulement si la main correspondante tient
        # un objet (et inactifs pendant une avance rapide).
        for slot, db in enumerate(self.drop_btns):
            occupied = state.hands[slot] is not None
            db.opacity = 1 if occupied else 0
            db.disabled = (not occupied) or self._ff_active

        # Boutons : tout verrouille en avance rapide ; sinon selon la zone /
        # l'etat (dormir, boire, remplir la gourde).
        for btn, action in self._action_buttons:
            btn.disabled = self._ff_active or not _action_available(state, action)
        self.map_btn.disabled = self._ff_active
        self.craft_btn.disabled = self._ff_active
        self.back_btn.disabled = self._ff_active

        self.background.set_seconds(state.time_seconds)
        key = (zone, state.player_x, state.player_y)
        if key != self._scene_key:
            self.scenery.set_scene(zone, state.player_x * 131 + state.player_y)
            self._scene_key = key

    def _periodic_autosave(self, _dt):
        if not self._ff_active:
            App.get_running_app().autosave()
