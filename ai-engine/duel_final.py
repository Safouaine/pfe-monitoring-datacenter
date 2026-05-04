import pandas as pd
import os
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from sklearn.metrics import classification_report, f1_score

print("Chargement des données...")
# Lecture du fichier de données local
data_path = 'data/datacenter_tunisia_rf_dataset.csv'
if not os.path.exists(data_path):
    data_path = 'data/datacenter_tunisia_20K_fixed.csv'


df = pd.read_csv(data_path)

# Features réelles de votre datacenter
features = [
    'temp_ext', 'humidity',
    'rack1_h', 'rack1_m', 'rack1_b',
    'rack2_h', 'rack2_m', 'rack2_b',
    'pwr_consumption', 'fuel_level', 'battery_health'
]

X = df[features]
# On transforme la colonne target (0,1,2,3) en classification binaire (0 = normal, 1 = problème)
y = (df['target'] != 0).astype(int)

print("Séparation des données (Train/Test)...")
# SOLUTION 1 : On mélange les données (shuffle=True) et on s'assure d'avoir autant de pannes dans le test que dans l'entraînement (stratify=y)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=True, stratify=y, random_state=42)

print("Entraînement des modèles (Duel: Random Forest VS XGBoost)...")
# SOLUTION 2 : On ajoute 'class_weight="balanced"' pour forcer l'IA à faire très attention aux pannes (qui sont rares)
rf = RandomForestClassifier(n_estimators=100, class_weight='balanced', random_state=42).fit(X_train, y_train)

# Calcul du ratio pour XGBoost (Nombre de normaux / Nombre de pannes)
ratio = float(y_train.value_counts()[0]) / y_train.value_counts()[1]
xgb = XGBClassifier(eval_metric='logloss', scale_pos_weight=ratio, random_state=42).fit(X_train, y_train)

print("\n--- RÉSULTATS DU DUEL ---")
print("Score F1 Random Forest:", f1_score(y_test, rf.predict(X_test), zero_division=0))
print("Score F1 XGBoost:", f1_score(y_test, xgb.predict(X_test), zero_division=0))

print("\nDétails Random Forest:\n", classification_report(y_test, rf.predict(X_test), zero_division=0))
print("\nDétails XGBoost:\n", classification_report(y_test, xgb.predict(X_test), zero_division=0))
