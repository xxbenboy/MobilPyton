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
  On en CHOISIT une d'un toucher, puis on tape les cubes a batir : elle reste
  en main jusqu'a ce qu'on la retape ou qu'on en prenne une autre. Poser
  vingt murs demande donc vingt-et-un touchers, contre vingt glissers d'un
  bout a l'autre de l'ecran.

  CHAQUE PIECE EST UNE CATEGORIE : la choisir ouvre ses MODELES -- une piece,
  quatre, ou neuf d'un coup. Neuf touchers pour couvrir un carre de trois sur
  trois, c'etaient neuf occasions de viser a cote ; un seul suffit. Le modele
  est CENTRE sur le cube vise, et ce qui deborderait de la grille est
  simplement omis : viser le bord pose ce qui tient, au lieu de tout refuser.
  Chaque cube pose coute son prix -- un modele n'est pas une remise.

  CHAQUE PIECE A SA COULEUR -- sol vert, mur jaune, toit rouge -- et c'est la
  seule facon de savoir, en regardant le volume, ce qu'on a mis ou. Trente
  cubes tous couleur bois ne se lisaient pas.

  UN ETAGE N'ATTEND QU'UNE PIECE : le sol veut des sols, les deux etages de
  murs veulent des murs, le toit veut des toits. Les autres restent visibles
  mais grisees -- savoir ce qu'on batira plus tard fait partie de ce que le
  chantier doit dire.

- LE STOCK, a gauche, FERME par defaut : les trois matieres et ce qu'on en a.
  Il s'ouvre d'une fleche et se referme de la meme fleche, ou d'un toucher
  ailleurs -- comme on repousse un panneau. On le consulte, on n'agit pas
  dessus ; il n'a donc pas a occuper l'ecran en permanence.

LE VOLUME SE TOURNE AU DOIGT, dans tous les sens. Sur le volume, un TAP pose
et un GLISSER tourne : seule la distance parcourue les separe, comme dans
l'inventaire ou un tap ouvre la fiche d'un objet et un glisser le deplace.

