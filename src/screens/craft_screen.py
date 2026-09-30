"""
Ecran CRAFT : pour l'instant, LE JOUEUR SE PENCHE VERS LE SOL, et rien
d'autre.

L'ancien systeme de fabrication est retire, en attendant sa nouvelle forme :
plus de recettes, plus de colonnes, plus de bande de mains ni de sac. Les
recettes sont gardees de cote dans src/recettes_archive.py.

CE QUI RESTE :
- le TITRE A DEUX VOLETS en haut, pour revenir a l'inventaire (voir
  src/widgets/menu_toggle.py). Il garde sa place exacte : basculer d'un
  ecran a l'autre ne doit rien deplacer sous le doigt ;
- le bouton RETOUR, pour sortir du menu, a la hauteur ou il est dans
  l'inventaire.

LE FOND EST LA VRAIE SCENE DE LA CASE, celle de l'ecran de jeu, elements et
proportions compris. Seule la CAMERA bouge : en entrant, elle glisse vers le
bas, comme un regard qui se baisse vers le sol, et la scene entiere -- ciel
et decor ensemble -- monte a l'ecran sans qu'un seul element change de
taille ou de place par rapport au joueur. Ses mains, elles, restent ou elles
sont : elles sont attachees a lui, pas au paysage. En sortant, la camera se
releve avant de quitter l'ecran.
"""
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, PushMatrix, PopMatrix, Translate
from kivy.metrics import dp

from src.widgets import daylight
from src.widgets.animated_background import AnimatedBackground, night_darkness
from src.widgets.zone_scenery import ZoneScenery
from src.widgets.player_hands import PlayerHands
from src.widgets.styled_button import StyledButton
from src.widgets.responsive import (scale_font, ROW_TITLE, ROW_BODY,
                                    ROW_HANDS, ROW_HINT, ROW_BACK)
from src.widgets.menu_toggle import MenuToggle

# Largeur du bouton Retour, en part de l'ecran. Il n'occupe plus toute la
# largeur comme dans l'inventaire : il se glisse ENTRE LES DEUX AVANT-BRAS,
# qui descendent jusqu'au bas de l'ecran de part et d'autre (voir
# PlayerHands.HAND_FX). Sa hauteur, elle, est celle de l'inventaire.
LARGEUR_RETOUR = 0.20

# --- LA CAMERA QUI SE PENCHE ----------------------------------------- #
# Ou le regard amene l'horizon, en part de la hauteur d'ecran. La scene de
# jeu le pose entre 0,47 (foret) et 0,75 (lac) : baisser les yeux le fait
# monter tout en haut, et le sol occupe alors presque tout l'ecran.
#
# LE GLISSEMENT EST DONC PROPRE A CHAQUE ZONE : 0,40 de l'ecran en foret,
# 0,18 au bord du lac, dont l'horizon est deja haut. Un glissement
# unique aurait envoye la berge d'en face hors de l'ecran, ou laisse la
# foret a mi-hauteur.
HORIZON_PENCHE = 0.88
# Bornes du glissement, en part de la hauteur. Le haut est aussi ce qui
# decide du sol prepare sous l'ecran (voir ZoneScenery.sous_sol).
#
# LE BAS NE DESCEND PAS SOUS 0,18 : au bord du lac, la formule ne donnait que
# 0,13, et sur l'apercu on sentait a peine le joueur se pencher. La berge
# d'en face y remonte un peu au-dessus du haut ideal -- ses cimes frolent le
# haut de l'ecran -- mais le geste se voit.
GLISSE_MIN = 0.18
GLISSE_MAX = 0.40
# Durees du mouvement, en secondes. Se pencher prend un peu de temps ; se
# relever est plus vif, parce que c'est ce qui precede un changement
# d'ecran, et que personne n'aime attendre un bouton.
DUREE_PENCHE = 0.85
DUREE_RELEVE = 0.35
# Images par seconde de l'animation : elle ne deplace qu'une translation,
# c'est la carte graphique qui fait le reste.
FPS_CAMERA = 60.0


def adoucir(p):
    """Le trajet de la camera : depart et arrivee en douceur.

    Un mouvement a vitesse constante demarre et s'arrete d'un coup sec, ce
    qu'un cou ne fait pas. Cette courbe (le "smootherstep") part a vitesse
    nulle, accelere, puis se pose a vitesse nulle, sans a-coup d'acceleration
    ni au depart ni a l'arrivee."""
    p = max(0.0, min(1.0, p))
    return p * p * p * (p * (p * 6.0 - 15.0) + 10.0)


def glissement(crete):
    """De combien la camera fait monter la scene, en part de la hauteur,
    pour amener une crete a `crete` jusqu'a HORIZON_PENCHE."""
    return max(GLISSE_MIN, min(GLISSE_MAX, HORIZON_PENCHE - crete))


class CraftScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = FloatLayout()

        # LE MONDE : le ciel et la scene, qui bougent ENSEMBLE quand la
        # camera se penche. Une seule translation pour les deux, posee autour
        # d'eux : le decor dessine avec son propre shader (voir ZoneScenery)
        # reprend la matrice de son parent, il suit donc aussi.
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

        # LES MAINS DU JOUEUR, hors du monde : elles restent en place pendant
        # que le regard se baisse.
        self.hands = PlayerHands(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.hands)

        # Voile de NUIT : assombrit tout selon l'heure, mains comprises, comme
        # dans l'ecran de jeu.
        self.night = Widget(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        with self.night.canvas:
            self._night_color = Color(0.03, 0.05, 0.12, 0.0)
            self._night_rect = Rectangle(pos=self.night.pos,
                                         size=self.night.size)

        def _sync_night(*_):
            self._night_rect.pos = self.night.pos
            self._night_rect.size = self.night.size
        self.night.bind(pos=_sync_night, size=_sync_night)
        root.add_widget(self.night)

        # LES DEUX BOUTONS, AUX PLACES QU'ILS ONT DANS L'INVENTAIRE. On garde
        # la meme colonne, aux memes mesures (gabarit de responsive.py), en
        # remplacant simplement ce qui n'existe plus par du vide : le titre
        # et le Retour tombent ainsi exactement la ou le doigt les attend.
        # Aucun panneau derriere : la colonne est transparente.
        col = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8),
                        size_hint=(0.96, 0.96),
                        pos_hint={"center_x": 0.5, "center_y": 0.5})
        # Le titre passe par `switch` : la camera se releve AVANT qu'on ne
        # parte vers l'inventaire.
        col.add_widget(MenuToggle(self, "craft", size_hint=(1, ROW_TITLE),
                                  switch=self.partir))
        col.add_widget(Widget(size_hint=(1, ROW_BODY + ROW_HANDS + ROW_HINT)))

        bas = BoxLayout(orientation="horizontal", size_hint=(1, ROW_BACK))
        marge = (1.0 - LARGEUR_RETOUR) / 2.0
        bas.add_widget(Widget(size_hint_x=marge))
        back = scale_font(StyledButton(text="Retour",
                                       size_hint_x=LARGEUR_RETOUR), 0.022)
        back.bind(on_release=lambda *_: self.partir("game"))
        bas.add_widget(back)
        bas.add_widget(Widget(size_hint_x=marge))
        col.add_widget(bas)
        root.add_widget(col)

        self.add_widget(root)

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

    # ------------------------------------------------------------------ #
    def on_pre_enter(self):
        state = App.get_running_app().game_state
        # On arrive TOUJOURS avec le regard du jeu : la scene est d'abord
        # exactement celle qu'on vient de quitter, puis le joueur se penche.
        self._arrete_camera()
        self._pente = 0.0
        self._apres = None
        self._place_camera()
        if state is None:
            return
        self.background.set_seconds(state.time_seconds)
        self.background.set_weather(state.effective_weather())
        self.scenery.set_wind(state.effective_weather())
        # Le voile de nuit prend AUSSI la teinte de l'heure, et le decor suit
        # le soleil (couleur de la lumiere, ombres portees).
        self._night_color.rgb = daylight.veil_color(state.time_seconds)
        self._night_color.a = night_darkness(state.time_seconds)
        self.scenery.set_daylight(state.time_seconds)
        # LA SCENE DE LA CASE, la meme que dans l'ecran de jeu (voir
        # ZoneScenery.montre_la_case).
        self.scenery.montre_la_case(state)
        self.background.set_horizon(self.scenery.hauteur_horizon())
        self.scenery.set_brume(self.background.couleur_ciel(
            self.scenery.hauteur_horizon()))
        self._glisse = glissement(self.scenery.hauteur_horizon())
        self.refresh()

    def on_enter(self):
        # Les mains respirent, comme dans l'ecran de jeu.
        self.hands.start_breathing()
        # Et le joueur baisse les yeux.
        self._anime_vers(1.0, DUREE_PENCHE)

    def on_leave(self):
        self.hands.stop_breathing()
        self._arrete_camera()

    def refresh(self):
        """Les mains montrent ce qu'elles tiennent, gants compris."""
        state = App.get_running_app().game_state
        if state is None:
            return
        self.hands.set_items(state.hands[0], state.hands[1])
        self.hands.set_glove(state.equipment.get("gant"))

    # -- la camera ------------------------------------------------------ #
    def partir(self, ecran):
        """Se relever, PUIS ouvrir `ecran`. Un second toucher pendant le
        mouvement ne fait que changer la destination : on ne se releve pas
        deux fois."""
        self._apres = ecran
        if self._horloge is not None and self._cible == 0.0:
            return
        self._anime_vers(0.0, DUREE_RELEVE)

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
        if self._cible == 0.0 and self._apres and self.manager is not None:
            ecran, self._apres = self._apres, None
            self.manager.current = ecran

    def _arrete_camera(self):
        if self._horloge is not None:
            self._horloge.cancel()
            self._horloge = None

    def _place_camera(self):
        """La scene monte a l'ecran d'autant que la camera se penche."""
        self._camera.y = self._pente * self._glisse * self.height
