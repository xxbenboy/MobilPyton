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

- LES PIECES, a droite, toujours visibles. Sol, mur, toit pour le palier 1.
  On en GLISSE une sur un cube pour la batir la : le geste est celui de la
  pose d'un plan, et pour la meme raison -- il faut voir ou l'on vise avant
  de lacher.

- LE STOCK, a gauche, FERME par defaut : les trois matieres et ce qu'on en a.
  Il s'ouvre d'une fleche et se referme de la meme fleche, ou d'un toucher
  ailleurs -- comme on repousse un panneau. On le consulte, on n'agit pas
  dessus ; il n'a donc pas a occuper l'ecran en permanence.

LE VOLUME SE TOURNE AU DOIGT, dans les deux sens. Un glisser qui part du
volume le fait tourner ; un glisser qui part des pieces y depose. L'origine du
geste suffit a les distinguer, sans mode ni bouton.
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

# Un cube BATI : franchement plus dense, couleur du bois. Il doit se distinguer
# du vide au premier coup d'oeil, sinon on ne voit pas ce qu'on a deja fait.
PIECE_FILL = (0.62, 0.44, 0.24, 0.55)
PIECE_EDGE = (0.86, 0.70, 0.46, 0.95)

# Le cube VISE pendant qu'on glisse une piece dessus. Memes couleurs que
# l'apercu de pose d'un objet, pour que le vert et le rouge veuillent dire la
# meme chose partout dans le jeu.
APERCU_OK = (0.45, 1.00, 0.62, 0.95)
APERCU_OK_FILL = (0.45, 1.00, 0.62, 0.32)
APERCU_NO = (1.00, 0.42, 0.35, 0.95)
APERCU_NO_FILL = (1.00, 0.42, 0.35, 0.32)


