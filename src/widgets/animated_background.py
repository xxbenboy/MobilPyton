"""
Fond anime d'ambiance.

Idee du jeu : le temps s'ecoule SANS arret et un fond anime accompagne
l'ambiance. Ce widget pose les bases de cette idee : il dessine un fond
qui change lentement de couleur en boucle (aube -> jour -> crepuscule ->
nuit -> aube...), pour donner la sensation que le temps passe.

Plus tard, le jeu pourra appeler `set_mood(...)` pour changer l'ambiance
selon l'action effectuee (foret, combat, repos, etc.). Pour l'instant il
sert surtout au menu : c'est purement decoratif.
"""
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle


# Palette d'ambiances parcourue en boucle. Chaque entree est une couleur
# (r, g, b) vers laquelle le fond se dirige doucement.
MOODS = [
    (0.12, 0.10, 0.20),  # nuit
    (0.30, 0.18, 0.22),  # aube
    (0.20, 0.35, 0.40),  # jour
    (0.35, 0.22, 0.18),  # crepuscule
]


class AnimatedBackground(Widget):
    """Rectangle plein qui derive lentement entre plusieurs couleurs."""

    def __init__(self, speed=0.15, **kwargs):
        super().__init__(**kwargs)
        # `speed` = vitesse de transition (plus grand = plus rapide).
        self.speed = speed
        self._mood_index = 0
        self._current = list(MOODS[0])          # couleur affichee
        self._target = list(MOODS[1])           # couleur visee

        # On dessine le fond dans le canvas du widget.
        with self.canvas.before:
            self._color = Color(*self._current)
            self._rect = Rectangle(pos=self.pos, size=self.size)

        # Le rectangle doit toujours couvrir le widget, meme si on
        # redimensionne la fenetre.
        self.bind(pos=self._update_rect, size=self._update_rect)

        # Mise a jour ~60 fois par seconde.
        Clock.schedule_interval(self._tick, 1 / 60.0)

    def set_mood(self, rgb):
        """Force l'ambiance vers une couleur precise (ex. selon l'action).

        Le fond continue ensuite sa boucle naturelle a partir de la.
        """
        self._target = list(rgb)

    def _update_rect(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def _tick(self, dt):
        # On rapproche doucement la couleur courante de la couleur visee.
        done = True
        for i in range(3):
            diff = self._target[i] - self._current[i]
            if abs(diff) > 0.001:
                self._current[i] += diff * self.speed * dt
                done = False
        self._color.rgb = self._current

        # Couleur visee atteinte : on passe a l'ambiance suivante.
        if done:
            self._mood_index = (self._mood_index + 1) % len(MOODS)
            self._target = list(MOODS[self._mood_index])
