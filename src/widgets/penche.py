"""
LE JOUEUR SE PENCHE : la camera des ecrans d'inventaire et de craft.

Les deux ecrans montrent LA VRAIE SCENE DE LA CASE, celle de l'ecran de jeu,
elements et proportions compris. Seule la CAMERA bouge : en entrant, elle
glisse vers le bas, comme un regard qui se baisse vers le sol, et la scene
entiere -- ciel et decor ensemble -- monte a l'ecran sans qu'un seul element
change de taille ou de place par rapport au joueur. Ses mains restent ou
elles sont : elles sont attachees a lui, pas au paysage. En sortant vers le
jeu, la camera se releve avant de quitter l'ecran.

ENTRE LES DEUX ECRANS, ON RESTE PENCHE. L'inventaire et le craft regardent
le meme sol sous deux angles, et l'on passe de l'un a l'autre par le titre a
deux volets : se relever pour se repencher aussitot ferait faire au joueur
une gymnastique sans objet. La bascule est donc immediate, et l'ecran
d'arrivee s'ouvre deja penche.

Ce module est un MELANGEUR (comme drag_drop) : l'ecran en herite et appelle
construit_monde, prepare_penche, lance_penche et quitte_penche aux bons
moments. S'il a un sol en cases (`self.sol`, voir sol_de_craft), celui-ci
apparait a la fin du mouvement et ne repond qu'une fois la camera arrivee.
"""
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.floatlayout import FloatLayout
from kivy.graphics import PushMatrix, PopMatrix, Translate

from src.widgets import daylight
from src.widgets.animated_background import AnimatedBackground, night_darkness
from src.widgets.zone_scenery import ZoneScenery

# Ou le regard amene l'horizon, en part de la hauteur d'ecran. La scene de
# jeu le pose entre 0,47 (foret) et 0,75 (lac) : baisser les yeux le fait
# monter tout en haut, et le sol occupe alors presque tout l'ecran. Il etait
# a 0,88 ; le joueur trouvait qu'on ne se penchait pas assez.
#
# LE GLISSEMENT EST DONC PROPRE A CHAQUE ZONE : 0,46 de l'ecran en foret.
# Un glissement unique aurait laisse la foret a mi-hauteur, ou envoye
# l'horizon d'une autre zone hors de l'ecran.
HORIZON_PENCHE = 0.93
# Bornes du glissement, en part de la hauteur. Le haut est aussi ce qui
# decide du sol prepare sous l'ecran (voir ZoneScenery.sous_sol).
GLISSE_MIN = 0.22
GLISSE_MAX = 0.46
# AU BORD DU LAC, LE REGARD DESCEND JUSQU'A LA PLAGE. Les grilles du sol
# (voir sol_de_craft) montent jusqu'a 0,55 de l'ecran ; avec le glissement
# de 0,22, tout le plan de travail et le fond de la proximite tombaient sur
# l'eau -- des objets poses sur le lac. Le sable sec de la rive s'arrete a
# 0,108 de la hauteur de la scene (la ou l'eau commence a laper, dans
# rive_B) : a 0,42, il monte jusqu'a 0,53 de l'ecran, et les grilles
# reposent sur la greve. La berge d'en face sort alors par le haut : a la
# rive, se pencher, c'est regarder la plage.
GLISSE_RIVE = 0.42
# Durees du mouvement, en secondes. Se pencher prend un peu de temps ; se
# relever est plus vif, parce que c'est ce qui precede un changement
# d'ecran, et que personne n'aime attendre un bouton.
DUREE_PENCHE = 0.85
DUREE_RELEVE = 0.35
# Images par seconde de l'animation : elle ne deplace qu'une translation,
# c'est la carte graphique qui fait le reste.
FPS_CAMERA = 60.0
# Le sol en cases apparait a la FIN du mouvement, en fondu, sur ce dernier
# bout de la course : il est pose sur le sol tel qu'on le voit penche, et
# glisser avec lui pendant le mouvement l'aurait fait flotter.
APPARITION_GRILLES = 0.25

