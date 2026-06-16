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


# Objets trouvables par type de zone (nom, poids).
ZONE_FINDS = {
    "Foret": [("branche", 4), ("feuille", 4), ("pierre", 2),
              ("champignon", 2), ("baie", 2)],
    "Plaine": [("herbe", 4), ("branche", 2), ("pierre", 2),
               ("baie", 2), ("fleur", 2)],
    "Montagne": [("pierre", 5), ("branche", 1), ("minerai", 2)],
    "Lac": [("roseau", 3), ("poisson", 3), ("pierre", 2), ("branche", 1)],
}


def random_find(zone, rng=None):
    """Tire un objet au hasard selon la zone."""
    rng = rng or _random
    table = ZONE_FINDS.get(zone, ZONE_FINDS["Foret"])
    pool = [name for name, weight in table for _ in range(weight)]
    return rng.choice(pool)


# Recettes : resultat <- ingredients (objet: quantite).
RECIPES = [
    {"result": "couteau", "ingredients": {"pierre": 1, "branche": 1}},
    {"result": "hache", "ingredients": {"pierre": 1, "branche": 2}},
    {"result": "lance", "ingredients": {"branche": 1, "couteau": 1}},
    {"result": "feu_de_camp", "ingredients": {"branche": 3, "pierre": 2}},
]
