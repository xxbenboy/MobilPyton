"""
Objets, trouvailles par zone, et recettes de craft.

Chaque objet a un NOM court (ex. "branche", "pierre", "couteau"). Son image
est cherchee dans assets/items/<nom>.png (voir assets/items/LISEZMOI.txt).
Si l'image n'existe pas encore, l'interface affiche un "?" avec le nom dessous.
"""
import os
import random as _random

_HERE = os.path.dirname(os.path.abspath(__file__))
ITEMS_DIR = os.path.abspath(os.path.join(_HERE, "..", "assets", "items"))


def image_path(name):
    """Chemin de l'image de l'objet si elle existe, sinon None."""
    for ext in (".png", ".jpg", ".jpeg"):
        p = os.path.join(ITEMS_DIR, name + ext)
        if os.path.isfile(p):
            return p
    return None


def display_name(name):
    """Nom lisible : 'feu_de_camp' -> 'Feu de camp'."""
    return name.replace("_", " ").capitalize()


# Objets trouvables par type de zone : (nom, poids).
# Le POIDS = rarete relative. Plus il est grand, plus l'objet est frequent.
# Ex : une branche ou une pierre (poids eleve) sont communes ; une carcasse
# (poids 1) est rare.
ZONE_FINDS = {
    "Foret": [("branche", 12), ("feuille", 10), ("pierre", 7),
              ("champignon", 4), ("baie", 4), ("plume", 2), ("carcasse", 1)],
    "Plaine": [("herbe", 12), ("fleur", 7), ("branche", 6), ("pierre", 5),
               ("baie", 3), ("plume", 2), ("carcasse", 1)],
    "Montagne": [("pierre", 12), ("branche", 4), ("minerai", 3),
                 ("os", 2), ("carcasse", 1)],
    "Lac": [("roseau", 9), ("poisson", 7), ("pierre", 4), ("branche", 3),
            ("coquillage", 2), ("carcasse", 1)],
}


def random_find(zone, rng=None):
    """Tire un objet au hasard selon la zone, pondere par la rarete."""
    rng = rng or _random
    table = ZONE_FINDS.get(zone, ZONE_FINDS["Foret"])
    names = [name for name, _ in table]
    weights = [weight for _, weight in table]
    return rng.choices(names, weights=weights, k=1)[0]


# Recettes : resultat <- ingredients (objet: quantite).
RECIPES = [
    {"result": "couteau", "ingredients": {"pierre": 1, "branche": 1}},
    {"result": "hache", "ingredients": {"pierre": 1, "branche": 2}},
    {"result": "lance", "ingredients": {"branche": 1, "couteau": 1}},
    {"result": "feu_de_camp", "ingredients": {"branche": 3, "pierre": 2}},
]
