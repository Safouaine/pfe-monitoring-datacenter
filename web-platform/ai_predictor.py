"""
Module d'IA : Architecture Hybride TimesFM + Random Forest
Retourne une analyse détaillée par capteur pour la plateforme web.
"""

import os
import sys
import numpy as np
import pandas as pd
import joblib
from datetime import datetime

# ─── Chemins des ressources ────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

DATA_CANDIDATES = [
    os.path.join(BASE_DIR, "data", "datacenter_tunisia_rf_dataset.csv"),
    os.path.join(PROJECT_ROOT, "data", "datacenter_tunisia_rf_dataset.csv"),
    os.path.join(BASE_DIR, "data", "datacenter_tunisia_20K_fixed.csv"),
    os.path.join(PROJECT_ROOT, "data", "datacenter_tunisia_20K_fixed.csv"),
]

MODEL_CANDIDATES = [
    os.path.join(BASE_DIR, "advanced_rf_model.pkl"),
    os.path.join(PROJECT_ROOT, "advanced_rf_model.pkl"),
]

# ─── Métadonnées des capteurs ──────────────────────────────────────────────────
SENSOR_META = {
    "temp_ext":       {"label": "Température Extérieure", "unit": "°C",  "icon": "🌡️",  "threshold_warn": 35, "threshold_crit": 42},
    "humidity":       {"label": "Humidité",               "unit": "%",   "icon": "💧",  "threshold_warn": 70, "threshold_crit": 85},
    "rack1_h":        {"label": "Rack 1 – Haut",          "unit": "°C",  "icon": "🖥️",  "threshold_warn": 30, "threshold_crit": 40},
    "rack1_m":        {"label": "Rack 1 – Milieu",        "unit": "°C",  "icon": "🖥️",  "threshold_warn": 30, "threshold_crit": 40},
    "rack1_b":        {"label": "Rack 1 – Bas",           "unit": "°C",  "icon": "🖥️",  "threshold_warn": 30, "threshold_crit": 40},
    "rack2_h":        {"label": "Rack 2 – Haut",          "unit": "°C",  "icon": "🖥️",  "threshold_warn": 30, "threshold_crit": 40},
    "rack2_m":        {"label": "Rack 2 – Milieu",        "unit": "°C",  "icon": "🖥️",  "threshold_warn": 30, "threshold_crit": 40},
    "rack2_b":        {"label": "Rack 2 – Bas",           "unit": "°C",  "icon": "🖥️",  "threshold_warn": 30, "threshold_crit": 40},
    "pwr_consumption":{"label": "Consommation Énergie",   "unit": "kW",  "icon": "⚡",  "threshold_warn": 80, "threshold_crit": 95},
    "fuel_level":     {"label": "Niveau Carburant",       "unit": "%",   "icon": "⛽",  "threshold_warn": 30, "threshold_crit": 15},
    "battery_health": {"label": "Santé Batterie",         "unit": "%",   "icon": "🔋",  "threshold_warn": 50, "threshold_crit": 30},
}

BASE_FEATURES = list(SENSOR_META.keys())

RF_FEATURES = [
    "temp_ext", "humidity",
    "rack1_h", "rack1_m", "rack1_b",
    "rack2_h", "rack2_m", "rack2_b",
    "pwr_consumption", "fuel_level", "battery_health",
    "temp_ext_rolling10", "humidity_rolling10",
    "rack1_delta_temp", "rack2_delta_temp",
]

CONTEXT_LEN = 100
HORIZON_LEN = 32

# ─── Chargement paresseux des modèles (une seule fois au démarrage) ────────────
_timesfm_model = None
_rf_model = None
_df = None


def _find_file(candidates):
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _load_data():
    global _df
    if _df is not None:
        return _df
    path = _find_file(DATA_CANDIDATES)
    if path is None:
        raise FileNotFoundError("Fichier CSV introuvable. Placez datacenter_tunisia_rf_dataset.csv dans data/")
    _df = pd.read_csv(path)
    return _df


def _load_rf():
    global _rf_model
    if _rf_model is not None:
        return _rf_model
    path = _find_file(MODEL_CANDIDATES)
    if path is None:
        raise FileNotFoundError("Modèle 'advanced_rf_model.pkl' introuvable.")
    _rf_model = joblib.load(path)
    return _rf_model


def _load_timesfm():
    global _timesfm_model
    if _timesfm_model is not None:
        return _timesfm_model
    import timesfm
    hparams = timesfm.TimesFmHparams(
        backend="cpu",
        context_len=128,
        horizon_len=HORIZON_LEN,
        input_patch_len=32,
        output_patch_len=128,
        num_layers=20,
        model_dims=1280,
        per_core_batch_size=32,
        use_positional_embedding=False,
    )
    checkpoint = timesfm.TimesFmCheckpoint(
        huggingface_repo_id="google/timesfm-1.0-200m-pytorch"
    )
    _timesfm_model = timesfm.TimesFm(hparams=hparams, checkpoint=checkpoint)
    return _timesfm_model


