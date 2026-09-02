"""
STATISTIQUES DU PERSONNAGE.

Sept aptitudes qui montent SEPAREMENT, chacune par les actions qui la
sollicitent : on devient fort en coupant du bois, pas en fabriquant des
objets. Aucune ne monte "toute seule" avec le temps.

Au depart, toutes sont au NIVEAU 1. Le joueur repartit ensuite 35 points
comme il veut avant de commencer (mode debug : 5 points partout, ce qui
revient au meme total).

Le detail du niveau suivant est dans xp_needed() : le cout monte avec le
niveau, donc les premiers niveaux viennent vite et les suivants se meritent.
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

# Toutes les aptitudes commencent la, avant repartition des points.
START_LEVEL = 1
# Points a repartir librement au debut d'une partie.
START_POINTS = 35
# Mode debug : meme total, mais reparti d'office a parts egales.
DEBUG_POINTS_EACH = START_POINTS // len(STAT_ORDER)

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
    """Experience a accumuler pour quitter ce niveau.

    Le cout croit avec le niveau : passer de 1 a 2 demande 10 points, de
    10 a 11 en demande 100. Un niveau eleve ne s'obtient donc pas en
    repetant la meme action mille fois sans y penser."""
    return max(1, 10 * int(level))


def normalize(raw, default=START_LEVEL):
    """Remet un dictionnaire de niveaux d'aplomb (sauvegarde, saisie...).

    Toute aptitude manquante revient a sa valeur de depart, toute valeur
    illisible ou negative aussi : une sauvegarde abimee ne peut pas donner
    un personnage sans aptitudes."""
    out = {}
    for key in STAT_ORDER:
        try:
            out[key] = max(1, int((raw or {}).get(key, default)))
        except (TypeError, ValueError):
            out[key] = default
    return out


def distribute_even(points_each=DEBUG_POINTS_EACH):
    """Repartition a parts egales, utilisee par la partie de test."""
    return {key: START_LEVEL + points_each for key in STAT_ORDER}
