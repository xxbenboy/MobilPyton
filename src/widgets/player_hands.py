"""
Mains du joueur (vue 1re personne).

APPROCHE SIMPLE : UNE SEULE IMAGE par etat du joueur. L'image contient
les 2 mains (gauche + droite) en un seul fichier, affichee au bas de
l'ecran. On peut definir plusieurs etats (paumes vers le haut, main qui
tient un outil, etc.) ; pour l'instant un seul etat : 'haut'.

L'image va dans `assets/Character/<nom>.png`, le nom etant donne par
le dictionnaire HAND_IMAGES ci-dessous.

Les objets tenus (set_items) sont dessines au-dessus de l'image, dans
le creux de la paume correspondante.
"""
import os

from kivy.uix.widget import Widget
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Rectangle

from src import items

_HERE = os.path.dirname(os.path.abspath(__file__))
CHARACTER_DIR = os.path.abspath(os.path.join(_HERE, "..", "..", "assets",
                                             "Character"))

# Fichier image par ETAT du joueur. Etat 'haut' = paumes vers le haut.
# (D'autres etats peuvent etre ajoutes plus tard : 'craft', 'grip', etc.)
HAND_IMAGES = {
    'haut': 'mains_haut.png',
}

# Hauteur de l'image en fraction de la hauteur du widget.
HAND_HEIGHT_FRAC = 0.30

_TEX_CACHE = {}
_ITEM_TEX = {}


def _hand_texture(state):
    """Charge (ou recupere en cache) l'image de mains pour un etat."""
    fname = HAND_IMAGES.get(state)
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
    # x du centre de chaque main (gauche, droite) en fraction de la largeur.
    # Sert UNIQUEMENT a positionner les objets tenus.
    HAND_FX = (0.31, 0.69)
    # y des objets tenus, en fraction de la hauteur du widget (depuis le bas).
    ITEM_FY = 0.20

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
        """Change l'etat des mains (voir HAND_IMAGES). Redessine."""
        if state == self._state:
            return
        self._state = state
        self._redraw()

    # ---- Rendu -----------------------------------------------------------

    def _redraw(self, *_):
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return
        tex = _hand_texture(self._state)
        if tex is not None:
            # Image affichee centree horizontalement, alignee en bas.
            target_h = self.height * HAND_HEIGHT_FRAC
            target_w = target_h * (tex.width / max(1, tex.height))
            x = self.x + (self.width - target_w) / 2
            y = self.y
            with self.canvas:
                Color(1, 1, 1, 1)
                Rectangle(texture=tex, pos=(x, y), size=(target_w, target_h))
        self._draw_items()

    def _draw_items(self):
        """Dessine les objets tenus au-dessus des mains."""
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
