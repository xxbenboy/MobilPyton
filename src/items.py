"""
Objets, trouvailles par zone, et recettes de craft.

Chaque objet a un NOM court (ex. "Small_Stick", "Pierre", "Couteau"). Son image
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


# Objets qui ne peuvent PAS etre tenus en main : quand on les trouve ils
# restent AU SOL, et on ne peut pas les ramasser dans la main. (Vide pour
# l'instant : tous les objets sont ramassables. A completer plus tard.)
GROUND_ONLY = set()


def is_hand_collectable(name):
    """Vrai si l'objet peut etre pris en main (faux = reste au sol)."""
    return name not in GROUND_ONLY


# Objets trouvables par type de zone : (nom, poids).
# Le POIDS = rarete relative. Plus il est grand, plus l'objet est frequent.
# Ex : une Small_Stick ou une Pierre (poids eleve) sont communes ; une Carcasse
# (poids 1) est rare.
ZONE_FINDS = {
    "Foret": [("Small_Stick", 12), ("Long_Stick", 4), ("Loafy_Long_Stick", 4), ("Feuille", 10), ("Pierre", 7),
              ("Champignon", 4), ("Baie", 4), ("Plume", 2), ("Carcasse", 1)],
    "Plaine": [("Herbe", 12), ("Fleur", 7), ("Small_Stick", 6), ("Long_Stick", 2), ("Pierre", 5),
               ("Baie", 3), ("Plume", 2), ("Carcasse", 1)],
    "Montagne": [("Pierre", 12), ("Small_Stick", 4), ("Long_Stick", 2), ("Pierre_Coupante", 3),
                 ("Os", 2), ("Carcasse", 1)],
    "Lac": [("Roseau", 9), ("Poisson", 7), ("Pierre", 4), ("Small_Stick", 3), ("Long_Stick", 1),
            ("Coquillage", 2), ("Carcasse", 1)],
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
    {"result": "Couteau", "ingredients": {"Pierre": 1, "Small_Stick": 1}},
    {"result": "Hache", "ingredients": {"Pierre": 1, "Long_Stick": 1, "Small_Stick": 1}},
    {"result": "Lance", "ingredients": {"Long_Stick": 1, "Couteau": 1}},
    {"result": "Feu_de_camp", "ingredients": {"Small_Stick": 3, "Pierre": 2}},
]
