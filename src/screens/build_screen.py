"""
ECRAN CHANTIER : le volume d'un plan de construction, cube par cube.

On y entre depuis la ZONE, en touchant un plan pose. L'ecran garde le decor de
la case -- on est toujours au meme endroit -- mais RIEN du jeu : ni les mains,
ni la barre de survie, ni les boutons d'action. On ne survit pas ici, on
batit ; tout ce qui ne sert pas a batir n'a rien a y faire, et le volume a
besoin de toute la place.

TROIS ELEMENTS, et rien d'autre :

- LE VOLUME, au centre, en cubes transparents cercles de blanc. Transparents
  parce qu'il faut voir a travers : un cube plein cacherait ceux du fond, et
  c'est justement le fond qu'on vient designer.

- LE TIROIR DES PIECES, a droite, ferme par defaut. Sol, mur, toit pour le
  palier 1. Il s'ouvre d'une fleche et se referme de la meme fleche, ou d'un
  toucher ailleurs sur l'ecran -- comme on repousse un panneau.

- LE STOCK, a gauche : les trois matieres et ce qu'on en a. Il ne se touche
  pas, il informe. Sans lui, le tiroir annoncerait des pieces impossibles
  sans jamais dire ce qui manque.
"""
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, Line, Rectangle, Mesh
from kivy.metrics import dp

from src import items
from src.widgets.animated_background import AnimatedBackground, night_darkness
from src.widgets import daylight
from src.widgets.zone_scenery import ZoneScenery
from src.widgets.styled_button import StyledButton
from src.widgets.responsive import scale_font
from src.widgets.item_icon import ItemIcon
from src.widgets.panels import panel
from src.widgets import build_grid

# Les cubes. Le remplissage est TRES pale : il donne le volume sans rien
# cacher, et quatre etages empiles restent lisibles au travers.
CUBE_FILL = (1.0, 1.0, 1.0, 0.045)
CUBE_EDGE = (1.0, 1.0, 1.0, 0.55)
# L'ARETE DU CONTOUR est nettement plus franche : c'est elle qui donne sa
# forme au volume. Sans elle, quatre-vingt-seize traits pales se valent tous
# et l'oeil ne trouve plus les bords.
CUBE_EDGE_OUT = (1.0, 1.0, 1.0, 0.95)


