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
    # Huit pierres, posees en cercle par le mini-jeu (voir
    # minijeux.MiniJeuFeu).
    {"result": "Feu_de_camp", "objets": {"Pierre": 8}, "minijeu": "feu"},
]

# L'EQUIPEMENT EN FEUILLE : une seule liste d'objets pour les cinq pieces --
# quatre feuilles, deux branches, une corde, et le couteau qui perce (un
# outil). C'est LA FORME DES QUATRE FEUILLES dans la vue d'assemblage qui dit
# quelle piece on fabrique ; les branches, la corde et le couteau se collent
# ou l'on veut. Chaque forme ressemble a sa piece (y vers le haut) :
#
#   Casque   . X .      un dome : une rangee, une feuille dessus au milieu
#            X X X
#
#   Veste    X X X      les epaules et les manches, le corps dessous
#            . X .
#
#   Pantalon X . X      deux jambes (collees ou non : X X / X X aussi)
#            X . X
#
#   Gants    X .        la main et le pouce sur le cote (d'un cote ou de
#            X X        l'autre)
#            X .
#
#   Souliers X . .      une botte : le pied, et la tige a un bout (d'un cote
#            X X X      ou de l'autre)
FEUILLE = "Feuille"
FORMES_FEUILLE = {
    "Casque_De_Feuille": ({(0, 0), (1, 0), (2, 0), (1, 1)},),
    "Veste_De_Feuille": ({(0, 1), (1, 1), (2, 1), (1, 0)},),
    "Pantalon_De_Feuille": ({(0, 0), (0, 1), (2, 0), (2, 1)},
                            {(0, 0), (0, 1), (1, 0), (1, 1)}),
    "Gant_De_Feuille": ({(0, 0), (0, 1), (0, 2), (1, 1)},
                        {(1, 0), (1, 1), (1, 2), (0, 1)}),
    "Soulier_De_Feuille": ({(0, 0), (1, 0), (2, 0), (0, 1)},
                           {(0, 0), (1, 0), (2, 0), (2, 1)}),
}
EQUIPEMENT_FEUILLE = {
    "result": None, "famille": "feuille",
    "objets": {FEUILLE: 4, "Small_Stick": 2, COUTEAU_EN_PIERRE: 1,
               "Corde": 1},
    "outils": {COUTEAU_EN_PIERRE: 0.10},
    "minijeu": "feuille", "formes": FORMES_FEUILLE,
}
ASSEMBLAGES.append(EQUIPEMENT_FEUILLE)

# LA FIBRE VEGETALE : un couteau en pierre et trois brins, herbes ou feuilles
# dans n'importe quelle proportion (3 herbes, 2 herbes et 1 feuille, ...). Le
# couteau y laisse un dixieme de sa solidite, comme tout mini-jeu.
BRINS_FIBRE = 3
USURE_FIBRE = 0.10          # un mini-jeu use le couteau de 10 %
RECETTES_FIBRE = [
    {"result": "Fibre_Vegetale",
     "objets": {k: v for k, v in (("Herbe", h), ("Feuille", BRINS_FIBRE - h),
                                  (COUTEAU_EN_PIERRE, 1)) if v},
     "outils": {COUTEAU_EN_PIERRE: USURE_FIBRE}, "minijeu": "fibre"}
    for h in range(BRINS_FIBRE, -1, -1)]
ASSEMBLAGES[3:3] = RECETTES_FIBRE

# Le plus de CASES qu'une recette peut prendre, a mains nues (le plan fait
# 2 x 2). Une matiere qui s'empile n'en prend qu'une (voir cases_requises).
OBJETS_MAX = 4


def cases_requises(recette):
    """Combien de cases du plan cette recette occupe : une par matiere qui
    s'empile, une par exemplaire pour les autres."""
    from src import items
    return sum(1 if items.empilable_au_plan(n) else c
               for n, c in recette["objets"].items())


def forme(points):
    """Les points (en tailles d'objet) ramenes a des cases entieres, le coin
    bas gauche en (0, 0) : un ensemble de (colonne, rangee)."""
    if not points:
        return set()
    x0 = min(x for x, _y in points)
    y0 = min(y for _x, y in points)
    return {(int(round(x - x0)), int(round(y - y0))) for x, y in points}


def selon_forme(recette, points):
    """L'objet d'une famille (voir EQUIPEMENT_FEUILLE) que dessinent ces
    points, ou None."""
    f = forme(points)
    if len(f) != len(points):
        return None
    for objet, formes in recette["formes"].items():
        if f in formes:
            return objet
    return None


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


def valide(objets, liens, position=None):
    """La recette realisee par ces objets ({"nom": ...}) et leurs contacts
    dans la vue d'assemblage, ou None si l'un d'eux n'est colle a rien.

    Pour une FAMILLE (l'equipement en feuille), c'est la forme des feuilles
    qui choisit l'objet : `position(objet)` rend sa place en tailles
    d'objet. La recette rendue est alors une copie, son objet renseigne."""
    r = selon_objets([o["nom"] for o in objets])
    if r is None or not chacun_colle(objets, liens):
        return None
    if r.get("famille"):
        if position is None:
            return None
        objet = selon_forme(r, [position(o) for o in objets
                                if o["nom"] == FEUILLE])
        if objet is None:
            return None
        r = dict(r, result=objet)
    return r


__all__ = ["ASSEMBLAGES", "COUTEAU_EN_PIERRE", "selon_objets", "valide",
           "tous_colles", "chacun_colle", "compte"]
