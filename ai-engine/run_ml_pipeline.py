import pandas as pd
import numpy as np
import os
import joblib
from sklearn.model_selection import RandomizedSearchCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, f1_score
from imblearn.over_sampling import SMOTE
from sqlalchemy import create_engine

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

print("=====================================================")
print("DEMARRAGE DU PIPELINE ML AVANCE (DATACENTER)")
print("=====================================================")

# ---------------------------------------------------------
# 1. CHARGEMENT DES DONNÉES
# ---------------------------------------------------------
print("\n[1/6] Chargement des données...")
data_path = os.path.join(PROJECT_ROOT, 'data', 'datacenter_tunisia_rf_dataset.csv')
if not os.path.exists(data_path):
    data_path = os.path.join(PROJECT_ROOT, 'data', 'datacenter_tunisia_20K_fixed.csv')

df = pd.read_csv(data_path)
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp').reset_index(drop=True)
print(f"[OK] {len(df)} lignes chargees avec succes.")

# ---------------------------------------------------------
# 2. FEATURE ENGINEERING (Création de la Mémoire)
# ---------------------------------------------------------
print("\n[2/6] Feature Engineering (Création de nouvelles variables intelligentes)...")
# Moyennes glissantes (Accumulation de chaleur sur 10 minutes)
df['temp_ext_rolling10'] = df['temp_ext'].rolling(window=10, min_periods=1).mean()
df['humidity_rolling10'] = df['humidity'].rolling(window=10, min_periods=1).mean()

# Écarts thermiques (Détection de problème de ventilation : Haut du rack vs Bas du rack)
df['rack1_delta_temp'] = df['rack1_h'] - df['rack1_b']
df['rack2_delta_temp'] = df['rack2_h'] - df['rack2_b']

# Liste complète des variables utilisées par l'IA
features = [
    'temp_ext', 'humidity',
    'rack1_h', 'rack1_m', 'rack1_b',
    'rack2_h', 'rack2_m', 'rack2_b',
    'pwr_consumption', 'fuel_level', 'battery_health',
    'temp_ext_rolling10', 'humidity_rolling10',
    'rack1_delta_temp', 'rack2_delta_temp'
]

X = df[features]
# Transformation de la target en binaire (0 = Normal, 1 = Panne)
y = (df['target'] != 0).astype(int)

# ---------------------------------------------------------
# 3. SÉPARATION ET SMOTE (Équilibrage des classes)
# ---------------------------------------------------------
print("\n[3/6] Préparation des données et Équilibrage SMOTE...")
from sklearn.model_selection import train_test_split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

print(f"   Split stratifié : train={len(X_train)} lignes, test={len(X_test)} lignes")
print(f"   Répartition avant SMOTE (Entraînement) : Normaux={sum(y_train==0)}, Pannes={sum(y_train==1)}")

# Application de SMOTE UNIQUEMENT sur les données d'entraînement !
smote = SMOTE(random_state=42)
X_train_smote, y_train_smote = smote.fit_resample(X_train, y_train)

print(f"   [OK] Repartition APRES SMOTE (Entrainement) : Normaux={sum(y_train_smote==0)}, Pannes={sum(y_train_smote==1)}")

# ---------------------------------------------------------
# 4. OPTIMISATION ET ENTRAÎNEMENT (GridSearch)
# ---------------------------------------------------------
print("\n[4/6] Entraînement du modèle Random Forest Avancé...")

# SMOTE gère déjà le déséquilibre — pas besoin de class_weight='balanced'
rf = RandomForestClassifier(random_state=42)

# Grille élargie — 20 combinaisons testées pour une meilleure optimisation
param_dist = {
    'n_estimators': [100, 200, 300, 500],
    'max_depth': [None, 10, 20, 30],
    'min_samples_split': [2, 5, 10],
    'min_samples_leaf': [1, 2, 4],
    'max_features': ['sqrt', 'log2'],
}

search = RandomizedSearchCV(rf, param_distributions=param_dist, n_iter=20, cv=5, scoring='f1', n_jobs=-1, random_state=42)
search.fit(X_train_smote, y_train_smote)

best_rf = search.best_estimator_
print(f"   [OK] Meilleure configuration trouvee : {search.best_params_}")

# Sauvegarde en chemin absolu (fonctionne quel que soit le répertoire courant)
model_path = os.path.join(PROJECT_ROOT, 'advanced_rf_model.pkl')
joblib.dump(best_rf, model_path)
print(f"   [SAUVEGARDE] Modele sauvegarde sous '{model_path}'")

# ---------------------------------------------------------
# 5. ÉVALUATION
# ---------------------------------------------------------
print("\n[5/6] Évaluation du Modèle sur le jeu de Test (Données réelles jamais vues)...")
y_pred = best_rf.predict(X_test)
print(classification_report(y_test, y_pred, zero_division=0))

# ---------------------------------------------------------
# 6. GÉNÉRATION DES PRÉDICTIONS ET ENVOI SUR POSTGRESQL
# ---------------------------------------------------------
print("\n[6/6] Calcul du 'Risk Percentage' sur tout le DataCenter et envoi sur PostgreSQL...")

# Prédiction des probabilités sur TOUT le dataset
probabilities = best_rf.predict_proba(X)
predictions = best_rf.predict(X)

# La probabilité de la classe 1 (Panne) correspond à notre Pourcentage de Risque
risk_percentage = probabilities[:, 1] * 100

results_df = pd.DataFrame({
    'timestamp': df['timestamp'],
    'predicted_class': predictions,
    'risk_percentage': risk_percentage
})

print("   Connexion à la base de données PostgreSQL (datacenter-dw)...")
try:
    # On se connecte via localhost (car PostgreSQL tourne sur Windows)
    # L'ajout de connect_args empêche le crash de traduction Python
    connection_url = "postgresql://postgres:admin@localhost:5432/datacenter-dw"
    import sqlalchemy
    engine = sqlalchemy.create_engine(
        connection_url,
        connect_args={'client_encoding': 'utf8'}
    )
    results_df.to_sql('ai_predictions', engine, if_exists='replace', index=False)
    print("   [OK] Predictions sauvegardees avec succes dans la table 'ai_predictions' !")
except Exception as e:
    print(f"   [ERREUR] Impossible de se connclearecter a PostgreSQL sur localhost : {e}")
    print("   (Assurez-vous que le conteneur PostgreSQL est bien lancé et accessible)")

print("\n=====================================================")
print("[SUCCESS] PIPELINE TERMINE AVEC SUCCES !")
print("Pour afficher les prédictions dans Grafana, utilisez cette requête :")
print("SELECT timestamp AS time, risk_percentage AS metric, predicted_class FROM ai_predictions ORDER BY time ASC")
print("=====================================================")
