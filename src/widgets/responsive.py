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


# --------------------------------------------------------------------- #
# GABARIT COMMUN AUX ECRANS INVENTAIRE ET CRAFT
# --------------------------------------------------------------------- #
# Les deux ecrans se repondent par un titre a deux volets : on passe de l'un
# a l'autre d'un seul toucher. Leurs colonnes doivent donc tomber EXACTEMENT
# au meme endroit, sinon tout saute a chaque bascule. Les mesures vivent ici,
# a un seul endroit, plutot qu'en double dans les deux fichiers ou elles
# auraient fini par diverger.
#
# Ce sont des poids de BoxLayout vertical : Kivy les normalise par leur SOMME.
# Ils valent donc les uns par rapport aux autres, et il ne sert a rien de
# chercher a les faire totaliser 1 -- mais les deux ecrans doivent porter la
# MEME LISTE, sinon les hauteurs different.
SIDE_SHARE = 0.26          # largeur de la colonne de gauche (a proximite)

ROW_TITLE = 0.07           # le titre a deux volets
ROW_BODY = 0.76            # les trois colonnes
ROW_HANDS = 0.16           # les deux mains, en bas
ROW_HINT = 0.05            # la ligne d'explication
ROW_BACK = 0.09            # le bouton Retour

COL_TITLE = 0.09           # titre d'une colonne
COL_LIST = 0.91            # sa liste, dessous


def center_share():
    """Largeur des colonnes du CENTRE et de DROITE : elles se partagent a
    egalite tout ce que la colonne de gauche ne prend pas."""
    return (1.0 - SIDE_SHARE) / 2.0


# --------------------------------------------------------------------- #
# TAILLE DU TEXTE : une seule regle pour tout le jeu
# --------------------------------------------------------------------- #
# `scale_font` fait REMPLIR LA HAUTEUR de sa boite au texte. C'est ce qu'on
# veut pour un titre ou un bouton, dont la hauteur EST la taille voulue. Mais
# applique a un message pose dans une boite haute, il donnait une police
# enorme, qui debordait de sa colonne et se faisait rogner.
#
# `fit_text` part au contraire d'une taille de REFERENCE commune, puis la
# reduit tant que le texte ne tient pas. Trois limites, la plus petite gagne :
# la reference, la hauteur disponible par ligne, et la largeur reelle du texte
# une fois rendu. Deux libelles ecrits a la meme echelle sortent donc a la
# meme taille d'un ecran a l'autre.

# Taille de reference : la hauteur d'une ligne de liste (dh(70)), dont le
# texte occupe 46 %. Toutes les echelles ci-dessous en partent.
TEXT_REF = 70
TEXT_BASE = 0.46

# Echelles courantes, pour que les memes roles gardent la meme taille partout.
TEXT_TITLE = 1.30      # nom d'un objet, en-tete
TEXT_NORMAL = 1.00     # texte courant
TEXT_SMALL = 0.80      # detail, precision

# Marges : on ne remplit jamais la boite a ras bord.
_H_ROOM = 0.90
_W_ROOM = 0.96
# Bornes de la reduction quand le texte est renvoye a la ligne.
_WRAP_STEPS = 12
_WRAP_FACTOR = 0.92


def fit_text(widget, scale=TEXT_NORMAL, wrap=False, minimum=9):
    """Ecrit `widget` a la plus grande taille qui TIENNE dans sa boite.

    `wrap=True` : le texte est renvoye a la ligne dans la largeur, et c'est sa
    hauteur totale qui commande. A utiliser pour les phrases ; sans cela, un
    message un peu long serait reduit a un filet illisible pour tenir sur une
    seule ligne."""
    def _update(*_):
        if widget.width <= 1 or widget.height <= 1:
            return
        target = dh(TEXT_REF) * TEXT_BASE * scale
        if wrap:
            widget.text_size = (widget.width * _W_ROOM, None)
            widget.font_size = max(minimum, target)
            widget.texture_update()
            steps = 0
            while (widget.texture_size[1] > widget.height * _H_ROOM
                   and widget.font_size > minimum and steps < _WRAP_STEPS):
                widget.font_size = max(minimum,
                                       widget.font_size * _WRAP_FACTOR)
                widget.texture_update()
                steps += 1
            return
        lines = (widget.text or "").count("\n") + 1
        target = min(target, widget.height * _H_ROOM / lines)
        widget.text_size = (None, None)
        widget.font_size = target
        widget.texture_update()
        if widget.texture_size[0] > widget.width * _W_ROOM:
            target = target * widget.width * _W_ROOM / widget.texture_size[0]
        widget.font_size = max(minimum, target)
        widget.text_size = (widget.width, widget.height)

    _update()
    widget.bind(size=_update, text=_update)
    return widget
