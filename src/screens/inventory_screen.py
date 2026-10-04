"""Ecran INVENTAIRE : ce qui est A PORTEE, ce qu'on PORTE, ce qu'on TRANSPORTE.

LE JOUEUR SE PENCHE, comme dans le craft (voir src/widgets/penche.py) : le
fond est la vraie scene de la case, la camera glisse vers le sol, et l'on
voit ses VRAIES MAINS au premier plan -- la bande de mains dessinee en bas
d'ecran est retiree.

Trois sections :
- a gauche, LE SOL EN CASES, pose a plat devant soi : la meme proximite que
  dans le craft, 5 cases sur 5 (voir sol_de_craft). C'est le meme sol, au
  meme endroit : passer d'un ecran a l'autre ne deplace rien ;
- au milieu, deux menus a deux sous-menus chacun :
    Equipement -> Tenue (la silhouette et ses emplacements)
               -> Statistiques (ce que chaque piece apporte)
    Personnage -> Apparence (le personnage habille, juste a regarder)
               -> Aptitudes (niveaux et experience)
- a droite le contenu du SAC A DOS. Sans sac, il n'y a aucune place : la
  colonne l'explique au lieu d'afficher une grille vide.

Les deux sections du milieu et de droite tiennent dans le HAUT de l'ecran :
le bas est au sol et aux mains. Un objet se glisse librement d'une section a
l'autre : les cases du sol, les mains, le sac, le corps.

Le titre est un TITRE A DEUX VOLETS partage avec le craft : les deux ecrans
montrent les memes objets sous deux angles, on passe de l'un a l'autre en
tapant le volet sombre (voir src/widgets/menu_toggle.py).

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
from src import stats as stats_mod
from src.widgets.animated_background import AnimatedBackground, night_darkness
from src.widgets import daylight
from src.widgets.zone_scenery import ZoneScenery
from src.widgets.item_icon import ItemIcon
from src.widgets.item_info import show_item_info
from src.widgets.styled_button import StyledButton, TabButton
from src.widgets.panels import panel
from src.widgets.hand_slot import empty_slot, item_text
from src.widgets.item_grid import fill_bag
from src.widgets.player_hands import PlayerHands
from src.widgets.sol_de_craft import (SolDeCraft, coins_rect, PROX_GAUCHE,
                                      PROX_DROITE, MAIN_DEMI_LARGEUR,
                                      MAIN_HAUT)
from src.widgets.penche import Penche
from src.widgets.corps import Corps, ANCRES
from src.widgets.drag_drop import (DragDrop, hit,
                                   make_highlightable)
from src.widgets.responsive import (scale_font, dh, fit_text,
                                    TEXT_NORMAL, SIDE_SHARE,
                                    center_share, ROW_TITLE, ROW_BODY,
                                    ROW_HANDS, ROW_HINT, ROW_BACK,
                                    COL_TITLE, COL_LIST)
from src.widgets.menu_toggle import MenuToggle

# Couleur des textes secondaires (emplacement vide, explications).
_DIM = (0.62, 0.64, 0.70, 1)
_GOLD = (0.96, 0.82, 0.45, 1)
# Vert des bonus apportes par l'equipement.
_BONUS = (0.55, 0.92, 0.62, 1)

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
_STAT_ROW = 120         # hauteur d'une ligne de statistique

# LA MISE EN PAGE PENCHEE. La colonne garde le gabarit du craft -- titre en
# haut, Retour en bas, aux memes places -- et les sections du milieu et de
# droite (equipement, sac) descendent du haut de l'ecran JUSQU'AU-DESSUS DES
# MAINS. MESURE sur l'image des mains au repos (HandIdle) : les doigts
# montent a 0,28 de la hauteur. Les sections s'arretent donc a 0,30. Une main
# qui tient un objet leve la paume plus haut (0,47) : ses doigts passent
# alors derriere le bas des panneaux, qui sont translucides.
# Ce sont des poids de BoxLayout (voir responsive.py), calcules pour cette
# limite : la colonne occupe 0,96 de l'ecran, a partir de 0,02.
BAS_SECTIONS = 0.30
# La place laissee a gauche pour le sol, en part de la rangee : les panneaux
# descendent maintenant a cote de la grille, ils doivent commencer apres son
# bord droit (0,28 de l'ecran, voir sol_de_craft.PROX_DROITE).
_PART_SOL = 0.28
_POIDS_TITRE = ROW_TITLE
_POIDS_BAS = ROW_BACK
_POIDS_VIDE = (BAS_SECTIONS - 0.02) / 0.96 - _POIDS_BAS
_POIDS_SECTIONS = 1.0 - _POIDS_TITRE - _POIDS_VIDE - _POIDS_BAS
# Le bas : le Retour ENTRE LES DEUX AVANT-BRAS, comme dans le craft, et la
# ligne d'aide a droite de la main droite (qui s'arrete a 0,71 de la
# largeur). Parts de la largeur de la rangee.
_BAS_MARGE = 0.40
_BAS_RETOUR = 0.20
_BAS_ECART = 0.13
_BAS_AIDE = 0.27

# Les deux menus du milieu, et leurs sous-menus dans l'ordre des boutons.
_SUBTABS = {
    "equip": (("tenue", "Tenue"), ("stats", "Statistiques")),
    "perso": (("apparence", "Apparence"), ("stats", "Aptitudes")),
}
_CELL_H = _ICON_SIDE + _CELL_LABEL + _NAME_LABEL
_BAG_CELL_H = _ICON_SIDE + _NAME_LABEL

# La Tenue : chaque emplacement est place VIS-A-VIS de la partie du corps
# qu'il habille, et relie a elle par un trait (le bout du trait est sur
# l'image du corps, voir corps.ANCRES).
#   emplacement -> (x, y du cadre)
# Coordonnees en fractions du panneau (y = 0 en bas). Les six cases forment
# deux colonnes de trois, de part et d'autre du corps.
_SLOT_LAYOUT = {
    "casque":    (0.22, 0.84),
    "chandail":  (0.22, 0.50),
    "gant":      (0.22, 0.16),
    "sac":       (0.78, 0.84),
    "pantalon":  (0.78, 0.50),
    "chaussure": (0.78, 0.16),
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
    return panel(widget, alpha=alpha)


# LA PROXIMITE A UN TITRE, comme le sac : au-dessus de sa grille, a la meme
# hauteur que "Sac a dos", et de la meme taille.
TITRE_PROXIMITE = "A proximite"


def colonne_proximite():
    """La colonne de gauche de la rangee des panneaux : le titre de la
    proximite, et dessous la place de sa grille. Rend (colonne, titre,
    place)."""
    gauche = BoxLayout(orientation="vertical", spacing=dp(6),
                       size_hint_x=_PART_SOL)
    titre = scale_font(Label(text=TITRE_PROXIMITE, bold=True,
                             size_hint=(1, COL_TITLE)), 0.022)
    place = Widget(size_hint=(1, COL_LIST))
    gauche.add_widget(titre)
    gauche.add_widget(place)
    return gauche, titre, place


def gabarit_proximite():
    """Une copie INVISIBLE de la colonne de l'inventaire, ou seule la
    proximite (titre et place) existe. Le craft s'en sert pour poser sa
    proximite EXACTEMENT ou l'inventaire pose la sienne : memes mesures,
    meme mise en page par Kivy, rien a recalculer a la main. Rend (colonne,
    titre, place)."""
    col = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8),
                    size_hint=(0.96, 0.96),
                    pos_hint={"center_x": 0.5, "center_y": 0.5})
    col.add_widget(Widget(size_hint=(1, _POIDS_TITRE)))
    body = BoxLayout(orientation="horizontal", spacing=dp(10),
                     size_hint=(1, _POIDS_SECTIONS))
    gauche, titre, place = colonne_proximite()
    body.add_widget(gauche)
    rest = (1.0 - _PART_SOL) / 2.0
    body.add_widget(Widget(size_hint_x=rest))
    body.add_widget(Widget(size_hint_x=rest))
    col.add_widget(body)
    col.add_widget(Widget(size_hint=(1, _POIDS_VIDE)))
    col.add_widget(Widget(size_hint=(1, _POIDS_BAS)))
    return col, titre, place


def coins_estimes():
    """La proximite avant toute mise en page (parts de l'ecran)."""
    haut = 0.98 - 0.96 * _POIDS_TITRE
    return coins_rect(PROX_GAUCHE, BAS_SECTIONS, PROX_DROITE,
                      haut - (haut - BAS_SECTIONS) * COL_TITLE)


def _row_font(w, *_):
    """Ligne d'inventaire. `font_scale` ecrit un nom plus gros qu'un detail.

    Delegue a la regle commune (responsive.fit_text) : l'inventaire et le
    craft ecrivent ainsi a la meme taille, au lieu de chacun la sienne."""
    fit_text(w, TEXT_NORMAL * getattr(w, "font_scale", 1.0))


def _xp_bar(done, needed, **kwargs):
    """Petite barre montrant l'avancee vers le niveau suivant."""
    bar = Widget(**kwargs)
    part = max(0.0, min(1.0, done / float(needed))) if needed else 0.0
    with bar.canvas:
        Color(1, 1, 1, 0.12)
        back = RoundedRectangle(radius=[dp(3)])
        fill_color = Color(0.45, 0.85, 0.55, 0.85)
        fill = RoundedRectangle(radius=[dp(3)])

    def _sync(*_):
        height = min(bar.height, dp(7))
        y = bar.center_y - height / 2
        back.pos = (bar.x, y)
        back.size = (bar.width, height)
        width = bar.width * part
        # A zero, un RoundedRectangle garde ses coins et laisse une pastille
        # qui ferait croire a un debut de progression : on coupe sa couleur.
        fill_color.a = 0.85 if width > 0.5 else 0.0
        fill.radius = [max(1.0, min(dp(3), height / 2.0, width / 2.0))]
        fill.pos = (bar.x, y)
        fill.size = (max(0.0, width), height)
    bar.bind(pos=_sync, size=_sync)
    _sync()
    return bar


def _scroll_box():
    """Un ScrollView et la colonne verticale qu'il fait defiler."""
    scroll = ScrollView(size_hint=(1, 1))
    box = BoxLayout(orientation="vertical", spacing=dp(6), size_hint_y=None)
    box.bind(minimum_height=box.setter("height"))
    scroll.add_widget(box)
    return scroll, box


def _label(text, color=(0.92, 0.92, 0.95, 1), halign="left", scale=1.0,
           **kwargs):
    lbl = Label(text=text, color=color, halign=halign, valign="middle",
                **kwargs)
    lbl.font_scale = scale
    _row_font(lbl)
    return lbl


class InventoryScreen(Penche, DragDrop, Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = FloatLayout()
        # LE MONDE, vu par un joueur qui se penche (voir penche.py).
        self.construit_monde(root)

        # LE SOL EN CASES, la proximite seule : le milieu de l'ecran est a
        # l'equipement. Ici le glisser est mene par l'ecran (voir drag_drop) :
        # le sol ne sert qu'a dessiner et a dire quelle case est sous le
        # doigt.
        # LA PROXIMITE EN FACE DES DEUX PANNEAUX : meme haut, meme bas (voir
        # _cale_proximite) ; avant la mise en page, on l'estime.
        self.sol = SolDeCraft(avec_centre=False,
                              coins_prox=coins_estimes(),
                              size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        self.sol.opacity = 0.0
        root.add_widget(self.sol)

        # LES VRAIES MAINS, a la place de la bande de mains d'avant.
        self.hands = PlayerHands(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.hands)
        # Leurs places de depart et d'arrivee pour le glisser : invisibles,
        # elles ne font que s'allumer quand une main peut recevoir l'objet.
        self.hand_slots = [_MainReelle(i) for i in (0, 1)]
        for slot in self.hand_slots:
            root.add_widget(slot)

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
        # Titre a deux volets : "INVENTAIRE / craft". On passe au craft sans
        # se relever (voir penche.partir).
        col.add_widget(MenuToggle(self, "inventory",
                                  size_hint=(1, _POIDS_TITRE),
                                  switch=self.partir))

        body = BoxLayout(orientation="horizontal", spacing=dp(10),
                         size_hint=(1, _POIDS_SECTIONS))

        # ---- Gauche : la place du sol, EN FACE des deux panneaux, sous
        # son titre ----
        gauche, self.prox_title, self._place_sol = colonne_proximite()
        body.add_widget(gauche)
        # Le titre parait et s'efface avec la grille.
        self.prox_title.opacity = self.sol.opacity
        self.sol.bind(opacity=lambda _w, v: setattr(self.prox_title,
                                                    "opacity", v))
        self._place_sol.bind(pos=self._cale_proximite,
                             size=self._cale_proximite)
        # Le sol accepte tout ce qu'on y lache, case ou pas : cette zone
        # invisible, posee sur la grille, est la cible "sol" du glisser, et
        # fait clignoter les cases quand on peut y poser.
        self.ground_scroll = _ZoneSol(self.sol)
        root.add_widget(self.ground_scroll)
        self._ground_cells = []

        # ---- Milieu : deux menus, deux sous-menus chacun ----
        rest = (1.0 - _PART_SOL) / 2.0
        center = BoxLayout(orientation="vertical", spacing=dp(4),
                           size_hint_x=rest)
        self._main = "equip"
        self._sub = {"equip": "tenue", "perso": "apparence"}

        mrow = BoxLayout(orientation="horizontal", spacing=dp(4),
                         size_hint=(1, 0.09))
        self.main_buttons = {}
        for key, label in (("equip", "Equipement"), ("perso", "Personnage")):
            btn = scale_font(TabButton(text=label, bold=True), 0.018)
            btn.bind(on_release=lambda _w, k=key: self._show_main(k))
            mrow.add_widget(btn)
            self.main_buttons[key] = btn
        center.add_widget(mrow)

        # Deux boutons seulement : leur libelle change avec le menu choisi.
        srow = BoxLayout(orientation="horizontal", spacing=dp(4),
                         size_hint=(1, 0.08))
        self.sub_buttons = []
        for i in range(2):
            btn = scale_font(TabButton(text=""), 0.016)
            btn.bind(on_release=lambda _w, i=i: self._show_sub(i))
            srow.add_widget(btn)
            self.sub_buttons.append(btn)
        center.add_widget(srow)

        self.content = BoxLayout(size_hint=(1, 0.83))
        center.add_widget(self.content)
        _panel(center)
        body.add_widget(center)
        # Les panneaux, pour que les mains qu'ils recouvrent en partie ne
        # volent pas les depots qui leur sont destines.
        self._panneaux = [center]

        # Les quatre panneaux, crees une fois et permutes dans `content`.
        self.equip_box = _BodyPanel(size_hint=(1, 1))
        self.avatar_box = _BodyPanel(traits=False, size_hint=(1, 1))
        self.hero_panel, self.hero_box = _scroll_box()
        self.gear_panel, self.gear_box = _scroll_box()

        # ---- Droite : contenu du sac ----
        right = BoxLayout(orientation="vertical", spacing=dp(6),
                          size_hint_x=rest)
        self.bag_title = scale_font(Label(text="Sac a dos", bold=True,
                                    size_hint=(1, COL_TITLE)), 0.022)
        right.add_widget(self.bag_title)
        sc2 = self.bag_scroll = make_highlightable(ScrollView(
            size_hint=(1, COL_LIST)))
        self.bag_box = BoxLayout(orientation="vertical", spacing=dp(4),
                                 size_hint_y=None)
        self.bag_box.bind(minimum_height=self.bag_box.setter("height"))
        sc2.add_widget(self.bag_box)
        right.add_widget(sc2)
        _panel(right)
        body.add_widget(right)
        self._panneaux.append(right)

        col.add_widget(body)
        col.add_widget(Widget(size_hint=(1, _POIDS_VIDE)))

        # ---- En bas : le Retour entre les avant-bras, l'aide a droite ----
        bas = BoxLayout(orientation="horizontal", spacing=dp(6),
                        size_hint=(1, _POIDS_BAS))
        bas.add_widget(Widget(size_hint_x=_BAS_MARGE))
        back = scale_font(StyledButton(text="Retour",
                                       size_hint_x=_BAS_RETOUR), 0.022)
        back.bind(on_release=lambda *_: self.partir("game"))
        bas.add_widget(back)
        bas.add_widget(Widget(size_hint_x=_BAS_ECART))
        # Message d'aide / refus (pourquoi un depot n'a pas marche).
        self.hint = fit_text(Label(
            text="Glisse un objet entre le sol, tes mains, ton sac et ton "
                 "equipement.", color=_DIM, halign="center", valign="middle",
            size_hint_x=_BAS_AIDE), TEXT_NORMAL * 0.8, wrap=True)
        bas.add_widget(self.hint)
        col.add_widget(bas)

        root.add_widget(col)

        # Couche du glisser-deposer : l'objet suivi par le doigt passe
        # AU-DESSUS de tout le reste.
        self.drag_layer = FloatLayout(size_hint=(1, 1),
                                      pos_hint={"x": 0, "y": 0})
        root.add_widget(self.drag_layer)
        self._root = root
        # Cibles du glisser-deposer, reconstruites a chaque rafraichissement.
        self._equip_slots = []
        self._bag_cells = []
        self.init_drag()
        # Les cases d'equipement ont une taille FIXE (celle d'une case du
        # sac) : il faut la recalculer quand le panneau change de taille.
        self.equip_box.bind(size=self._size_equip_slots)
        self._sync_tabs()
        self.add_widget(root)

    # ------------------------------------------------------------------ #
    def on_pre_enter(self):
        state = App.get_running_app().game_state
        # Le monde, la scene de la case et le regard de depart (voir
        # penche.py) : depuis le jeu on arrive debout, depuis le craft deja
        # penche.
        self.prepare_penche(state)
        self.refresh()

    def on_enter(self):
        self.hands.start_breathing()
        self.equip_box.corps.respire(True)
        self.avatar_box.corps.respire(True)
        self.lance_penche()

    def on_leave(self):
        """Ne laisse ni clignotement ni fiche ouverte sur un ecran qu'on quitte."""
        self._cancel_drag()
        if self._info is not None:
            self._info.close()
        self.hands.stop_breathing()
        self.equip_box.corps.respire(False)
        self.avatar_box.corps.respire(False)
        self.quitte_penche()

    def refresh(self):
        state = App.get_running_app().game_state
        if state is None:
            return
        self._fill_avatar(state)
        self._fill_stats(state)
        self._fill_equipment(state)
        self._fill_bag(state)
        # Apres les DEUX colonnes : la mise a l'echelle touche les cases de
        # l'equipement comme celles du sac, qui viennent d'etre recreees.
        self._size_equip_slots()
        # Les mains et le sol.
        self.hands.set_items(state.hands[0], state.hands[1])
        self.hands.set_glove(state.equipment.get("gant"))
        for slot in self.hand_slots:
            slot.item = state.hands[slot.hand]
        self.sol.montre(state.sol_en_cases(), state.hands,
                        metres=state.metres_des_piles())
        self._place_cibles()

    # ------------------------------------------------------------------ #
    # Le sol en cases et les vraies mains dans le glisser (voir drag_drop)
    # ------------------------------------------------------------------ #
    def _cale_proximite(self, *_):
        """La proximite prend exactement la place de gauche de la rangee des
        panneaux : son haut et son bas sont les leurs."""
        w, sol = self._place_sol, self.sol
        if sol.width <= 0 or sol.height <= 0 or w.height <= 0:
            return
        sol.set_coins_proximite(coins_rect(
            (w.x - sol.x) / float(sol.width),
            (w.y - sol.y) / float(sol.height),
            (w.right - sol.x) / float(sol.width),
            (w.top - sol.y) / float(sol.height)))
        self._place_cibles()

    def _place_cibles(self, *_):
        """Pose les cibles invisibles des mains et du sol sur leurs dessins."""
        w, h = self.width, self.height
        for slot in self.hand_slots:
            fx = PlayerHands.HAND_FX[slot.hand]
            slot.size_hint = (None, None)
            # Jusqu'au bas des panneaux seulement : au-dessus, ce sont eux
            # qu'on vise.
            slot.size = (2 * MAIN_DEMI_LARGEUR * w,
                         min(MAIN_HAUT, BAS_SECTIONS) * h)
            slot.pos = (self.x + (fx - MAIN_DEMI_LARGEUR) * w, self.y)
            slot.paume_y = self.y + PlayerHands.ITEM_FY * h
            slot._sync()
        xs, ys = zip(*[(fx * w, fy * h) for fx, fy in
                       self.sol.proximite.coins])
        self.ground_scroll.size_hint = (None, None)
        self.ground_scroll.pos = (self.x + min(xs), self.y + min(ys))
        self.ground_scroll.size = (max(xs) - min(xs), max(ys) - min(ys))

    def on_size(self, *_):
        self._place_cibles()

    def _source_virtuelle(self, touch):
        """Une pile du sol sous le doigt : ("case", "G:3", objet)."""
        if self._pente < 0.999:
            return None
        cible = self.sol.sous_le_doigt(touch.x, touch.y)
        if cible is None or cible[0] != "case":
            return None
        nom = self.sol.objet_de(cible)
        return ("case", cible[1], nom) if nom else None

    def _survol_virtuel(self, touch):
        """La case sous l'objet qu'on porte s'allume."""
        if touch is None or self._drag is None:
            self.sol.visee_externe(None)
            return
        cible = self.sol.vise_depot(touch.x, touch.y)
        if cible is None or cible[0] != "case":
            self.sol.visee_externe(None)
            return
        kind, _i, nom = self._drag["source"]
        dessus = self.sol.objet_de(cible)
        refus = (kind != "case" and dessus is not None and dessus != nom)
        self.sol.visee_externe(cible[1], refus)

    def _depot_virtuel(self, state, kind, index, name, touch):
        """Ce que font les cases du sol et les vraies mains, comme source ou
        comme cible. Rend un message, ou None pour laisser les regles
        ordinaires (le sac, le corps) s'appliquer."""
        label = items.display_name(name)
        # La case visee est UNE RANGEE AU-DESSUS du doigt (voir
        # sol_de_craft._Grille.visee) : celle qui s'allume pendant le glisser.
        cible = self.sol.vise_depot(touch.x, touch.y)
        if cible and cible[0] == "main" and any(
                hit(p, touch) for p in self._panneaux):
            cible = None
        case = cible[1] if cible and cible[0] == "case" else None
        main = cible[1] if cible and cible[0] == "main" else None
        # ---- DEPUIS une case du sol ----
        if kind == "case":
            if case is not None:
                if case == index:
                    return ""
                state.deplace_au_sol(index, case)
                return ""
            if main is not None:
                if state.hands[main] is not None:
                    return "Cette main est deja occupee."
                state.sol_vers_main(index, main)
                return f"{label} ramasse."
            if hit(self.bag_scroll, touch):
                if state.bag_capacity() <= 0:
                    return "Aucun sac a dos pour ranger cet objet."
                if state.bag_free() <= 0:
                    return "Le sac est plein."
                state.sol_vers_sac(index)
                return f"{label} ramasse dans le sac."
            for widget in self._equip_widgets():
                if not hit(widget, touch):
                    continue
                good = items.equip_slot(name)
                if good is None:
                    return f"{label} ne se porte pas."
                if good != widget.slot:
                    return (f"{label} se porte a "
                            f"l'emplacement {items.EQUIP_SLOT_NAMES[good]}.")
                state.sol_equipe(index)
                return f"{label} ramasse et equipe."
            return ""
        # ---- VERS une case du sol ----
        if case is not None:
            dessus = self.sol.objet_de(cible)
            if dessus is not None and dessus != name:
                return "Cette case est deja prise."
            if kind == "hand":
                state.main_vers_sol(index, case)
                return f"{label} pose au sol."
            if kind == "bag":
                state.vers_case(case, name, lambda: state.bag_drop(index))
                return f"{label} sorti du sac, pose au sol."
            if kind == "equip":
                res = state.vers_case(case, name,
                                      lambda: state.unequip_to_ground(index))
                if res is None:
                    return ""
                return f"{label} retire et pose au sol."
            return None
        # ---- D'une main a l'autre ----
        if kind == "hand" and main is not None:
            if main != index:
                state.echange_mains()
            return ""
        return None

    def _drop(self, touch):
        """Le depot ordinaire, puis LE GESTE de chaque main dont le contenu
        vient de changer : elle a pris ou pose quelque chose."""
        state = App.get_running_app().game_state
        avant = list(state.hands) if state is not None else None
        super()._drop(touch)
        if state is None:
            return
        for i in (0, 1):
            if state.hands[i] != avant[i]:
                self.hands.geste(i)

    # ------------------------------------------------------------------ #
    # Glisser-deposer
    # ------------------------------------------------------------------ #
    def _show_main(self, key):
        """Passe d'un menu a l'autre, en gardant le sous-menu de chacun."""
        self._main = key
        self._sync_tabs()

    def _show_sub(self, index):
        self._sub[self._main] = _SUBTABS[self._main][index][0]
        self._sync_tabs()

    def _sync_tabs(self):
        """Met les boutons a jour et pose le bon panneau dans la fenetre."""
        # L'onglet ouvert est SELECTIONNE (or, contour epais), pas desactive.
        # Il l'etait, et se peignait donc en gris terne comme un bouton en
        # panne : l'ecran donnait l'impression que l'onglet courant etait
        # celui qu'on ne pouvait PAS ouvrir, exactement l'inverse.
        for key, btn in self.main_buttons.items():
            btn.selected = (key == self._main)
        subs = _SUBTABS[self._main]
        for i, btn in enumerate(self.sub_buttons):
            btn.text = subs[i][1]
            btn.selected = (subs[i][0] == self._sub[self._main])
        panneau = {
            ("equip", "tenue"): self.equip_box,
            ("equip", "stats"): self.gear_panel,
            ("perso", "apparence"): self.avatar_box,
            ("perso", "stats"): self.hero_panel,
        }[(self._main, self._sub[self._main])]
        if self.content.children[:1] != [panneau]:
            self.content.clear_widgets()
            self.content.add_widget(panneau)

    def _panel_row(self, height_ratio=1.0):
        """Ligne encadree, commune aux deux onglets."""
        row = BoxLayout(orientation="vertical", size_hint_y=None,
                        height=dh(_STAT_ROW * height_ratio),
                        padding=(dp(10), dp(4)))
        with row.canvas.before:
            Color(0.05, 0.07, 0.10, 0.42)
            bg = RoundedRectangle(radius=[dp(8)])
        row.bind(pos=lambda w, *_, r=bg: setattr(r, "pos", w.pos),
                 size=lambda w, *_, r=bg: setattr(r, "size", w.size))
        return row

    def _fill_stats(self, state):
        """Remplit les DEUX panneaux de statistiques.

        On les garnit tous les deux a chaque rafraichissement : passer d'un
        sous-menu a l'autre n'a alors rien a recalculer, et aucun ne peut
        montrer un etat perime."""
        self.hero_box.clear_widgets()
        self.gear_box.clear_widgets()
        self._fill_hero_stats(state)
        self._fill_gear_stats(state)
        self._sync_tabs()

    def _fill_hero_stats(self, state):
        """Une ligne par aptitude : niveau, quantite, et experience en cours.

        Quatre chiffres comptent et sont montres separement : le niveau
        atteint, ce que l'equipement y ajoute, la QUANTITE que cela
        represente, et l'avancee vers le niveau suivant."""
        for key in stats_mod.STAT_ORDER:
            level = state.stat(key)
            bonus = state.stat_bonus(key)
            done, needed = state.stat_progress(key)
            row = self._panel_row(1.25)

            head = BoxLayout(orientation="horizontal", size_hint_y=0.34)
            head.add_widget(_label(stats_mod.STAT_NAMES[key], _GOLD,
                                   size_hint_x=0.58, scale=1.10))
            # Le niveau atteint, puis ce que l'equipement y ajoute : les deux
            # sont visibles separement, l'un se gagne, l'autre s'enleve.
            head.add_widget(_label(f"niv. {level}" + (f" +{bonus}" if bonus
                                                      else ""),
                                   _BONUS if bonus else (0.92, 0.92, 0.95, 1),
                                   halign="right", size_hint_x=0.42,
                                   scale=1.10))
            row.add_widget(head)

            # La QUANTITE : ce que le niveau vaut vraiment. Avec le bonus de
            # l'equipement s'il y en a un, puisque c'est celle-la qui sert.
            quantite = stats_mod.quantity(level + bonus)
            ligne = BoxLayout(orientation="horizontal", size_hint_y=0.22)
            ligne.add_widget(_label("Quantite", _DIM, size_hint_x=0.58,
                                    scale=0.78))
            ligne.add_widget(_label(str(quantite),
                                    _BONUS if bonus else _DIM,
                                    halign="right", size_hint_x=0.42,
                                    scale=0.78))
            row.add_widget(ligne)

            # Barre d'experience : on voit ce qui reste avant le niveau
            # suivant, sinon un niveau semblerait tomber sans raison.
            row.add_widget(_xp_bar(done, needed, size_hint_y=0.18))
            row.add_widget(_label(f"{done} / {needed} xp  vers niv. "
                                  f"{level + 1}", _DIM, halign="center",
                                  size_hint_y=0.26, scale=0.78))
            self.hero_box.add_widget(row)

        note = _label("Chaque aptitude monte par les actions qui la "
                      "sollicitent.", _DIM, halign="center",
                      size_hint_y=None, height=dh(_STAT_ROW * 0.6))
        self.hero_box.add_widget(note)

    def _fill_gear_stats(self, state):
        """Ce que chaque piece portee apporte.

        Une entree par PIECE : son nom en grand, ses apports en petit
        dessous. Le cumul de tout ce qui est porte ouvre la liste."""
        porte = [(slot, state.equipment[slot]) for slot in items.EQUIP_SLOTS
                 if state.equipment.get(slot)]
        if not porte:
            self.gear_box.add_widget(
                _label("Tu ne portes rien.", _DIM, halign="center",
                       size_hint_y=None, height=dh(_STAT_ROW)))
            return

        # ---- Le cumul, en tete ----
        totaux = [f"{stats_mod.STAT_NAMES[k]} +{state.stat_bonus(k)}"
                  for k in stats_mod.STAT_ORDER if state.stat_bonus(k)]
        # Sept bonus sur une seule ligne deviendraient minuscules dans une
        # colonne aussi etroite : on les repartit sur deux lignes.
        moitie = (len(totaux) + 1) // 2
        resume = "\n".join(filter(None, (", ".join(totaux[:moitie]),
                                         ", ".join(totaux[moitie:]))))
        row = self._panel_row(1.0)
        row.add_widget(_label("Total porte", _GOLD, size_hint_y=0.34,
                              scale=1.15))
        row.add_widget(_label(resume or "Aucun bonus pour l'instant.",
                              _BONUS if totaux else _DIM, size_hint_y=0.66,
                              scale=0.80))
        self.gear_box.add_widget(row)

        # ---- Puis piece par piece ----
        for slot, worn in porte:
            gains = items.item_stats(worn)
            detail = ", ".join(
                f"{stats_mod.STAT_NAMES[k]} +{gains[k]}"
                for k in stats_mod.STAT_ORDER if k in gains)
            row = self._panel_row(0.85)
            head = BoxLayout(orientation="horizontal", size_hint_y=0.52)
            # Le NOM est ce qu'on cherche du regard : il passe en grand.
            head.add_widget(_label(items.display_name(worn), size_hint_x=0.70,
                                   scale=1.30))
            head.add_widget(_label(items.EQUIP_SLOT_NAMES[slot], _DIM,
                                   halign="right", size_hint_x=0.30,
                                   scale=0.72))
            row.add_widget(head)
            row.add_widget(_label(detail or "N'apporte aucun bonus.",
                                  _BONUS if detail else _DIM,
                                  size_hint_y=0.48, scale=0.80))
            self.gear_box.add_widget(row)

    def _fill_equipment(self, state):
        """Pose une case par emplacement, en face de sa partie du corps."""
        self.equip_box.clear_widgets()
        self._equip_slots = []
        for slot in items.EQUIP_SLOTS:
            sx, sy = _SLOT_LAYOUT[slot]
            worn = state.equipment.get(slot)
            widget = _EquipSlot(slot, worn,
                                item_text(state, worn, worn=True),
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
        for cell in self._bag_cells + self._ground_cells:
            cell.name_label.height = label
            cell.height = icon + label

    def _fill_avatar(self, state):
        """Le personnage tel qu'il est habille, juste pour le regarder : les
        vetements portes sont poses SUR LE CORPS (voir corps.py), dans la
        Tenue comme ici. Rien n'y est cliquable."""
        self.avatar_box.clear_widgets()
        porte = {slot: state.equipment.get(slot) for slot in items.EQUIP_SLOTS}
        self.avatar_box.habille(porte)
        self.equip_box.habille(porte)
        nombre = sum(1 for v in porte.values() if v)
        self.avatar_box.add_widget(_label(
            f"{nombre} piece(s) portee(s)" if nombre
            else "Aucun vetement porte",
            _DIM, halign="center", size_hint=(1, 0.08),
            pos_hint={"center_x": 0.5, "y": 0.0}))

    def _fill_bag(self, state):
        """Le sac. Meme colonne que dans le craft (widget partage)."""
        self._bag_cells = fill_bag(self.bag_box, self.bag_title, state)


class _MainReelle(Widget):
    """La place d'une vraie main dans le glisser : invisible, elle porte ce
    que la main tient (`item`) et s'allume quand elle peut recevoir
    l'objet porte -- une lueur verte au creux de la paume, qui clignote."""

    def __init__(self, hand, **kwargs):
        super().__init__(**kwargs)
        self.hand = hand
        self.item = None
        self.paume_y = None
        with self.canvas:
            self._lueur = Color(0.45, 1.0, 0.62, 0.0)
            self._disque = Ellipse()
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        r = self.width * 0.62
        cy = self.paume_y if self.paume_y is not None else self.center_y
        self._disque.pos = (self.center_x - r, cy - r * 0.55)
        self._disque.size = (2 * r, 1.1 * r)

    def set_highlight(self, on, pulse=1.0):
        self._lueur.a = 0.16 + 0.22 * pulse if on else 0.0


class _ZoneSol(Widget):
    """La cible "sol" du glisser : invisible, posee sur la grille de la
    proximite. Elle NE CLIGNOTE PAS quand on porte un objet : toute la grille
    qui flashe a chaque prise genait. Seule la case sous le doigt s'allume
    (voir InventoryScreen._survol_virtuel)."""

    def __init__(self, sol, **kwargs):
        super().__init__(**kwargs)
        self._sol = sol

    def set_highlight(self, on, pulse=1.0):
        pass


class _BodyPanel(FloatLayout):
    """Le CORPS DU PERSONNAGE (voir src/widgets/corps.py), habille de ce
    qu'il porte et qui respire, avec -- dans la Tenue -- un trait de chaque
    emplacement d'equipement vers la partie du corps qu'il habille.

    Tout est dessine dans `canvas.before` : les cases d'equipement, ajoutees
    comme enfants, passent donc par-dessus."""

    def __init__(self, traits=True, **kwargs):
        super().__init__(**kwargs)
        self.traits = traits
        self.corps = Corps()
        self.porte = {}
        self.bind(pos=self._redraw, size=self._redraw)

    def habille(self, porte):
        """Ce que porte le personnage (emplacement -> objet)."""
        porte = {k: v for k, v in (porte or {}).items() if v}
        if porte != self.porte:
            self.porte = porte
            self._redraw()

    def _redraw(self, *_):
        self.canvas.before.clear()
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        if w <= 0 or h <= 0:
            return
        # Dans la Tenue, le corps tient entre les deux colonnes de cases ;
        # dans l'Apparence, rien ne le gene.
        rect = Corps.rect_dans(x0, y0, w, h,
                               part_l=0.32 if self.traits else 0.80)
        self.corps.rect = rect
        if self.traits:
            # Demi-largeur d'une case, en fraction du panneau : les traits
            # partent du bord de la case, pas de son centre.
            half = _cell_size(self)[0] / (2.0 * w)
            with self.canvas.before:
                Color(1, 1, 1, 0.22)
                for slot, (sx, sy) in _SLOT_LAYOUT.items():
                    edge = sx + (half if sx < 0.5 else -half)
                    Line(points=[x0 + edge * w, y0 + sy * h,
                                 *self.corps.point(*ANCRES[slot])],
                         width=1.2)
        self.corps.dessine(self.canvas.before, rect, self.porte)


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


