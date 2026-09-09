"""
LES MAINS PENDANT L'EXPLORATION.

Le joueur fouille les environs. Ses mains ne CHANGENT PAS de pose pour
autant : elles gardent celle du repos, simplement ABAISSEES -- comme si on
les avait avancees devant soi -- et animees d'un va-et-vient rapide.

POURQUOI PAS DE POSE PARTICULIERE. Une image de "fouille" a bien ete
essayee : les mains changeaient d'aspect au debut de l'action et le
reprenaient a la fin. Ces deux ruptures se voyaient plus que le geste
lui-meme. Garder la meme main et ne bouger que sa POSITION donne un
mouvement continu, sans aucune bascule -- et supprime du meme coup une image
a fournir pour chaque variante des mains (les gants, par exemple).

LE MOUVEMENT NE MONTE JAMAIS. Il part du bas de l'ecran vers le bas : les
mains descendent, oscillent, et remontent a leur place. C'est indispensable,
pas decoratif : les bras des images s'arretent au bord inferieur du cadre, et
tout ce qui les ferait monter decouvrirait du VIDE en dessous.

CONSTANT, PAS IMPREVISIBLE -- l'inverse exact du souffle (voir breathing.py).
Le souffle doit se faire oublier, donc son rythme derive sans cesse. Ici on
veut un geste VOLONTAIRE, repetitif, qu'on remarque : une sinusoide pure, de
periode fixe. Et le rythme est compte en SECONDES REELLES, pas en fraction de
l'action : si la duree de l'exploration change un jour, la cadence des mains,
elle, ne changera pas.
"""
import math

# Duree d'un aller-retour, en secondes reelles. Bien plus rapide que le
# souffle (4,2 s) : c'est ce qui distingue "il s'active" de "il respire".
# L'exploration dure 1,5 s a l'ecran, soit cinq allers-retours.
PERIOD = 0.30

# Part de l'amplitude consacree au VA-ET-VIENT ; le reste est l'abaissement
# constant. A 0.45, les mains restent toujours entre 55 % et 100 % de
# l'abaissement : le va-et-vient se voit bien, mais elles ne remontent jamais
# jusqu'a leur position de repos en cours d'action.
SWING = 0.45

# Adoucissement des extremites : le mouvement part de zero et y revient. Sans
# lui, les mains SAUTERAIENT en place au debut de l'exploration et de nouveau
# a la fin. L'exposant aplatit le sommet -- le milieu de l'action garde
# presque tout l'abaissement, seuls les bords sont retenus.
_ADOUCI = 0.55


def envelope(frac):
    """Ampleur du mouvement a cet instant de l'action : 0 aux deux bouts."""
    if frac is None or frac <= 0.0 or frac >= 1.0:
        return 0.0
    return math.sin(math.pi * frac) ** _ADOUCI


def offset(t, frac):
    """Decalage vertical des mains, dans [-1, 0].

    `t`    : temps ecoule, en secondes reelles (donne la cadence) ;
    `frac` : avancement de l'action, de 0 a 1 (donne l'entree et la sortie),
             ou None hors exploration.

    Le resultat est toujours NEGATIF ou nul : les mains descendent, jamais
    l'inverse. A multiplier par l'amplitude voulue (voir player_hands)."""
    env = envelope(frac)
    if env <= 0.0:
        return 0.0
    # va va de 0 (bas du mouvement) a SWING (haut du mouvement).
    va = SWING * 0.5 * (1.0 + math.sin(math.tau * t / PERIOD))
    return env * (va - 1.0)


def span():
    """(le plus haut, le plus bas) que le mouvement puisse atteindre.

    Sert a verifier que rien ne remonte au-dessus de la position de repos :
    la borne haute doit valoir 0."""
    return (0.0, -1.0)
