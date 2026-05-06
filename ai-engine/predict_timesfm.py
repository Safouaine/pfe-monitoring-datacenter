import pandas as pd
import numpy as np
import timesfm
import torch
import matplotlib.pyplot as plt
import os
import joblib

print("--- Chargement des données ---")
# 1. Charger les données via le volume monté par Docker ou localement
data_path = 'data/datacenter_tunisia_rf_dataset.csv'
if not os.path.exists(data_path):
    data_path = '../data/datacenter_tunisia_rf_dataset.csv'
if not os.path.exists(data_path):
    data_path = 'data/datacenter_tunisia_20K_fixed.csv'
if not os.path.exists(data_path):
    data_path = '../data/datacenter_tunisia_20K_fixed.csv'

df = pd.read_csv(data_path)

print("--- Initialisation de Google TimesFM 1.0 (PyTorch) ---")
# 2. Initialisation (API stable de PyPI avec Hparams et Checkpoint)
hparams = timesfm.TimesFmHparams(
    backend="cpu",
    context_len=128,
    horizon_len=32,
    input_patch_len=32,
    output_patch_len=128,
    num_layers=20,
    model_dims=1280,
    per_core_batch_size=32,
    use_positional_embedding=False
)
checkpoint = timesfm.TimesFmCheckpoint(
    huggingface_repo_id="google/timesfm-1.0-200m-pytorch"
)
model = timesfm.TimesFm(hparams=hparams, checkpoint=checkpoint)

print("--- Génération des Prédictions Multivariées (TimesFM) ---")
# Liste des 11 capteurs de base
base_features = [
    'temp_ext', 'humidity',
    'rack1_h', 'rack1_m', 'rack1_b',
    'rack2_h', 'rack2_m', 'rack2_b',
    'pwr_consumption', 'fuel_level', 'battery_health'
]

context_len = 100
horizon_len = 32

# On extrait l'historique (100 dernières minutes) pour TOUS les capteurs
inputs = []
for feat in base_features:
    inputs.append(df[feat].values[-context_len:])

frequencies = [0] * len(base_features)

# TimesFM prévoit l'avenir pour tous les capteurs en même temps
point_forecast, _ = model.forecast(inputs, freq=frequencies)

# Reconstruction du futur DataFrame (32 prochaines minutes)
future_df = pd.DataFrame()
for i, feat in enumerate(base_features):
    future_df[feat] = point_forecast[i][:horizon_len]

# Combinaison du Passé et du Futur pour calculer les indicateurs techniques
past_df = df[base_features].iloc[-context_len:].copy()
combined_df = pd.concat([past_df, future_df], ignore_index=True)

print("--- Feature Engineering sur le Futur ---")
# Calcul des mêmes indicateurs que ceux utilisés par le Random Forest
combined_df['temp_ext_rolling10'] = combined_df['temp_ext'].rolling(window=10, min_periods=1).mean()
combined_df['humidity_rolling10'] = combined_df['humidity'].rolling(window=10, min_periods=1).mean()
combined_df['rack1_delta_temp'] = combined_df['rack1_h'] - combined_df['rack1_b']
combined_df['rack2_delta_temp'] = combined_df['rack2_h'] - combined_df['rack2_b']

# Liste complète des variables requises par le Random Forest
rf_features = [
    'temp_ext', 'humidity',
    'rack1_h', 'rack1_m', 'rack1_b',
    'rack2_h', 'rack2_m', 'rack2_b',
    'pwr_consumption', 'fuel_level', 'battery_health',
    'temp_ext_rolling10', 'humidity_rolling10',
    'rack1_delta_temp', 'rack2_delta_temp'
]

print("--- Prédiction des Pannes avec Random Forest ---")
rf_model_path = 'advanced_rf_model.pkl'
if not os.path.exists(rf_model_path):
    rf_model_path = '../advanced_rf_model.pkl'
if not os.path.exists(rf_model_path):
    print("[ERREUR] Impossible de trouver le modèle Random Forest 'advanced_rf_model.pkl'")
    exit(1)

best_rf = joblib.load(rf_model_path)

# Extraction des données et calcul des probabilités de panne
X_past = combined_df.iloc[:-horizon_len][rf_features]
past_probabilities = best_rf.predict_proba(X_past)[:, 1]

X_future = combined_df.iloc[-horizon_len:][rf_features]
future_probabilities = best_rf.predict_proba(X_future)[:, 1]

print("[SUCCES] Prédiction réussie pour les 32 prochaines minutes !")

# 4. Visualisation
plt.figure(figsize=(12, 6))

# Données passées (Contexte = 100 dernières minutes)
plt.plot(range(context_len), past_probabilities * 100, label="Risque de Panne Actuel (Passé)", color='#3498db', linewidth=2)

# Prédiction du futur par l'architecture Hybride (Horizon = 32 minutes)
plt.plot(range(context_len, context_len + horizon_len), future_probabilities * 100, label="Risque de Panne Prévu (Futur simulé)", color='#e74c3c', linestyle='--', linewidth=2)

# Seuil d'alerte à 50% de probabilité
plt.axhline(y=50, color='orange', linestyle='-', label='Seuil d\'Alerte Critique (50%)')
plt.title("Prévision du Risque de Panne du Datacenter (Google TimesFM + Random Forest)")
plt.xlabel("Temps (Minutes)")
plt.ylabel("Probabilité de Panne (%)")
plt.ylim(-5, 105)
plt.grid(True, alpha=0.3)
plt.legend()

plt.savefig('timesfm_forecast.png')
print("[SUCCES] Graphique sauvegardé sous 'timesfm_forecast.png'")
