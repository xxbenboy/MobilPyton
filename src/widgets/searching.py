"""
LES MAINS QUI FOUILLENT : l'animation d'exploration.

Le joueur fouille les environs. Ses deux mains ne font pas la meme chose au
meme moment : l'une descend pendant que l'autre remonte, puis l'inverse. C'est
cette ALTERNANCE qui se lit comme "il cherche" ; deux mains qui monteraient et
descendraient ensemble donneraient un haussement d'epaules.

UNE SEULE IMAGE, PAS UNE SUITE. L'ancienne exploration alternait entre deux
dessins figes (HandEx1 / HandEx2) : le mouvement sautait d'une pose a l'autre,
et il fallait fournir une image de plus pour chaque variante (les gants, par
exemple). Ici, l'image de fouille est unique et c'est le CODE qui la fait
monter et descendre, chaque main de son cote. Le mouvement est donc continu,
et une nouvelle paire de gants ne demande qu'une image au lieu de deux.

LE MOUVEMENT EST DONNE EN FRACTION DE L'ACTION (0 au debut, 1 a la fin), pas
en secondes. L'exploration dure 1,5 s a l'ecran aujourd'hui ; si cette duree
change un jour, l'animation gardera exactement le meme dessin, simplement plus
lent ou plus rapide. Avec une cadence en secondes, une exploration plus courte
se serait arretee au milieu d'un geste.
"""
import math

# Nombre d'ALLERS-RETOURS complets sur la duree de l'action.
# 1,5 donne TROIS temps forts : une main descend, l'autre descend pendant que
# la premiere remonte, puis la premiere redescend -- et l'on s'arrete. C'est le
# minimum pour que l'alternance se lise comme un va-et-vient et non comme un
# simple soubresaut.
ALTERNATIONS = 1.5

# Adoucissement des extremites. Le mouvement part de zero et y revient : sans
# cela, les mains SAUTERAIENT en place au debut de l'exploration et de nouveau
# a la fin, au moment de reprendre la pose de repos.
# L'exposant aplatit le sommet de l'enveloppe : les temps forts du milieu
# gardent presque toute leur ampleur, seuls les bords sont retenus.
_ADOUCI = 0.55


def envelope(frac):
    """Ampleur du mouvement a cet instant de l'action : 0 aux deux bouts."""
    if frac <= 0.0 or frac >= 1.0:
        return 0.0
    return math.sin(math.pi * frac) ** _ADOUCI


def offset(frac):
    """(gauche, droite) dans [-1, 1] : le decalage vertical de chaque main.

    Les deux valeurs sont exactement OPPOSEES : quand l'une descend, l'autre
    monte. A multiplier par l'amplitude voulue (voir player_hands).

    En dehors de l'action, les deux valent 0 : les mains sont alors a leur
    place normale, et reprendre la pose de repos ne fait aucun a-coup."""
    if frac is None or frac <= 0.0 or frac >= 1.0:
        return (0.0, 0.0)
    a = envelope(frac) * math.sin(math.tau * ALTERNATIONS * frac)
    # La GAUCHE descend en premier (signe moins) : il faut bien en choisir une,
    # et commencer par la gauche laisse la droite -- la main qui tient le plus
    # souvent un objet -- terminer en haut.
    return (-a, a)


def beats():
    """Instants (en fraction de l'action) des temps forts, et quelle main est
    alors en bas. Sert a verifier que l'alternance est bien celle voulue."""
    out = []
    n = 2000
    prev = offset(0.0)[0]
    montait = None
    for i in range(1, n + 1):
        cur = offset(i / n)[0]
        monte = cur > prev
        if montait is not None and monte != montait:
            out.append(((i - 1) / n, "gauche" if prev < 0 else "droite"))
        montait = monte
        prev = cur
    return out