class _Volume(Widget):
    """Le volume en cubes : transparent, cercle de blanc, et ORIENTABLE.

    Il ne gere pas les gestes lui-meme -- l'ecran sait seul si un doigt vient
    le tourner ou y deposer une piece -- mais il sait se redessiner sous
    n'importe quel angle, et dire quel cube se trouve sous un point."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.volume = (0, 0, 0)
        self.tour = build_grid.TOUR_DEFAUT
        self.inclinaison = build_grid.INCLINAISON_DEFAUT
        self.batis = {}          # {(x, y, z): piece} deja construit
        self.apercu = None       # cube vise pendant un glisser
        self.apercu_ok = False
        self.bind(pos=self._redraw, size=self._redraw)

    # -- geometrie ------------------------------------------------------ #
    def _cadre(self):
        """(taille d'un cube, centre x, centre y) a l'ecran."""
        taille = build_grid.echelle(self.volume, self.width, self.height)
        return taille, self.center_x, self.center_y

    def cube_sous(self, x, y):
        """Le cube sous le point donne, ou None."""
        if min(self.volume) <= 0:
            return None
        taille, cx, cy = self._cadre()
        return build_grid.cube_sous(x, y, self.volume, cx, cy, taille,
                                    self.tour, self.inclinaison)

    def pivote(self, dx, dy):
        """Tourne le volume d'un deplacement de doigt.

        Horizontalement on tourne autour de la verticale, verticalement on
        change l'inclinaison. Le signe de l'inclinaison est INVERSE par
        rapport au doigt : tirer vers le bas doit faire basculer le dessus
        vers soi, comme on inclinerait une maquette posee sur la table."""
        if self.width <= 0:
            return
        self.tour += dx / self.width * build_grid.TOUR_PAR_ECRAN
        inc = self.inclinaison + dy / max(1.0, self.height) \
            * build_grid.TOUR_PAR_ECRAN
        borne = build_grid.INCLINAISON_MAX
        self.inclinaison = max(-borne, min(borne, inc))
        self._redraw()

    # -- dessin --------------------------------------------------------- #
    def _redraw(self, *_):
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0 or min(self.volume) <= 0:
            return
        taille, cx, cy = self._cadre()
        args = (self.volume, cx, cy, taille, self.tour, self.inclinaison)
        with self.canvas:
            for cube in build_grid.ordre_dessin(self.volume, self.tour,
                                                self.inclinaison):
                self._cube(cube, args)
            # Le contour du volume entier, par-dessus : les douze aretes de la
            # grande boite, tracees plus franchement.
            Color(*CUBE_EDGE_OUT)
            for a, b in build_grid.boite_aretes(self.volume):
                p1 = build_grid.project(*a, *args)
                p2 = build_grid.project(*b, *args)
                Line(points=[p1[0], p1[1], p2[0], p2[1]], width=1.9)

    def _cube(self, cube, args):
        piece = self.batis.get(cube)
        vise = (cube == self.apercu)
        # LE CUBE VISE L'EMPORTE, meme s'il est deja bati. C'est justement
        # dans ce cas qu'il faut voir le rouge : sans lui, viser un cube
        # occupe ne changerait rien a l'ecran et le refus, au moment du
        # lacher, tomberait sans prevenir.
        if vise:
            fond, bord = ((APERCU_OK_FILL, APERCU_OK) if self.apercu_ok
                          else (APERCU_NO_FILL, APERCU_NO))
        elif piece is not None:
            fond, bord = PIECE_FILL, PIECE_EDGE
        else:
            fond, bord = CUBE_FILL, CUBE_EDGE
        for pts in build_grid.cube_faces_vues(cube, *args):
            Color(*fond)
            self._quad(pts)
        Color(*bord)
        for (p1, p2) in build_grid.cube_aretes(cube, *args):
            Line(points=[p1[0], p1[1], p2[0], p2[1]],
                 width=2.2 if (piece is not None or vise) else 1.0)

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

        # LE VOLUME, au centre. Il occupe presque tout l'ecran : c'est lui
        # qu'on manipule, et le tourner demande de la place pour le doigt.
        self.volume = _Volume(size_hint=(0.72, 0.84),
                              pos_hint={"center_x": 0.5, "center_y": 0.50})
        root.add_widget(self.volume)

        # LES PIECES, a DROITE, toujours visibles : on en glisse une sur un
        # cube pour la batir. Un tiroir a ouvrir avant chaque pose aurait
        # double le nombre de gestes.
        self.parts_box = BoxLayout(orientation="vertical", padding=dp(6),
                                   spacing=dp(6), size_hint=(0.155, 0.56),
                                   pos_hint={"right": 0.988,
                                             "center_y": 0.50})
        panel(self.parts_box, alpha=0.55)
        root.add_widget(self.parts_box)

        # LE STOCK, a GAUCHE, ferme par defaut. On le consulte, on n'agit pas
        # dessus : il n'a pas a occuper l'ecran en permanence.
        self.drawer = BoxLayout(orientation="vertical", padding=dp(6),
                                spacing=dp(4), size_hint=(0.145, 0.42),
                                pos_hint={"x": 0.012, "center_y": 0.50})
        panel(self.drawer, alpha=0.50)
        root.add_widget(self.drawer)

        # La FLECHE qui l'ouvre et le referme. Elle reste toujours visible :
        # c'est la seule chose qui dit que le stock existe.
        self.arrow = scale_font(StyledButton(text=">", size_hint=(0.042, 0.10),
                                pos_hint={"x": 0.166,
                                          "center_y": 0.50}), 0.030)
        self.arrow.bind(on_release=lambda *_: self._toggle_drawer())
        root.add_widget(self.arrow)

        # Couche du FANTOME : la piece suivie par le doigt. Jamais desactivee
        # -- dans Kivy un widget desactive avale les touches qui tombent
        # dessus, et celle-ci couvre tout l'ecran.
        self.drag_layer = FloatLayout(size_hint=(1, 1),
                                      pos_hint={"x": 0, "y": 0})
        root.add_widget(self.drag_layer)
        self._drag = None            # piece en cours de depot
        self._spin = None            # doigt en train de tourner le volume

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
        # La fleche pointe vers OU LE PANNEAU VA : dehors quand il est ferme,
        # dedans quand il est ouvert. Le stock etant a gauche, c'est l'inverse
        # des chevrons d'un panneau de droite.
        self.arrow.text = "<" if self._drawer_open else ">"

    # ---------------- GESTES ------------------------------------------- #
    def on_touch_down(self, touch):
        # 1. Un toucher AILLEURS referme le stock -- comme on repousse un
        #    panneau. La fleche est exclue : elle a deja sa propre bascule, et
        #    refermer ici la ferait rouvrir aussitot.
        if (self._drawer_open
                and not self.drawer.collide_point(*touch.pos)
                and not self.arrow.collide_point(*touch.pos)):
            self._set_drawer(False)
            return True
        # 2. Un doigt qui part d'une PIECE vient en deposer une.
        piece = self._piece_sous(touch)
        if piece is not None:
            self._start_drag(piece, touch)
            return True
        # 3. Un doigt qui part du VOLUME le fait tourner. L'origine du geste
        #    suffit a distinguer les deux : aucun mode, aucun bouton.
        if self.volume.collide_point(*touch.pos):
            self._spin = touch.pos
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self._drag is not None:
            self._drag["ghost"].center = touch.pos
            self._vise(touch)
            return True
        if self._spin is not None:
            self.volume.pivote(touch.x - self._spin[0],
                               touch.y - self._spin[1])
            self._spin = touch.pos
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if self._drag is not None:
            self._drop(touch)
            return True
        if self._spin is not None:
            self._spin = None
            return True
        return super().on_touch_up(touch)

    def _piece_sous(self, touch):
        """La piece touchee dans la colonne de droite, ou None."""
        for btn in self.parts_box.children:
            piece = getattr(btn, "piece", None)
            if piece is not None and btn.collide_point(*touch.pos):
                return piece
        return None

    def _start_drag(self, piece, touch):
        ghost = BoxLayout(size_hint=(None, None), padding=dp(4),
                          size=(self.width * 0.10, self.height * 0.09))
        panel(ghost, alpha=0.60)
        ghost.add_widget(scale_font(Label(
            text=items.BUILD_PART_NAMES.get(piece, piece), bold=True,
            color=(1, 1, 1, 1)), 0.022))
        ghost.center = touch.pos
        ghost.opacity = 0.92
        self.drag_layer.add_widget(ghost)
        self._drag = {"ghost": ghost, "piece": piece}
        self._vise(touch)

    def _vise(self, touch):
        """Met a jour le cube vise, et s'il accepte la piece."""
        state = App.get_running_app().game_state
        cube = self.volume.cube_sous(*touch.pos)
        self.volume.apercu = cube
        # LES DEUX RAISONS D'UN REFUS : le cube est deja bati, ou la matiere
        # manque. On les distingue en rouge sans les nommer ici -- le stock,
        # a gauche, dit deja ce qui manque.
        self.volume.apercu_ok = bool(
            cube is not None and state is not None
            and cube not in self.volume.batis and state.can_build())
        self.volume._redraw()

    def _clear_drag(self):
        drag, self._drag = self._drag, None
        if drag is not None:
            self.drag_layer.remove_widget(drag["ghost"])
        self.volume.apercu = None
        self.volume.apercu_ok = False
        self.volume._redraw()

    def _drop(self, touch):
        piece = self._drag["piece"]
        cube = self.volume.cube_sous(*touch.pos)
        self._clear_drag()
        state = App.get_running_app().game_state
        if state is None or self.blueprint is None:
            return
        if cube is None:
            self.hint.text = "Glisse la piece SUR un cube."
            return
        if cube in self.volume.batis:
            self.hint.text = "Ce cube est deja bati."
            return
        if not state.can_build():
            self.hint.text = "Il manque de la matiere (vois le stock)."
            self._set_drawer(True)
            return
        _nom, gx, gy = self.blueprint
        if state.build_piece(gx, gy, cube, piece):
            App.get_running_app().autosave()
            self.hint.text = "%s bati." % items.BUILD_PART_NAMES.get(piece,
                                                                     piece)
            self._refresh(state)

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
        # L'orientation est REMISE A NEUF a chaque entree : on revient sur un
        # chantier des heures plus tard, et retrouver la vue de trois quarts
        # vaut mieux que l'angle bancal ou on l'avait laisse.
        self.volume.tour = build_grid.TOUR_DEFAUT
        self.volume.inclinaison = build_grid.INCLINAISON_DEFAUT
        self.title.text = "Chantier — %s" % items.display_name(nom)
        self._set_drawer(False)
        self._clear_drag()
        self._spin = None
        self.hint.text = ""
        self._refresh(state)

    def _refresh(self, state):
        """Relit tout ce qui depend de l'etat : le bati, le stock, les pieces."""
        nom = self.blueprint[0] if self.blueprint else None
        if self.blueprint is not None:
            _n, gx, gy = self.blueprint
            self.volume.batis = state.built_here(gx, gy)
        else:
            self.volume.batis = {}
        self.volume._redraw()
        self._rebuild_stock(state)
        self._rebuild_parts(state, nom)

    def _rebuild_stock(self, state):
        """Les trois matieres et ce qu'on en a, a gauche."""
        self.drawer.clear_widgets()
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
            self.drawer.add_widget(ligne)

    def _rebuild_parts(self, state, nom):
        """Les pieces batissables, a droite. On les GLISSE sur un cube."""
        self.parts_box.clear_widgets()
        payable = state.can_build()
        for piece in items.build_parts(nom):
            btn = scale_font(StyledButton(
                text=items.BUILD_PART_NAMES.get(piece, piece)), 0.022)
            # `piece` est accroche au bouton : c'est ainsi que le glisser
            # retrouve ce qu'on a pris, sans table parallele a tenir a jour.
            btn.piece = piece
            # Une piece qu'on ne peut pas payer reste VISIBLE mais eteinte :
            # savoir ce qu'on pourra batir plus tard fait partie de ce que le
            # chantier doit dire. Elle n'est pas `disabled` -- un widget
            # desactive avalerait le toucher, et le glisser ne partirait
            # jamais ; c'est _piece_sous qui la laisse passer ou non.
            btn.opacity = 1.0 if payable else 0.45
            self.parts_box.add_widget(btn)
