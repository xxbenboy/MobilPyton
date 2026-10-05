"""
LE MODE ACTION de l'ecran de jeu.

Le bouton Action n'ouvre plus de sous-menu : le HUD s'efface en fondu et ce
avec quoi l'on peut agir CLIGNOTE dans la scene -- les buissons qui portent
des baies, l'eau du lac, les arbres (une hache en main). Toucher un element
qui clignote fait AVANCER LA CAMERA vers lui, comme le craft vers le plan de
travail, et lance son mini-jeu :

    BUISSON  cueillir chaque baie : un toucher sur une grappe, la main la
             plus proche va la prendre ;
    EAU      les deux mains, jointes, suivent le doigt : les plonger dans
             l'eau, puis les monter jusqu'en haut de l'ecran pour boire ;
    ARBRE    la main qui tient la hache suit le doigt : un coup a chaque
             passage rapide a travers le tronc.

Ce fichier ne touche PAS a la partie : il dit a l'ecran ce que le joueur a
fait (`fini(resultat)`), et l'ecran l'applique (voir GameScreen).
"""
import math
import random

from kivy.clock import Clock
from kivy.graphics import (Color, Ellipse, Line, Rectangle, PushMatrix,
                           PopMatrix, Translate, Scale, Triangle)
from kivy.graphics.texture import Texture
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget

from src.widgets.zone_scenery import dessine_grappe

FPS = 60.0
DUREE_APPROCHE = 0.5        # la camera avance (et recule), en secondes


