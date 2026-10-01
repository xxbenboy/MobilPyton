"""
LE BOIS ET LA PIERRE DES MENUS DU CRAFT : des objets du monde plutot que des
panneaux d'interface.

- `plaque(widget)` pose sous un widget une PLANCHETTE GRAVEE (decoupee en
  neuf : ses coins et son cadre ne s'etirent pas, seul le milieu grandit) ;
- `BoutonGalet` est un bouton en forme de GALET, le texte grave dessus ; il
  s'assombrit et s'enfonce un peu sous le doigt.

Les images sont dans assets/craft/ (voir sol_de_craft.texture_craft). Sans
elles, la planchette retombe sur le panneau sombre habituel.
"""
from kivy.graphics import BorderImage, Color, Rectangle
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.label import Label

from src.widgets.panels import panel
from src.widgets.sol_de_craft import DOSSIER_CRAFT, texture_craft

import os

PLANCHETTE = os.path.join(DOSSIER_CRAFT, "planchette.png")
# Le cadre de la planchette, en pixels de l'image : il ne s'etire pas.
BORD_PLANCHETTE = 56
# Les textes poses sur le bois : creme, et un titre plus chaud.
TEXTE_BOIS = (0.97, 0.92, 0.80, 1)
TITRE_BOIS = (1.00, 0.84, 0.50, 1)
# Le texte grave sur le galet.
TEXTE_GALET = (0.16, 0.15, 0.14, 1)
# Le galet garde ses proportions (480 x 180).
RAPPORT_GALET = 480.0 / 180.0


def plaque(widget, echelle_bord=0.55):
    """Une planchette gravee sous `widget`, qui le suit."""
    if not os.path.isfile(PLANCHETTE):
        return panel(widget, alpha=0.82)
    b = BORD_PLANCHETTE
    with widget.canvas.before:
        Color(1, 1, 1, 1)
        img = BorderImage(source=PLANCHETTE, border=(b, b, b, b),
                          display_border=(b * echelle_bord,) * 4)

    def _sync(w, *_):
        img.pos = w.pos
        img.size = w.size
    widget.bind(pos=_sync, size=_sync)
    _sync(widget)
    return widget


class BoutonGalet(ButtonBehavior, Label):
    """Un bouton galet : l'image du galet, le texte grave dessus."""

    def __init__(self, **kwargs):
        kwargs.setdefault("color", TEXTE_GALET)
        kwargs.setdefault("bold", True)
        super().__init__(**kwargs)
        with self.canvas.before:
            self._teinte = Color(1, 1, 1, 1)
            self._galet = Rectangle(texture=texture_craft("galet"))
        self.bind(pos=self._place, size=self._place, state=self._place)
        self._place()

    def _place(self, *_):
        enfonce = getattr(self, "state", "normal") == "down"
        nom = "galet_appuye" if enfonce else "galet"
        self._galet.texture = texture_craft(nom)
        # Le galet tient dans le bouton sans se deformer, et rapetisse un
        # peu quand on l'enfonce.
        w, h = self.width, self.height
        if w / max(1.0, h) > RAPPORT_GALET:
            gw, gh = h * RAPPORT_GALET, h
        else:
            gw, gh = w, w / RAPPORT_GALET
        if enfonce:
            gw, gh = gw * 0.96, gh * 0.96
        self._galet.size = (gw, gh)
        self._galet.pos = (self.x + (w - gw) / 2.0, self.y + (h - gh) / 2.0)
        self.font_size = max(10.0, min(gh * 0.36,
                                       gw * 0.8 / max(1, len(self.text))
                                       / 0.55))


__all__ = ["plaque", "BoutonGalet", "TEXTE_BOIS", "TITRE_BOIS"]
