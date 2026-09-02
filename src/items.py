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
    """Nom lisible : 'feu_de_camp' -> 'Feu de camp'.

    Tolere None (emplacement vide) : renvoie une chaine vide plutot que de
    faire echouer l'affichage."""
    if not name:
        return ""
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
    "Sac_De_Feuille": 6,
    "Sac_A_Dos": 8,
}

# A quel emplacement se porte chaque piece d'equipement.
EQUIP_ITEM_SLOT = {
    # Tenue de depart.
    "Chandail_Rescape": "chandail",
    "Pantalon_Rescape": "pantalon",
    "Chaussures_Rescape": "chaussure",
    # Premiere tenue fabriquable : feuilles liees a la corde.
    "Casque_De_Feuille": "casque",
    "Veste_De_Feuille": "chandail",
    "Gant_De_Feuille": "gant",
    "Pantalon_De_Feuille": "pantalon",
    "Soulier_De_Feuille": "chaussure",
    "Sac_De_Feuille": "sac",
}


def equip_slot(name):
    """Emplacement ou se porte cet objet, ou None s'il ne se porte pas."""
    return EQUIP_ITEM_SLOT.get(name)


def is_equipment(name):
    return name in EQUIP_ITEM_SLOT


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


# Categories des recettes, dans l'ordre d'affichage de l'ecran Craft. Chaque
# categorie s'y replie et se deplie.
RECIPE_CATEGORIES = ("Outils", "Materiaux", "Equipement", "Installations")

# Recettes : resultat <- ingredients (objet: quantite).
# Une recette peut demander, en plus de ses `ingredients` (tous consommes) :
# - "any_of" : une SEULE des matieres listees est consommee (au choix) ;
# - "tool"   : un OUTIL qui doit etre a proximite. Il n'est pas consomme, mais
#              "tool_wear" lui coute une part de sa solidite (0.10 = 10 %).
RECIPES = [
    {"result": "Couteau", "category": "Outils",
     "ingredients": {"Pierre": 1, "Small_Stick": 1}},
    {"result": "Hache", "category": "Outils",
     "ingredients": {"Pierre": 1, "Small_Stick": 4, "Corde": 1}},
    {"result": "Lance", "category": "Outils",
     "ingredients": {"Long_Stick": 1, "Couteau": 1, "Corde": 1}},
    {"result": "Allume_feu", "category": "Outils",
     "ingredients": {"Silex": 1, "Pierre": 1}},
    {"result": "Fibre_Vegetale", "category": "Materiaux", "ingredients": {},
     "any_of": ["Feuille", "Herbe"], "tool": "Couteau", "tool_wear": 0.10},
    {"result": "Corde", "category": "Materiaux",
     "ingredients": {"Fibre_Vegetale": 3}},
    # Premiere tenue : des feuilles maintenues par des batons et de la corde.
    {"result": "Casque_De_Feuille", "category": "Equipement",
     "ingredients": {"Small_Stick": 5, "Feuille": 10, "Corde": 1}},
    {"result": "Veste_De_Feuille", "category": "Equipement",
     "ingredients": {"Small_Stick": 5, "Feuille": 10, "Corde": 1}},
    {"result": "Gant_De_Feuille", "category": "Equipement",
     "ingredients": {"Feuille": 5, "Corde": 1}},
    {"result": "Pantalon_De_Feuille", "category": "Equipement",
     "ingredients": {"Small_Stick": 5, "Feuille": 10, "Corde": 1}},
    {"result": "Soulier_De_Feuille", "category": "Equipement",
     "ingredients": {"Feuille": 5, "Corde": 1}},
    {"result": "Sac_De_Feuille", "category": "Equipement",
     "ingredients": {"Small_Stick": 10, "Feuille": 20, "Corde": 2}},
    {"result": "Feu_de_camp", "category": "Installations",
     "ingredients": {"Small_Stick": 3, "Pierre": 2}},
]


