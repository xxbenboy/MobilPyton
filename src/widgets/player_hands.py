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
    'haut': 'HandHUD.png',     # par defaut (paumes vers le haut)
    'ex1': 'HandEx1.png',      # exploration : phases 1 et 3 (debut et fin)
    'ex2': 'HandEx2.png',      # exploration : phase 2 (milieu)
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
    ITEM_FY = 0.225

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._items = [None, None]      # objets tenus : [gauche, droite]
        self._state = 'haut'             # etat par defaut
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
            # En etat 'haut' (repos), on n'affiche QUE les mains qui
            # tiennent un objet (les mains vides sont cachees).
            # Dans tout autre etat (= animation, ex. 'ex1'/'ex2'), on
            # dessine TOUJOURS les 2 mains (l'animation montre les mains
            # en action, independamment des objets).
            animating = self._state != 'haut'
            if animating:
                show_left, show_right = True, True
            else:
                show_left = self._items[0] is not None
                show_right = self._items[1] is not None

            if show_left or show_right:
                tw, th = max(1, tex.width), max(1, tex.height)
                total_w = self.width
                total_h = total_w * th / tw
                with self.canvas:
                    Color(1, 1, 1, 1)
                    if show_left and show_right:
                        # 2 mains : on dessine l'image entiere.
                        Rectangle(texture=tex, pos=self.pos,
                                  size=(total_w, total_h))
                    else:
                        # Une seule main : on dessine LA MOITIE
                        # correspondante au bon endroit a l'ecran
                        # (gauche ou droite). Le HUD reste a la meme
                        # echelle, juste la moitie est masquee.
                        half_tw = tw // 2
                        if show_left:
                            sub = tex.get_region(0, 0, half_tw, th)
                            Rectangle(texture=sub, pos=self.pos,
                                      size=(total_w / 2, total_h))
                        else:
                            sub = tex.get_region(half_tw, 0, half_tw, th)
                            Rectangle(texture=sub,
                                      pos=(self.x + total_w / 2, self.y),
                                      size=(total_w / 2, total_h))
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
