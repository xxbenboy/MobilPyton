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

# Hauteur de la resolution de BASE (cf. main.py : 2340 x 1080 paysage).
BASE_HEIGHT = 1080

# Multiplicateur global pour les calculs bases sur la fenetre (font_for).
FONT_SCALE = 1.3


def dh(design_px):
    """Hauteur PROPORTIONNELLE a la fenetre (et INDEPENDANTE de la densite).

    `design_px` est une taille pensee pour la resolution de base (fenetre de
    1080 de haut). On la met a l'echelle de la fenetre reelle.

    Contrairement a `dp()` (qui multiplie par la densite de l'ecran et donne
    donc des tailles differentes sur PC et sur telephone), `dh()` ne depend QUE
    de la taille de la fenetre : a resolution egale, le rendu est IDENTIQUE sur
    PC et sur telephone. A utiliser pour les hauteurs fixes (lignes de liste...).
    """
    return Window.height / BASE_HEIGHT * design_px

# Part de la HAUTEUR DU CONTENEUR occupee par le texte (par ligne). Proche de
# 1 = le texte remplit au maximum la hauteur de sa boite.
FILL_RATIO = 0.78


def font_for(fraction, minimum=10):
    """Taille de police (px) correspondant a une fraction de la hauteur fenetre.

    Sert encore pour des dimensions de mise en page (hauteur de ligne, etc.).
    """
    return max(minimum, Window.height * fraction * FONT_SCALE)


def scale_font(widget, fraction=None, minimum=10):
    """Fait que le texte REMPLIT la hauteur de son conteneur.

    La police est calculee a partir de la hauteur du widget lui-meme, divisee
    par le nombre de lignes du texte -> le texte occupe au mieux sa boite,
    quelle que soit la taille de l'ecran. (`fraction` est ignore, garde pour
    compatibilite avec les appels existants.)
    """
    def _update(*_):
        text = widget.text or ""
        lines = text.count("\n") + 1
        widget.font_size = max(minimum, widget.height * FILL_RATIO / lines)

    _update()
    widget.bind(height=_update, text=_update)
    return widget
