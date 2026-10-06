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

CHAQUE PANNEAU EST DECOUPE A SA TRANCHE de l'ecran. Un element proche d'un
raccord est dessine dans les deux panneaux (voir ZoneScenery.vu) ; sans
decoupe, le second recouvrait le premier, et un arbre lointain passait
par-dessus le sol proche de l'autre panneau. Decoupe, chaque tranche montre
sa propre scene, dans le bon ordre de profondeur.
"""
import math

from kivy.core.window import Window
from kivy.graphics import (Color, PushMatrix, PopMatrix, Rectangle,
                           RenderContext, Translate)
from kivy.graphics.scissor_instructions import ScissorPush, ScissorPop
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget

from src.widgets import textures

FOV = 90.0
TANGAGE_MAX = 90.0
# L'horizon par defaut, tant que l'ecran n'a pas donne celui de sa case : le
# plus haut des zones (le lac), le plus prudent pour la tete baissee.
HORIZON_DEFAUT = 0.75
# La nappe ne descend pas tout a fait a la verticale (son premier anneau est
# a quelques centimetres des pieds) : la tete s'arrete d'autant plus haut,
# avec un peu de marge, pour qu'aucune bande de ciel ne reste en bas.
MARGE_PIEDS = 6.0
# Hauteur du sol prolonge sous un panneau, en hauteurs d'ecran : de quoi
# baisser la tete jusqu'a regarder ses pieds.
SOL_PROLONGE = 3.0


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
            self._coupe = ScissorPush(x=0, y=0, width=1, height=1)
            PushMatrix()
            self._t = Translate(0, 0, 0)
            self._sol_c = Color(1, 1, 1, 1)
            self._sol = Rectangle()
        with self.canvas.after:
            PopMatrix()
            ScissorPop()
        self.add_widget(scene)
        self.bind(pos=self._sol_en_place, size=self._sol_en_place)

    def decale(self, dx, dy, vers_ecran=None):
        """Deplace le panneau et recale sa decoupe. `vers_ecran` (x, y) ->
        (x, y) : une transformation de plus, celle de la camera qui avance
        (mode action), que la decoupe doit suivre."""
        self._t.x, self._t.y = dx, dy
        gauche, droite = self.x + dx, self.x + dx + self.width
        if vers_ecran is not None:
            gauche = vers_ecran(gauche, self.y)[0]
            droite = vers_ecran(droite, self.y)[0]
        # Arrondi vers l'EXTERIEUR : deux tranches voisines se chevauchent
        # d'un pixel plutot que de laisser voir le ciel entre elles.
        g = int(math.floor(gauche))
        self._coupe.x = g
        self._coupe.y = 0
        self._coupe.width = max(1, int(math.ceil(droite)) - g)
        self._coupe.height = int(Window.height)

    def decalage(self):
        return self._t.x, self._t.y

    def _sol_en_place(self, *_):
        self.peint_sol()

    def peint_sol(self):
        """Le sol sous la scene, de la matiere de sa zone. Aucun quand la
        nappe du tour le peint (voir sol.py) : il la recouvrirait."""
        if getattr(self.scene, "_sans_sol", False):
            self._sol.size = (0, 0)
            return
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


# Le fond d'un panneau : ses formes, multipliees par la lumiere du jour.
FS_FOND = """
$HEADER$
uniform vec3 fond_teinte;
void main(void) {
    gl_FragColor = frag_color * texture2D(texture0, tex_coord0)
                   * vec4(fond_teinte, 1.0);
}
"""


class FondHorizon(Widget):
    """LE TOUT DERNIER PLAN d'un panneau : les silhouettes de l'horizon (la
    frange de la foret voisine, les cretes de la montagne).

    Elles etaient dessinees par le panneau lui-meme, donc PAR-DESSUS le
    terrain, que la nappe du sol peint dessous (voir sol.py). Dans un second
    tour de panneaux, pose ENTRE LE CIEL ET LE SOL, le terrain les recouvre :
    leur pied disparait derriere la crete, comme celui d'une vraie foret au
    loin. La scene de la direction y dessine (voir ZoneScenery.fond).

    La lumiere du jour les teinte par un seul reglage (voir teinte)."""

    _sans_sol = True                # (voir Plaque.peint_sol)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        ctx = RenderContext(use_parent_projection=True,
                            use_parent_modelview=True,
                            use_parent_frag_modelview=True)
        ctx.shader.fs = FS_FOND
        if ctx.shader.success:
            ctx["fond_teinte"] = [1.0, 1.0, 1.0]
            self.canvas.add(ctx)
            self.ctx = ctx
            self._shader = True
        else:
            self.ctx = self.canvas
            self._shader = False

    def texture_du_sol(self):
        return "grass"

    def vide(self):
        self.ctx.clear()

    def teinte(self, rgb):
        if self._shader:
            self.ctx["fond_teinte"] = [float(c) for c in rgb[:3]]


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
        self.vers_ecran = None      # transformation de la camera (mode action)
        # OU EST L'HORIZON dans la scene (part de sa hauteur, voir
        # ZoneScenery.hauteur_horizon) : il borne la tete baissee (voir
        # tangage_min). L'ecran le donne quand il connait la case.
        self.horizon = HORIZON_DEFAUT

    def _taille(self, *_):
        for p in self.plaques:
            p.pos = self.pos
            p.size = self.size
        self.regle()

    def ppd(self):
        return self.width / FOV

    def tangage_min(self):
        """La tete baissee au plus (degres, negatif).

        Le sol s'arrete au point juste sous les pieds, a 90 degres sous
        l'horizon. Baisser la tete plus loin faisait monter ce point dans
        l'ecran, et en dessous il n'y avait plus que le ciel du fond : on
        voyait du bleu a ses pieds. On s'arrete donc quand ce point atteint
        le bas de l'ecran."""
        ppd = self.ppd()
        if ppd <= 0 or self.height <= 0:
            return -TANGAGE_MAX
        return max(-TANGAGE_MAX, self.horizon * self.height / ppd - 90.0
                   + MARGE_PIEDS)

    def regle(self, lacet=None, tangage=None):
        """Place les panneaux pour ce regard (degres)."""
        if lacet is not None:
            self.lacet = lacet % 360.0
        if tangage is not None:
            self.tangage = tangage
        self.tangage = max(self.tangage_min(), min(TANGAGE_MAX, self.tangage))
        if self.width <= 0:
            return
        ppd = self.ppd()
        dy = -self.tangage * ppd
        for p in self.plaques:
            dx = ecart(p.direction * FOV - self.lacet) * ppd
            p.decale(dx, dy, self.vers_ecran)
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


__all__ = ["Panorama", "Plaque", "FondHorizon", "FOV", "TANGAGE_MAX",
           "ecart"]
