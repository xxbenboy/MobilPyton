"""
Aide a l'interface responsive (qui s'adapte a la taille de l'ecran).

La taille et la position des boutons sont deja gerees par Kivy via
`size_hint` / `pos_hint` (proportions de la fenetre). Il reste a faire
suivre la TAILLE DU TEXTE : sinon, sur un grand ecran, les boutons
grandissent mais le texte reste petit.

`scale_font(widget, fraction)` lie la taille de police d'un widget a la
HAUTEUR de la fenetre. Exemple : fraction=0.03 => le texte fait toujours
3 % de la hauteur de la fenetre, quelle que soit la resolution.
"""
from kivy.core.window import Window

# Multiplicateur GLOBAL de la taille du texte (1.0 = normal). On l'augmente
# pour grossir toutes les ecritures du jeu d'un coup.
FONT_SCALE = 1.3


def font_for(fraction, minimum=10):
    """Taille de police (px) correspondant a une fraction de la hauteur."""
    return max(minimum, Window.height * fraction * FONT_SCALE)


def scale_font(widget, fraction, minimum=10):
    """Fait suivre la police du widget a la hauteur de la fenetre.

    Retourne le widget pour pouvoir l'utiliser directement a la creation :
        layout.add_widget(scale_font(Label(text="Titre"), 0.035))
    """
    def _update(*_):
        widget.font_size = font_for(fraction, minimum)

    _update()
    # `on_resize` est l'evenement fiable quand la fenetre change de taille
    # (binder `height` ne se declenche pas toujours : c'est une AliasProperty).
    Window.bind(on_resize=_update)
    return widget
