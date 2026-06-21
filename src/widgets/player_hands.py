"""
Mains du joueur (vue a la premiere personne), PAUMES VERS LE HAUT.

Structure du code, partie par partie (chaque element a sa propre methode) :

    _bras_l / _bras_r           avant-bras (cote gauche / droit)
        _main(side)             paume + 4 doigts + pouce
            _paume              compose la paume a partir de ses pieces :
                _paume1         section base (cote poignet, bande sombre)
                _paume2         section milieu (corps clair principal)
                _paume3         section haut (coussinets metacarpiens)
                _thenar         monticule charnu cote pouce
                _hypothenar     monticule charnu cote auriculaire
                _lignes_paume   3 plis : coeur / tete / vie
            _doigt1 (...)       phalange PROXIMALE d'un doigt (base)
            _doigt2 (...)       phalange MOYENNE
            _doigt3 (...)       phalange DISTALE (bout avec pulpe)
            _pouce_segment(num) une phalange du pouce
                                num = 1 (proximale) ou 2 (distale)

REUTILISATION DES "IMAGES" :
- _doigt1 / _doigt2 / _doigt3 sont les 3 phalanges d'UN doigt et sont
  reutilisees a l'identique pour les 4 doigts de chaque main (8 doigts).
  Seule la LONGUEUR TOTALE de chaque doigt change.
- _paume1 / _paume2 / _paume3 et _thenar / _hypothenar / _lignes_paume
  sont les pieces de LA PAUME, reutilisees a l'identique pour les 2 mains.
  Seul le cote du pouce (et donc du thenar/hypothenar et de la ligne de
  vie) change selon la main.

ORIENTATION :
- Paumes vers le HAUT (vue de la paume, pas du dos de la main).
- Les pouces pointent VERS L'EXTERIEUR de l'ecran (loin du centre) :
  main gauche -> pouce a gauche ; main droite -> pouce a droite.
- L'auriculaire (le plus court) est place du cote OPPOSE au pouce.

Si le joueur tient un objet, l'image (assets/items/<nom>.png) est dessinee
au creux de la main correspondante (via `set_items`).
"""
import os

from kivy.uix.widget import Widget
from kivy.core.image import Image as CoreImage
from kivy.graphics import (Color, Ellipse, Quad, Rectangle, RoundedRectangle,
                           Line, RenderContext)

from src import items
from src.widgets import textures, pbr

_ITEM_TEX = {}

# ---- Images de personnage (assets/Character/<nom>.png) --------------------
# Les images de la MAIN GAUCHE sont positionnees a GAUCHE de leur canvas
# (le reste est transparent). Pour la main droite, on FLIP horizontalement.
# Chaque image est facultative : si elle manque, on retombe sur le dessin
# canvas par defaut.

_HERE = os.path.dirname(os.path.abspath(__file__))
CHARACTER_DIR = os.path.abspath(os.path.join(_HERE, "..", "..", "assets",
                                             "Character"))
_CHAR_TEX = {}

# Multiplicateurs pour la TAILLE des images a l'ecran (ajustables a vue).
# Tout est exprime en multiple de la dimension "naturelle" anatomique.

# MAITRE : echelle globale de toute la main+bras. 1.0 = taille de reference,
# < 1 = plus petit. Pratique pour reduire ou agrandir d'un coup tout le
# rendu sans toucher aux proportions internes.
HAND_SCALE = 0.65

HAND_H_MULT = 2.0             # hauteur image / hauteur paume (ph)
HAND_OFFSET_Y = 0.0           # decalage vertical centre bbox (en x ph)
FOREARM_H_MULT = 1.0          # hauteur image / hauteur forearm (hy - y0)

# Taille des doigts et pouces (1.0 = doigt anatomique). 1.2 = doigt aussi
# long que la paume (comme une vraie main, voir image de reference).
DOIGT_SIZE = 1.2
POUCE_SIZE = 1.2


