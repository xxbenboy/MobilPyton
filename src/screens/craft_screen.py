"""
Ecran CRAFT : pour l'instant, le SOL DEVANT SOI, et rien d'autre.

L'ancien systeme de fabrication est retire, en attendant sa nouvelle forme :
plus de recettes, plus de colonnes, plus de bande de mains ni de sac. Les
recettes sont gardees de cote dans src/recettes_archive.py.

CE QUI RESTE :
- le TITRE A DEUX VOLETS en haut, pour revenir a l'inventaire (voir
  src/widgets/menu_toggle.py). Il garde sa place exacte : basculer d'un
  ecran a l'autre ne doit rien deplacer sous le doigt ;
- le bouton RETOUR, pour sortir du menu, a la hauteur ou il est dans
  l'inventaire.

CE QUI EST NOUVEAU : LE FOND. Au lieu de la scene de la case vue de cote, on
voit ce que voit le joueur quand il baisse les yeux -- le sol de la case qui
fuit en perspective, le paysage de la meme case a l'horizon, et ses propres
mains au premier plan, avec ce qu'elles tiennent. C'est la scene sur
laquelle le prochain systeme de fabrication viendra se poser.
"""
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp

from src import world
from src.widgets import daylight, horizon
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


class CraftScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = FloatLayout()

        # LE CIEL, derriere tout : il suit l'heure et la meteo, et ses nuages
        # convergent vers l'horizon de la vue (voir on_pre_enter).
        self.background = AnimatedBackground(time_scale=0, size_hint=(1, 1),
                                             pos_hint={"x": 0, "y": 0})
        root.add_widget(self.background)

        # LE SOL DEVANT SOI et le paysage de la case (voir
        # ZoneScenery.set_plongee).
        self.scenery = ZoneScenery(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.scenery)

        # LES MAINS DU JOUEUR, avec ce qu'elles tiennent -- le meme widget que
        # dans l'ecran de jeu, donc les memes poses, les memes gants.
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
        col.add_widget(MenuToggle(self, "craft", size_hint=(1, ROW_TITLE)))
        col.add_widget(Widget(size_hint=(1, ROW_BODY + ROW_HANDS + ROW_HINT)))

        bas = BoxLayout(orientation="horizontal", size_hint=(1, ROW_BACK))
        marge = (1.0 - LARGEUR_RETOUR) / 2.0
        bas.add_widget(Widget(size_hint_x=marge))
        back = scale_font(StyledButton(text="Retour",
                                       size_hint_x=LARGEUR_RETOUR), 0.022)
        back.bind(on_release=lambda *_: setattr(self.manager, "current", "game"))
        bas.add_widget(back)
        bas.add_widget(Widget(size_hint_x=marge))
        col.add_widget(bas)
        root.add_widget(col)

        self.add_widget(root)

    # ------------------------------------------------------------------ #
    def on_pre_enter(self):
        state = App.get_running_app().game_state
        if state is None:
            return
        self.background.set_seconds(state.time_seconds)
        self.background.set_weather(state.effective_weather())
        self.scenery.set_wind(state.effective_weather())
        # Le voile de nuit prend AUSSI la teinte de l'heure, et le sol suit le
        # soleil (couleur de la lumiere).
        self._night_color.rgb = daylight.veil_color(state.time_seconds)
        self._night_color.a = night_darkness(state.time_seconds)
        self.scenery.set_daylight(state.time_seconds)
        # LE SOL DE LA CASE, vu en plongee. La graine est celle de la scene
        # de la case : le meme endroit montre toujours le meme sol.
        self.scenery.set_plongee(
            state.current_zone(),
            world.scene_seed(state.player_x, state.player_y),
            berge=horizon.zone_den_face(state))
        self.background.set_horizon(self.scenery.hauteur_horizon())
        self.scenery.set_brume(self.background.couleur_ciel(
            self.scenery.hauteur_horizon()))
        self.refresh()

    def on_enter(self):
        # Les mains respirent, comme dans l'ecran de jeu.
        self.hands.start_breathing()

    def on_leave(self):
        self.hands.stop_breathing()

    def refresh(self):
        """Les mains montrent ce qu'elles tiennent, gants compris."""
        state = App.get_running_app().game_state
        if state is None:
            return
        self.hands.set_items(state.hands[0], state.hands[1])
        self.hands.set_glove(state.equipment.get("gant"))
