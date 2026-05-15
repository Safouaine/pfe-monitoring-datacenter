"""
Train XGBoost + Random Forest on the same dataset and features.
Exports both models and a comparison metrics JSON for the ML dashboard.
"""
import os
import json
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report, roc_auc_score
)
from imblearn.over_sampling import SMOTE
from xgboost import XGBClassifier

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_PATH = os.path.join(PROJECT_ROOT, 'data', 'datacenter_tunisia_rf_dataset.csv')
RF_MODEL_PATH = os.path.join(PROJECT_ROOT, 'advanced_rf_model.pkl')
XGB_MODEL_PATH = os.path.join(PROJECT_ROOT, 'advanced_xgb_model.pkl')
METRICS_PATH = os.path.join(PROJECT_ROOT, 'data', 'ml_metrics.json')

FEATURES = [
    'temp_ext', 'humidity',
    'rack1_h', 'rack1_m', 'rack1_b',
    'rack2_h', 'rack2_m', 'rack2_b',
    'pwr_consumption', 'fuel_level', 'battery_health',
    'temp_ext_rolling10', 'humidity_rolling10',
    'rack1_delta_temp', 'rack2_delta_temp'
]

FEATURE_LABELS = {
    'temp_ext': 'Température Extérieure',
    'humidity': 'Humidité',
    'rack1_h': 'Rack 1 — Haut',
    'rack1_m': 'Rack 1 — Milieu',
    'rack1_b': 'Rack 1 — Bas',
    'rack2_h': 'Rack 2 — Haut',
    'rack2_m': 'Rack 2 — Milieu',
    'rack2_b': 'Rack 2 — Bas',
    'pwr_consumption': 'Consommation Énergie',
    'fuel_level': 'Niveau Carburant',
    'battery_health': 'Santé Batterie',
    'temp_ext_rolling10': 'Temp. Ext. Moy. 10min',
    'humidity_rolling10': 'Humidité Moy. 10min',
    'rack1_delta_temp': 'Delta Temp. Rack 1',
    'rack2_delta_temp': 'Delta Temp. Rack 2',
}


def load_and_engineer():
    df = pd.read_csv(DATA_PATH)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['temp_ext_rolling10'] = df['temp_ext'].rolling(window=10, min_periods=1).mean()
    df['humidity_rolling10'] = df['humidity'].rolling(window=10, min_periods=1).mean()
    df['rack1_delta_temp'] = df['rack1_h'] - df['rack1_b']
    df['rack2_delta_temp'] = df['rack2_h'] - df['rack2_b']
    return df


def evaluate_model(name, model, X_test, y_test, training_seconds):
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    cm = confusion_matrix(y_test, y_pred).tolist()
    importances = getattr(model, 'feature_importances_', None)
    if importances is not None:
        fi = [
            {'feature': FEATURES[i], 'label': FEATURE_LABELS[FEATURES[i]],
             'importance': float(importances[i])}
            for i in range(len(FEATURES))
        ]
        fi.sort(key=lambda x: x['importance'], reverse=True)
    else:
        fi = []
    return {
        'name': name,
        'accuracy': float(accuracy_score(y_test, y_pred)),
        'precision': float(precision_score(y_test, y_pred, zero_division=0)),
        'recall': float(recall_score(y_test, y_pred, zero_division=0)),
        'f1': float(f1_score(y_test, y_pred, zero_division=0)),
        'roc_auc': float(roc_auc_score(y_test, y_proba)),
        'confusion_matrix': cm,
        'feature_importance': fi,
        'training_seconds': round(training_seconds, 2),
        'predictions_sample': int(len(y_pred)),
    }


def main():
    print("=" * 60)
    print("COMPARATIF RANDOM FOREST vs XGBOOST — PIPELINE COMPLET")
    print("=" * 60)

    print("\n[1/5] Chargement et feature engineering...")
    df = load_and_engineer()
    print(f"   {len(df)} lignes chargées")

    X = df[FEATURES]
    y = (df['target'] != 0).astype(int)

    print("\n[2/5] Train/test split stratifié (80/20)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    print("[3/5] SMOTE pour équilibrage du train set...")
    smote = SMOTE(random_state=42)
    X_train_b, y_train_b = smote.fit_resample(X_train, y_train)
    print(f"   Après SMOTE : {sum(y_train_b==0)} normaux | {sum(y_train_b==1)} pannes")

    import time
    print("\n[4/5] Entraînement Random Forest...")
    t0 = time.time()
    rf = RandomForestClassifier(
        n_estimators=300, max_depth=None, max_features='log2',
        min_samples_split=5, min_samples_leaf=1, n_jobs=-1, random_state=42
    )
    rf.fit(X_train_b, y_train_b)
    rf_seconds = time.time() - t0
    joblib.dump(rf, RF_MODEL_PATH)
    rf_metrics = evaluate_model('Random Forest', rf, X_test, y_test, rf_seconds)
    print(f"   RF : Accuracy={rf_metrics['accuracy']:.3f} | F1={rf_metrics['f1']:.3f} | {rf_seconds:.1f}s")

    print("\n[5/5] Entraînement XGBoost...")
    t0 = time.time()
    xgb = XGBClassifier(
        n_estimators=300, max_depth=8, learning_rate=0.1,
        subsample=0.9, colsample_bytree=0.9,
        use_label_encoder=False, eval_metric='logloss',
        n_jobs=-1, random_state=42
    )
    xgb.fit(X_train_b, y_train_b)
    xgb_seconds = time.time() - t0
    joblib.dump(xgb, XGB_MODEL_PATH)
    xgb_metrics = evaluate_model('XGBoost', xgb, X_test, y_test, xgb_seconds)
    print(f"   XGB : Accuracy={xgb_metrics['accuracy']:.3f} | F1={xgb_metrics['f1']:.3f} | {xgb_seconds:.1f}s")

    if rf_metrics['f1'] >= xgb_metrics['f1']:
        best, gap = 'Random Forest', rf_metrics['f1'] - xgb_metrics['f1']
    else:
        best, gap = 'XGBoost', xgb_metrics['f1'] - rf_metrics['f1']

    payload = {
        'trained_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'dataset': os.path.basename(DATA_PATH),
        'rows': len(df),
        'features_count': len(FEATURES),
        'test_size': int(len(X_test)),
        'best_model': best,
        'f1_gap': round(gap, 4),
        'models': {
            'random_forest': rf_metrics,
            'xgboost': xgb_metrics,
        }
    }
    os.makedirs(os.path.dirname(METRICS_PATH), exist_ok=True)
    with open(METRICS_PATH, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] Métriques exportées vers : {METRICS_PATH}")
    print(f"[OK] Meilleur modèle : {best} (gap F1 = +{gap:.4f})")
    print("=" * 60)


if __name__ == '__main__':
    main()