class _Volume(Widget):
    """Le volume en cubes, centre, transparent, cercle de blanc."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.volume = (0, 0, 0)
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_):
        self.canvas.clear()
        nx, ny, nz = self.volume
        if self.width <= 0 or self.height <= 0 or min(nx, ny, nz) <= 0:
            return
        taille, cx, cy = build_grid.fit(self.volume, self.width, self.height)
        cx += self.x
        cy += self.y
        with self.canvas:
            for (x, y, z) in build_grid.ordre_dessin(self.volume):
                faces = build_grid.cube_faces(x, y, z, cx, cy, taille)
                for _nom, pts in faces:
                    Color(*CUBE_FILL)
                    self._quad(pts)
                    Color(*CUBE_EDGE)
                    Line(points=[c for p in pts for c in p], close=True,
                         width=1.0)
            # Le contour du volume entier, par-dessus : les douze aretes de la
            # grande boite, tracees plus franchement.
            Color(*CUBE_EDGE_OUT)
            for a, b in self._aretes(nx, ny, nz):
                p1 = build_grid.project(*a, cx, cy, taille)
                p2 = build_grid.project(*b, cx, cy, taille)
                Line(points=[p1[0], p1[1], p2[0], p2[1]], width=1.9)

    @staticmethod
    def _aretes(nx, ny, nz):
        """Les douze aretes de la boite englobante, en sommets de grille."""
        coins = [(x, y, z) for x in (0, nx) for y in (0, ny) for z in (0, nz)]
        out = []
        for i, a in enumerate(coins):
            for b in coins[i + 1:]:
                # Deux coins ne forment une arete que s'ils different sur UN
                # seul axe : sinon c'est une diagonale, qui traverserait la
                # boite.
                if sum(1 for k in range(3) if a[k] != b[k]) == 1:
                    out.append((a, b))
        return out

    @staticmethod
    def _quad(pts):
        """Remplit un quadrilatere. Kivy n'a pas de polygone : on passe par un
        maillage de deux triangles."""
        verts = []
        for x, y in pts:
            verts += [x, y, 0, 0]
        Mesh(vertices=verts, indices=[0, 1, 2, 0, 2, 3], mode="triangles")


class BuildScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Le plan dont on ouvre le chantier : (nom, gx, gy).
        self.blueprint = None
        self._part = None            # piece choisie dans le tiroir
        self._drawer_open = False

        root = FloatLayout()
        self.background = AnimatedBackground(time_scale=0, size_hint=(1, 1),
                                             pos_hint={"x": 0, "y": 0})
        root.add_widget(self.background)
        # Le decor de la case, vu du sol : on n'a pas quitte l'endroit.
        self.scenery = ZoneScenery(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.scenery)
        self._scene_key = None

        self.night = Widget(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        with self.night.canvas:
            self._night_color = Color(0.03, 0.05, 0.12, 0.0)
            self._night_rect = Rectangle()

        def _sync_night(*_):
            self._night_rect.pos = self.night.pos
            self._night_rect.size = self.night.size
        self.night.bind(pos=_sync_night, size=_sync_night)
        root.add_widget(self.night)

        # LE VOLUME, au centre. Il occupe la bande centrale : les deux bords
        # sont pris par le stock et par le tiroir.
        self.volume = _Volume(size_hint=(0.62, 0.86),
                              pos_hint={"center_x": 0.5, "center_y": 0.50})
        root.add_widget(self.volume)

        # LE STOCK, a gauche. Informe seulement.
        self.stock_box = BoxLayout(orientation="vertical", padding=dp(6),
                                   spacing=dp(4), size_hint=(0.135, 0.42),
                                   pos_hint={"x": 0.012, "center_y": 0.50})
        panel(self.stock_box, alpha=0.50)
        root.add_widget(self.stock_box)

        # LE TIROIR, a droite : ferme par defaut.
        self.drawer = BoxLayout(orientation="vertical", padding=dp(6),
                                spacing=dp(6), size_hint=(0.155, 0.62),
                                pos_hint={"right": 0.988, "center_y": 0.50})
        panel(self.drawer, alpha=0.55)
        root.add_widget(self.drawer)

        # La FLECHE qui l'ouvre et le referme. Elle reste toujours visible :
        # c'est la seule chose qui dit que le tiroir existe.
        self.arrow = scale_font(StyledButton(text="<", size_hint=(0.045, 0.10),
                                pos_hint={"right": 0.836,
                                          "center_y": 0.50}), 0.030)
        self.arrow.bind(on_release=lambda *_: self._toggle_drawer())
        root.add_widget(self.arrow)

        self.title = scale_font(Label(text="Chantier", bold=True,
                                color=(0.96, 0.82, 0.45, 1), halign="center",
                                valign="middle", size_hint=(0.6, 0.08),
                                pos_hint={"center_x": 0.5, "top": 0.99}),
                                0.028)
        self.title.bind(size=lambda w, *_: setattr(
            w, "text_size", (w.width, w.height)))
        root.add_widget(self.title)

        self.hint = scale_font(Label(text="", halign="center", valign="middle",
                               color=(0.88, 0.88, 0.92, 1),
                               size_hint=(0.6, 0.06),
                               pos_hint={"center_x": 0.5, "y": 0.10}), 0.019)
        self.hint.bind(size=lambda w, *_: setattr(
            w, "text_size", (w.width, w.height)))
        root.add_widget(self.hint)

        quit_btn = scale_font(StyledButton(text="Quitter le chantier",
                              size_hint=(0.24, 0.08),
                              pos_hint={"center_x": 0.5, "y": 0.015}), 0.022)
        quit_btn.bind(on_release=lambda *_: self._leave())
        root.add_widget(quit_btn)

        self.add_widget(root)
        self._set_drawer(False)

    # ------------------------------------------------------------------ #
    def _leave(self):
        self.manager.current = "game"

    def _toggle_drawer(self):
        self._set_drawer(not self._drawer_open)

    def _set_drawer(self, ouvert):
        self._drawer_open = bool(ouvert)
        # Masque par l'OPACITE, jamais par `disabled` : dans Kivy un widget
        # desactive avale les touches qui tombent dessus.
        self.drawer.opacity = 1.0 if self._drawer_open else 0.0
        self.arrow.text = ">" if self._drawer_open else "<"

    def on_touch_down(self, touch):
        # Un toucher AILLEURS referme le tiroir -- comme on repousse un
        # panneau. La fleche est exclue : elle a deja sa propre bascule, et
        # refermer ici la ferait rouvrir aussitot.
        if (self._drawer_open
                and not self.drawer.collide_point(*touch.pos)
                and not self.arrow.collide_point(*touch.pos)):
            self._set_drawer(False)
            return True
        return super().on_touch_down(touch)

    # ------------------------------------------------------------------ #
    def on_pre_enter(self):
        state = App.get_running_app().game_state
        if state is None:
            return
        self.background.set_seconds(state.time_seconds)
        self.background.set_weather(state.effective_weather())
        self._night_color.rgb = daylight.veil_color(state.time_seconds)
        self._night_color.a = night_darkness(state.time_seconds)
        self.scenery.set_daylight(state.time_seconds)
        zone = state.current_zone()
        seed = state.player_x * 131 + state.player_y
        key = (zone, state.player_x, state.player_y)
        if key != self._scene_key:
            self.scenery.set_ground(zone, seed)
            self._scene_key = key

        nom = self.blueprint[0] if self.blueprint else None
        self.volume.volume = build_grid.volume_for(nom)
        self.volume._redraw()
        self.title.text = "Chantier — %s" % items.display_name(nom)
        self._set_drawer(False)
        self._part = None
        self._rebuild_stock(state)
        self._rebuild_drawer(state, nom)
        self.hint.text = ""

    def _rebuild_stock(self, state):
        """Les trois matieres et ce qu'on en a, a gauche."""
        self.stock_box.clear_widgets()
        stock = state.build_stock()
        for matiere, requis in items.BUILD_COST.items():
            ligne = BoxLayout(orientation="horizontal", spacing=dp(4))
            ligne.add_widget(ItemIcon(matiere, show_name=False,
                                      size_hint_x=0.42))
            possede = stock.get(matiere, 0)
            # On montre CE QU'ON A sur CE QU'IL FAUT : un simple total ne
            # dirait pas si l'on peut batir.
            lbl = scale_font(Label(text="%d/%d" % (possede, requis),
                             halign="center", valign="middle",
                             bold=possede < requis,
                             color=((1.0, 0.55, 0.45, 1) if possede < requis
                                    else (0.85, 0.95, 0.85, 1))), 0.020)
            lbl.bind(size=lambda w, *_: setattr(
                w, "text_size", (w.width, w.height)))
            ligne.add_widget(lbl)
            self.stock_box.add_widget(ligne)

    def _rebuild_drawer(self, state, nom):
        """Les pieces batissables, a droite."""
        self.drawer.clear_widgets()
        payable = state.can_build()
        for piece in items.build_parts(nom):
            btn = scale_font(StyledButton(
                text=items.BUILD_PART_NAMES.get(piece, piece)), 0.022)
            # Une piece qu'on ne peut pas payer reste VISIBLE mais eteinte :
            # savoir ce qu'on pourra batir plus tard fait partie de ce que le
            # chantier doit dire.
            btn.disabled = not payable
            btn.opacity = 1.0 if payable else 0.45
            btn.bind(on_release=lambda _w, p=piece: self._choose(p))
            self.drawer.add_widget(btn)

    def _choose(self, piece):
        self._part = piece
        self._set_drawer(False)
        cout = ", ".join("%d %s" % (n, items.display_name(m))
                         for m, n in items.BUILD_COST.items())
        self.hint.text = "%s choisi (%s)" % (
            items.BUILD_PART_NAMES.get(piece, piece), cout)
