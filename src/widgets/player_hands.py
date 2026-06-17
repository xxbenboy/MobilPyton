"""
Mains du joueur (vue a la premiere personne).

Deux avant-bras qui remontent du bas de l'ecran vers le centre, termines par
des mains ouvertes (paume arrondie + doigts de longueurs variees + pouce).
Dessine devant le decor. Pour l'instant les mains sont VIDES.
"""
from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse, Quad, RoundedRectangle, RenderContext

from src.widgets import textures, pbr


class PlayerHands(Widget):
    SKIN = (0.84, 0.66, 0.50, 1)
    SKIN_MID = (0.76, 0.58, 0.43, 1)
    SKIN_DK = (0.64, 0.48, 0.35, 1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._pbr = pbr.LIGHTING and textures.has_any_normal()
        if self._pbr:
            self.canvas = RenderContext(use_parent_projection=True,
                                        use_parent_modelview=True,
                                        use_parent_frag_modelview=True)
            pbr.setup(self.canvas)
        self.bind(pos=self._redraw, size=self._redraw)

    def _skin(self, shade):
        """Pose la couleur de la peau et renvoie la BaseColor "skin" (ou None).

        S'il y a une BaseColor, on la TEINTE selon la nuance demandee (clair /
        moyen / sombre) pour garder le volume des mains ; sinon couleur plane."""
        tex = textures.base_texture("skin")
        if tex is None:
            Color(*shade)
        else:
            base = self.SKIN
            Color(shade[0] / base[0], shade[1] / base[1], shade[2] / base[2],
                  shade[3])
        return tex

    def _redraw(self, *_):
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return
        with self.canvas:
            if self._pbr:                        # relief de la peau (si dispo)
                pbr.bind_maps(textures.normal_texture("skin"),
                              textures.packed_texture("skin"))
            # Avant-bras quasi verticaux (paralleles), ecartes et plus bas.
            self._arm(0.30, 0.31, 0.12, +1)      # bras / main gauche
            self._arm(0.70, 0.69, 0.12, -1)      # bras / main droite

    def _arm(self, base_fx, hand_fx, hand_fy, thumb_dir):
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        bx = x0 + base_fx * w
        hx = x0 + hand_fx * w
        hy = y0 + hand_fy * h
        armw = 0.065 * w
        wristw = 0.045 * w

        # Avant-bras : cote sombre (volume) puis dessus clair, qui s'affine
        # vers le poignet.
        tex = self._skin(self.SKIN_DK)
        Quad(points=[bx - armw, y0, bx + armw, y0,
                     hx + wristw, hy, hx - wristw, hy], texture=tex)
        tex = self._skin(self.SKIN)
        Quad(points=[bx - armw * 0.62, y0, bx + armw * 0.78, y0,
                     hx + wristw * 0.7, hy - 0.004 * h,
                     hx - wristw * 0.55, hy - 0.004 * h], texture=tex)

        pw = 0.125 * w        # largeur paume
        ph = 0.085 * h        # hauteur paume
        fw = 0.026 * w        # largeur d'un doigt

        # Ombre de la paume (bas), puis paume claire.
        tex = self._skin(self.SKIN_DK)
        RoundedRectangle(pos=(hx - pw / 2, hy - 0.012 * h),
                         size=(pw, ph * 0.55), radius=[pw * 0.3], texture=tex)
        tex = self._skin(self.SKIN)
        RoundedRectangle(pos=(hx - pw / 2, hy), size=(pw, ph),
                         radius=[pw * 0.32], texture=tex)

        # 4 doigts, longueurs variees (index, majeur, annulaire, auriculaire),
        # legerement en eventail.
        lengths = (0.080, 0.095, 0.088, 0.068)
        for i, fl in enumerate(lengths):
            fx = hx + (i - 1.5) * (fw + 0.004 * w)
            tex = self._skin(self.SKIN if i % 2 == 0 else self.SKIN_MID)
            RoundedRectangle(pos=(fx - fw / 2, hy + ph * 0.62),
                             size=(fw, fl * h), radius=[fw * 0.5], texture=tex)

        # Pouce (cote interieur, plus court et un peu plus bas).
        tex = self._skin(self.SKIN)
        tw = fw * 1.05
        RoundedRectangle(pos=(hx + thumb_dir * (pw * 0.42) - tw / 2,
                              hy + ph * 0.2),
                         size=(tw, 0.05 * h), radius=[tw * 0.5], texture=tex)
        # Petite ombre sous les doigts (jointure paume).
        tex = self._skin(self.SKIN_MID)
        RoundedRectangle(pos=(hx - pw * 0.42, hy + ph * 0.55),
                         size=(pw * 0.84, ph * 0.18), radius=[ph * 0.09],
                         texture=tex)
