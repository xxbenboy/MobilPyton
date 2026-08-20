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

# Objets speciaux (a CRAFTER plus tard, indisponibles pour l'instant) :
# - CARTE   : necessaire pour ouvrir l'ecran carte.
# - BOUSSOLE: affiche les directions en points cardinaux (Nord/Sud/Est/Ouest)
#             au lieu de directions relatives (En face/Derriere/Gauche/Droite).
MAP_ITEM = "Carte"
COMPASS_ITEM = "Boussole"

# Outils requis pour certaines actions :
# - une HACHE (en main) pour couper du bois,
# - une GOURDE (possedee) pour remplir/transporter de l'eau.
AXE_ITEM = "Hache"
GOURDE_ITEMS = {"Gourde"}

# OUTILS A USAGE MULTIPLE : nombre d'utilisations avant de casser. Une hache
# de pierre abat cinq arbres, un couteau taille plus longtemps qu'il ne coupe
# fort. A 0, l'outil se brise et disparait.
TOOL_USES = {
    "Hache": 5,
    "Lance": 12,
    "Couteau": 15,
}


def tool_max_uses(name):
    """Nombre d'utilisations d'un outil neuf (0 = objet sans solidite)."""
    return TOOL_USES.get(name, 0)


def is_tool(name):
    """Vrai si l'objet s'use a l'usage (et affiche donc une barre)."""
    return name in TOOL_USES

# --------------------------------------------------------------------- #
# EQUIPEMENT PORTE
# --------------------------------------------------------------------- #
# Emplacements du personnage, dans l'ordre d'affichage (de la tete aux pieds,
# le sac en dernier).
EQUIP_SLOTS = ("casque", "chandail", "gant", "pantalon", "chaussure", "sac")
EQUIP_SLOT_NAMES = {
    "casque": "Casque",
    "chandail": "Chandail",
    "gant": "Gants",
    "pantalon": "Pantalon",
    "chaussure": "Chaussures",
    "sac": "Sac a dos",
}

# Tenue de depart : les vetements avec lesquels le personnage a survecu. Uses,
# mais ils couvrent le corps. Ni casque, ni gants, ni sac.
STARTING_EQUIPMENT = {
    "chandail": "Chandail_Rescape",
    "pantalon": "Pantalon_Rescape",
    "chaussure": "Chaussures_Rescape",
}

# Nombre d'emplacements apportes par un sac. Sans sac : AUCUNE place, le
# personnage ne transporte que ce qu'il tient dans ses mains.
BAG_CAPACITY = {
    "Sac_De_Fortune": 4,
    "Sac_A_Dos": 8,
}


def bag_capacity(name):
    """Nombre d'emplacements offerts par ce sac (0 = pas un sac)."""
    return BAG_CAPACITY.get(name, 0)


def is_bag(name):
    return name in BAG_CAPACITY


# Objets INSTALLABLES : peuvent etre "utilises" (montes/installes) depuis la
# main via un bouton Utiliser dedie. Une fois installes, ils passent dans
# game_state.installed (pas dans ground) et ne peuvent plus etre ramasses.
INSTALLABLE_ITEMS = {"Feu_de_camp"}

# Objets INTERACTIFS : une fois INSTALLES, on peut s'en servir -- en cliquant
# dessus dans la scene, ou en les choisissant dans l'ecran Proximite. Ils
# ouvrent alors leur fenetre d'action. Seul le feu de camp l'est pour l'instant.
INTERACTIVE_ITEMS = {"Feu_de_camp"}

# ALLUMER un feu : il faut un de ces objets EN MAIN. Deux pierres dures
# frappees l'une contre l'autre suffisent a faire une etincelle, mais un vrai
# allume-feu (a fabriquer, voir RECIPES) donne bien plus de chances.
FIRE_STARTER_BONUS = {
    "Allume_feu": 0.25,
    "Silex": 0.05,
    "Pierre_Coupante": 0.0,
}
FIRE_STARTER_ITEMS = set(FIRE_STARTER_BONUS)


def starter_bonus(name):
    """Bonus de chance d'allumage apporte par l'allume-feu tenu en main."""
    return FIRE_STARTER_BONUS.get(name, 0.0)