# Les ecrans qui regardent le sol penche : on passe de l'un a l'autre sans
# se relever.
ECRANS_PENCHES = ("inventory", "craft")
# Pose par un ecran penche qui en ouvre un autre : celui-ci s'ouvre deja
# penche, sans refaire le mouvement.
_DEJA_PENCHE = [False]


def adoucir(p):
    """Le trajet de la camera : depart et arrivee en douceur.

    Un mouvement a vitesse constante demarre et s'arrete d'un coup sec, ce
    qu'un cou ne fait pas. Cette courbe (le "smootherstep") part a vitesse
    nulle, accelere, puis se pose a vitesse nulle, sans a-coup d'acceleration
    ni au depart ni a l'arrivee."""
    p = max(0.0, min(1.0, p))
    return p * p * p * (p * (p * 6.0 - 15.0) + 10.0)


def glissement(crete, zone=None):
    """De combien la camera fait monter la scene, en part de la hauteur,
    pour amener une crete a `crete` jusqu'a HORIZON_PENCHE -- ou, au bord du
    lac, pour amener la plage sous les grilles (voir GLISSE_RIVE)."""
    if zone == "Lac":
        return GLISSE_RIVE
    return max(GLISSE_MIN, min(GLISSE_MAX, HORIZON_PENCHE - crete))


