import pandas as pd
import numpy as np
import timesfm
import torch
import matplotlib.pyplot as plt
import os

print("--- Chargement des données ---")
# 1. Charger les données via le volume monté par Docker
data_path = 'data/datacenter_tunisia_rf_dataset.csv'
if not os.path.exists(data_path):
    data_path = 'data/datacenter_tunisia_20K_fixed.csv'

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

print("--- Génération de la Prédiction ---")
# 3. Prédiction
# On lui donne les 100 dernières températures extérieures (temp_ext)
inputs = [df['temp_ext'].values[-100:]]
frequency = [0]
point_forecast, _ = model.forecast(inputs, freq=frequency)

print("✅ Prédiction réussie pour les 32 prochaines minutes !")

# 4. Visualisation
plt.figure(figsize=(12, 6))
# Données passées (Contexte = 100 dernières minutes)
plt.plot(range(100), inputs[0], label="Température Actuelle (Passé)", color='#3498db', linewidth=2)
# Prédiction du futur par Google (Horizon = 32 minutes)
plt.plot(range(100, 100+32), point_forecast[0], label="Prédiction Google (Futur)", color='#e74c3c', linestyle='--', linewidth=2)

plt.axhline(y=35, color='orange', linestyle='-', label='Seuil d\'Alerte Surchauffe')
plt.title("Prévision de Température du Datacenter (Google TimesFM)")
plt.xlabel("Temps (Minutes)")
plt.ylabel("Température Extérieure (°C)")
plt.grid(True, alpha=0.3)
plt.legend()

plt.savefig('timesfm_forecast.png')
print("✅ Graphique sauvegardé sous 'timesfm_forecast.png'")
