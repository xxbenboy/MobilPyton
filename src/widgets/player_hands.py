"""
Mains du joueur (vue 1re personne) - APPROCHE HUD plein ecran.

UNE SEULE IMAGE par etat du joueur : un HUD plein ecran dans lequel les
mains sont deja positionnees au bon endroit (en bas). Le HUD est dessine
sur toute la surface du widget (== plein ecran).

AU REPOS, chaque main a sa propre pose, et les deux sont TOUJOURS visibles :
- une main VIDE prend la pose de repos ('idle') ;
- une main qui TIENT quelque chose garde la paume ouverte ('haut'), car
  c'est dans ce creux que l'objet est pose.
Une main vide n'etait auparavant pas dessinee du tout : on ne voyait ses
mains qu'en portant quelque chose. Comme chaque image contient les deux
mains, on n'en prend que la moitie utile (voir _draw_half).

PENDANT L'EXPLORATION, les deux mains prennent la pose de FOUILLE et montent
et descendent l'une apres l'autre. Ce va-et-vient n'est pas une suite
d'images : une seule pose suffit, et le mouvement est calcule (searching.py).
Chaque main a donc sa propre translation, imbriquee dans celle du souffle.

Les objets tenus (set_items) sont dessines AU-DESSUS du HUD, aux
positions correspondant aux mains dans l'image (HAND_FX / ITEM_FY).
"""
import os

from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Rectangle, PushMatrix, PopMatrix, Translate

from src import items
from src.widgets import breathing, searching

_HERE = os.path.dirname(os.path.abspath(__file__))
CHARACTER_DIR = os.path.abspath(os.path.join(_HERE, "..", "..", "assets",
                                             "Character"))

# Fichier image par ETAT du joueur. L'image est un HUD PLEIN ECRAN
# (taille de reference : 2340 x 1080 pour un telephone portrait) avec
# les mains deja positionnees en bas. Le HUD est etire pour remplir
# la totalite du widget.
HUD_IMAGES = {
    'haut': 'HandHUD.png',      # paume ouverte : une main qui TIENT un objet
    'idle': 'HandIdle.png',     # main VIDE, au repos
    'search': 'HandSearch.png',  # exploration : les mains fouillent
}

# Pose d'une main qui TIENT quelque chose (paume ouverte, l'objet s'y pose).
REST_STATE = 'haut'
# Pose d'une main vide au repos.
IDLE_STATE = 'idle'
# Pose de FOUILLE. Elle ne s'anime pas par une suite d'images : les deux mains
# montent et descendent tour a tour, chacune de son cote (voir searching.py).
SEARCH_STATE = 'search'

# --------------------------------------------------------------------- #
# GANTS : des mains qui changent d'apparence
# --------------------------------------------------------------------- #
# Enfiler des gants doit SE VOIR. Le joueur passe la partie a regarder ses
# mains ; c'est la seule piece d'equipement qu'il a en permanence sous les
# yeux, et donc la seule dont le port peut se lire sans ouvrir un menu.
#
# La cle est le nom de l'objet porte a l'emplacement "gant", la valeur un
# SUFFIXE de nom de fichier : HandIdle.png a cote de HandIdleFeuille.png.
# Ajouter une paire de gants ne demande donc que deux choses -- une ligne
# ici, et des images qui suivent la meme convention.
GLOVE_SUFFIX = {
    "Gant_De_Feuille": "Feuille",
}

_TEX_CACHE = {}
_ITEM_TEX = {}


def _load(fname):
    """Charge une image du personnage (ou la recupere en cache).

    Un fichier ABSENT est retenu comme tel (None en cache) : sans cela, un
    etat sans variante gantee ferait un acces disque a chaque image."""
    if fname in _TEX_CACHE:
        return _TEX_CACHE[fname]
    p = os.path.join(CHARACTER_DIR, fname)
    tex = None
    if os.path.isfile(p):
        try:
            tex = CoreImage(p).texture
        except Exception:
            tex = None
    _TEX_CACHE[fname] = tex
    return tex


def _hud_texture(state, glove=None):
    """HUD d'un etat, GANTE si le joueur porte des gants qui se voient.

    Le repli sur les mains nues n'est pas un filet de securite mais la
    regle : toute pose sans variante gantee reprend la main nue. Aujourd'hui
    la pose de FOUILLE est dans ce cas -- les gants disparaissent donc le
    temps de l'exploration, ce qui vaut mieux qu'une main manquante, et se
    corrige en deposant un seul fichier (HandSearchFeuille.png)."""
    fname = HUD_IMAGES.get(state)
    if not fname:
        return None
    suffix = GLOVE_SUFFIX.get(glove)
    if suffix:
        tex = _load(fname[:-4] + suffix + fname[-4:])
        if tex is not None:
            return tex
    return _load(fname)