UN CHANTIER TERMINE NE SE TOUCHE PLUS : ni pose, ni retrait, ni retour en
arriere. Terminer engage. (La demolition viendra plus tard ; le jour ou elle
existera, c'est ici qu'il faudra rouvrir la porte.)
"""
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, Line, Rectangle, Mesh, Ellipse
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
from src.widgets.drag_drop import TAP_SLOP

# Les cubes. Le remplissage est TRES pale : il donne le volume sans rien
# cacher, et quatre etages empiles restent lisibles au travers.
CUBE_FILL = (1.0, 1.0, 1.0, 0.045)
CUBE_EDGE = (1.0, 1.0, 1.0, 0.55)
# L'ARETE DU CONTOUR est nettement plus franche : c'est elle qui donne sa
# forme au volume. Sans elle, quatre-vingt-seize traits pales se valent tous
# et l'oeil ne trouve plus les bords.
CUBE_EDGE_OUT = (1.0, 1.0, 1.0, 0.95)

# Un cube BATI prend LA COULEUR DE SA PIECE (voir items.BUILD_PART_COLORS) :
# sol vert, mur jaune, toit rouge. Un chantier tout couleur bois ne se lisait
# pas -- on ne voyait plus ce qu'on avait mis ou. Ces deux facteurs disent
# seulement l'opacite du remplissage et l'eclat de l'arete.
PIECE_ALPHA = 0.55
PIECE_ARETE_ECLAT = 1.35

# Le cube VISE pendant qu'on glisse une piece dessus. Memes couleurs que
# l'apercu de pose d'un objet, pour que le vert et le rouge veuillent dire la
# meme chose partout dans le jeu.
APERCU_OK = (0.45, 1.00, 0.62, 0.95)
APERCU_OK_FILL = (0.45, 1.00, 0.62, 0.32)
APERCU_NO = (1.00, 0.42, 0.35, 0.95)
APERCU_NO_FILL = (1.00, 0.42, 0.35, 0.32)

# Un cube d'un etage DEJA FINALISE, ou hors d'atteinte : il sert de repere et
# ne doit pas attirer l'oeil. Plus pale que tout le reste.
CUBE_FILL_MUET = (1.0, 1.0, 1.0, 0.02)
CUBE_EDGE_MUET = (1.0, 1.0, 1.0, 0.16)

# UNE PIECE D'UN ETAGE FINALISE devient PLEINE : couleur franche, sans arete.
# Tant qu'on peut la retirer, elle reste un projet -- transparente, cerclee,
# manipulable. Une fois l'etage clos elle est BATIE : la montrer encore en
# verre laissait croire qu'on pouvait y revenir, et empilait quatre etages de
# voiles qu'on ne pouvait plus lire. C'est aussi l'aspect qu'a le chantier
# termine, et c'est voulu : on voit la maison se solidifier etage par etage.
#
# Sans arete, c'est L'OMBRE qui donne le relief (build_grid.cube_faces_-
# eclairees) : une face eclairee et sa voisine dans l'ombre se separent
# d'elles-memes, alors qu'un aplat d'une seule couleur serait une tache.
PIECE_PLEIN_ALPHA = 0.98

# La croix de retrait, posee au coin haut droit d'un cube bati.
CROIX_FOND = (0.12, 0.08, 0.06, 0.80)
CROIX = (1.00, 0.62, 0.55, 1.0)


class _Volume(Widget):
    """Le volume en cubes : transparent, cercle de blanc, et ORIENTABLE.

    Il ne gere pas les gestes lui-meme -- l'ecran sait seul si un doigt vient
    le tourner, y deposer une piece ou retirer -- mais il sait se redessiner
    sous n'importe quel angle, et dire ce qui se trouve sous un point."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.volume = (0, 0, 0)
        self.tour = build_grid.TOUR_DEFAUT
        self.inclinaison = build_grid.INCLINAISON_DEFAUT
        self.batis = {}          # {(x, y, z): piece} deja construit
        self.etape = 0
        self.apercu = None       # cube vise pendant un glisser
        self.apercu_ok = False
        self.retrait = False     # mode retrait : des croix sur le bati
        self._croix = []         # [(cube, x, y, rayon)] pour viser les croix
        self._bandes = None      # (axe, bornes) des buches du plancher
        self.bind(pos=self._redraw, size=self._redraw)

    # -- ce qui est montre et ce qui repond ----------------------------- #
    def utilisables(self):
        return build_grid.cubes_utilisables(self.volume, self.etape,
                                            self.batis)

    def visibles(self):
        return build_grid.cubes_visibles(self.volume, self.etape, self.batis)

    def _cadre(self):
        """(boite cadree, taille d'un cube, centre x, centre y).

        On cadre sur l'ETAGE EN COURS plus ce qui est bati -- pas sur le
        volume entier, ou l'etage flotterait en miniature, ni sur les seuls
        cubes montres, ou la vue sauterait a chaque piece posee."""
        boite = build_grid.boite_cadre(self.volume, self.etape, self.batis)
        taille = build_grid.echelle(boite, self.width, self.height)
        return boite, taille, self.center_x, self.center_y

    def cube_sous(self, x, y):
        """Le cube UTILISABLE sous le point donne, ou None.

        Seuls les utilisables repondent : viser un mur deja bati d'un etage
        inferieur n'aurait aucun sens, il n'est la que comme repere."""
        if min(self.volume) <= 0:
            return None
        boite, taille, cx, cy = self._cadre()
        return build_grid.cube_sous(x, y, self.utilisables(), boite,
                                    cx, cy, taille, self.tour,
                                    self.inclinaison)

    def croix_sous(self, x, y):
        """Le cube dont la CROIX de retrait est sous le point, ou None."""
        for cube, cxx, cyy, r in self._croix:
            if (x - cxx) ** 2 + (y - cyy) ** 2 <= r * r:
                return cube
        return None

    def pivote(self, dx, dy):
        """Tourne le volume d'un deplacement de doigt.

        Horizontalement on tourne autour de la verticale, verticalement on
        change l'inclinaison. Le signe de l'inclinaison suit le doigt : tirer
        vers le bas fait basculer le dessus vers soi, comme on inclinerait une
        maquette posee sur la table."""
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
        self._croix = []
        if self.width <= 0 or self.height <= 0 or min(self.volume) <= 0:
            return
        boite, taille, cx, cy = self._cadre()
        args = (boite, cx, cy, taille, self.tour, self.inclinaison)
        montres = self.visibles()
        ouverts = set(self.utilisables())
        fini = self.etape >= build_grid.TERMINE
        # LES BUCHES DU PLANCHER, calculees une fois pour tout le sol : leur
        # largeur vient de celle du plancher ENTIER, pas du cube qu'on dessine.
        # Chaque cube n'en montre ensuite que le morceau qui le traverse, si
        # bien qu'une buche court d'un bout a l'autre sans couture.
        self._bandes = self._buches()
        with self.canvas:
            for cube in build_grid.ordre_dessin(montres, boite, self.tour,
                                                self.inclinaison):
                # UNE PIECE EST PLEINE des que son etage est clos : on ne peut
                # plus la retirer, ce n'est plus un projet.
                plein = fini or build_grid.etape_de(cube[2]) < self.etape
                self._cube(cube, args, cube in ouverts, plein)
            if not fini:
                # LE CONTOUR DE L'ETAGE, dans toute son etendue -- pas
                # seulement autour des cubes ouverts. Un etage a peine
                # commence se reduirait sinon a deux ou trois cubes
                # flottants, et le joueur ne saurait plus quelle surface il a
                # le droit de couvrir.
                Color(*CUBE_EDGE_OUT)
                etage = build_grid.boite_etage(self.volume, self.etape)
                for a, b in build_grid.boite_aretes(etage):
                    p1 = build_grid.project(*a, *args)
                    p2 = build_grid.project(*b, *args)
                    Line(points=[p1[0], p1[1], p2[0], p2[1]], width=1.9)
            if self.retrait:
                self._croix_de_retrait(args, taille)

    def _buches(self):
        """Les bandes de buches du plancher, ou None s'il n'y a pas lieu.

        RIEN AVANT LA CONFIRMATION DE L'ETAGE. Tant qu'on pose ses dalles, un
        sol est un projet : il se montre en verre, cube par cube, et on doit
        pouvoir compter ses cases. C'est en le finalisant qu'il devient un
        plancher -- et un plancher, ce sont des buches, pas des cases."""
        if self.etape <= 0:
            return None
        return build_grid.buches_du_plancher(self.batis)

    def _cube(self, cube, args, ouvert, plein):
        piece = self.batis.get(cube)
        vise = (cube == self.apercu)
        if piece is not None and plein and not vise:
            # ETAGE CLOS : couleur seule, opaque, SANS AUCUNE ARETE. Le relief
            # vient de l'ombre portee sur chaque face -- voir PIECE_PLEIN_ALPHA.
            r, g, b = items.build_part_color(piece)
            plancher = (piece == "sol" and self._bandes is not None
                        and build_grid.etape_de(cube[2]) == 0)
            for pts, f, normale in build_grid.cube_faces_orientees(cube, *args):
                if plancher and normale == (0, 0, 1):
                    # LE DESSUS D'UN PLANCHER porte ses buches. Les cotes, non :
                    # ce qu'on y verrait, c'est la tranche du plancher, et elle
                    # est pleine.
                    self._buches_du_dessus(cube, args, (r, g, b), f)
                    continue
                Color(r * f, g * f, b * f, PIECE_PLEIN_ALPHA)
                self._quad(pts)
            return
        if vise:
            # LE CUBE VISE L'EMPORTE, meme s'il est deja bati : c'est
            # justement la qu'il faut voir le rouge.
            fond, bord, ep = ((APERCU_OK_FILL, APERCU_OK, 2.2)
                              if self.apercu_ok
                              else (APERCU_NO_FILL, APERCU_NO, 2.2))
        elif piece is not None:
            # Une piece de l'etage EN COURS : encore un projet, donc encore en
            # verre -- on peut la retirer, et on doit voir a travers pour viser
            # les cubes du fond.
            r, g, b = items.build_part_color(piece)
            fond = (r, g, b, PIECE_ALPHA)
            e = PIECE_ARETE_ECLAT
            bord = (min(1.0, r * e), min(1.0, g * e), min(1.0, b * e), 0.95)
            ep = 2.2
        elif ouvert:
            fond, bord, ep = CUBE_FILL, CUBE_EDGE, 1.0
        else:
            # Un cube bati d'un etage inferieur, ou hors d'atteinte : il sert
            # de repere, il ne doit pas attirer l'oeil.
            fond, bord, ep = CUBE_FILL_MUET, CUBE_EDGE_MUET, 1.0
        for pts in build_grid.cube_faces_vues(cube, *args):
            Color(*fond)
            self._quad(pts)
        Color(*bord)
        for (p1, p2) in build_grid.cube_aretes(cube, *args):
            Line(points=[p1[0], p1[1], p2[0], p2[1]], width=ep)

    def _buches_du_dessus(self, cube, args, couleur, eclat):
        """Le dessus d'un cube de plancher, en morceaux de buches.

        Le decoupage vient de build_grid : la scene du jeu montre le MEME
        plancher, avec sa propre projection, et deux decoupages differents se
        seraient vus au passage de l'un a l'autre."""
        r, g, b = couleur
        haut = build_grid.z_haut(cube[2])
        axe, tranches = build_grid.tranches_buches(cube, self._bandes)
        for l0, l1, s0, s1, relief in tranches:
            f = eclat * relief
            pts = []
            for l, s in ((l0, s0), (l1, s0), (l1, s1), (l0, s1)):
                gx, gy = (l, s) if axe == 0 else (s, l)
                p = build_grid.project(gx, gy, haut, *args)
                pts.append((p[0], p[1]))
            Color(min(1.0, r * f), min(1.0, g * f), min(1.0, b * f),
                  PIECE_PLEIN_ALPHA)
            self._quad(pts)

    def _croix_de_retrait(self, args, taille):
        """Une croix au coin HAUT DROIT de chaque cube bati de l'etage.

        Seuls ceux de l'etage EN COURS en portent : les etages du dessous
        sont finalises, et les defaire par une croix perdue au milieu du
        decor serait trop facile a faire par accident. On revient en arriere
        par le bouton, qui dit ce qu'il fait."""
        r = max(dp(7), taille * 0.20)
        for cube in build_grid.cubes_de_etape(self.etape, self.batis):
            x, y = build_grid.coin_haut_droit(cube, *args)
            self._croix.append((cube, x, y, r * 1.25))
            Color(*CROIX_FOND)
            Ellipse(pos=(x - r, y - r), size=(r * 2, r * 2))
            Color(*CROIX)
            k = r * 0.52
            Line(points=[x - k, y - k, x + k, y + k], width=max(1.6, r * 0.22))
            Line(points=[x - k, y + k, x + k, y - k], width=max(1.6, r * 0.22))

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

        # LA PIECE CHOISIE, SON MODELE, et le geste en cours sur le volume. Une
        # piece reste choisie jusqu'a ce qu'on la retape ou qu'on en prenne une
        # autre : poser vingt murs demande vingt-et-un touchers, contre vingt
        # glissers d'un bout a l'autre de l'ecran.
        #
        # Le modele, lui, SURVIT au changement de piece : on choisit une facon
        # de batir -- a l'unite ou par pans -- et on la garde d'un etage a
        # l'autre. Le remettre a un a chaque fois obligerait a le rechoisir
        # apres chaque piece.
        self._piece = None
        self._modele = build_grid.MODELES[0]
        self._geste = None

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

        # LA BARRE DU CHANTIER, en bas. Trois commandes qui font AVANCER ou
        # RECULER le chantier, plus la sortie. Elles sont ensemble parce
        # qu'elles portent sur l'etage entier, alors que le glisser et la
        # croix portent sur une piece.
        barre = BoxLayout(orientation="horizontal", spacing=dp(8),
                          size_hint=(0.74, 0.085),
                          pos_hint={"center_x": 0.5, "y": 0.015})
        self.btn_prev = scale_font(StyledButton(text="Etage precedent"), 0.019)
        self.btn_prev.bind(on_release=lambda *_: self._previous())
        barre.add_widget(self.btn_prev)
        self.btn_retrait = scale_font(StyledButton(text="Retirer"), 0.019)
        self.btn_retrait.bind(on_release=lambda *_: self._toggle_retrait())
        barre.add_widget(self.btn_retrait)
        self.btn_next = scale_font(StyledButton(text="Etage suivant"), 0.019)
        self.btn_next.bind(on_release=lambda *_: self._next())
        barre.add_widget(self.btn_next)
        quit_btn = scale_font(StyledButton(text="Quitter"), 0.019)
        quit_btn.bind(on_release=lambda *_: self._leave())
        barre.add_widget(quit_btn)
        root.add_widget(barre)

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
    #
    # ON CHOISIT UNE PIECE, PUIS ON TAPE DES CUBES. La piece reste choisie
    # jusqu'a ce qu'on la retape ou qu'on en prenne une autre : poser vingt
    # murs demande donc vingt-et-un touchers, contre vingt glissers d'un bout
    # a l'autre de l'ecran.
    #
    # Un TAP sur le volume pose ; un GLISSER sur le volume le fait tourner.
    # Seule la distance parcourue les separe -- c'est la meme convention que
    # l'inventaire, ou un tap ouvre la fiche d'un objet et un glisser le
    # deplace.
    def on_touch_down(self, touch):
        # 1. Un toucher AILLEURS referme le stock -- comme on repousse un
        #    panneau. La fleche est exclue : elle a deja sa propre bascule, et
        #    refermer ici la ferait rouvrir aussitot.
        if (self._drawer_open
                and not self.drawer.collide_point(*touch.pos)
                and not self.arrow.collide_point(*touch.pos)):
            self._set_drawer(False)
            return True
        # 2. Une CROIX de retrait, si le mode est actif. Elle passe avant tout
        #    le reste : la croix est petite, et un doigt qui la vise ne doit
        #    pas faire pivoter le volume a la place.
        if self.volume.retrait:
            cube = self.volume.croix_sous(*touch.pos)
            if cube is not None:
                self._retire(cube)
                return True
        # 3. La colonne de droite : une PIECE, qu'on choisit ou qu'on lache si
        #    c'etait deja elle, ou un MODELE de la piece en main.
        btn = self._bouton_sous(touch)
        if btn is not None:
            modele = getattr(btn, "modele", None)
            if modele is not None:
                self._choisir_modele(modele)
            else:
                self._choisir(btn.piece)
            return True
        # 4. Le VOLUME : on retient d'ou part le doigt. La suite depend de ce
        #    qu'il fait -- bouger fait tourner, rester pose.
        if self.volume.collide_point(*touch.pos):
            self._geste = {"depart": touch.pos, "dernier": touch.pos,
                           "bouge": False}
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        g = self._geste
        if g is not None:
            if max(abs(touch.x - g["depart"][0]),
                   abs(touch.y - g["depart"][1])) > TAP_SLOP:
                g["bouge"] = True
            if g["bouge"]:
                self.volume.pivote(touch.x - g["dernier"][0],
                                   touch.y - g["dernier"][1])
                g["dernier"] = touch.pos
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        g, self._geste = self._geste, None
        if g is not None:
            # Un doigt pose et releve SANS BOUGER n'etait pas une rotation :
            # c'est une pose.
            if not g["bouge"]:
                self._poser(touch)
            return True
        return super().on_touch_up(touch)

    def _bouton_sous(self, touch):
        """Le bouton touche dans la colonne de droite, ou None.

        On descend d'un niveau : les modeles vivent dans une rangee, donc pas
        directement dans la colonne."""
        for enfant in self.parts_box.children:
            if not enfant.collide_point(*touch.pos):
                continue
            if getattr(enfant, "piece", None) is not None:
                return enfant
            for btn in enfant.children:
                if (getattr(btn, "modele", None) is not None
                        and btn.collide_point(*touch.pos)):
                    return btn
        return None

    def _choisir(self, piece):
        """Prend une piece, ou la lache si c'etait deja celle-la."""
        state = App.get_running_app().game_state
        if state is None:
            return
        attendue = build_grid.piece_de_etape(self.volume.etape)
        if piece != attendue:
            # Elle est grisee, mais un doigt tombe dessus quand meme : mieux
            # vaut dire pourquoi que ne rien faire.
            self.hint.text = "Cet etage attend un %s." \
                % items.BUILD_PART_NAMES.get(attendue, attendue).lower()
            return
        if not state.can_build():
            self.hint.text = "Il manque de la matiere (vois le stock)."
            self._set_drawer(True)
            return
        self._piece = None if self._piece == piece else piece
        self.hint.text = "" if self._piece is None else self._en_main()
        # La colonne CHANGE DE FORME : les modeles de la piece prise
        # apparaissent sous elle, ceux de la precedente disparaissent.
        self._rebuild_parts(state)

    def _choisir_modele(self, modele):
        """Change le nombre de pieces posees d'un coup."""
        self._modele = int(modele)
        if self._piece is not None:
            self.hint.text = self._en_main()
        self._sync_parts()

    def _en_main(self):
        """Ce que dit la ligne d'aide quand on tient une piece."""
        nom = items.BUILD_PART_NAMES.get(self._piece, self._piece)
        if self._modele > 1:
            return "%s x%d en main : touche un cube, les voisins suivent." \
                % (nom, self._modele)
        return "%s en main : touche les cubes a batir." % nom

    def _poser(self, touch):
        """Bati la piece choisie sur le cube touche, et sur ceux de son
        modele."""
        if self._piece is None:
            return
        state = App.get_running_app().game_state
        if state is None or self.blueprint is None:
            return
        cube = self.volume.cube_sous(*touch.pos)
        if cube is None:
            # On distingue les deux raisons. Touche dans le vide, c'est un
            # geste rate ; touche sur un cube FERME, c'est une regle du
            # chantier qu'il faut expliquer -- sinon le joueur croit a une
            # panne et recommence.
            self.hint.text = ("Ce cube n'a rien en dessous pour l'appuyer."
                              if self.volume.collide_point(*touch.pos)
                              else "")
            return
        if not state.can_build():
            # La matiere s'est epuisee en cours de serie : on lache la piece,
            # sinon le joueur continue de taper sans que rien ne se passe.
            self._piece = None
            self.hint.text = "Plus de matiere. Vois le stock."
            self._set_drawer(True)
            self._refresh(state)
            return
        _nom, gx, gy = self.blueprint
        # LE MODELE, filtre par ce qui est OUVERT : un cube deja bati ou sans
        # appui ne se pose pas parce qu'un voisin, lui, se posait. Le modele
        # est un raccourci de gestes, pas une derogation aux regles.
        ouverts = set(self.volume.utilisables())
        vises = [c for c in build_grid.cubes_modele(self._modele, cube,
                                                    self.volume.volume)
                 if c in ouverts]
        poses = 0
        for c in vises:
            if not state.can_build():
                break
            if state.build_piece(gx, gy, c, self._piece):
                poses += 1
        if not poses:
            return
        App.get_running_app().autosave()
        if poses < len(vises):
            # La matiere a manque EN COURS de modele : le dire, sinon le joueur
            # croit que la moitie de son carre s'est perdue en chemin.
            self.hint.text = "Matiere epuisee : %d piece%s posee%s sur %d." % (
                poses, "s" if poses > 1 else "", "s" if poses > 1 else "",
                len(vises))
        self._refresh(state)

    # ---------------- ETAPES ET RETRAIT -------------------------------- #
    def _toggle_retrait(self):
        self.volume.retrait = not self.volume.retrait
        self.volume._redraw()
        self._sync_barre()
        self.hint.text = ("Touche une croix pour retirer une piece."
                          if self.volume.retrait else "")

    def _retire(self, cube):
        state = App.get_running_app().game_state
        if state is None or self.blueprint is None:
            return
        _nom, gx, gy = self.blueprint
        if state.unbuild_piece(gx, gy, cube):
            App.get_running_app().autosave()
            rendu = ", ".join("%d %s" % (n, items.display_name(m))
                              for m, n in items.BUILD_COST.items())
            self.hint.text = "Piece retiree — %s rendus au sol." % rendu
            self._refresh(state)

    def _next(self):
        state = App.get_running_app().game_state
        if state is None or self.blueprint is None:
            return
        _nom, gx, gy = self.blueprint
        avant = state.build_stage(gx, gy)
        if not state.build_next_stage(gx, gy):
            self.hint.text = "Pose au moins une piece a cet etage."
            return
        App.get_running_app().autosave()
        apres = state.build_stage(gx, gy)
        self.volume.retrait = False
        self._lache()
        self.hint.text = ("Chantier termine." if apres >= build_grid.TERMINE
                          else "Etage %d : %s."
                          % (apres + 1, build_grid.ETAPES[apres]))
        self._refresh(state)

    def _previous(self):
        state = App.get_running_app().game_state
        if state is None or self.blueprint is None:
            return
        _nom, gx, gy = self.blueprint
        if not state.build_previous_stage(gx, gy):
            self.hint.text = "C'est deja le premier etage."
            return
        App.get_running_app().autosave()
        etape = state.build_stage(gx, gy)
        self.volume.retrait = False
        self._lache()
        self.hint.text = ("Etage defait. Retour a l'etage %d : %s."
                          % (etape + 1, build_grid.ETAPES[etape]))
        self._refresh(state)

    def _lache(self):
        """Repose la piece en main. On CHANGE D'ETAGE, donc de metier.

        Une piece gardee en main d'un etage a l'autre etait un piege : un sol
        reste choisi apres avoir finalise le sol se retrouve refuse par
        l'etage des murs, et le joueur tape des cubes sans que rien ne se
        passe. Pire, la piece que l'etage suivant attend est parfois LA MEME
        -- les deux etages de murs -- si bien qu'on ne savait plus si l'on
        tenait encore quelque chose ou non. Chaque etage se rouvre donc les
        mains vides."""
        self._piece = None

    def _sync_barre(self):
        """Met les boutons du bas en accord avec l'etage en cours."""
        etape = self.volume.etape
        fini = etape >= build_grid.TERMINE
        dernier = etape == build_grid.ETAPE_TOIT
        # A LA DERNIERE ETAPE, le bouton change de nom : il ne mene plus a un
        # etage suivant, il acheve le chantier.
        self.btn_next.text = ("Terminer le chantier" if dernier
                              else "Etage suivant")
        # UN CHANTIER TERMINE NE SE TOUCHE PLUS : ni pose, ni retrait, ni
        # retour en arriere. Terminer engage. Il ne reste que la sortie.
        for btn, actif in ((self.btn_next, not fini),
                           (self.btn_retrait, not fini),
                           (self.btn_prev, 0 < etape < build_grid.TERMINE)):
            btn.disabled = not actif
            btn.opacity = 1.0 if actif else 0.40
        self.btn_retrait.text = ("Fini de retirer" if self.volume.retrait
                                 else "Retirer")


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
        self._set_drawer(False)
        self._piece = None
        self._geste = None
        self.volume.retrait = False
        self.hint.text = ""
        self._refresh(state)

    def _refresh(self, state):
        """Relit tout ce qui depend de l'etat : l'etage, le bati, le stock,
        les pieces, et les boutons du bas."""
        nom = self.blueprint[0] if self.blueprint else None
        if self.blueprint is not None:
            _n, gx, gy = self.blueprint
            self.volume.etape = state.build_stage(gx, gy)
            self.volume.batis = state.built_here(gx, gy)
        else:
            self.volume.etape = 0
            self.volume.batis = {}
        self.volume._redraw()
        self._rebuild_stock(state)
        self._rebuild_parts(state, nom)
        self._sync_barre()
        # Le titre porte l'ETAGE : c'est l'information la plus utile de
        # l'ecran, et sans elle rien ne dit pourquoi tel cube est ouvert et
        # tel autre pas.
        etape = self.volume.etape
        if etape >= build_grid.TERMINE:
            self.title.text = "%s — termine" % items.display_name(nom)
        else:
            self.title.text = "Chantier — etage %d/%d : %s" % (
                etape + 1, len(build_grid.ETAPES), build_grid.ETAPES[etape])

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

    def _rebuild_parts(self, state, nom=None):
        """Les pieces, a droite. On en CHOISIT une, puis on tape des cubes.

        Chaque piece est une CATEGORIE : celle qu'on tient deploie sous elle
        ses modeles -- une, quatre ou neuf pieces d'un coup. Les modeles des
        autres restent replies : trois categories fois trois modeles feraient
        neuf boutons dans une colonne, ou l'on ne trouverait plus rien."""
        if nom is None:
            nom = self.blueprint[0] if self.blueprint else None
        self.parts_box.clear_widgets()
        # Un chantier TERMINE n'offre plus rien a poser : la colonne dispa-
        # rait, au lieu de proposer des pieces qui n'iraient nulle part.
        if self.volume.etape >= build_grid.TERMINE:
            self.parts_box.opacity = 0.0
            return
        self.parts_box.opacity = 1.0
        for piece in items.build_parts(nom):
            r, g, b = items.build_part_color(piece)
            btn = scale_font(StyledButton(
                text=items.BUILD_PART_NAMES.get(piece, piece)), 0.022)
            # `piece` est accroche au bouton : c'est ainsi que le toucher
            # retrouve ce qu'on a pris, sans table parallele a tenir a jour.
            btn.piece = piece
            # LE BOUTON PORTE LA COULEUR DE SA PIECE. C'est la seule facon de
            # savoir, en regardant le volume, quel cube vient de quel bouton.
            btn.background_color = (r, g, b, 1)
            self.parts_box.add_widget(btn)
            if piece != self._piece:
                continue
            # LES MODELES DE LA PIECE EN MAIN, en rangee sous elle. Plus basse
            # que la categorie : c'est un reglage de celle-ci, pas un frere.
            rangee = BoxLayout(orientation="horizontal", spacing=dp(3),
                               size_hint_y=0.62)
            for n in build_grid.MODELES:
                m = scale_font(StyledButton(text="x%d" % n), 0.019)
                m.modele = n
                m.background_color = (r * 0.72, g * 0.72, b * 0.72, 1)
                rangee.add_widget(m)
            self.parts_box.add_widget(rangee)
        self._sync_parts()

    def _sync_parts(self):
        """Grise les pieces que l'etage n'attend pas, allume celle en main."""
        state = App.get_running_app().game_state
        attendue = build_grid.piece_de_etape(self.volume.etape)
        payable = state is not None and state.can_build()
        for enfant in self.parts_box.children:
            piece = getattr(enfant, "piece", None)
            if piece is None:
                # La rangee de modeles : on y allume celui qui est actif.
                for m in enfant.children:
                    actif = getattr(m, "modele", None) == self._modele
                    m.bold = actif
                    m.opacity = 1.0 if actif else 0.55
                continue
            bonne = piece == attendue
            # Une piece que l'etage n'attend pas reste VISIBLE mais eteinte :
            # savoir ce qu'on batira plus tard fait partie de ce que le
            # chantier doit dire. Elle n'est pas `disabled` -- un widget
            # desactive avalerait le toucher, et l'on ne pourrait plus
            # expliquer le refus ; c'est _choisir qui tranche.
            enfant.opacity = 1.0 if (bonne and payable) else 0.35
            # La piece EN MAIN se distingue de celle qui est simplement
            # disponible : sans cela, on ne sait plus si l'on tient quelque
            # chose, et taper un cube semble ne rien faire.
            enfant.bold = (piece == self._piece)
            enfant.text = (items.BUILD_PART_NAMES.get(piece, piece)
                           + ("  ✓" if piece == self._piece else ""))