# Un foyer se nourrit de DEUX apports distincts, chacun avec son bouton dans
# l'ecran Proximite, mais ils ne jouent PAS le meme role :
#
# - COMBUSTIBLE (branche, buche) : c'est ce qui brule. Il donne la DUREE du
#   feu, en heures de jeu.
# - COMBURANT (feuille, ecorce) : c'est ce qui fait prendre la flamme. Il ne
#   donne aucune duree, il augmente la CHANCE de reussir a allumer. Plus il
#   est de bonne qualite et en quantite, plus le feu part facilement.
FIRE_WOOD_HOURS = {
    "Small_Stick": 0.75,
    "Loafy_Long_Stick": 1.25,
    "Long_Stick": 2.0,
    "Buche": 3.0,
}

# Chance d'allumage ajoutee par chaque apport de comburant (cumulable).
FIRE_TINDER_CHANCE = {
    "Feuille": 0.15,
    "Ecorce": 0.30,
}

# Matieres fournies D'OFFICE en mode debug, quand le joueur n'a rien sous la
# main : une branche pour le combustible, une ecorce pour le comburant.
FIRE_DEFAULT_WOOD = "Long_Stick"
FIRE_DEFAULT_TINDER = "Ecorce"

# Table de compatibilite : tout ce qui peut aller dans un foyer.
FIRE_FUEL_HOURS = dict(FIRE_WOOD_HOURS)


def fuel_hours(name):
    """Duree de combustion apportee par cet objet (0 = pas un combustible)."""
    return FIRE_FUEL_HOURS.get(name, 0.0)


def is_fire_starter(name):
    return name in FIRE_STARTER_ITEMS


def is_hand_collectable(name):
    """Vrai si l'objet peut etre pris en main (faux = reste au sol)."""
    return name not in GROUND_ONLY


# Objets trouvables par type de zone : (nom, poids).
# Le POIDS = rarete relative. Plus il est grand, plus l'objet est frequent.
# Ex : une Small_Stick ou une Pierre (poids eleve) sont communes ; une Carcasse
# (poids 1) est rare.
ZONE_FINDS = {
    "Foret": [("Small_Stick", 12), ("Long_Stick", 4), ("Loafy_Long_Stick", 4), ("Feuille", 10), ("Pierre", 7),
              ("Ecorce", 6), ("Brown_Mushroom", 4), ("Baie", 4), ("Plume", 2), ("Carcasse", 1)],
    "Plaine": [("Herbe", 12), ("Fleur", 7), ("Small_Stick", 6), ("Long_Stick", 2), ("Pierre", 5),
               ("Baie", 3), ("Plume", 2), ("Carcasse", 1)],
    "Montagne": [("Pierre", 12), ("Small_Stick", 4), ("Long_Stick", 2), ("Pierre_Coupante", 3),
                 ("Silex", 3), ("Os", 2), ("Carcasse", 1)],
    "Lac": [("Roseau", 9), ("Poisson", 7), ("Pierre", 4), ("Small_Stick", 3), ("Long_Stick", 1),
            ("Silex", 2), ("Coquillage", 2), ("Carcasse", 1)],
}


def random_find(zone, rng=None):
    """Tire un objet au hasard selon la zone, pondere par la rarete."""
    rng = rng or _random
    table = ZONE_FINDS.get(zone, ZONE_FINDS["Foret"])
    names = [name for name, _ in table]
    weights = [weight for _, weight in table]
    return rng.choices(names, weights=weights, k=1)[0]


# Recettes : resultat <- ingredients (objet: quantite).
# Une recette peut demander, en plus de ses `ingredients` (tous consommes) :
# - "any_of" : une SEULE des matieres listees est consommee (au choix) ;
# - "tool"   : un OUTIL qui doit etre a proximite. Il n'est pas consomme, mais
#              "tool_wear" lui coute une part de sa solidite (0.10 = 10 %).
RECIPES = [
    {"result": "Couteau", "ingredients": {"Pierre": 1, "Small_Stick": 1}},
    {"result": "Fibre_Vegetale", "ingredients": {},
     "any_of": ["Feuille", "Herbe"], "tool": "Couteau", "tool_wear": 0.10},
    {"result": "Corde", "ingredients": {"Fibre_Vegetale": 3}},
    {"result": "Hache",
     "ingredients": {"Pierre": 1, "Small_Stick": 4, "Corde": 1}},
    {"result": "Lance",
     "ingredients": {"Long_Stick": 1, "Couteau": 1, "Corde": 1}},
    {"result": "Feu_de_camp", "ingredients": {"Small_Stick": 3, "Pierre": 2}},
    {"result": "Allume_feu", "ingredients": {"Silex": 1, "Pierre": 1}},
]
