"""Ecran PLACEMENT : vue de dessus + grille 5x5 pour choisir ou installer
un objet (feu de camp, ...) sur la case courante.

Le joueur est fixe au centre-bas de la grille (gx=2, gy=0), regardant vers le
haut (gy croissant). Un tap sur une case libre confirme la position ; l'objet
tenu dans la main _slot (definie par GameScreen avant la navigation) passe
dans state.installed et la vue revient au jeu.

Le placement est IRREVERSIBLE : un objet installe ne peut plus etre
ramasse ni deplace.
"""
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import (Color, Rectangle, RoundedRectangle, Line, Ellipse)
from kivy.metrics import dp

from src import items
from src.widgets.animated_background import AnimatedBackground, night_darkness
from src.widgets.zone_scenery import ZoneScenery
from src.widgets.styled_button import StyledButton
from src.widgets.responsive import scale_font, dh

# Couleurs de la grille. Definies ICI une seule fois : la grille ET la legende
# les utilisent, elles ne peuvent donc jamais se contredire.
CELL_BG = (0, 0, 0, 0.20)             # fond commun a toutes les cases
CELL_LINE = (1, 1, 1, 0.60)           # trait de separation
CELL_TAKEN = (0.90, 0.35, 0.30, 0.35)     # rouge  : deja utilise
CELL_NATURE = (0.25, 0.55, 0.30, 0.45)    # vert   : occupe par la nature
CELL_PLAYER = (0.30, 0.70, 1.00, 0.35)    # bleu   : le joueur
CELL_FREE = (0, 0, 0, 0)                  # aucune : libre

# Legende affichee a gauche de la grille, dans l'ordre d'affichage.
LEGEND = (
    (CELL_TAKEN, "Emplacement\ndeja utilise"),
    (CELL_NATURE, "Zone occupee\n(nature)"),
    (CELL_FREE, "Zone vacante"),
    (CELL_PLAYER, "Vous"),
)


