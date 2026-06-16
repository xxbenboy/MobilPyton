"""
Fond commun des ecrans de MENU (accueil, nouvelle partie, charger).

Pour que ces ecrans aient TOUS le meme decor que l'accueil, on regroupe ici
les deux couches du fond du menu :
- le ciel anime qui defile (24h en 4 min, depart 6h) ;
- la silhouette de foret.

Comme tous les ecrans de menu utilisent ce meme MenuBackdrop avec les memes
reglages, leurs fonds restent identiques et synchronises. Les ecrans EN PARTIE
(survie, carte) utilisent un fond different, pilote par l'horloge de la partie.
"""
from kivy.uix.floatlayout import FloatLayout

from src.widgets.animated_background import AnimatedBackground, MENU_TIME_SCALE
from src.widgets.nature_silhouette import NatureSilhouette


class MenuBackdrop(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_widget(AnimatedBackground(start_seconds=6 * 3600,
                                           time_scale=MENU_TIME_SCALE,
                                           size_hint=(1, 1),
                                           pos_hint={"x": 0, "y": 0}))
        self.add_widget(NatureSilhouette(size_hint=(1, 1),
                                         pos_hint={"x": 0, "y": 0}))
