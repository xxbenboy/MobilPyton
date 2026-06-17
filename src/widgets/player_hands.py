"""
Mains du joueur (vue a la premiere personne).

Deux avant-bras qui remontent du bas de l'ecran vers le centre, termines par
des mains ouvertes (paume arrondie + doigts de longueurs variees + pouce).
Dessine devant le decor. Pour l'instant les mains sont VIDES.
"""
from kivy.uix.widget import Widget
from kivy.graphics import (Color, Ellipse, Quad, RoundedRectangle, Line,
                           RenderContext)

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

        # Jointure paume/doigts (ombre douce) sous les doigts.
        tex = self._skin(self.SKIN_MID)
        RoundedRectangle(pos=(hx - pw * 0.42, hy + ph * 0.55),
                         size=(pw * 0.84, ph * 0.20), radius=[ph * 0.10],
                         texture=tex)

        # 4 doigts FUSELES (base large -> pointe fine), pointe arrondie, ongle
        # et petite jointure a la base.
        fb = hy + ph * 0.62
        lengths = (0.080, 0.095, 0.088, 0.068)
        for i, fl in enumerate(lengths):
            fx = hx + (i - 1.5) * (fw + 0.004 * w)
            flh = fl * h
            tipw = fw * 0.72
            shade = self.SKIN if i % 2 == 0 else self.SKIN_MID
            tex = self._skin(shade)                       # corps du doigt (cone)
            Quad(points=[fx - fw / 2, fb, fx + fw / 2, fb,
                         fx + tipw / 2, fb + flh, fx - tipw / 2, fb + flh],
                 texture=tex)
            tex = self._skin(shade)                       # pointe arrondie
            RoundedRectangle(pos=(fx - tipw / 2, fb + flh - tipw * 0.5),
                             size=(tipw, tipw), radius=[tipw * 0.5], texture=tex)
            Color(0.96, 0.88, 0.82, 0.45)                 # ongle (reflet clair)
            Ellipse(pos=(fx - tipw * 0.26, fb + flh - tipw * 0.10),
                    size=(tipw * 0.52, tipw * 0.42))
            tex = self._skin(self.SKIN)                   # jointure (knuckle)
            RoundedRectangle(pos=(fx - fw / 2, fb - ph * 0.05),
                             size=(fw, ph * 0.18), radius=[fw * 0.5], texture=tex)

        # Pouce FUSELE (cote interieur), incline vers l'exterieur.
        tw = fw * 1.1
        twt = tw * 0.7
        tbx = hx + thumb_dir * (pw * 0.40)
        tby = hy + ph * 0.16
        tlen = 0.06 * h
        lean = thumb_dir * tlen * 0.5
        tex = self._skin(self.SKIN)
        Quad(points=[tbx - tw / 2, tby, tbx + tw / 2, tby,
                     tbx + lean + twt / 2, tby + tlen,
                     tbx + lean - twt / 2, tby + tlen], texture=tex)
        tex = self._skin(self.SKIN)
        RoundedRectangle(pos=(tbx + lean - twt / 2, tby + tlen - twt * 0.5),
                         size=(twt, twt), radius=[twt * 0.5], texture=tex)

        # Pli de la paume (ligne douce, legerement plus sombre).
        Color(self.SKIN_DK[0] * 0.8, self.SKIN_DK[1] * 0.8,
              self.SKIN_DK[2] * 0.8, 0.45)
        Line(points=[hx - pw * 0.30, hy + ph * 0.46,
                     hx + pw * 0.26, hy + ph * 0.32], width=max(1.0, pw * 0.03))
