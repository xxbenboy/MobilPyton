"""
LA VUE A 360 DEGRES DE LA CASE, hors de l'ecran de jeu.

Le meme tour complet que le jeu -- le ciel, la nappe du sol (sol.py), les
quatre panneaux du decor (panorama.py) -- mais sans rien de ce qui sert a
jouer (mains, mode action, insectes). Un ecran la pose en fond (la carte),
la tient a jour avec `montre(state)` et la fait tourner au doigt avec
`glisse(touch)`.
"""
from kivy.uix.floatlayout import FloatLayout

from src.widgets import daylight
from src.widgets.animated_background import AnimatedBackground
from src.widgets.panorama import Panorama
from src.widgets.sol import SolPanorama
from src.widgets.zone_scenery import ZoneScenery, NAPPES, SCENE_DE_ZONE

# Comme dans le jeu : la part de l'ecran que chaque panneau dessine sous son
# bas (on y voit en baissant la tete).
SOUS_SOL = 2.3
# En deca de ce deplacement du doigt (pixels), ce n'est pas un glisse.
SEUIL = 14.0


class Vue360(FloatLayout):
    """Le tour de la case, qu'on regarde en glissant le doigt."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background = AnimatedBackground(time_scale=0, size_hint=(1, 1),
                                             pos_hint={"x": 0, "y": 0})
        self.add_widget(self.background)
        self.sol = SolPanorama(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        self.add_widget(self.sol)
        scenes = [ZoneScenery(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
                  for _ in range(4)]
        for sc in scenes:
            sc.sous_sol = SOUS_SOL
        self.panorama = Panorama(scenes, size_hint=(1, 1),
                                 pos_hint={"x": 0, "y": 0})
        self.panorama.sur_attache = self._attache
        self.add_widget(self.panorama)
        # Le panneau nord, toujours a jour : la nappe du sol tient de lui
        # ses reglages (voir ZoneScenery.reglages_nappe).
        self.scenery = scenes[0]
        self.lacet = 0.0
        self.tangage = 0.0
        self._state = None
        self._case = None
        self._glisse = None             # [touch, x0, y0, a bouge]

    # -- la case --------------------------------------------------------- #
    def montre(self, state):
        """La case telle qu'elle est maintenant, a l'heure et au temps qu'il
        fait. Ne redessine que ce qui a change."""
        self._state = state
        self._montre_panneau(self.panorama.plaque(0))
        for plaque in self.panorama.visibles():
            if plaque.direction != 0:
                self._montre_panneau(plaque)
        case = (state.player_x, state.player_y)
        if case != self._case:
            self._case = case
            reglages = self.scenery.reglages_nappe()
            if reglages is None:
                self.sol.cache()
            else:
                self.sol.regle(**reglages)
        secondes = state.time_seconds
        meteo = state.effective_weather()
        self.background.set_seconds(secondes)
        self.background.set_weather(meteo)
        self.background.set_horizon(self.scenery.hauteur_horizon())
        ciel = self.background.couleur_ciel(self.scenery.hauteur_horizon())
        self.sol.set_teinte(daylight.light_tint(secondes))
        self.sol.set_brume(ciel)
        for plaque in self.panorama.visibles():
            self._eclaire(plaque.scene)

    def _montre_panneau(self, plaque):
        state = self._state
        if state is None:
            return
        zone = state.current_zone()
        plaque.scene.montre_la_case(
            state, direction=plaque.direction,
            sans_sol=SCENE_DE_ZONE.get(zone, zone) in NAPPES)
        sol = (plaque.scene.texture_du_sol(), plaque.scene._sans_sol)
        if getattr(plaque, "_sol_de", None) != sol:
            plaque._sol_de = sol
            plaque.peint_sol()

    def _eclaire(self, scene):
        state = self._state
        scene.set_daylight(state.time_seconds)
        scene.set_brume(self.background.couleur_ciel(scene.hauteur_horizon()))
        scene.set_wind(state.effective_weather())

    def _attache(self, plaque):
        """Un panneau entre a l'ecran : il montre la case, eclaire."""
        if self._state is not None:
            self._montre_panneau(plaque)
            self._eclaire(plaque.scene)

    # -- le regard ------------------------------------------------------- #
    def regarde(self, lacet, tangage=None):
        self.lacet = lacet % 360.0
        if tangage is not None:
            self.tangage = tangage
        self.panorama.regle(self.lacet, self.tangage)
        self.tangage = self.panorama.tangage
        self.background.set_camera(self.lacet, self.tangage)
        self.sol.set_camera(self.lacet, self.tangage)

    def commence(self, touch):
        """Un doigt se pose (sur rien d'autre) : il pourra faire tourner la
        vue."""
        if self._glisse is None:
            self._glisse = [touch, touch.x, touch.y, False]
            return True
        return False

    def glisse(self, touch):
        g = self._glisse
        if g is None or touch is not g[0]:
            return False
        if not g[3] and abs(touch.x - g[1]) + abs(touch.y - g[2]) > SEUIL:
            g[3] = True
        if g[3]:
            # Le decor suit le doigt, comme dans le jeu.
            ppd = self.panorama.ppd()
            if ppd > 0:
                self.regarde(self.lacet - touch.dx / ppd,
                             self.tangage - touch.dy / ppd)
        return True

    def leve(self, touch):
        g = self._glisse
        if g is None or touch is not g[0]:
            return False
        self._glisse = None
        return True


__all__ = ["Vue360"]
