"""
Mains du joueur (vue 1re personne) - APPROCHE HUD plein ecran.

UNE SEULE IMAGE par etat du joueur : un HUD plein ecran dans lequel les
mains sont deja positionnees au bon endroit (en bas). Le HUD est dessine
sur toute la surface du widget (== plein ecran).

Plusieurs etats possibles via HUD_IMAGES (par ex. paumes vers le haut,
main qui tient un outil, etc.) ; pour l'instant un seul etat : 'haut'.

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
    'haut': 'HandHUD.png',
}

_TEX_CACHE = {}
_ITEM_TEX = {}


def _hud_texture(state):
    """Charge (ou recupere en cache) le HUD pour un etat donne."""
    fname = HUD_IMAGES.get(state)
    if not fname:
        return None
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
    ITEM_FY = 0.185

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._items = [None, None]      # objets tenus : [gauche, droite]
        self._state = 'haut'             # etat par defaut
        self.bind(pos=self._redraw, size=self._redraw)

    # ---- API publique ----------------------------------------------------

    def set_items(self, left, right):
        """Definit les objets tenus (None = main vide)."""
        new = [left, right]
        if new == self._items:
            return
        self._items = new
        self._draw_items()

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
        tex = _hud_texture(self._state)
        if tex is not None:
            # HUD : on PRESERVE l'aspect ratio de l'image (sinon les mains
            # se deforment quand l'image est landscape et l'ecran portrait).
            # Largeur = celle du widget, hauteur derivee, aligne en bas.
            tw, th = max(1, tex.width), max(1, tex.height)
            target_w = self.width
            target_h = target_w * th / tw
            x = self.x
            y = self.y
            with self.canvas:
                Color(1, 1, 1, 1)
                Rectangle(texture=tex, pos=(x, y), size=(target_w, target_h))
        self._draw_items()

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
