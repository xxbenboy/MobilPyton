"""
STATISTIQUES DU PERSONNAGE.

Sept aptitudes qui montent SEPAREMENT, chacune par les actions qui la
sollicitent : on devient fort en coupant du bois, pas en fabriquant des
objets. Aucune ne monte "toute seule" avec le temps.

Au depart, toutes sont au NIVEAU 0. Le joueur repartit ensuite 500 points
d'experience comme il veut, par tranches de 10 (mode debug : niveau 5
partout, sans passer par cet ecran).

Le cout d'un niveau DOUBLE a chaque fois (20, 40, 80, 160...) : les premiers
viennent vite, les suivants se meritent vraiment.
"""

# Ordre d'affichage, partout dans le jeu.
STAT_ORDER = ("force", "endurance", "ingeniosite", "chance",
              "discretion", "vitesse", "agilite")

STAT_NAMES = {
    "force": "Force",
    "endurance": "Endurance",
    "ingeniosite": "Ingeniosite",
    "chance": "Chance",
    "discretion": "Discretion",
    "vitesse": "Vitesse",
    "agilite": "Agilite",
}

# Ce que chaque aptitude represente, et surtout CE QUI LA FAIT MONTER.
STAT_NOTES = {
    "force": "Porter et frapper. Monte en coupant du bois.",
    "endurance": "Tenir la distance. Monte en marchant d'une case a l'autre.",
    "ingeniosite": "Se debrouiller. Monte en fabriquant des objets.",
    "chance": "Le hasard qui tourne bien. Monte en allumant un feu.",
    "discretion": "Passer inapercu. Monte en explorant de nuit.",
    "vitesse": "Deplacement et action. Monte en explorant.",
    "agilite": "La main sure. Monte en ramassant des objets.",
}

# Toutes les aptitudes commencent la, avant repartition.
START_LEVEL = 0
# Experience a repartir librement au debut d'une partie...
START_XP = 500
# ...par tranches de 10 : un appui sur "+" vaut 10 points d'experience.
XP_STEP = 10
# Cout du PREMIER niveau. Chaque niveau suivant coute le double.
XP_FIRST = 20
# Mode debug : niveau 5 partout, sans passer par l'ecran de repartition.
DEBUG_LEVEL = 5

# Quelle aptitude progresse a quelle action, et de combien de points
# d'experience. Les valeurs suivent la RARETE de l'action : on se deplace
# souvent, on abat un arbre rarement.
ACTION_XP = {
    "couper": ("force", 6),
    "marcher": ("endurance", 2),
    "fabriquer": ("ingeniosite", 5),
    "feu": ("chance", 4),
    "nuit": ("discretion", 3),
    "explorer": ("vitesse", 2),
    "ramasser": ("agilite", 1),
}


def xp_needed(level):
    """Experience a accumuler pour QUITTER ce niveau.

    Le cout double a chaque niveau : 20 pour atteindre le niveau 1, 40 pour
    le 2, 80 pour le 3... Un niveau eleve ne s'obtient donc pas en repetant
    la meme action indefiniment."""
    return XP_FIRST * (2 ** max(0, int(level)))


def xp_for_level(level):
    """Experience TOTALE a cumuler depuis zero pour atteindre ce niveau.

    Somme de la suite doublante : 20, 60, 140, 300, 620..."""
    return XP_FIRST * (2 ** max(0, int(level)) - 1)


def level_from_xp(total):
    """(niveau atteint, experience en cours) pour une experience TOTALE.

    Sert a l'ecran de repartition, qui distribue de l'experience brute et
    doit en montrer le niveau correspondant."""
    level, left = 0, max(0, int(total))
    while left >= xp_needed(level):
        left -= xp_needed(level)
        level += 1
    return level, left


def normalize(raw, default=START_LEVEL):
    """Remet un dictionnaire de niveaux d'aplomb (sauvegarde, saisie...).

    Toute aptitude manquante revient a sa valeur de depart, toute valeur
    illisible ou negative aussi : une sauvegarde abimee ne peut pas donner
    un personnage sans aptitudes."""
    out = {}
    for key in STAT_ORDER:
        try:
            out[key] = max(0, int((raw or {}).get(key, default)))
        except (TypeError, ValueError):
            out[key] = default
    return out


def debug_levels():
    """Aptitudes de la partie de test : niveau 5 partout."""
    return {key: DEBUG_LEVEL for key in STAT_ORDER}
