"""
LES RECETTES DE L'ANCIEN CRAFT, MISES DE COTE.

LE JEU NE LIT PAS CE FICHIER. Rien ne l'importe : c'est une archive.

Le systeme de craft a ete retire en attendant sa nouvelle forme. Plutot que
d'effacer les recettes, on les garde ici TELLES QU'ELLES ETAIENT, pour que
la nouvelle version reparte de ce qui existait -- les noms, les matieres,
les outils, les durees -- au lieu de tout reinventer de memoire.

CE QUI N'A PAS BOUGE
--------------------
- LES OBJETS EUX-MEMES existent toujours dans le jeu : leurs noms, leurs
  fiches (items.ITEM_NOTES), leurs cases d'equipement, leur solidite. Une
  partie sauvegardee qui contient un couteau ou une veste de feuille le
  garde, et il reste utilisable.
- LEURS IMAGES sont toujours dans assets/items/, sous le meme nom (voir
  IMAGES ci-dessous, et assets/items/LISEZMOI.txt pour celles qui manquent).

Seule la FABRICATION a disparu : items.RECIPES est vide, donc aucun ecran ne
propose plus de fabriquer quoi que ce soit.

POUR REMETTRE L'ANCIEN SYSTEME TEL QUEL
---------------------------------------
    items.RECIPES = list(recettes_archive.RECETTES)

Le format est celui qu'attendent encore GameState.can_craft / do_craft et
l'ecran d'atelier (voir le commentaire au-dessus de items.RECIPES).
"""
from src.items import BLUEPRINT_T1, WORKBENCH_T1

# Les categories de l'ancien ecran Craft, dans leur ordre d'affichage.
CATEGORIES = ("Outils", "Materiaux", "Equipement", "Installations")

# Les recettes, a l'identique. Rappel du format :
# - "ingredients" : consommes, tous ;
# - "any_of"      : UNE seule des matieres listees est consommee ;
# - "tool"        : un outil a proximite, non consomme, qui perd
#                   "tool_wear" de sa solidite (0.10 = 10 %) ;
# - "station"     : un deposable qui doit etre POSE sur la case ;
# - "minutes"     : le temps de jeu que l'ouvrage prend.
RECETTES = [
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
    {"result": "Marteau", "category": "Outils",
     "ingredients": {"Pierre": 1, "Small_Stick": 4, "Corde": 1}},
    {"result": WORKBENCH_T1, "category": "Installations",
     "ingredients": {"Pierre": 5, "Long_Stick": 2},
     "tool": "Marteau", "tool_wear": 0.20, "minutes": 60},
    {"result": BLUEPRINT_T1, "category": "Installations",
     "ingredients": {"Small_Stick": 4, "Corde": 1},
     "station": WORKBENCH_T1},
]

# LES OBJETS QUI SE FABRIQUAIENT, et le nom de leur image dans
# assets/items/. None = l'image n'a jamais ete livree (voir le LISEZMOI du
# dossier). L'ordre est celui des recettes.
IMAGES = {
    "Couteau": "Couteau.png",
    "Hache": "Hache.png",
    "Lance": "Lance.png",
    "Allume_feu": None,
    "Fibre_Vegetale": "Fibre_Vegetale.png",
    "Corde": "Corde.png",
    "Casque_De_Feuille": "Casque_De_Feuille.png",
    "Veste_De_Feuille": "Veste_De_Feuille.png",
    "Gant_De_Feuille": "Gant_De_Feuille.png",
    "Pantalon_De_Feuille": "Pantalon_De_Feuille.png",
    "Soulier_De_Feuille": "Soulier_De_Feuille.png",
    "Sac_De_Feuille": None,
    "Feu_de_camp": "Feu_de_camp.png",
    # Marteau et Atelier : leurs images attendent dans assets/items/futur/
    # (Marteau.png) ou n'existent pas encore.
    "Marteau": None,
    WORKBENCH_T1: None,
    BLUEPRINT_T1: None,
}
