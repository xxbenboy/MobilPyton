"""
LES ASSEMBLAGES : ce que l'on fabrique en disposant des objets sur le plan de
travail.

Une recette dit QUELS objets il faut (et combien). Leur disposition dans la
vue d'assemblage est libre : il suffit que CHAQUE objet soit colle a au
moins un autre (voir Assemblage.contacts), peu importe par quelles cases.

A CHAQUE FOIS, il faut reussir le mini-jeu de l'objet (voir minijeux.py).
Une fois fabrique au moins une fois, l'objet est CONNU : l'ecran de craft le
montre a droite au lieu d'un "?".
"""
COUTEAU_EN_PIERRE = "Couteau_En_Pierre"

# A MAINS NUES, LE PLAN DE TRAVAIL FAIT 2 x 2 : une recette demande QUATRE
# OBJETS AU PLUS. Les anciennes recettes qui en demandaient davantage
# attendent un meilleur etabli (voir recettes_archive.py).
#
# "outils" : des objets qui doivent etre sur le plan mais NE SONT PAS
# consommes ; ils perdent cette part de leur solidite et retournent a la
# proximite (ou se brisent, uses jusqu'au bout).
ASSEMBLAGES = [
    # Deux pierres collees : l'une taille l'autre en lame.
    {"result": COUTEAU_EN_PIERRE, "objets": {"Pierre": 2},
     "minijeu": "couteau"},
    # Le couteau emmanche au bout d'un long baton, ligature a la corde.
    {"result": "Lance",
     "objets": {"Long_Stick": 1, COUTEAU_EN_PIERRE: 1, "Corde": 1}},
    # Un silex et une pierre pour battre le feu.
    {"result": "Allume_feu", "objets": {"Silex": 1, "Pierre": 1}},
    # Trois brins -- herbes ou feuilles, melangees comme on veut -- effiloches
    # au couteau (voir RECETTES_FIBRE plus bas).
    # Trois fibres tressees.
    {"result": "Corde", "objets": {"Fibre_Vegetale": 3}},
]

# LA FIBRE VEGETALE : un couteau en pierre et trois brins, herbes ou feuilles
# dans n'importe quelle proportion (3 herbes, 2 herbes et 1 feuille, ...). Le
# couteau y laisse un quart de sa solidite.
BRINS_FIBRE = 3
USURE_FIBRE = 0.25
RECETTES_FIBRE = [
    {"result": "Fibre_Vegetale",
     "objets": {k: v for k, v in (("Herbe", h), ("Feuille", BRINS_FIBRE - h),
                                  (COUTEAU_EN_PIERRE, 1)) if v},
     "outils": {COUTEAU_EN_PIERRE: USURE_FIBRE}, "minijeu": "fibre"}
    for h in range(BRINS_FIBRE, -1, -1)]
ASSEMBLAGES[3:3] = RECETTES_FIBRE

# Le plus d'objets qu'une recette peut demander, a mains nues.
OBJETS_MAX = 4


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


def chacun_colle(objets, liens):
    """Chaque objet est-il colle a au moins un autre ?"""
    if len(objets) < 2:
        return False
    return all(any(a is o or b is o for a, b in liens) for o in objets)


def valide(objets, liens):
    """La recette realisee par ces objets ({"nom": ...}) et leurs contacts
    dans la vue d'assemblage, ou None si l'un d'eux n'est colle a rien."""
    r = selon_objets([o["nom"] for o in objets])
    if r is None or not chacun_colle(objets, liens):
        return None
    return r


__all__ = ["ASSEMBLAGES", "COUTEAU_EN_PIERRE", "selon_objets", "valide",
           "tous_colles", "chacun_colle", "compte"]