# --------------------------------------------------------------------- #
# FICHES D'OBJET
# --------------------------------------------------------------------- #
# Une phrase par objet. Tout le RESTE de la fiche (recette, zones, solidite,
# duree de combustion...) est CALCULE a partir des tables ci-dessus : la
# fiche ne peut donc pas contredire les regles reelles du jeu.
ITEM_NOTES = {
    # Bois et vegetation
    "Small_Stick": "Une brindille seche. La base de presque tout.",
    "Long_Stick": "Une branche droite, assez solide pour faire un manche.",
    "Loafy_Long_Stick": "Une branche encore feuillue : elle brule moins bien.",
    "Buche": "Un rondin fendu d'un arbre abattu. Il tient toute la nuit.",
    "Ecorce": "Une plaque d'ecorce seche. Elle prend feu au moindre eclat.",
    "Feuille": "Une large feuille. Seche, elle aide la flamme a prendre.",
    "Herbe": "Une touffe d'herbe. Ses fibres se tressent.",
    "Fleur": "Jolie, et rien de plus pour l'instant.",
    "Roseau": "Une tige creuse du bord de l'eau.",
    # Pierres
    "Pierre": "Un caillou quelconque, lourd et utile.",
    "Pierre_Coupante": "Un eclat a l'arete vive. Il coupe, il n'etincelle pas.",
    "Silex": "Une pierre sombre et dure. Frappee, elle crache des etincelles.",
    # Nourriture et trouvailles
    "Baie": "Des baies sauvages. De quoi tromper la faim.",
    "Brown_Mushroom": "Un champignon des sous-bois. Comestible.",
    "Red_Mushroom": "Chapeau rouge a pois blancs. Mieux vaut s'abstenir.",
    "Poisson": "Un poisson du lac. Cru, c'est un pari.",
    "Carcasse": "Les restes d'une bete. Rare, et lourd de viande.",
    "Os": "Un os blanchi par le temps.",
    "Plume": "Une plume tombee d'un oiseau.",
    "Coquillage": "Un coquillage du rivage.",
    # Matieres travaillees
    "Fibre_Vegetale": "Un tas de fibres tirees d'une feuille ou d'une herbe.",
    "Corde": "Un metre de corde tressee. Tout ce qui doit tenir en depend.",
    # Outils
    "Couteau": "Un eclat de pierre emmanche. Il taille plus qu'il ne tranche.",
    "Hache": "Une tete de pierre liee a un manche. De quoi abattre un arbre.",
    "Lance": "Une pointe de pierre au bout d'une longue branche.",
    "Allume_feu": "Un silex prepare. Le meilleur moyen de partir un feu.",
    # Installations
    "Feu_de_camp": "Un cercle de pierres. Chaleur, lumiere, et de quoi cuire.",
    # Tenue de rescape
    "Chandail_Rescape": "Le chandail que tu portais. Dechire, mais c'est le tien.",
    "Pantalon_Rescape": "Un pantalon use jusqu'a la trame.",
    "Chaussures_Rescape": "Des chaussures fatiguees. Elles tiennent encore.",
    # Tenue de feuille
    "Casque_De_Feuille": "Des feuilles liees en calotte. Contre la pluie.",
    "Veste_De_Feuille": "Un plastron de feuilles cousues a la corde.",
    "Gant_De_Feuille": "De quoi ne plus s'ecorcher les mains.",
    "Pantalon_De_Feuille": "Des jambieres de feuilles, mieux que rien.",
    "Soulier_De_Feuille": "Des chaussons de feuilles, doux et fragiles.",
    "Sac_De_Feuille": "Un sac tresse. Enfin de quoi transporter autre chose "
                      "que ses deux mains.",
    "Sac_A_Dos": "Un vrai sac a dos. Introuvable pour l'instant.",
}

# Comment on qualifie une trouvaille selon son poids dans ZONE_FINDS.
_RARITY = ((9, "tres commun"), (5, "commun"), (3, "peu commun"), (0, "rare"))


def _rarity(weight):
    for seuil, mot in _RARITY:
        if weight >= seuil:
            return mot
    return "rare"


def recipe_for(name):
    """Recette qui produit cet objet, ou None."""
    for recipe in RECIPES:
        if recipe.get("result") == name:
            return recipe
    return None


def recipe_inputs(recipe):
    """Matieres d'une recette, ecrites comme dans l'ecran Craft."""
    parts = [f"{display_name(key)} x{count}"
             for key, count in recipe.get("ingredients", {}).items()]
    alts = recipe.get("any_of")
    if alts:
        parts.append(" ou ".join(display_name(a) for a in alts))
    tool = recipe.get("tool")
    if tool:
        cost = int(round(recipe.get("tool_wear", 0.0) * 100))
        parts.append(f"{display_name(tool)} (-{cost} %)")
    return ", ".join(parts)


def zones_for(name):
    """Zones ou l'objet se trouve, de la plus genereuse a la plus avare."""
    found = []
    for zone, table in ZONE_FINDS.items():
        for item, weight in table:
            if item == name:
                found.append((weight, zone))
    found.sort(reverse=True)
    return [f"{zone} ({_rarity(weight)})" for weight, zone in found]


def used_in(name):
    """Objets dont la recette demande celui-ci."""
    out = []
    for recipe in RECIPES:
        if (name in recipe.get("ingredients", {})
                or name in (recipe.get("any_of") or [])
                or name == recipe.get("tool")):
            out.append(recipe["result"])
    return out


def describe(name):
    """Fiche d'un objet : (phrase, [faits]).

    Les faits sont deduits des tables du jeu, jamais recopies a la main :
    changer une recette ou la solidite d'un outil met la fiche a jour toute
    seule."""
    if not name:
        return ("", [])
    facts = []

    slot = equip_slot(name)
    if slot:
        facts.append(f"Se porte : {EQUIP_SLOT_NAMES[slot]}")
    places = bag_capacity(name)
    if places:
        facts.append(f"Sac : {places} emplacements")
    uses = tool_max_uses(name)
    if uses:
        facts.append(f"Outil : {uses} utilisations avant de casser")
    hours = fuel_hours(name)
    if hours:
        facts.append(f"Combustible : {hours:g} h de feu")
    tinder = FIRE_TINDER_CHANCE.get(name)
    if tinder:
        facts.append(f"Comburant : +{int(tinder * 100)} % de chance "
                     f"d'allumer un feu")
    if name in FIRE_STARTER_BONUS:
        bonus = FIRE_STARTER_BONUS[name]
        facts.append(f"Allume un feu : +{int(bonus * 100)} % de chance"
                     if bonus else
                     "Allume un feu, sans aucun bonus de chance")
    if name in INSTALLABLE_ITEMS:
        facts.append("Se pose au sol")

    recipe = recipe_for(name)
    if recipe:
        facts.append(f"Se fabrique avec : {recipe_inputs(recipe)}")
    zones = zones_for(name)
    if zones:
        facts.append(f"Se trouve : {', '.join(zones)}")
    serves = used_in(name)
    if serves:
        facts.append("Sert a fabriquer : "
                     + ", ".join(display_name(s) for s in serves))
    if not facts:
        facts.append("Aucun usage connu pour l'instant.")
    return (ITEM_NOTES.get(name, ""), facts)
