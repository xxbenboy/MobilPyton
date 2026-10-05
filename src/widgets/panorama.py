"""
LE PANORAMA : le joueur, immobile au centre de sa case, regarde tout autour
de lui.

Le decor est un TOUR COMPLET fait de quatre panneaux, un par direction
(nord, est, sud, ouest). Chacun couvre un quart du tour, soit FOV degres sur
la largeur de l'ecran : un panneau est exactement un ecran de large. Glisser
le doigt tourne le regard (le lacet, sur 360 degres, sans fin) et leve ou
baisse la tete (le tangage, de -90 a +90 : on ne fait pas de salto).

TOURNER fait glisser les panneaux de cote ; seuls ceux qui sont a l'ecran
(un ou deux) sont attaches, les autres ne coutent rien. LEVER LA TETE fait
descendre tout le decor, et le ciel -- une sphere, voir AnimatedBackground
.set_camera -- montre son zenith ; la BAISSER le fait monter, et l'on voit
le sol a ses pieds, prolonge sous chaque panneau.

Les panneaux ne bougent jamais pour de bon : une scene se redessine des que
sa position change (des dixiemes de seconde sur un telephone). Ils sont
deplaces par une TRANSFORMATION d'affichage, gratuite.
"""
from kivy.graphics import (Color, PushMatrix, PopMatrix, Rectangle,
                           Translate)
from kivy.graphics.texture import Texture
from kivy.uix.floatlayout import FloatLayout

from src.widgets import textures

FOV = 90.0
TANGAGE_MAX = 90.0
# Hauteur du sol prolonge sous un panneau, en hauteurs d'ecran : de quoi
# baisser la tete jusqu'a regarder ses pieds.
SOL_PROLONGE = 3.0


# Le raccord scene / sol prolonge, en hauteurs d'ecran, au-dessus et
# au-dessous de la ligne, et son opacite sur la ligne.
RACCORD_DESSUS = 0.07
RACCORD_DESSOUS = 0.10
RACCORD_ALPHA = 0.85

_RAMPE = []


def _rampe():
    """Une colonne blanche, opaque en bas (RACCORD_ALPHA) et transparente
    en haut."""
    if not _RAMPE:
        n = 64
        buf = bytearray()
        for i in range(n):
            a = RACCORD_ALPHA * (1.0 - i / float(n - 1)) ** 1.6
            buf += bytes((255, 255, 255, int(a * 255)))
        tex = Texture.create(size=(1, n), colorfmt="rgba")
        tex.blit_buffer(bytes(buf), colorfmt="rgba", bufferfmt="ubyte")
        tex.wrap = "clamp_to_edge"
        _RAMPE.append(tex)
    return _RAMPE[0]


def ecart(a):
    """Un angle ramene entre -180 et 180 degres."""
    return (a + 180.0) % 360.0 - 180.0


class Plaque(FloatLayout):
    """Un panneau du tour : une scene, deplacee par une transformation, et
    le sol qui la prolonge vers le bas."""

    def __init__(self, scene, direction, **kwargs):
        super().__init__(**kwargs)
        self.scene = scene
        self.direction = direction
        with self.canvas.before:
            PushMatrix()
            self._t = Translate(0, 0, 0)
            self._sol_c = Color(1, 1, 1, 1)
            self._sol = Rectangle()
        with self.canvas.after:
            # LE RACCORD entre le bas de la scene et le sol prolonge : une
            # ombre douce, plus forte sur la ligne, qui s'efface des deux
            # cotes. Sans elle, une coupure droite traversait l'ecran.
            self._raccord_c = Color(1, 1, 1, 1)
            self._raccord_haut = Rectangle(texture=_rampe())
            self._raccord_bas = Rectangle(texture=_rampe())
            PopMatrix()
        self.add_widget(scene)
        self.bind(pos=self._sol_en_place, size=self._sol_en_place)

    def decale(self, dx, dy):
        self._t.x, self._t.y = dx, dy

    def decalage(self):
        return self._t.x, self._t.y

    def _sol_en_place(self, *_):
        self.peint_sol()

    def peint_sol(self):
        """Le sol sous la scene, de la matiere de sa zone."""
        w, h = self.width, self.height
        haut = h * SOL_PROLONGE
        nom = self.scene.texture_du_sol()
        tex = textures.base_texture(nom)
        if tex is None:
            self._sol_c.rgba = textures.fallback(nom)
            self._sol.texture = None
        else:
            # Une teinte un peu sombre : c'est le sol a l'ombre du joueur.
            self._sol_c.rgba = (0.78, 0.78, 0.78, 1)
            self._sol.texture = tex
            self._sol.tex_coords = textures.tiled_coords(
                w, haut, textures.tile_for(nom))
        self._sol.pos = (self.x, self.y - haut)
        self._sol.size = (w, haut)
        r, g, b, _a = textures.fallback(nom)
        self._raccord_c.rgba = (r * 0.8, g * 0.8, b * 0.8, 1.0)
        dessus, dessous = h * RACCORD_DESSUS, h * RACCORD_DESSOUS
        # La rampe est opaque en BAS de sa texture : le haut monte du sol
        # vers la scene en s'effacant, le bas descend en s'effacant aussi.
        self._raccord_haut.pos = (self.x, self.y)
        self._raccord_haut.size = (w, dessus)
        self._raccord_bas.pos = (self.x, self.y)
        self._raccord_bas.size = (w, -dessous)


class Panorama(FloatLayout):
    """Les quatre panneaux du tour, places selon le regard."""

    def __init__(self, scenes, **kwargs):
        super().__init__(**kwargs)
        self.lacet = 0.0
        self.tangage = 0.0
        self.plaques = [Plaque(sc, d, size_hint=(None, None))
                        for d, sc in enumerate(scenes)]
        self.bind(size=self._taille, pos=self._taille)
        self.sur_attache = None     # appele quand un panneau entre a l'ecran

    def _taille(self, *_):
        for p in self.plaques:
            p.pos = self.pos
            p.size = self.size
        self.regle()

    def ppd(self):
        return self.width / FOV

    def regle(self, lacet=None, tangage=None):
        """Place les panneaux pour ce regard (degres)."""
        if lacet is not None:
            self.lacet = lacet % 360.0
        if tangage is not None:
            self.tangage = max(-TANGAGE_MAX, min(TANGAGE_MAX, tangage))
        if self.width <= 0:
            return
        ppd = self.ppd()
        dy = -self.tangage * ppd
        for p in self.plaques:
            dx = ecart(p.direction * FOV - self.lacet) * ppd
            p.decale(dx, dy)
            visible = abs(dx) < self.width
            if visible and p.parent is None:
                self.add_widget(p)
                if self.sur_attache is not None:
                    self.sur_attache(p)
            elif not visible and p.parent is not None:
                self.remove_widget(p)

    def visibles(self):
        return [p for p in self.plaques if p.parent is not None]

    def plaque(self, direction):
        return self.plaques[direction % 4]

    def vers_monde(self, direction, x, y):
        """Un point de la scene du panneau `direction`, la ou il tombe a
        l'ecran (avant toute autre transformation), ou None s'il n'est pas a
        l'ecran."""
        p = self.plaques[direction % 4]
        if p.parent is None:
            return None
        dx, dy = p.decalage()
        return x + dx, y + dy

    def direction_vue(self):
        """La direction cardinale la plus proche du regard (0 a 3)."""
        return int(round(self.lacet / FOV)) % 4


__all__ = ["Panorama", "Plaque", "FOV", "TANGAGE_MAX", "ecart"]