class _Swatch(Widget):
    """Petit carre de couleur, dessine EXACTEMENT comme une case de la grille.

    Meme fond sombre et meme contour : une case "vacante" (sans couleur) est
    donc reconnaissable telle quelle."""

    def __init__(self, rgba, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            Color(*CELL_BG)
            self._bg = Rectangle()
            Color(*rgba)
            self._fill = Rectangle()
            Color(*CELL_LINE)
            self._border = Line(width=1.2)
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        s = min(self.width, self.height)
        x = self.x + (self.width - s) / 2.0
        y = self.y + (self.height - s) / 2.0
        self._bg.pos = self._fill.pos = (x, y)
        self._bg.size = self._fill.size = (s, s)
        self._border.rectangle = (x, y, s, s)


class _Legend(BoxLayout):
    """Panneau explicatif : a quoi correspond la couleur de chaque case."""

    def __init__(self, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("padding", dp(8))
        kwargs.setdefault("spacing", dp(4))
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(0.05, 0.07, 0.10, 0.55)
            self._bg = RoundedRectangle(radius=[dp(10)])
        self.bind(pos=self._sync, size=self._sync)

        title = scale_font(Label(text="Legende", bold=True,
                                 color=(0.96, 0.82, 0.45, 1),
                                 halign="center", valign="middle",
                                 size_hint_y=None, height=dh(46)))
        title.bind(size=lambda w, *_: setattr(
            w, "text_size", (w.width, w.height)))
        self.add_widget(title)

        for rgba, text in LEGEND:
            row = BoxLayout(orientation="horizontal", spacing=dp(8),
                            size_hint_y=None, height=dh(70))
            row.add_widget(_Swatch(rgba, size_hint_x=None, width=dh(70)))
            lbl = scale_font(Label(text=text, color=(0.92, 0.92, 0.95, 1),
                                   halign="left", valign="middle"))
            lbl.bind(size=lambda w, *_: setattr(
                w, "text_size", (w.width, w.height)))
            row.add_widget(lbl)
            self.add_widget(row)

    def _sync(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size


class _GridOverlay(Widget):
    """Grille 5x5 avec joueur en (gx=2, gy=0). Cellules cliquables (sauf
    la case joueur et les cases deja prises)."""

    def __init__(self, on_cell_pick, **kwargs):
        super().__init__(**kwargs)
        self.on_cell_pick = on_cell_pick
        self.taken = set()               # {(gx, gy), ...} objets installes
        self.nature = set()              # {(gx, gy), ...} arbre/buisson/rocher
        self.bind(pos=self._redraw, size=self._redraw)

    def _grid_geom(self):
        cs = min(self.width, self.height) / 5.2   # petite marge autour
        total = 5 * cs
        ox = self.center_x - total / 2
        oy = self.center_y - total / 2
        return ox, oy, cs

    def _redraw(self, *_):
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return
        ox, oy, cs = self._grid_geom()
        with self.canvas:
            # Fond de la grille (semi-transparent pour laisser voir le decor).
            Color(*CELL_BG)
            Rectangle(pos=(ox, oy), size=(5 * cs, 5 * cs))
            # Lignes blanches translucides.
            Color(*CELL_LINE)
            for i in range(6):
                Line(points=[ox + i * cs, oy,
                             ox + i * cs, oy + 5 * cs], width=1.2)
                Line(points=[ox, oy + i * cs,
                             ox + 5 * cs, oy + i * cs], width=1.2)
            # Case joueur (gx=2, gy=0) : surlignee bleu, non cliquable.
            px = ox + 2 * cs
            py = oy + 0 * cs
            Color(*CELL_PLAYER)
            Rectangle(pos=(px, py), size=(cs, cs))
            # Point du joueur (petit disque bleu au centre de sa case).
            r = cs * 0.18
            Color(0.30, 0.70, 1.00, 1.0)
            Ellipse(pos=(px + cs / 2 - r, py + cs / 2 - r),
                    size=(r * 2, r * 2))
            # Fleche de direction (le joueur regarde vers le haut de la grille).
            Color(1, 1, 1, 0.95)
            aw, ah = cs * 0.28, cs * 0.28
            acx = px + cs / 2
            ay0 = py + cs * 0.55
            ay1 = py + cs * 0.90
            Line(points=[acx, ay0, acx, ay1], width=2.2)
            Line(points=[acx - aw / 2, ay1 - aw * 0.55, acx, ay1,
                         acx + aw / 2, ay1 - aw * 0.55], width=2.2)
            # Cases occupees par la NATURE (arbre, buisson, gros rocher) :
            # surlignees vertes, non cliquables.
            Color(*CELL_NATURE)
            for (gx, gy) in self.nature:
                tx = ox + gx * cs
                ty = oy + gy * cs
                Rectangle(pos=(tx, ty), size=(cs, cs))
            # Cases deja prises (installees) : surlignees rouge.
            Color(*CELL_TAKEN)
            for (gx, gy) in self.taken:
                tx = ox + gx * cs
                ty = oy + gy * cs
                Rectangle(pos=(tx, ty), size=(cs, cs))

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        ox, oy, cs = self._grid_geom()
        if not (ox <= touch.x < ox + 5 * cs and oy <= touch.y < oy + 5 * cs):
            return super().on_touch_down(touch)
        gx = int((touch.x - ox) / cs)
        gy = int((touch.y - oy) / cs)
        gx = max(0, min(4, gx))
        gy = max(0, min(4, gy))
        if (gx, gy) == (2, 0):
            return True                  # case joueur : ignoree
        if (gx, gy) in self.taken or (gx, gy) in self.nature:
            return True                  # deja prise ou occupee par la nature
        self.on_cell_pick(gx, gy)
        return True


class PlaceScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._slot = None                # main dont on installe (0 ou 1)

        root = FloatLayout()
        self.background = AnimatedBackground(time_scale=0, size_hint=(1, 1),
                                             pos_hint={"x": 0, "y": 0})
        root.add_widget(self.background)
        # Fond = vue VERS LE BAS du sol de la case courante.
        self.scenery = ZoneScenery(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.scenery)
        self._scene_key = None

        # Voile de nuit (comme dans la carte et le craft).
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

        self.grid_overlay = _GridOverlay(on_cell_pick=self._on_cell_pick,
                                         size_hint=(0.90, 0.78),
                                         pos_hint={"center_x": 0.5,
                                                   "center_y": 0.46})
        root.add_widget(self.grid_overlay)

        # Legende, a GAUCHE de la grille : en paysage la grille est carree et
        # centree, la bande de gauche est donc libre.
        self.legend = _Legend(size_hint=(0.24, None),
                              pos_hint={"x": 0.02, "center_y": 0.46})
        self.legend.bind(minimum_height=self.legend.setter("height"))
        self.legend.height = self.legend.minimum_height
        root.add_widget(self.legend)

        # Titre (haut).
        self.title = scale_font(Label(text="Choisis une case",
                                bold=True, color=(1, 1, 1, 1),
                                halign="center", valign="middle",
                                size_hint=(0.90, 0.08),
                                pos_hint={"center_x": 0.5, "top": 0.98}),
                                0.028)
        self.title.bind(size=lambda w, *_: setattr(
            w, "text_size", (w.width, w.height)))
        root.add_widget(self.title)

        # Bouton Annuler (bas droite) : retour au jeu sans installer.
        cancel = scale_font(StyledButton(text="Annuler",
                            size_hint=(0.20, 0.08),
                            pos_hint={"right": 0.98, "y": 0.02}), 0.022)
        cancel.bind(on_release=lambda *_: setattr(self.manager,
                                                  "current", "game"))
        root.add_widget(cancel)

        self.add_widget(root)

    def on_pre_enter(self):
        state = App.get_running_app().game_state
        if state is None:
            return
        self.background.set_seconds(state.time_seconds)
        self.background.set_weather(state.effective_weather())
        self._night_color.a = night_darkness(state.time_seconds)
        zone = state.current_zone()
        key = (zone, state.player_x, state.player_y)
        if key != self._scene_key:
            self.scenery.set_ground(zone,
                                    state.player_x * 131 + state.player_y)
            self._scene_key = key
        # Marque les positions deja installees comme non cliquables, et les
        # cases occupees par un GROS element du decor (arbre, buisson, rocher).
        self.grid_overlay.taken = {(int(o[1]), int(o[2]))
                                   for o in state.installed_objects_here()}
        self.grid_overlay.nature = set(state.nature_cells_here().keys())
        self.grid_overlay._redraw()
        # Titre : quel objet on est en train de placer ?
        if self._slot is not None and self._slot in (0, 1):
            item = state.hands[self._slot]
            if item:
                self.title.text = f"Placer : {items.display_name(item)}"
            else:
                self.title.text = "Choisis une case"
        else:
            self.title.text = "Choisis une case"

    def _on_cell_pick(self, gx, gy):
        state = App.get_running_app().game_state
        if state is None or self._slot is None:
            self.manager.current = "game"
            return
        if state.install_from_hand(self._slot, gx, gy):
            App.get_running_app().autosave()
        self._slot = None
        self.manager.current = "game"