def _item_texture(name):
    """Texture de l'image d'un objet (assets/items/<nom>.png), ou None."""
    if not name:
        return None
    path = items.image_path(name)
    if not path:
        return None
    if path not in _ITEM_TEX:
        try:
            _ITEM_TEX[path] = CoreImage(path).texture
        except Exception:
            _ITEM_TEX[path] = None
    return _ITEM_TEX[path]


# --------------------------------------------------------------------- #
# LE SOUFFLE
# --------------------------------------------------------------------- #
# Amplitude du mouvement, en fraction de la HAUTEUR du widget (donc de
# l'ecran). Les deux se mesurent sur la hauteur, et pas l'une sur la largeur :
# sinon le va-et-vient lateral serait plus ample sur un ecran large, et le
# souffle changerait de forme d'un telephone a l'autre.
#
# Ces valeurs sont PETITES a dessein. Le souffle doit se sentir sans se
# remarquer : au-dela, les mains ont l'air de flotter, et le regard va au
# mouvement au lieu d'aller au decor. 0.9 % de la hauteur fait ~10 px sur un
# telephone -- c'est le seuil ou l'oeil voit que "ca vit" sans savoir quoi.
BREATH_Y = 0.009
BREATH_X = 0.0035

# Images par seconde du souffle. Le mouvement est LENT (un cycle en 4 s) : le
# rafraichir 60 fois par seconde ne le rendrait pas plus fluide, cela
# doublerait juste le travail. 30 suffisent largement.
BREATH_FPS = 30.0

# Amplitude de l'ALTERNANCE des mains pendant la fouille, en fraction de la
# hauteur. Bien plus ample que le souffle : c'est un geste volontaire, il doit
# se voir franchement, la ou le souffle doit seulement se sentir.
SEARCH_Y = 0.035


