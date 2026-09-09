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

PENDANT UNE ACTION (exploration...), l'animation prend le dessus et montre
les deux mains ensemble, quel que soit ce qu'elles tiennent.

Les objets tenus (set_items) sont dessines AU-DESSUS du HUD, aux
positions correspondant aux mains dans l'image (HAND_FX / ITEM_FY).
"""
import os

from kivy.uix.widget import Widget
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Rectangle

from src import items

_HERE = os.path.dirname(os.path.abspath(__file__))
CHARACTER_DIR = os.path.abspath(os.path.join(_HERE, "..", "..", "assets",
                                             "Character"))

# Fichier image par ETAT du joueur. L'image est un HUD PLEIN ECRAN
# (taille de reference : 2340 x 1080 pour un telephone portrait) avec
# les mains deja positionnees en bas. Le HUD est etire pour remplir
# la totalite du widget.
HUD_IMAGES = {
    'haut': 'HandHUD.png',     # paume ouverte : une main qui TIENT un objet
    'idle': 'HandIdle.png',    # main VIDE, au repos
    'ex1': 'HandEx1.png',      # exploration : phases 1 et 3 (debut et fin)
    'ex2': 'HandEx2.png',      # exploration : phase 2 (milieu)
}

# Etat de REPOS : le joueur ne fait rien de particulier. Les autres etats sont
# des animations d'action.
REST_STATE = 'haut'
# Pose d'une main vide au repos.
IDLE_STATE = 'idle'

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
    regle : seules les poses de REPOS ont une variante gantee. Les images
    d'exploration n'en ont pas -- les gants disparaissent donc le temps de
    l'animation, ce qui vaut mieux qu'une main manquante."""
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
        self._state = 'haut'             # etat par defaut
        self._glove = None               # gants portes (voir set_glove)
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

    def set_state(self, state):
        """Change l'etat des mains (voir HUD_IMAGES). Redessine."""
        if state == self._state:
            return
        self._state = state
        self._redraw()

    # ---- Rendu -----------------------------------------------------------

    def _redraw(self, *_):
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return
        if self._state != REST_STATE:
            # ANIMATION (exploration...) : les deux mains sont en action, on
            # pose l'image entiere sans se soucier de ce qu'elles tiennent.
            tex = _hud_texture(self._state, self._glove)
            if tex is not None:
                tw, th = max(1, tex.width), max(1, tex.height)
                with self.canvas:
                    Color(1, 1, 1, 1)
                    Rectangle(texture=tex, pos=self.pos,
                              size=(self.width, self.width * th / tw))
        else:
            # AU REPOS, chaque main a SA pose. Une main vide n'etait pas
            # dessinee du tout : le joueur ne voyait ses mains qu'en portant
            # quelque chose. Elle prend maintenant la pose de repos.
            # La main qui TIENT garde la paume ouverte : c'est dans ce creux
            # que l'objet est pose (voir HAND_FX / ITEM_FY), et il flotterait
            # sur des doigts refermes.
            for i in (0, 1):
                self._draw_half(i, REST_STATE if self._items[i] is not None
                                else IDLE_STATE)
        self._draw_items()

    def _draw_half(self, index, state):
        """Dessine UNE main (0 = gauche, 1 = droite) dans la pose demandee.

        Chaque image contient les deux mains : on n'en prend que la moitie
        correspondante, posee a sa place a l'ecran. L'echelle ne change pas,
        seule l'autre moitie est ecartee."""
        tex = _hud_texture(state, self._glove)
        if tex is None:
            return
        tw, th = max(1, tex.width), max(1, tex.height)
        half = tw // 2
        total_w = self.width
        total_h = total_w * th / tw
        sub = tex.get_region(index * half, 0, half, th)
        with self.canvas:
            Color(1, 1, 1, 1)
            Rectangle(texture=sub,
                      pos=(self.x + index * total_w / 2, self.y),
                      size=(total_w / 2, total_h))

    def _draw_items(self):
        """Dessine les objets tenus au-dessus du HUD."""
        self.canvas.after.clear()
        if self.width <= 0 or self.height <= 0:
            return
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
