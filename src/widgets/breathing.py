"""
LE SOUFFLE DU JOUEUR : le mouvement lent des mains, en permanence.

Un decor immobile a l'ecran se lit comme une image ; il suffit que les mains
respirent pour qu'il y ait quelqu'un derriere. C'est le mouvement qui donne
un corps au joueur, pas le dessin des mains.

DEUX EXIGENCES QUI SE CONTREDISENT, et tout le module est la pour les tenir
ensemble :

- TOUJOURS LA. Le souffle ne doit jamais mollir ni s'arreter : une respiration
  qui s'eteint par moments donne l'impression d'un bug d'animation, pas d'un
  personnage calme.
- IMPREVISIBLE. Une sinusoide pure se repere en trois cycles : l'oeil attrape
  la boucle et le mouvement devient mecanique -- pire que pas de mouvement du
  tout, parce qu'il attire l'attention sur lui.

La solution N'EST PAS de faire varier l'AMPLITUDE (somme de sinusoides
d'ecarts irrationnels) : cela produit des battements, donc des moments ou le
souffle est presque plat. C'est exactement ce qu'il ne faut pas.

On fait donc varier le RYTHME, jamais la profondeur. La phase avance a
vitesse legerement variable -- le souffle s'allonge, se raccourcit, repart --
mais chaque inspiration va toujours jusqu'au bout. L'amplitude reste
exactement 1, la duree d'un cycle change sans cesse et ne se repete jamais
(les trois frequences de derive sont sans rapport simple entre elles).

Ce module est de la pure arithmetique : il ne connait ni Kivy ni l'ecran, et
se verifie donc seul.
"""
import math

# Duree moyenne d'un cycle, en secondes reelles. ~14 respirations par minute :
# le rythme d'un adulte au repos. Plus court, le personnage parait haletant.
PERIOD = 4.2

# DERIVE DU RYTHME : (frequence en Hz, ampleur en radians de phase).
# Ces trois frequences sont volontairement sans rapport simple entre elles
# (pas de 2x, pas de 3x) : leur somme ne revient donc jamais au meme point,
# et aucun cycle ne ressemble tout a fait au precedent.
#
# Elles sont TOUTES beaucoup plus lentes que la respiration elle-meme : ce
# qu'on percoit n'est pas un tremblement mais un souffle qui prend son temps,
# puis se presse un peu. Leur effet cumule sur la VITESSE reste sous les 12 %
# (voir rate_span) -- assez pour tromper l'oeil, trop peu pour se voir comme
# une acceleration.
_DRIFT = (
    (0.0310, 0.55),
    (0.0170, 0.38),
    (0.0073, 0.30),
)

# Decalages de depart, pour que les trois ondes ne partent pas ensemble.
_PHASES = (0.0, 2.399, 4.113)

# ASYMETRIE du souffle. Une sinusoide monte et descend a la meme vitesse ; un
# vrai souffle inspire vite et relache lentement. On ajoute donc une pointe de
# deuxieme harmonique, qui creuse ce desequilibre sans changer la periode.
_SKEW = 0.18


def _brut(theta):
    return math.sin(theta) + _SKEW * math.sin(2.0 * theta)


# L'asymetrie change le maximum de la courbe : on le mesure une fois pour
# toutes et on divise par lui. L'amplitude vaut ainsi exactement 1, quelle que
# soit la valeur donnee a _SKEW.
_PEAK = max(abs(_brut(i * math.tau / 2048.0)) for i in range(2048))


def phase(t):
    """Ou en est le souffle a l'instant `t`, en radians.

    C'est ici que se joue l'imprevisibilite : la phase n'avance pas
    regulierement, elle est decalee par trois ondes lentes. Comme la vitesse
    est la DERIVEE de cette phase, decaler la phase revient a accelerer et
    ralentir le souffle -- sans jamais toucher a sa profondeur."""
    theta = math.tau * t / PERIOD
    for (freq, poids), depart in zip(_DRIFT, _PHASES):
        theta += poids * math.sin(math.tau * freq * t + depart)
    return theta


def depth(t):
    """Profondeur du souffle a l'instant `t`, dans [-1, 1].

    -1 = poumons vides (mains au plus bas), +1 = pleins (au plus haut)."""
    return _brut(phase(t)) / _PEAK


def offset(t):
    """(dx, dy) dans [-1, 1] : le deplacement du souffle a l'instant `t`.

    A multiplier par l'amplitude voulue (voir player_hands). Le VA-ET-VIENT
    LATERAL est deux fois plus lent que le souffle : le buste ne se balance
    pas au rythme des poumons, il derive plus lentement. C'est ce decalage qui
    empeche le mouvement de se lire comme un simple haut-bas."""
    return (math.cos(phase(t) * 0.5 + 0.7), depth(t))


def rate(t):
    """Vitesse du souffle a l'instant `t`, en radians par seconde.

    Sert a verifier que le souffle ne s'arrete jamais et ne repart jamais en
    arriere : la vitesse doit rester franchement positive."""
    v = math.tau / PERIOD
    for (freq, poids), depart in zip(_DRIFT, _PHASES):
        v += poids * math.tau * freq * math.cos(math.tau * freq * t + depart)
    return v


def rate_span():
    """(vitesse mini, vitesse maxi, ecart en %) que le rythme peut atteindre.

    Bornes THEORIQUES : on additionne les trois derives au pire cas, sans
    supposer qu'elles se croisent vraiment. Si la borne basse est positive,
    le souffle ne peut pas s'arreter, quelle que soit l'heure."""
    base = math.tau / PERIOD
    ecart = sum(poids * math.tau * freq for freq, poids in _DRIFT)
    return base - ecart, base + ecart, 100.0 * ecart / base
