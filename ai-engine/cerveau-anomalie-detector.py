import pandas as pd
from influxdb_client import InfluxDBClient
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt

# 1. Paramètres de connexion 
url = "http://localhost:8086"
token = "-ifTMHhawX5DuysgqTP5ik7K0UyWiqKH3fNPyaQbp4GNTKqQHT0kgmrvNAGfHjZIJw-DzNeKIrgNEP7nYbnKCA=="
org = "Nouvameq"
bucket = "datacenter_metrics"

client = InfluxDBClient(url=url, token=token, org=org, timeout=60000)

# 2. Récupération optimisée des données depuis InfluxDB
# EXTRÊMEMENT IMPORTANT : On filtre TOUTES les métriques internes du CPU/Système
# en isolant avec un Regex les capteurs (rack, temp, humidity, pwr, fuel, water, smoke, etc.)
query = f'''
from(bucket: "{bucket}") 
  |> range(start: -90d)
  |> filter(fn: (r) => r["_field"] =~ /temp.*|hum.*|rack.*|pwr.*|pow.*|fuel.*|bat.*|water.*|smoke.*|door.*/)
  |> drop(columns: ["_start", "_stop", "result", "table"])
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
'''

print(f"Extraction hyper-optimisée depuis le bucket '{bucket}'...")
try:
    response = client.query_api().query_data_frame(query)
except Exception as e:
    print(f"Erreur majeure lors de l'extraction InfluxDB : {e}")
    exit()

# InfluxDB peut retourner une liste de DataFrames si les données sont réparties sur plusieurs tables (ex: tags différents)
if isinstance(response, list):
    df = pd.concat(response, ignore_index=True) if response else pd.DataFrame()
else:
    df = response

if df.empty:
    print(f"ERREUR : Aucune donnée CAPTEUR trouvée pour les 90 derniers jours dans le bucket {bucket}.")
    exit()

# Tri par temps au cas où l'union Pandas aurait mélangé l'ordre chronologique
df = df.sort_values(by='_time').reset_index(drop=True)

# 3. Préparation dynamique et Nettoyage pour le ML (S'adapte à TOUT le fichier)
colonnes_a_ignorer = ['_time', '_measurement', 'target', 'source', 'counter', 'sensor_name', 'pwr_source', 'ac_status', 'table']

# L'IA repère automatiquement toutes les colonnes contenant des nombres !
features = [col for col in df.columns if col not in colonnes_a_ignorer and pd.api.types.is_numeric_dtype(df[col])]

print(f"-> {len(features)} colonnes découvertes et exploitées par l'IA : {features}")

if len(features) == 0:
    print("ERREUR : Aucune colonne numérique n'a pu être exploitée. Re-vérifiez InfluxDB.")
    exit()

data_ready = df[features].ffill().fillna(0) # Anti-crash

# 4. Optimisation PRO : La Standardisation
# Indispensable quand on mélange des valeurs de différentes échelles 
# (ex: rack1 à 25°C et pwr_cons à 200W)
print("Standardisation mathématique de l'échantillon...")
scaler = StandardScaler()
data_scaled = scaler.fit_transform(data_ready)

# 5. Entraînement de l'IA (Isolation Forest Multi-dimensionnelle)
print("Entraînement de l'Isolation Forest sur l'ensemble du réseau...")
model = IsolationForest(contamination=0.02, random_state=42)
df['anomaly_status'] = model.fit_predict(data_scaled)

# Résultat : 1 = Normal, -1 = Anomalie (Erreur détectée)
anomalies = df[df['anomaly_status'] == -1]

print(f"\n==============================================")
print(f"  BILAN DU MACHINE LEARNING (IA PREDICTIVE)")
print(f"==============================================")
print(f"Points analysés : {len(df)}")
print(f"Anomalies isolées : {len(anomalies)}")
print(f"Ratio d'anomalies : {(len(anomalies)/len(df))*100:.2f}%\n")

# 6. Affichage intelligent
# On prend les 2 meilleures métriques disponibles pour dessiner 2 tableaux de bords !
m1 = 'temp_ext' if 'temp_ext' in features else features[0]
m2 = 'pwr_consumption' if 'pwr_consumption' in features else ('fuel_level' if 'fuel_level' in features else (features[1] if len(features) > 1 else None))

plt.figure(figsize=(12, 8))

# Subplot Numéro 1
plt.subplot(2, 1, 1)
plt.plot(df['_time'], df[m1], label=f"Trafic Normal ({m1})", color='#3498db', alpha=0.7)
plt.scatter(anomalies['_time'], anomalies[m1], color='#e74c3c', label='ANOMALIE DÉTECTÉE', zorder=5)
plt.title("Oeil Numérique 1 : Analyse Température et Climat", fontsize=14)
plt.legend()
plt.grid(True, alpha=0.3)

# Subplot Numéro 2 (si disponible)
if m2:
    plt.subplot(2, 1, 2)
    plt.plot(df['_time'], df[m2], label=f"Trafic Normal ({m2})", color='#2ecc71', alpha=0.7)
    plt.scatter(anomalies['_time'], anomalies[m2], color='#9b59b6', label='COMPORTEMENT ÉTRANGE', zorder=5)
    plt.title("Oeil Numérique 2 : Analyse Flux Électriques", fontsize=14)
    plt.legend()
    plt.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()
