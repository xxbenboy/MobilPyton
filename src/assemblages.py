"""
LES ASSEMBLAGES : ce que l'on fabrique en disposant des objets sur le plan de
travail.

Une recette dit QUELS objets il faut (et combien), et COMMENT ils doivent
etre places dans la vue d'assemblage : pour l'instant, tous colles les uns
aux autres (voir Assemblage.liens), peu importe par quelles cases.

LA PREMIERE FOIS, il faut reussir le mini-jeu de l'objet (voir minijeux.py).
Une fois fabrique au moins une fois, l'objet est CONNU : l'ecran de craft le
montre a droite au lieu d'un "?", et l'assembler ne demande plus le
mini-jeu.
"""
COUTEAU_EN_PIERRE = "Couteau_En_Pierre"

ASSEMBLAGES = [
    # Deux pierres collees : l'une taille l'autre en lame.
    {"result": COUTEAU_EN_PIERRE, "objets": {"Pierre": 2},
     "minijeu": "couteau"},
]


def compte(noms):
    """{nom: nombre} d'une liste de noms."""
    total = {}
    for n in noms:
        total[n] = total.get(n, 0) + 1
    return total


def selon_objets(noms):
    """La recette qui demande EXACTEMENT ces objets, ou None. Ne regarde pas
    leur disposition : c'est ce que l'ecran de craft montre a droite."""
    total = compte(noms)
    for r in ASSEMBLAGES:
        if r["objets"] == total:
            return r
    return None


def tous_colles(objets, liens):
    """Les objets forment-ils un seul bloc, de lien en lien ?"""
    if not objets:
        return False
    vus = [objets[0]]
    a_voir = [objets[0]]
    while a_voir:
        o = a_voir.pop()
        for a, b in liens:
            autre = b if a is o else (a if b is o else None)
            if autre is not None and not any(autre is v for v in vus):
                vus.append(autre)
                a_voir.append(autre)
    return len(vus) == len(objets)


def valide(objets, liens):
    """La recette realisee par ces objets ({"nom": ...}) et leurs liens dans
    la vue d'assemblage, ou None s'ils ne sont pas bien places."""
    r = selon_objets([o["nom"] for o in objets])
    if r is None or not tous_colles(objets, liens):
        return None
    return r


__all__ = ["ASSEMBLAGES", "COUTEAU_EN_PIERRE", "selon_objets", "valide",
           "tous_colles", "compte"]