def _char_texture(name):
    """Charge une image personnage + sa BBOX alpha (zone visible).

    Renvoie (texture, meta) ou (None, None). meta = (u_left, v_bottom,
    u_right, v_top, aspect_ratio) ou les uv decoupent automatiquement la
    zone transparente autour de l'artwork. L'artwork peut donc etre
    positionne n'importe ou dans le canvas : le code retrouve la zone utile.
    """
    if name in _CHAR_TEX:
        return _CHAR_TEX[name]
    result = (None, None)
    for ext in (".png", ".jpg", ".jpeg"):
        p = os.path.join(CHARACTER_DIR, name + ext)
        if not os.path.isfile(p):
            continue
        try:
            from PIL import Image as PILImage
            pil = PILImage.open(p)
            if pil.mode != 'RGBA':
                pil = pil.convert('RGBA')
            cw, ch = pil.size
            bbox = pil.split()[-1].getbbox()
            if bbox is None:
                bbox = (0, 0, cw, ch)
            left, top, right, bottom = bbox
            u_left = left / cw
            u_right = right / cw
            v_top = 1.0 - top / ch
            v_bottom = 1.0 - bottom / ch
            aspect = (right - left) / max(1, bottom - top)
            tex = CoreImage(p).texture
            result = (tex, (u_left, v_bottom, u_right, v_top, aspect))
        except Exception:
            result = (None, None)
        break
    _CHAR_TEX[name] = result
    return result