def doux(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


# --------------------------------------------------------------------- #
# LA CAMERA QUI AVANCE
# --------------------------------------------------------------------- #
class Approche(FloatLayout):
    """Le monde (ciel, decor, insectes) : tout son contenu avance ensemble
    vers un point de la scene. `regle(e)` : e = 0, vue normale ; e = 1, le
    `point` de la scene arrive en `cible` a l'ecran, grossi `zoom` fois."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.e = 0.0
        self.point = (0.0, 0.0)
        self.cible = (0.0, 0.0)
        self.zoom = 1.0
        self.secousse = (0.0, 0.0)
        with self.canvas.before:
            PushMatrix()
            self._t = Translate(0, 0, 0)
            self._s = Scale(1.0, 1.0, 1.0, origin=(0, 0))
        with self.canvas.after:
            PopMatrix()

    def vise(self, point, cible, zoom):
        """Ou avancer. La `cible` est ramenee de sorte que le monde grossi
        couvre toujours tout l'ecran : vers un arbre au bord du cadre, la
        camera s'arrete avant de montrer le vide au-dela du decor."""
        s = float(zoom)
        w, h = self.width, self.height
        x0, y0 = self.x, self.y
        px, py = point
        cx = max(x0 + w - s * (x0 + w - px), min(x0 + s * (px - x0),
                                                  cible[0]))
        cy = max(y0 + h - s * (y0 + h - py), min(y0 + s * (py - y0),
                                                  cible[1]))
        self.point, self.cible, self.zoom = point, (cx, cy), s

    def regle(self, e=None):
        if e is not None:
            self.e = float(e)
        s = 1.0 + (self.zoom - 1.0) * self.e
        self._s.origin = self.point
        self._s.x = self._s.y = s
        self._t.x = (self.cible[0] - self.point[0]) * self.e + self.secousse[0]
        self._t.y = (self.cible[1] - self.point[1]) * self.e + self.secousse[1]

    def echelle(self):
        return 1.0 + (self.zoom - 1.0) * self.e

    def ecran(self, x, y):
        """Ou tombe a l'ecran le point (x, y) de la scene."""
        s = self.echelle()
        px, py = self.point
        return (px + self._t.x + s * (x - px), py + self._t.y + s * (y - py))


# --------------------------------------------------------------------- #
# CE QUI CLIGNOTE
# --------------------------------------------------------------------- #
_SILHOUETTES = {}


def silhouette(tex):
    """La silhouette BLANCHE d'une image : ses pixels passes en blanc, sa
    transparence gardee. Calculee une fois par image ; None si l'image ne se
    laisse pas lire."""
    cle = id(tex)
    if cle not in _SILHOUETTES:
        sil = None
        try:
            w, h = tex.size
            px = bytearray(tex.pixels)
            n = w * h
            if len(px) == n * 4:
                blanc = b"\xff" * n
                px[0::4] = blanc
                px[1::4] = blanc
                px[2::4] = blanc
                sil = Texture.create(size=(w, h), colorfmt="rgba")
                sil.blit_buffer(bytes(px), colorfmt="rgba", bufferfmt="ubyte")
                sil.wrap = "clamp_to_edge"
                if tex.uvsize[1] < 0:
                    sil.flip_vertical()
        except Exception:
            sil = None
        _SILHOUETTES[cle] = (tex, sil)
    return _SILHOUETTES[cle][1]


JAUNE = (1.0, 0.88, 0.10)           # le clignotement, transparent
CONTOUR = (0.85, 0.58, 0.0, 1.0)    # le contour, jaune fonce et plein
EPAISSEUR_CONTOUR = 0.0065          # en part de la hauteur de l'ecran
VOILE = (0.80, 0.82, 0.85, 0.42)    # estompe le reste du decor
CADENCE = 1.4                       # clignotements par seconde


class Clignote(Widget):
    """Les elements avec lesquels on peut agir, qui clignotent.

    Une cible : {"kind": "baies" | "eau" | "arbre", "cell": (gx, gy) ou
    None, "boite": (x0, y0, x1, y1) a l'ecran, et, si le decor l'a
    dessinee en image, "image": (texture, x, y, l, h, teinte) et "baies":
    [(x, y, d)]}.

    LE RESTE DU DECOR S'ESTOMPE sous un voile clair, et chaque element est
    REDESSINE PAR-DESSUS : on le voit donc en entier, meme cache derriere un
    rocher ou un autre arbre. Sa silhouette est cernee d'un contour jaune
    fonce et plein, et un jaune transparent clignote sur lui."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cibles = []
        self._t = 0.0
        self._horloge = None

    def montre(self, cibles):
        self.cibles = list(cibles)
        self._t = 0.0
        if self._horloge is None:
            self._horloge = Clock.schedule_interval(self._pas, 1.0 / FPS)

    def cache(self):
        self.cibles = []
        if self._horloge is not None:
            self._horloge.cancel()
            self._horloge = None
        self.canvas.clear()

    def cible_sous(self, x, y):
        """La cible touchee (la plus petite qui contient le doigt), ou
        None."""
        meilleure, aire = None, None
        for c in self.cibles:
            x0, y0, x1, y1 = c["boite"]
            m = 0.04 * self.width
            if x0 - m <= x <= x1 + m and y0 - m <= y <= y1 + m:
                a = (x1 - x0) * (y1 - y0)
                if aire is None or a < aire:
                    meilleure, aire = c, a
        return meilleure

    def _pas(self, dt):
        self._t += min(dt, 0.1)
        p = 0.5 + 0.5 * math.sin(self._t * 2.0 * math.pi * CADENCE)
        self.canvas.clear()
        with self.canvas:
            self._voile()
            for c in self.cibles:
                if c["kind"] == "eau":
                    self._eau(c, p)
                elif c.get("image") is not None:
                    self._silhouette(c, p)
                else:
                    self._ovale(c, p)

    def _voile(self):
        """Le voile sur tout l'ecran, SAUF l'eau qui clignote (elle n'est
        pas redessinee : la voiler la cacherait)."""
        x, w = self.x, self.width
        bandes = sorted((c["boite"][1], c["boite"][3]) for c in self.cibles
                        if c["kind"] == "eau")
        Color(*VOILE)
        bas = self.y
        for b0, b1 in bandes:
            if b0 > bas:
                Rectangle(pos=(x, bas), size=(w, b0 - bas))
            bas = max(bas, b1)
        if bas < self.top:
            Rectangle(pos=(x, bas), size=(w, self.top - bas))

    def _silhouette(self, c, p):
        tex, x, y, w, h, teinte = c["image"]
        # La silhouette BLANCHE de l'image : teintee, elle donne un jaune
        # franc. L'image elle-meme, multipliee par du jaune, restait verte.
        sil = silhouette(tex) or tex
        e = max(1.5, EPAISSEUR_CONTOUR * self.height)
        # Le CONTOUR : la silhouette en jaune fonce, decalee tout autour.
        Color(*CONTOUR)
        for k in range(12):
            a = 2.0 * math.pi * k / 12.0
            Rectangle(texture=sil, pos=(x + math.cos(a) * e,
                                        y + math.sin(a) * e), size=(w, h))
        # L'element lui-meme, par-dessus le voile et ce qui le cachait.
        Color(*teinte, 1.0)
        Rectangle(texture=tex, pos=(x, y), size=(w, h))
        for bx, by, d in c.get("baies", ()):
            dessine_grappe(bx, by, d)
        # Le CLIGNOTEMENT : un jaune transparent sur sa silhouette.
        Color(*JAUNE, 0.10 + 0.40 * p)
        Rectangle(texture=sil, pos=(x, y), size=(w, h))

    def _eau(self, c, p):
        x0, y0, x1, y1 = c["boite"]
        Color(*JAUNE, 0.14 + 0.28 * p)
        Rectangle(pos=(x0, y0), size=(x1 - x0, y1 - y0))
        Color(*CONTOUR)
        e = max(1.5, EPAISSEUR_CONTOUR * self.height)
        Line(points=[x0, y1, x1, y1], width=e)

    def _ovale(self, c, p):
        """Un element dessine sans image : un ovale a sa place."""
        x0, y0, x1, y1 = c["boite"]
        w, h = x1 - x0, y1 - y0
        Color(*JAUNE, 0.12 + 0.35 * p)
        Ellipse(pos=(x0, y0), size=(w, h))
        Color(*CONTOUR)
        Line(ellipse=(x0, y0, w, h),
             width=max(1.5, EPAISSEUR_CONTOUR * self.height))
        for bx, by, d in c.get("baies", ()):
            dessine_grappe(bx, by, d)


# --------------------------------------------------------------------- #
# LES MINI-JEUX
# --------------------------------------------------------------------- #
class _Mains(object):
    """Mene les mains en douceur vers un decalage (dx, dy) chacune."""

    def __init__(self, mains):
        self.mains = mains
        self.cible = [(0.0, 0.0), (0.0, 0.0)]
        self.pos = [list(mains.decalage(0)), list(mains.decalage(1))]

    def base(self, i):
        """Le creux de la paume `i` a sa place : une main qui TIENT un objet
        a une autre pose (HandHUD), sa paume n'est pas au meme endroit que
        celle d'une main vide (HandIdle)."""
        m = self.mains
        if getattr(m, "_items", [None, None])[i] is not None:
            return (m.x + m.HAND_FX[i] * m.width, m.y + m.ITEM_FY * m.height)
        return m.paume(i)

    def vers_paume(self, i, x, y):
        """La paume `i` doit aller en (x, y) a l'ecran."""
        bx, by = self.base(i)
        self.cible[i] = (x - bx, y - by)

    def repos(self, i):
        self.cible[i] = (0.0, 0.0)

    def paume(self, i):
        bx, by = self.base(i)
        return bx + self.pos[i][0], by + self.pos[i][1]

    def pas(self, dt, tau=0.07):
        k = 1.0 - math.exp(-dt / tau)
        for i in (0, 1):
            tx, ty = self.cible[i]
            self.pos[i][0] += (tx - self.pos[i][0]) * k
            self.pos[i][1] += (ty - self.pos[i][1]) * k
            self.mains.decale(i, *self.pos[i])

    def arrivee(self, i, seuil=3.0):
        tx, ty = self.cible[i]
        return math.hypot(tx - self.pos[i][0], ty - self.pos[i][1]) < seuil

    def remet(self):
        for i in (0, 1):
            self.cible[i] = (0.0, 0.0)
            self.pos[i] = [0.0, 0.0]
            self.mains.decale(i, 0.0, 0.0)


class MiniJeu(object):
    """Le socle : une horloge, les mains, deux couches de dessin (sous les
    mains et sur elles), une consigne et la fin."""

    def __init__(self, ecran, cible, fini, consigne):
        self.ecran = ecran
        self.cible = cible
        self.fini = fini
        self.consigne = consigne
        self.mains = _Mains(ecran.hands)
        self.sous = ecran.couche_sous
        self.sur = ecran.couche_sur
        self._horloge = None
        self.termine = False

    def demarre(self):
        self._horloge = Clock.schedule_interval(self._tick, 1.0 / FPS)

    def arrete(self):
        if self._horloge is not None:
            self._horloge.cancel()
            self._horloge = None
        self.sous.canvas.clear()
        self.sur.canvas.clear()
        self.mains.remet()

    def _tick(self, dt):
        dt = min(dt, 0.1)
        self.mains.pas(dt)
        self.pas(dt)

    def termine_avec(self, resultat):
        if self.termine:
            return
        self.termine = True
        Clock.schedule_once(lambda *_: self.fini(resultat), 0.35)

    # A redefinir.
    def pas(self, dt):
        pass

    def touche(self, touch):
        return True

    def bouge(self, touch):
        return True

    def leve(self, touch):
        return True


class JeuBaies(MiniJeu):
    """Cueillir les baies d'un buisson, grappe par grappe."""

    ALLER = 0.20
    RETOUR = 0.30

    def __init__(self, ecran, cible, fini, consigne, baies, libres=(0, 1)):
        super().__init__(ecran, cible, fini, consigne)
        # Seule une main LIBRE cueille.
        self.libres = tuple(libres)
        app = ecran.monde
        # Les baies a l'ecran, la camera rapprochee (voir Approche.ecran).
        self.baies = [{"x": app.ecran(x, y)[0], "y": app.ecran(x, y)[1],
                       "d": d * app.echelle(), "etat": "la"}
                      for x, y, d in baies]
        self.total = len(self.baies)
        self.cueillies = 0
        self.geste = [None, None]       # [baie, temps] par main

    def demarre(self):
        super().demarre()
        self._dit()
        self._dessine()

    def _dit(self):
        self.consigne("Cueille les baies (%d/%d)" % (self.cueillies,
                                                    self.total))

    def touche(self, touch):
        if self.termine:
            return True
        meilleure, dist = None, None
        for b in self.baies:
            if b["etat"] != "la":
                continue
            d = math.hypot(touch.x - b["x"], touch.y - b["y"])
            if d <= max(b["d"] * 2.2, 0.05 * self.ecran.height) and \
                    (dist is None or d < dist):
                meilleure, dist = b, d
        if meilleure is None:
            return True
        proche = 0 if meilleure["x"] < self.ecran.center_x else 1
        mains = [i for i in (proche, 1 - proche)
                 if i in self.libres and self.geste[i] is None]
        if not mains:
            return True
        i = mains[0]
        meilleure["etat"] = "prise"
        self.geste[i] = [meilleure, 0.0]
        self.mains.vers_paume(i, meilleure["x"], meilleure["y"])
        return True

    def pas(self, dt):
        for i in (0, 1):
            g = self.geste[i]
            if g is None:
                continue
            g[1] += dt
            if g[1] >= self.ALLER and g[0]["etat"] == "prise":
                g[0]["etat"] = "main"          # la main la tient : retour
                self.mains.repos(i)
            if g[1] >= self.ALLER + self.RETOUR:
                g[0]["etat"] = "cueillie"
                self.geste[i] = None
                self.cueillies += 1
                self._dit()
                if self.cueillies >= self.total:
                    self.termine_avec({"baies": self.cueillies})
        self._dessine()

    def _dessine(self):
        self.sous.canvas.clear()
        with self.sous.canvas:
            for b in self.baies:
                if b["etat"] in ("la", "prise"):
                    dessine_grappe(b["x"], b["y"], b["d"])
            for i in (0, 1):
                g = self.geste[i]
                if g is not None and g[0]["etat"] == "main":
                    px, py = self.mains.paume(i)
                    dessine_grappe(px, py, g[0]["d"])


class JeuEau(MiniJeu):
    """Puiser l'eau a deux mains et la monter jusqu'a la bouche."""

    PLONGE = 0.35       # temps dans l'eau pour remplir les mains (s)
    HAUT = 0.86         # part de la hauteur : la bouche
    JOINT = 0.030       # ecart d'une paume au milieu, en part de la largeur

    def __init__(self, ecran, cible, fini, consigne, eau_bas, eau_haut):
        super().__init__(ecran, cible, fini, consigne)
        self.eau_bas = eau_bas
        self.eau_haut = eau_haut
        self.doigt = None
        self.dans_l_eau = 0.0
        self.pleine = 0.0           # 0 a 1 : l'eau dans les mains
        self.gouttes = []

    def demarre(self):
        super().demarre()
        self.consigne("Joins les mains dans l'eau, puis monte-les en haut")

    def _joint(self, x, y):
        j = self.JOINT * self.ecran.width
        self.mains.vers_paume(0, x - j, y)
        self.mains.vers_paume(1, x + j, y)

    def touche(self, touch):
        if self.termine:
            return True
        self.doigt = touch
        self._joint(touch.x, touch.y)
        return True

    def bouge(self, touch):
        if touch is self.doigt and not self.termine:
            self._joint(touch.x, touch.y)
        return True

    def leve(self, touch):
        if touch is self.doigt:
            self.doigt = None
            if self.pleine > 0 and not self.termine:
                self._renverse()
                self.consigne("L'eau a coule... recommence")
            self.mains.repos(0)
            self.mains.repos(1)
        return True

    def _milieu(self):
        (ax, ay), (bx, by) = self.mains.paume(0), self.mains.paume(1)
        return (ax + bx) / 2.0, (ay + by) / 2.0

    def _renverse(self):
        x, y = self._milieu()
        for _ in range(int(14 * self.pleine)):
            self.gouttes.append([x + random.uniform(-20, 20), y,
                                 random.uniform(-60, 60),
                                 random.uniform(-20, 80), 0.0])
        self.pleine = 0.0

    def pas(self, dt):
        x, y = self._milieu()
        jointes = self.doigt is not None and self.mains.arrivee(0, 25.0) \
            and self.mains.arrivee(1, 25.0)
        if jointes and self.eau_bas <= y <= self.eau_haut:
            self.dans_l_eau += dt
            if self.dans_l_eau >= self.PLONGE and self.pleine < 1.0:
                self.pleine = 1.0
                self.consigne("Monte l'eau jusqu'en haut pour boire")
        else:
            self.dans_l_eau = 0.0
        # Hors de l'eau, un peu fuit entre les doigts en route.
        if self.pleine > 0 and y > self.eau_haut:
            self.pleine = max(0.35, self.pleine - dt * 0.12)
            if random.random() < dt * 6.0:
                self.gouttes.append([x + random.uniform(-15, 15), y - 10,
                                     random.uniform(-15, 15), 0.0, 0.0])
        if self.pleine > 0 and y >= self.HAUT * self.ecran.height:
            self.termine_avec({"eau": True})
            self.pleine = 0.0
            self.consigne("Ahh... de l'eau fraiche")
        self._dessine(dt)

    def _dessine(self, dt):
        h = self.ecran.height
        self.sur.canvas.clear()
        with self.sur.canvas:
            if self.pleine > 0:
                x, y = self._milieu()
                w = self.JOINT * self.ecran.width * 2.6
                Color(0.45, 0.70, 0.90, 0.55 * self.pleine)
                Ellipse(pos=(x - w / 2, y - w * 0.22), size=(w, w * 0.44))
                Color(0.85, 0.95, 1.0, 0.45 * self.pleine)
                Ellipse(pos=(x - w * 0.25, y + w * 0.02),
                        size=(w * 0.3, w * 0.08))
            reste = []
            for g in self.gouttes:
                g[4] += dt
                g[3] -= 900.0 * dt
                g[0] += g[2] * dt
                g[1] += g[3] * dt
                if g[4] < 1.2 and g[1] > 0:
                    reste.append(g)
                    Color(0.55, 0.78, 0.95, 0.8 * (1.0 - g[4] / 1.2))
                    d = 0.008 * h
                    Ellipse(pos=(g[0] - d / 2, g[1] - d / 2), size=(d, d * 1.3))
            self.gouttes = reste


class JeuArbre(MiniJeu):
    """Abattre un arbre a la hache, coup par coup."""

    COUPS = 6
    VITESSE = 0.55      # vitesse minimale du doigt, en largeurs d'ecran / s
    BANDE = 0.20        # le doigt passe a moins de cette part de hauteur de
                        # l'entaille

    def __init__(self, ecran, cible, fini, consigne, main, tronc, entaille,
                 largeur_tronc):
        super().__init__(ecran, cible, fini, consigne)
        self.main = main                # la main qui tient la hache
        self.tronc_x = tronc
        self.entaille_y = entaille
        self.larg = largeur_tronc
        self.doigt = None
        self.coups = 0
        self.dernier = None             # (x, t) du dernier pas du doigt
        self.copeaux = []
        self.secoue = 0.0
        self._t = 0.0

    def demarre(self):
        super().demarre()
        self._dit()

    def _dit(self):
        self.consigne("Glisse le doigt a travers le tronc (%d/%d)"
                      % (self.coups, self.COUPS))

    def touche(self, touch):
        if not self.termine:
            self.doigt = touch
            self.dernier = (touch.x, self._t)
            self.mains.vers_paume(self.main, touch.x, touch.y)
        return True

    def bouge(self, touch):
        if touch is not self.doigt or self.termine:
            return True
        self.mains.vers_paume(self.main, touch.x, touch.y)
        x0, t0 = self.dernier
        dt = max(1e-3, self._t - t0)
        vitesse = abs(touch.x - x0) / dt / max(1.0, self.ecran.width)
        traverse = (x0 - self.tronc_x) * (touch.x - self.tronc_x) <= 0 \
            and x0 != touch.x
        pres = abs(touch.y - self.entaille_y) <= self.BANDE \
            * self.ecran.height
        if traverse and pres and vitesse >= self.VITESSE:
            self._coup(1 if touch.x > x0 else -1)
        self.dernier = (touch.x, self._t)
        return True

    def leve(self, touch):
        if touch is self.doigt:
            self.doigt = None
            self.mains.repos(self.main)
        return True

    def _coup(self, sens):
        self.coups += 1
        self.secoue = 0.18
        for _ in range(10):
            self.copeaux.append([self.tronc_x - self.larg / 2.0,
                                 self.entaille_y,
                                 sens * random.uniform(120, 420),
                                 random.uniform(80, 420), 0.0,
                                 random.uniform(0.6, 1.0)])
        self._dit()
        if self.coups >= self.COUPS:
            self.consigne("L'arbre tombe !")
            self.termine_avec({"arbre": True})

    def pas(self, dt):
        self._t += dt
        app = self.ecran.monde
        if self.secoue > 0:
            self.secoue = max(0.0, self.secoue - dt)
            a = 6.0 * self.secoue / 0.18
            app.secousse = (random.uniform(-a, a), random.uniform(-a, a) * 0.4)
        else:
            app.secousse = (0.0, 0.0)
        app.regle()
        self.ecran._recoupe()
        h = self.ecran.height
        # L'ENTAILLE grandit a chaque coup, sous les mains.
        self.sous.canvas.clear()
        with self.sous.canvas:
            if self.coups:
                # Une encoche en V, du bord du tronc vers son coeur : le bois
                # clair a l'interieur, cerne d'ecorce arrachee.
                p = self.coups / float(self.COUPS)
                prof = self.larg * (0.20 + 0.65 * p)
                hh = self.larg * (0.45 + 0.45 * p)
                x = self.tronc_x - self.larg / 2.0 + app.secousse[0]
                y = self.entaille_y + app.secousse[1]
                Color(0.16, 0.09, 0.04, 0.95)
                Triangle(points=[x, y + hh / 2, x, y - hh / 2, x + prof, y])
                Color(0.86, 0.70, 0.46, 1.0)
                Triangle(points=[x, y + hh * 0.34, x, y - hh * 0.34,
                                 x + prof * 0.78, y])
        self.sur.canvas.clear()
        with self.sur.canvas:
            reste = []
            for c in self.copeaux:
                c[4] += dt
                c[3] -= 1400.0 * dt
                c[0] += c[2] * dt
                c[1] += c[3] * dt
                if c[4] < 0.9 and c[1] > 0:
                    reste.append(c)
                    Color(0.80 * c[5], 0.64 * c[5], 0.40 * c[5],
                          1.0 - c[4] / 0.9)
                    d = 0.018 * h
                    Rectangle(pos=(c[0], c[1]), size=(d, d * 0.55))
            self.copeaux = reste

    def arrete(self):
        app = self.ecran.monde
        app.secousse = (0.0, 0.0)
        app.regle()
        super().arrete()


__all__ = ["Approche", "Clignote", "JeuBaies", "JeuEau", "JeuArbre",
           "DUREE_APPROCHE", "doux"]