def _feature_engineering(df_combined):
    df_combined = df_combined.copy()
    df_combined["temp_ext_rolling10"] = df_combined["temp_ext"].rolling(window=10, min_periods=1).mean()
    df_combined["humidity_rolling10"] = df_combined["humidity"].rolling(window=10, min_periods=1).mean()
    df_combined["rack1_delta_temp"]   = df_combined["rack1_h"] - df_combined["rack1_b"]
    df_combined["rack2_delta_temp"]   = df_combined["rack2_h"] - df_combined["rack2_b"]
    return df_combined


# ─── Fonction principale ───────────────────────────────────────────────────────
def run_prediction():
    """
    Exécute la pipeline complète et retourne un dict structuré pour l'API.
    """
    df = _load_data()
    rf = _load_rf()
    tfm = _load_timesfm()

    # 1. Prévision TimesFM sur les 11 capteurs bruts
    inputs = [df[feat].values[-CONTEXT_LEN:] for feat in BASE_FEATURES]
    frequencies = [0] * len(BASE_FEATURES)
    point_forecast, _ = tfm.forecast(inputs, freq=frequencies)

    # Valeurs actuelles (dernière ligne réelle)
    current_values = {feat: float(df[feat].iloc[-1]) for feat in BASE_FEATURES}

    # Valeurs prévues à +30 min (dernier point de l'horizon)
    predicted_values = {feat: float(point_forecast[i][-1]) for i, feat in enumerate(BASE_FEATURES)}

    # 2. Feature engineering sur passé + futur combiné
    past_df    = df[BASE_FEATURES].iloc[-CONTEXT_LEN:].copy()
    future_raw = pd.DataFrame({feat: point_forecast[i][:HORIZON_LEN] for i, feat in enumerate(BASE_FEATURES)})
    combined   = pd.concat([past_df, future_raw], ignore_index=True)
    combined   = _feature_engineering(combined)

    # 3. Prédiction RF sur le futur uniquement
    X_future = combined.iloc[-HORIZON_LEN:][RF_FEATURES]
    future_proba = rf.predict_proba(X_future)[:, 1]   # proba de panne [0..1]

    # Risque global = max de la courbe du futur (scénario le plus pessimiste)
    global_risk = float(np.max(future_proba) * 100)

    if global_risk >= 70:
        status = "CRITIQUE"
    elif global_risk >= 40:
        status = "ALERTE"
    else:
        status = "NORMAL"

    # 4. Contribution par capteur (via importances du RF × delta normalisé)
    importances = rf.feature_importances_       # par RF_FEATURE
    feature_importance_map = dict(zip(RF_FEATURES, importances))

    sensor_list = []
    total_base_importance = 0
    raw_sensor_importance = {}

    for feat in BASE_FEATURES:
        # Somme des importances des variables liées à ce capteur
        related_keys = [k for k in RF_FEATURES if k.startswith(feat)]
        importance_sum = sum(feature_importance_map.get(k, 0) for k in related_keys)
        raw_sensor_importance[feat] = importance_sum
        total_base_importance += importance_sum

    # Normalisation des contributions en %
    contributions = {
        feat: round((raw_sensor_importance[feat] / total_base_importance) * 100, 1)
        for feat in BASE_FEATURES
    }

    # Niveau de danger par capteur (en tenant compte du delta prédit)
    for feat in BASE_FEATURES:
        meta = SENSOR_META[feat]
        cur  = current_values[feat]
        pred = predicted_values[feat]
        delta = pred - cur
        contribs = contributions[feat]

        # Niveau de danger basé sur les seuils
        is_inverted = feat in ("fuel_level", "battery_health")
        check_val = pred
        if is_inverted:
            # Pour ces capteurs, c'est dangereux quand la valeur BAISSE
            if check_val <= meta["threshold_crit"]:
                danger = "critical"
            elif check_val <= meta["threshold_warn"]:
                danger = "warning"
            else:
                danger = "normal"
        else:
            if check_val >= meta["threshold_crit"]:
                danger = "critical"
            elif check_val >= meta["threshold_warn"]:
                danger = "warning"
            else:
                danger = "normal"

        sensor_list.append({
            "id":                feat,
            "label":             meta["label"],
            "unit":              meta["unit"],
            "icon":              meta["icon"],
            "current_value":     round(cur, 2),
            "predicted_value":   round(pred, 2),
            "delta":             round(delta, 2),
            "risk_contribution": contribs,
            "danger_level":      danger,
            "threshold_warn":    meta["threshold_warn"],
            "threshold_crit":    meta["threshold_crit"],
        })

    # Tri par contribution décroissante
    sensor_list.sort(key=lambda x: x["risk_contribution"], reverse=True)

    return {
        "predicted_at":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "global_risk_percent": round(global_risk, 1),
        "status":              status,
        "horizon_minutes":     HORIZON_LEN,
        "risk_timeline":       [round(float(p) * 100, 2) for p in future_proba],
        "sensors":             sensor_list,
    }