def _draw_char_image(tex_data, cx, cy, target_h, flip_h, target_w=None):
    """Dessine l'ARTWORK (cropped au bbox alpha) centre sur (cx, cy), avec
    une hauteur target_h. La largeur suit le ratio aspect de l'artwork
    PAR DEFAUT ; passe target_w pour forcer une largeur (l'image est alors
    etiree). flip_h=True mirroirise horizontalement (main droite).

    Important : on passe par texture.get_region() pour extraire le bout de
    texture correspondant au bbox. Kivy a un bug : tex_coords passe en
    kwarg du Rectangle est ECRASE par les uv du texture. Avec get_region,
    on cree une sous-texture independante qui s'affiche normalement.
    """
    tex, meta = tex_data
    if tex is None:
        return
    u_left, v_bottom, u_right, v_top, aspect = meta
    if target_w is None:
        target_w = target_h * aspect
    # Sous-texture cropee au bbox alpha (la sous-texture porte ses propres
    # tex_coords correctes, donc le rendu est natif et fiable).
    tw, th = tex.size
    rx = u_left * tw
    ry = v_bottom * th       # bbox bottom en Kivy y (0 = bas)
    rw = (u_right - u_left) * tw
    rh = (v_top - v_bottom) * th
    sub = tex.get_region(rx, ry, rw, rh)
    # Flip horizontal pour la main droite : flip_horizontal() de Kivy
    # echange les uv proprement (au niveau de la sous-texture).
    if flip_h:
        sub.flip_horizontal()
    Color(1, 1, 1, 1)
    Rectangle(texture=sub,
              pos=(cx - target_w / 2, cy - target_h / 2),
              size=(target_w, target_h))


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
    SKIN = (0.84, 0.66, 0.50, 1)
    SKIN_MID = (0.76, 0.58, 0.43, 1)
    SKIN_DK = (0.64, 0.48, 0.35, 1)

    # Geometrie d'un bras+main.
    # CONVENTION : toutes les TAILLES et tous les Y sont en fractions de
    # `scale = min(width, height)` (=> proportions FIXES entre les pieces,
    # peu importe l'aspect de la fenetre). Seuls les X (HAND_FX, ARM_BASE_FX)
    # restent en fraction de `width` pour que les mains restent ancrees
    # aux coins gauche et droit de l'ecran.
    HAND_FX = (0.31, 0.69)              # x centre de chaque main / width
    ARM_BASE_FX = (0.30, 0.70)          # x base du bras / width
    ARM_HAND_FY = 0.26                   # y du poignet / scale
    ARM_BASE_W = 0.065                  # demi-largeur base du bras / scale
    WRIST_W = 0.045                     # demi-largeur poignet / scale
    PALM_W = 0.125                      # largeur paume / scale
    PALM_H = 0.184                      # hauteur paume / scale
    FINGER_W = 0.026                    # largeur d'un doigt / scale
    # Longueurs des doigts (index, majeur, annulaire, auriculaire) / scale.
    FINGER_LENGTHS = (0.173, 0.206, 0.191, 0.147)
    # Longueur totale du pouce (2 phalanges) / scale.
    THUMB_LEN = 0.152

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._pbr = pbr.LIGHTING and textures.has_any_normal()
        if self._pbr:
            self.canvas = RenderContext(use_parent_projection=True,
                                        use_parent_modelview=True,
                                        use_parent_frag_modelview=True)
            pbr.setup(self.canvas)
        self._items = [None, None]      # objets tenus : [gauche, droite]
        self.bind(pos=self._redraw, size=self._redraw)

    # ====================================================================== #
    # API
    # ====================================================================== #

    def set_items(self, left, right):
        """Definit les objets tenus (None = main vide)."""
        new = [left, right]
        if new == self._items:
            return
        self._items = new
        self._draw_items()

    # ====================================================================== #
    # Helpers
    # ====================================================================== #

    def _skin(self, shade):
        """Pose la couleur de peau et renvoie la BaseColor (ou None).

        Teinte la texture pour rester proche de la nuance demandee."""
        tex = textures.base_texture("skin")
        if tex is None:
            Color(*shade)
        else:
            base = self.SKIN
            Color(shade[0] / base[0], shade[1] / base[1], shade[2] / base[2],
                  shade[3])
        return tex

    @staticmethod
    def _thumb_dir(side):
        """Direction OUTWARD du pouce : +1 pour main droite, -1 pour gauche."""
        return +1 if side == 'R' else -1

    def _scale_ref(self):
        """Reference de dimensionnement = min(width, height) * HAND_SCALE.

        Toutes les tailles et tous les Y du dessin de la main utilisent
        cette reference => les pieces gardent leurs positions relatives
        constantes peu importe l'aspect (proportions) de la fenetre.
        HAND_SCALE permet de reduire/agrandir la main en bloc.
        """
        return min(self.width, self.height) * HAND_SCALE

    def _draw_items(self):
        """Dessine l'image des objets tenus dans les mains (canvas.after)."""
        self.canvas.after.clear()
        if self.width <= 0 or self.height <= 0:
            return
        w, x0, y0 = self.width, self.x, self.y
        scale = self._scale_ref()
        box = 0.17 * scale                  # taille de l'objet tenu / scale
        for i, name in enumerate(self._items):
            tex = _item_texture(name)
            if tex is None:
                continue
            tw, th = tex.size
            if tw >= th:
                iw, ih = box, box * th / max(1, tw)
            else:
                iw, ih = box * tw / max(1, th), box
            cx = x0 + self.HAND_FX[i] * w   # X = fraction de width
            cy = y0 + 0.45 * scale          # Y = fraction de scale
            with self.canvas.after:
                Color(1, 1, 1, 1)
                Rectangle(texture=tex, pos=(cx - iw / 2, cy - ih / 2),
                          size=(iw, ih))

    # ====================================================================== #
    # Dessin : top-level
    # ====================================================================== #

    def _redraw(self, *_):
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return
        with self.canvas:
            if self._pbr:
                pbr.bind_maps(textures.normal_texture("skin"),
                              textures.packed_texture("skin"))
            self._bras_l()
            self._bras_r()
        self._draw_items()

    # ----- BRAS (avant-bras + main) -------------------------------------- #

    def _bras_l(self):
        """Avant-bras GAUCHE + main gauche."""
        self._dessiner_bras(self.ARM_BASE_FX[0], self.HAND_FX[0], 'L')

    def _bras_r(self):
        """Avant-bras DROIT + main droite."""
        self._dessiner_bras(self.ARM_BASE_FX[1], self.HAND_FX[1], 'R')

    def _dessiner_bras(self, base_fx, hand_fx, side):
        w, x0, y0 = self.width, self.x, self.y
        scale = self._scale_ref()
        bx = x0 + base_fx * w               # X = fraction de width
        hx = x0 + hand_fx * w               # X = fraction de width
        hy = y0 + self.ARM_HAND_FY * scale  # Y / sizes = fraction de scale
        armw = self.ARM_BASE_W * scale
        wristw = self.WRIST_W * scale

        # Image avant_hand.png si dispo, sinon Quads canvas.
        # L'image (juste le bout du poignet) est positionnee avec son
        # HAUT a la hauteur du poignet (hy).
        tex_data = _char_texture("avant_hand")
        if tex_data[0] is not None:
            forearm_h = (hy - y0) * FOREARM_H_MULT
            cy = hy - forearm_h / 2          # haut de l'image au poignet
            _draw_char_image(tex_data, hx, cy, forearm_h,
                             flip_h=(side == 'R'))
        else:
            # Cote sombre (volume) puis dessus clair vers le poignet.
            tex = self._skin(self.SKIN_DK)
            Quad(points=[bx - armw, y0, bx + armw, y0,
                         hx + wristw, hy, hx - wristw, hy], texture=tex)
            tex = self._skin(self.SKIN)
            Quad(points=[bx - armw * 0.62, y0, bx + armw * 0.78, y0,
                         hx + wristw * 0.7, hy - 0.004 * scale,
                         hx - wristw * 0.55, hy - 0.004 * scale], texture=tex)

        self._main(hx, hy, side)

    # ----- MAIN ---------------------------------------------------------- #

    def _main(self, hx, hy, side):
        """Paume + 4 doigts (chacun = doigt1+doigt2+doigt3) + pouce."""
        scale = self._scale_ref()
        pw = self.PALM_W * scale
        ph = self.PALM_H * scale
        fw = self.FINGER_W * scale
        thumb_dir = self._thumb_dir(side)

        self._paume(hx, hy, pw, ph, side)

        # 4 DOIGTS : meme jeu de phalanges (_doigt1/_doigt2/_doigt3), seule
        # la LONGUEUR TOTALE change. Ordre anatomique : index, majeur,
        # annulaire, auriculaire. L'auriculaire (le plus court) doit etre
        # du cote OPPOSE au pouce.
        lengths = self.FINGER_LENGTHS
        if thumb_dir > 0:                          # main droite : on inverse
            lengths = lengths[::-1]                # pour que l'auriculaire
                                                   # soit a gauche
        spacing = fw + 0.004 * scale
        # Les doigts attachent legerement DANS la paume (base_y < top palm)
        # pour qu'ils paraissent connectes au lieu de flotter au-dessus.
        if _char_texture("hand")[0] is not None:
            base_y = hy + ph * 0.85            # 15% dans la paume image
        else:
            base_y = hy + ph * 0.62            # interieur paume canvas
        for i, fl in enumerate(lengths):
            fx = hx + (i - 1.5) * spacing
            total_len = fl * scale
            cy = base_y
            cy = self._doigt1(fx, cy, fw, total_len, side)
            cy = self._doigt2(fx, cy, fw, total_len, side)
            self._doigt3(fx, cy, fw, total_len, side)

        # POUCE : 2 phalanges (proximale puis distale), toujours dessinees.
        self._pouce_segment(1, hx, hy, pw, ph, fw, side)
        self._pouce_segment(2, hx, hy, pw, ph, fw, side)

    # ----- PAUME : 3 sections + 2 muscles + 3 lignes --------------------- #
    #
    # Meme logique que les doigts : chaque piece est dessinee par sa propre
    # methode et reutilisee a l'identique pour les deux mains. Seul le cote
    # du pouce (thenar / hypothenar / ligne de vie) bascule selon la main.

    def _paume(self, hx, hy, pw, ph, side):
        """Compose la paume.

        Si une image hand.png existe (assets/Character/), on l'utilise telle
        quelle. Sinon : composition canvas (3 sections + muscles + lignes).
        """
        tex_data = _char_texture("hand")
        if tex_data[0] is not None:
            target_h = ph * HAND_H_MULT
            cy = hy + ph * HAND_OFFSET_Y
            _draw_char_image(tex_data, hx, cy, target_h,
                             flip_h=(side == 'R'))
            return
        # Fallback canvas : corps + muscles + lignes.
        self._paume1(hx, hy, pw, ph)
        self._paume2(hx, hy, pw, ph)
        self._paume3(hx, hy, pw, ph)
        self._thenar(hx, hy, pw, ph, side)
        self._hypothenar(hx, hy, pw, ph, side)
        self._lignes_paume(hx, hy, pw, ph, side)

    def _paume1(self, hx, hy, pw, ph):
        """SECTION 1 : base de la paume (cote poignet). Bande sombre arrondie
        sous le corps qui forme l'ombre du talon de la main."""
        tex = self._skin(self.SKIN_DK)
        RoundedRectangle(pos=(hx - pw / 2, hy - 0.026 * self._scale_ref()),
                         size=(pw, ph * 0.55), radius=[pw * 0.30],
                         texture=tex)

    def _paume2(self, hx, hy, pw, ph):
        """SECTION 2 : corps clair principal de la paume (rectangle arrondi
        qui occupe presque toute la surface visible)."""
        tex = self._skin(self.SKIN)
        RoundedRectangle(pos=(hx - pw / 2, hy), size=(pw, ph),
                         radius=[pw * 0.32], texture=tex)

    def _paume3(self, hx, hy, pw, ph):
        """SECTION 3 : haut de la paume, sous les doigts. Bombement charnu
        des coussinets metacarpiens."""
        tex = self._skin(self.SKIN)
        RoundedRectangle(pos=(hx - pw * 0.42, hy + ph * 0.55),
                         size=(pw * 0.84, ph * 0.22), radius=[ph * 0.11],
                         texture=tex)

    def _thenar(self, hx, hy, pw, ph, side):
        """Monticule charnu COTE POUCE : le plus marque des deux muscles
        lateraux de la paume."""
        thumb_dir = self._thumb_dir(side)
        tex = self._skin(self.SKIN)
        tnw = pw * 0.36
        tnh = ph * 0.55
        tnx = hx + thumb_dir * (pw * 0.32) - tnw / 2
        tny = hy + ph * 0.05
        RoundedRectangle(pos=(tnx, tny), size=(tnw, tnh),
                         radius=[tnw * 0.5], texture=tex)

    def _hypothenar(self, hx, hy, pw, ph, side):
        """Monticule charnu COTE AURICULAIRE (oppose au pouce) : plus petit
        et moins prononce que le thenar."""
        thumb_dir = self._thumb_dir(side)
        tex = self._skin(self.SKIN)
        hyw = pw * 0.28
        hyh = ph * 0.45
        hyx = hx - thumb_dir * (pw * 0.32) - hyw / 2
        hyy = hy + ph * 0.08
        RoundedRectangle(pos=(hyx, hyy), size=(hyw, hyh),
                         radius=[hyw * 0.5], texture=tex)

    def _lignes_paume(self, hx, hy, pw, ph, side):
        """Les 3 lignes caracteristiques d'une paume ouverte : COEUR (haut),
        TETE (milieu, inclinee), VIE (arc autour du pouce cote thumb_dir)."""
        thumb_dir = self._thumb_dir(side)
        Color(self.SKIN_DK[0] * 0.6, self.SKIN_DK[1] * 0.6,
              self.SKIN_DK[2] * 0.6, 0.40)
        lw = max(1.0, pw * 0.028)
        # COEUR (en haut).
        Line(points=[hx - pw * 0.38, hy + ph * 0.58,
                     hx - pw * 0.05, hy + ph * 0.56,
                     hx + pw * 0.32, hy + ph * 0.52], width=lw)
        # TETE (milieu, legerement inclinee).
        Line(points=[hx - pw * 0.34, hy + ph * 0.42,
                     hx + pw * 0.06, hy + ph * 0.36,
                     hx + pw * 0.30, hy + ph * 0.28], width=lw)
        # VIE : arc autour de la base du pouce (cote thumb_dir).
        ts = thumb_dir
        Line(points=[hx + ts * pw * 0.05, hy + ph * 0.58,
                     hx + ts * pw * 0.28, hy + ph * 0.45,
                     hx + ts * pw * 0.35, hy + ph * 0.22,
                     hx + ts * pw * 0.22, hy + ph * 0.04], width=lw)

    # ----- DOIGT : 3 phalanges reutilisees pour les 4 doigts ------------- #
    #
    # Chaque phalange est appelee une fois par doigt, dans l'ordre :
    #     _doigt1 (proximale)  ->  _doigt2 (moyenne)  ->  _doigt3 (distale)
    #
    # Le SEUL parametre qui varie d'un doigt a l'autre est `total_len` (la
    # longueur totale du doigt). Les proportions internes (45/32/23 % et les
    # largeurs) restent IDENTIQUES pour les 4 doigts -> meme "image" partout.
    # Chaque _doigtN renvoie le nouveau y (haut de la phalange dessinee), pour
    # que le suivant sache ou commencer.

    def _doigt1(self, fx, cy, fw, total_len, side):
        """Phalange PROXIMALE (45 % du doigt, attachee a la paume).
        Image doigt1.png si dispo, sinon canvas. Largeur fixe a fw * 1.4
        (les vraies phalanges sont longues et fines, pas chunky). On
        AVANCE de 90 % seulement pour que la phalange suivante chevauche
        legerement et cache la jointure visible entre les images."""
        seg_h = total_len * 0.45 * DOIGT_SIZE
        tex_data = _char_texture("doigt1")
        if tex_data[0] is not None:
            _draw_char_image(tex_data, fx, cy + seg_h / 2, seg_h,
                             flip_h=(side == 'R'), target_w=fw * 1.4)
            return cy + seg_h * 0.90
        wb = fw * 1.00
        wt = fw * 0.88
        self._phalange(fx, cy, seg_h, wb, wt, shade_clair=True, joint=False)
        return cy + seg_h

    def _doigt2(self, fx, cy, fw, total_len, side):
        """Phalange MOYENNE (32 % du doigt). Avance reduite (chevauchement
        avec la suivante pour cacher la jointure)."""
        seg_h = total_len * 0.32 * DOIGT_SIZE
        tex_data = _char_texture("doigt2")
        if tex_data[0] is not None:
            _draw_char_image(tex_data, fx, cy + seg_h / 2, seg_h,
                             flip_h=(side == 'R'), target_w=fw * 1.3)
            return cy + seg_h * 0.90
        wb = fw * 0.88
        wt = fw * 0.74
        self._phalange(fx, cy, seg_h, wb, wt, shade_clair=False, joint=True)
        return cy + seg_h

    def _doigt3(self, fx, cy, fw, total_len, side):
        """Phalange DISTALE (23 % du doigt, avec pointe arrondie + pulpe)."""
        seg_h = total_len * 0.23 * DOIGT_SIZE
        tex_data = _char_texture("doigt3")
        if tex_data[0] is not None:
            _draw_char_image(tex_data, fx, cy + seg_h / 2, seg_h,
                             flip_h=(side == 'R'), target_w=fw * 1.2)
            return cy + seg_h
        wb = fw * 0.74
        wt = fw * 0.55
        self._phalange(fx, cy, seg_h, wb, wt, shade_clair=True, joint=True)
        # Bout : pointe arrondie + pulpe charnue cote paume.
        tipw = wt
        tex = self._skin(self.SKIN)
        RoundedRectangle(pos=(fx - tipw / 2, cy + seg_h - tipw * 0.5),
                         size=(tipw, tipw), radius=[tipw * 0.5], texture=tex)
        Color(self.SKIN_DK[0] * 0.85, self.SKIN_DK[1] * 0.85,
              self.SKIN_DK[2] * 0.85, 0.38)
        Ellipse(pos=(fx - tipw * 0.32, cy + seg_h - tipw * 0.55),
                size=(tipw * 0.64, tipw * 0.50))
        return cy + seg_h

    def _phalange(self, fx, cy, seg_h, wb, wt, shade_clair, joint):
        """Helper interne : trapeze d'UNE phalange + pli d'articulation a sa
        base si demande (entre 2 phalanges consecutives)."""
        shade = self.SKIN if shade_clair else self.SKIN_MID
        tex = self._skin(shade)
        Quad(points=[fx - wb / 2, cy, fx + wb / 2, cy,
                     fx + wt / 2, cy + seg_h, fx - wt / 2, cy + seg_h],
             texture=tex)
        if joint:
            Color(self.SKIN_DK[0] * 0.7, self.SKIN_DK[1] * 0.7,
                  self.SKIN_DK[2] * 0.7, 0.35)
            lw = max(1.0, wb * 0.10)
            Line(points=[fx - wb * 0.40, cy, fx + wb * 0.40, cy], width=lw)

    # ----- POUCE (2 phalanges articulees) -------------------------------- #

    def _pouce_segment(self, num, hx, hy, pw, ph, fw, side):
        """Une phalange du pouce.

        num = 1 : proximale (base, attachee au thenar, plus large)
        num = 2 : distale (bout, plus etroite, avec pulpe arrondie)

        Le pouce sort cote EXTERIEUR de la paume et s'incline vers
        l'exterieur (loin du centre de l'ecran).
        """
        thumb_dir = self._thumb_dir(side)
        scale = self._scale_ref()

        tw_base = fw * 1.2                   # largeur a la base du pouce
        # Longueur totale du pouce, scalee par POUCE_SIZE (les 2 phalanges).
        tlen_total = self.THUMB_LEN * scale * POUCE_SIZE
        prox_ratio = 0.58                    # part de la proximale
        dist_ratio = 0.42                    # part de la distale

        # Origine du pouce (base de la proximale).
        tbx = hx + thumb_dir * (pw * 0.42)
        tby = hy + ph * 0.18

        # Longueurs et largeurs caracteristiques.
        prox_len = tlen_total * prox_ratio
        dist_len = tlen_total * dist_ratio
        wb_prox = tw_base                    # largeur bas de la proximale
        wt_prox = tw_base * 0.85             # largeur haut de la proximale
        wt_dist = tw_base * 0.70             # largeur haut de la distale

        # Image pouce<num>.png si dispo : on dessine l'image au centre de la
        # phalange (le flip H se charge du cote pour la main droite).
        tex_data = _char_texture("pouce%d" % num)
        if tex_data[0] is not None:
            tbcx = hx + thumb_dir * (pw * 0.42)
            if num == 1:
                seg_len = prox_len
                cy = tby + seg_len / 2
            else:
                seg_len = dist_len
                cy = tby + prox_len + seg_len / 2
            _draw_char_image(tex_data, tbcx, cy, seg_len,
                             flip_h=(side == 'R'))
            return

        # Inclinaison vers l'exterieur (le pouce s'evase loin du centre).
        lean_prox = thumb_dir * prox_len * 0.5
        lean_dist = thumb_dir * dist_len * 0.5

        if num == 1:
            # Phalange PROXIMALE : trapeze qui s'evase de wb_prox a wt_prox,
            # legerement incline vers l'exterieur.
            tex = self._skin(self.SKIN)
            Quad(points=[tbx - wb_prox / 2, tby, tbx + wb_prox / 2, tby,
                         tbx + lean_prox + wt_prox / 2, tby + prox_len,
                         tbx + lean_prox - wt_prox / 2, tby + prox_len],
                 texture=tex)
            # Pli d'articulation au sommet (jonction avec la distale).
            Color(self.SKIN_DK[0] * 0.7, self.SKIN_DK[1] * 0.7,
                  self.SKIN_DK[2] * 0.7, 0.35)
            lw = max(1.0, wt_prox * 0.10)
            Line(points=[tbx + lean_prox - wt_prox * 0.40, tby + prox_len,
                         tbx + lean_prox + wt_prox * 0.40, tby + prox_len],
                 width=lw)
        else:
            # Phalange DISTALE : part de la fin de la proximale et continue
            # de s'incliner. Termine par une pointe arrondie + pulpe.
            base_x = tbx + lean_prox
            base_y = tby + prox_len
            tex = self._skin(self.SKIN_MID)
            Quad(points=[base_x - wt_prox / 2, base_y,
                         base_x + wt_prox / 2, base_y,
                         base_x + lean_dist + wt_dist / 2, base_y + dist_len,
                         base_x + lean_dist - wt_dist / 2, base_y + dist_len],
                 texture=tex)
            tip_cx = base_x + lean_dist
            tip_cy = base_y + dist_len
            tex = self._skin(self.SKIN)
            RoundedRectangle(pos=(tip_cx - wt_dist / 2, tip_cy - wt_dist * 0.5),
                             size=(wt_dist, wt_dist),
                             radius=[wt_dist * 0.5], texture=tex)
            Color(self.SKIN_DK[0] * 0.85, self.SKIN_DK[1] * 0.85,
                  self.SKIN_DK[2] * 0.85, 0.38)
            Ellipse(pos=(tip_cx - wt_dist * 0.32, tip_cy - wt_dist * 0.55),
                    size=(wt_dist * 0.64, wt_dist * 0.50))