class Penche(object):
    """La camera qui se penche, pour un ecran qui en herite."""

    # -- construction --------------------------------------------------- #
    def construit_monde(self, root):
        """Le ciel et la scene, sous une seule translation : ils bougent
        ENSEMBLE quand la camera se penche. Le decor dessine avec son propre
        shader (voir ZoneScenery) reprend la matrice de son parent, il suit
        donc aussi."""
        self.monde = FloatLayout(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        with self.monde.canvas.before:
            PushMatrix()
            self._camera = Translate(0, 0, 0)
        with self.monde.canvas.after:
            PopMatrix()
        self.background = AnimatedBackground(time_scale=0, size_hint=(1, 1),
                                             pos_hint={"x": 0, "y": 0})
        self.monde.add_widget(self.background)
        # La VRAIE scene de la case, avec du sol prepare sous le bas de
        # l'ecran : c'est celui que la camera decouvre en se penchant.
        self.scenery = ZoneScenery(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        self.scenery.sous_sol = GLISSE_MAX + 0.02
        self.monde.add_widget(self.scenery)
        root.add_widget(self.monde)
        # L'etat de la camera : ou elle en est (0 = regard du jeu, 1 =
        # penchee), d'ou elle part, ou elle va, et l'ecran a ouvrir une fois
        # relevee.
        self._pente = 0.0
        self._depart = 0.0
        self._cible = 0.0
        self._duree = DUREE_PENCHE
        self._ecoule = 0.0
        self._apres = None
        self._horloge = None
        self._glisse = GLISSE_MIN
        # Une fenetre qui change de taille garde son regard : la translation
        # se compte en part de la hauteur.
        self.bind(size=lambda *_: self._place_camera())

    # -- cycle de l'ecran ------------------------------------------------ #
    def prepare_penche(self, state):
        """A l'entree : la scene de la case, et le regard de depart.

        On arrive avec le regard du jeu -- la scene est d'abord exactement
        celle qu'on vient de quitter -- SAUF depuis l'autre ecran penche, ou
        l'on etait deja penche."""
        self._arrete_camera()
        self._apres = None
        self._pente = 1.0 if _DEJA_PENCHE[0] else 0.0
        _DEJA_PENCHE[0] = False
        if state is not None:
            self.background.set_seconds(state.time_seconds)
            self.background.set_weather(state.effective_weather())
            self.scenery.set_wind(state.effective_weather())
            # Le voile de nuit prend AUSSI la teinte de l'heure, et le decor
            # suit le soleil (couleur de la lumiere, ombres portees).
            nuit = getattr(self, "_night_color", None)
            if nuit is not None:
                nuit.rgb = daylight.veil_color(state.time_seconds)
                nuit.a = night_darkness(state.time_seconds)
            self.scenery.set_daylight(state.time_seconds)
            # LA SCENE DE LA CASE, la meme que dans l'ecran de jeu (voir
            # ZoneScenery.montre_la_case).
            self.scenery.montre_la_case(state)
            self.background.set_horizon(self.scenery.hauteur_horizon())
            self.scenery.set_brume(self.background.couleur_ciel(
                self.scenery.hauteur_horizon()))
            self._glisse = glissement(self.scenery.hauteur_horizon(),
                                      self.scenery._zone)
        self._place_camera()

    def lance_penche(self):
        """A l'entree effective : le joueur baisse les yeux, s'il ne l'a
        pas deja fait."""
        if self._pente < 1.0:
            self._anime_vers(1.0, DUREE_PENCHE)

    def quitte_penche(self):
        self._arrete_camera()

    # -- sortie ---------------------------------------------------------- #
    def partir(self, ecran):
        """Quitter l'ecran vers `ecran`.

        Vers l'AUTRE ecran penche, tout de suite : on reste penche. Vers le
        jeu, on se releve PUIS on part ; un second toucher pendant le
        mouvement ne fait que changer la destination."""
        sol = getattr(self, "sol", None)
        if sol is not None:
            sol.annule()
            sol.actif = False
        if ecran in ECRANS_PENCHES and self._pente >= 0.999:
            self._arrete_camera()
            _DEJA_PENCHE[0] = True
            if self.manager is not None:
                self.manager.current = ecran
            return
        self._apres = ecran
        if self._horloge is not None and self._cible == 0.0:
            return
        self._anime_vers(0.0, DUREE_RELEVE)

    # -- l'animation ------------------------------------------------------ #
    def _anime_vers(self, cible, duree):
        self._depart = self._pente
        self._cible = float(cible)
        self._ecoule = 0.0
        # Partir d'une position intermediaire (un demi-mouvement interrompu)
        # prend la part de temps qui reste, pas la duree entiere.
        self._duree = max(1e-3, duree * abs(self._cible - self._depart))
        if self._horloge is None:
            self._horloge = Clock.schedule_interval(self._tick_camera,
                                                    1.0 / FPS_CAMERA)

    def _tick_camera(self, dt):
        # Un ralentissement (reveil, chargement) ne doit pas faire sauter la
        # camera : le pas est plafonne.
        self._ecoule += min(dt, 0.1)
        p = self._ecoule / self._duree
        self._pente = self._depart + (self._cible - self._depart) * adoucir(p)
        self._place_camera()
        if p < 1.0:
            return
        self._arrete_camera()
        self._place_camera()
        if self._cible == 0.0 and self._apres and self.manager is not None:
            ecran, self._apres = self._apres, None
            self.manager.current = ecran

    def _arrete_camera(self):
        if self._horloge is not None:
            self._horloge.cancel()
            self._horloge = None

    def _place_camera(self):
        """La scene monte a l'ecran d'autant que la camera se penche, et le
        sol en cases apparait a la fin du mouvement."""
        self._camera.y = self._pente * self._glisse * self.height
        sol = getattr(self, "sol", None)
        if sol is None:
            return
        debut = 1.0 - APPARITION_GRILLES
        sol.opacity = max(0.0, min(1.0, (self._pente - debut)
                                   / APPARITION_GRILLES))
        # Le doigt n'agit que camera arrivee ET tant qu'on ne repart pas.
        sol.actif = self._pente >= 0.999 and not (
            self._horloge is not None and self._cible == 0.0)
        self._sur_camera()

    def _sur_camera(self):
        """Prevenu a chaque pas de la camera (rien par defaut)."""


__all__ = ["Penche", "adoucir", "glissement", "HORIZON_PENCHE", "GLISSE_MIN",
           "GLISSE_MAX", "GLISSE_RIVE", "DUREE_PENCHE", "DUREE_RELEVE",
           "APPARITION_GRILLES", "ECRANS_PENCHES"]
