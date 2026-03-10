"""import time
import sys

print("--- TENTATIVE DE DÉMARRAGE DU COLLECTEUR ---")

try:
    from pysnmp.hlapi import *
    print("[OK] Bibliothèques SNMP chargées.")
except Exception as e:
    print(f"[ERREUR] Problème d'importation : {e}")
    # On ne quitte pas le script pour laisser le conteneur tourner
    while True: time.sleep(10)

# CONFIGURATION NOUVAMEQ
IP_AKCP = "192.168.1.100" 

def loop():
    print(f"[{time.strftime('%H:%M:%S')}] Recherche de l'AKCP sur {IP_AKCP}...")
    # On ajoutera la logique getCmd() une fois le build validé
    time.sleep(5)

if __name__ == "__main__":
    while True:
        loop() 
"""
import time
import random
import sys

# On force l'affichage immédiat pour Docker
print("--- [START] COLLECTEUR NOUVAMEQ ---", flush=True)

while True:
    try:
        # Simulation d'une lecture (car tu n'as pas encore l'AKCP)
        temp_simulee = round(random.uniform(20.0, 25.0), 2)
        
        # Affiche l'heure et la valeur
        current_time = time.strftime('%H:%M:%S')
        print(f"[{current_time}] Lecture SNMP (Simulée) : {temp_simulee} °C", flush=True)
        
    except Exception as e:
        print(f"ERREUR : {e}", flush=True)

    time.sleep(5) # On réduit à 5 secondes pour voir les logs plus vite