class PlayerHands(Widget):
    # x du centre de chaque main (gauche, droite) en fraction de la largeur
    # du widget. Mesures depuis HandHUD.png (mains a 34 % et 65 %).
    HAND_FX = (0.346, 0.654)
    # y des objets tenus (creux de la paume), en fraction de la hauteur du
    # widget depuis le bas. Mesures depuis HandHUD.png : palm center a
    # 21 % du bas de l'image, image affichee sur 21 % de la hauteur ecran.
    ITEM_FY = 0.225

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._items = [None, None]      # objets tenus : [gauche, droite]
        self._glove = None               # gants portes (voir set_glove)
        # Fouille : avancement de l'action (0 a 1), ou None au repos.
        self._search = None
        # Une translation PAR MAIN : c'est ce qui leur permet de monter et
        # descendre CHACUNE DE SON COTE pendant la fouille.
        self._half_shift = [None, None]
        # Souffle : l'horloge du temps qui passe, et les deux translations
        # qu'elle deplace (mains et objets tenus).
        self._breath_t = 0.0
        self._breath_event = None
        self._shift = None
        self._shift_items = None
        self.bind(pos=self._redraw, size=self._redraw)

    # ---- API publique ----------------------------------------------------

    def set_items(self, left, right):
        """Definit les objets tenus (None = main vide).

        Comme la VISIBILITE des mains depend maintenant des items en main
        (main vide cachee en etat 'haut'), on redessine TOUT le widget
        (pas seulement les items).
        """
        new = [left, right]
        if new == self._items:
            return
        self._items = new
        self._redraw()

    def set_glove(self, name):
        """Definit les gants PORTES (None = mains nues).

        On garde le nom de l'objet, pas un simple oui/non : passer d'une
        paire de gants a une autre doit changer l'image, et un booleen ne
        le verrait pas."""
        if name == self._glove:
            return
        self._glove = name
        self._redraw()

    def start_breathing(self):
        """Met le souffle en route (a l'arrivee sur l'ecran de jeu)."""
        if self._breath_event is None:
            self._breath_event = Clock.schedule_interval(self._tick_breath,
                                                         1.0 / BREATH_FPS)

    def stop_breathing(self):
        """Arrete le souffle (en quittant l'ecran).

        Le temps ecoule, lui, est CONSERVE : au retour, la respiration reprend
        ou elle en etait, au lieu de repartir d'une inspiration franche a
        chaque fois qu'on ouvre un menu."""
        if self._breath_event is not None:
            self._breath_event.cancel()
            self._breath_event = None

    def set_search(self, progress):
        """Fouille en cours : `progress` va de 0 a 1 sur la duree de l'action,
        et vaut None hors exploration.

        On ne redessine QUE si l'on entre dans la fouille ou si l'on en sort :
        entre les deux, le mouvement n'est que deux nombres a changer (voir
        _apply_search), appeles a chaque image du jeu."""
        avant = self._search is not None
        self._search = progress
        if (progress is not None) != avant:
            self._redraw()
        else:
            self._apply_search()

    # ---- Souffle ---------------------------------------------------------

    def _tick_breath(self, dt):
        self._breath_t += dt
        self._apply_breath()

    def _apply_breath(self):
        """Porte le souffle du moment sur les deux translations.

        Les mains et les objets recoivent LE MEME decalage : c'est ce qui fait
        qu'un objet tenu reste dans la paume au lieu d'y glisser."""
        dx, dy = breathing.offset(self._breath_t)
        ox = dx * self.height * BREATH_X
        oy = dy * self.height * BREATH_Y
        for shift in (self._shift, self._shift_items):
            if shift is not None:
                shift.x = ox
                shift.y = oy

    def _apply_search(self):
        """Porte l'alternance du moment sur les deux mains."""
        gauche, droite = searching.offset(self._search)
        for shift, val in zip(self._half_shift, (gauche, droite)):
            if shift is not None:
                shift.y = val * self.height * SEARCH_Y

    # ---- Rendu -----------------------------------------------------------

    def _redraw(self, *_):
        self.canvas.clear()
        self._shift = None
        if self.width <= 0 or self.height <= 0:
            return
        # Le souffle est une TRANSLATION posee devant tout le reste, pas une
        # position recalculee dans chaque forme. Deux raisons : les mains et
        # les objets tenus bougent forcement ENSEMBLE (un objet qui ne suivrait
        # pas la main flotterait), et une image de souffle ne coute alors que
        # deux nombres a changer -- au lieu de reconstruire tout le canvas
        # trente fois par seconde.
        with self.canvas:
            PushMatrix()
            self._shift = Translate(0, 0, 0)
        # CHAQUE MAIN EST DESSINEE A PART, toujours -- au repos comme en
        # fouille. Au repos, c'est parce que les deux mains n'ont pas la meme
        # pose (celle qui tient garde la paume ouverte, l'autre se referme) ;
        # en fouille, c'est ce qui leur permet de monter et descendre l'une
        # apres l'autre.
        for i in (0, 1):
            if self._search is not None:
                pose = SEARCH_STATE
            else:
                pose = REST_STATE if self._items[i] is not None else IDLE_STATE
            self._draw_half(i, pose)
        with self.canvas:
            PopMatrix()
        self._draw_items()
        self._apply_breath()
        self._apply_search()

    def _draw_half(self, index, state):
        """Dessine UNE main (0 = gauche, 1 = droite) dans la pose demandee.

        Chaque image contient les deux mains : on n'en prend que la moitie
        correspondante, posee a sa place a l'ecran. L'echelle ne change pas,
        seule l'autre moitie est ecartee."""
        self._half_shift[index] = None
        tex = _hud_texture(state, self._glove)
        if tex is None:
            return
        tw, th = max(1, tex.width), max(1, tex.height)
        half = tw // 2
        total_w = self.width
        total_h = total_w * th / tw
        sub = tex.get_region(index * half, 0, half, th)
        with self.canvas:
            # Translation PROPRE a cette main, imbriquee dans celle du souffle
            # (qui, elle, deplace tout ensemble). Les deux s'additionnent : la
            # main fouille ET respire en meme temps.
            PushMatrix()
            self._half_shift[index] = Translate(0, 0, 0)
            Color(1, 1, 1, 1)
            Rectangle(texture=sub,
                      pos=(self.x + index * total_w / 2, self.y),
                      size=(total_w / 2, total_h))
            PopMatrix()

    def _draw_items(self):
        """Dessine les objets tenus au-dessus du HUD."""
        self.canvas.after.clear()
        self._shift_items = None
        if self.width <= 0 or self.height <= 0:
            return
        # Les objets sont dans un AUTRE canvas (celui de devant) : il leur faut
        # donc leur propre translation. Elle recoit exactement la meme valeur
        # que celle des mains (voir _apply_breath), sans quoi un objet tenu
        # glisserait dans la paume au fil du souffle.
        with self.canvas.after:
            PushMatrix()
            self._shift_items = Translate(0, 0, 0)
        box = 0.15 * min(self.width, self.height)
        for i, name in enumerate(self._items):
            tex = _item_texture(name)
            if tex is None:
                continue
            tw, th = tex.size
            if tw >= th:
                iw, ih = box, box * th / max(1, tw)
            else:
                iw, ih = box * tw / max(1, th), box
            cx = self.x + self.HAND_FX[i] * self.width
            cy = self.y + self.height * self.ITEM_FY
            with self.canvas.after:
                Color(1, 1, 1, 1)
                Rectangle(texture=tex,
                          pos=(cx - iw / 2, cy - ih / 2),
                          size=(iw, ih))
        with self.canvas.after:
            PopMatrix()
