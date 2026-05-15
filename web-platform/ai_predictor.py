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
XGB_MODEL_CANDIDATES = [
    os.path.join(BASE_DIR, "advanced_xgb_model.pkl"),
    os.path.join(PROJECT_ROOT, "advanced_xgb_model.pkl"),
]
ML_METRICS_CANDIDATES = [
    os.path.join(BASE_DIR, "data", "ml_metrics.json"),
    os.path.join(PROJECT_ROOT, "data", "ml_metrics.json"),
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

CONTEXT_LEN = 128
HORIZON_LEN = 32

# ─── Chargement paresseux des modèles (une seule fois au démarrage) ────────────
_timesfm_model = None
_rf_model = None
_xgb_model = None
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


def _load_xgb():
    global _xgb_model
    if _xgb_model is not None:
        return _xgb_model
    path = _find_file(XGB_MODEL_CANDIDATES)
    if path is None:
        return None  # XGBoost is optional — fall back to RF if missing
    _xgb_model = joblib.load(path)
    return _xgb_model


def _get_best_model():
    """Read ml_metrics.json and return (model_name, model_object).
    Falls back to RF if XGB unavailable or metrics file missing."""
    import json
    metrics_path = _find_file(ML_METRICS_CANDIDATES)
    best_name = "Random Forest"
    if metrics_path:
        try:
            with open(metrics_path, "r", encoding="utf-8") as f:
                best_name = json.load(f).get("best_model", "Random Forest")
        except Exception:
            pass
    if best_name == "XGBoost":
        xgb = _load_xgb()
        if xgb is not None:
            return "XGBoost", xgb
    return "Random Forest", _load_rf()


def _load_timesfm():
    global _timesfm_model
    if _timesfm_model is not None:
        return _timesfm_model
    import timesfm
    hparams = timesfm.TimesFmHparams(
        backend="cpu",
        context_len=CONTEXT_LEN,
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
def run_prediction(csv_path: str = None):
    """
    Exécute la pipeline complète et retourne un dict structuré pour l'API.
    """
    if csv_path:
        df = pd.read_csv(csv_path)
    else:
        df = _load_data()

    model_name, rf = _get_best_model()
    
    # 1. Prévision TimesFM sur les 11 capteurs bruts
    inputs = [df[feat].values[-CONTEXT_LEN:] for feat in BASE_FEATURES]
    
    try:
        tfm = _load_timesfm()
        frequencies = [0] * len(BASE_FEATURES)
        point_forecast, _ = tfm.forecast(inputs, freq=frequencies)
    except ImportError:
        # Fallback: Flat forecast if timesfm is not installed
        print("[WARN] TimesFM non disponible. Utilisation d'une prévision linéaire plate pour RF.")
        point_forecast = []
        for feat in BASE_FEATURES:
            last_val = df[feat].iloc[-1]
            point_forecast.append([float(last_val)] * HORIZON_LEN)

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
    peak_minute = int(np.argmax(future_proba)) + 1   # 1-indexed minutes ahead

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
        feat: round(float(raw_sensor_importance[feat]) / float(total_base_importance) * 100, 1)
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

        # Génération d'un insight IA textuel
        direction = "baisse" if delta < 0 else "hausse" if delta > 0 else "stagnation"
        if danger == "critical":
            ai_insight = f"IA: {direction.capitalize()} critique prévue ({delta:+.1f} {meta['unit']}). Responsable à {contribs}% du risque de panne."
        elif danger == "warning":
            ai_insight = f"IA: Anomalie détectée ({direction}). Le capteur dévie de son comportement nominal."
        else:
            ai_insight = f"IA: Valeurs stables et conformes aux seuils de sécurité."

        sensor_list.append({
            "id":                str(feat),
            "label":             str(meta["label"]),
            "unit":              str(meta["unit"]),
            "icon":              str(meta["icon"]),
            "current_value":     round(float(cur), 2),
            "predicted_value":   round(float(pred), 2),
            "delta":             round(float(delta), 2),
            "risk_contribution": round(float(contribs), 1),
            "danger_level":      str(danger),
            "threshold_warn":    float(meta["threshold_warn"]),
            "threshold_crit":    float(meta["threshold_crit"]),
            "ai_insight":        str(ai_insight)
        })

    # Tri par contribution décroissante
    sensor_list.sort(key=lambda x: x["risk_contribution"], reverse=True)

    # Capteurs binaires : état courant (dernière ligne) + historique récent contextualisé
    binary_sensors = ["water_leak", "cyber_alert"]
    binary_labels = {"water_leak": "Fuites d'eau", "cyber_alert": "Alertes Cyber"}
    for col in binary_sensors:
        if col in df.columns:
            # État courant = dernière valeur observée (0 = inactif, 1 = actif)
            current_state = int(df[col].iloc[-1])
            # Contexte : nombre d'incidents sur les 100 dernières lignes (~1h40)
            recent_count = int(df[col].tail(100).sum())
            danger = "critical" if current_state == 1 else ("warning" if recent_count > 0 else "normal")

            if current_state == 1:
                insight = f"IA: Incident en cours. {recent_count} occurrence(s) sur la dernière heure."
            elif recent_count > 0:
                insight = f"IA: {recent_count} incident(s) récent(s) — surveillance renforcée."
            else:
                insight = "IA: Aucun incident détecté."

            sensor_list.append({
                "id": col,
                "label": binary_labels[col],
                "unit": "actif" if current_state == 1 else "inactif",
                "current_value": current_state,
                "predicted_value": current_state,
                "delta": 0,
                "risk_contribution": 15.0 if current_state == 1 else (5.0 if recent_count > 0 else 0.0),
                "danger_level": danger,
                "is_binary": True,
                "ai_insight": insight
            })

    # ── Construction de l'explication "Pourquoi ce niveau de risque ?" ──────
    # Top 3 capteurs par contribution réelle au modèle
    sorted_sensors = sorted(sensor_list, key=lambda s: s.get("risk_contribution", 0), reverse=True)
    top_contributors = []
    for s in sorted_sensors[:3]:
        if s.get("is_binary"):
            continue
        cur = float(s.get("current_value", 0) or 0)
        pred = float(s.get("predicted_value", 0) or 0)
        delta = float(pred - cur)
        trend = "hausse" if delta > 0.5 else "baisse" if delta < -0.5 else "stable"
        top_contributors.append({
            "id": str(s["id"]),
            "label": str(s["label"]),
            "contribution_percent": round(float(s.get("risk_contribution", 0)), 1),
            "current_value": cur,
            "predicted_value": pred,
            "delta": round(delta, 2),
            "trend": trend,
            "danger_level": str(s.get("danger_level", "normal")),
            "unit": str(s.get("unit", "")),
        })

    # Capteurs déjà en alerte (warning / critical)
    sensors_in_alert = [s for s in sensor_list if s.get("danger_level") in ("warning", "critical") and not s.get("is_binary")]

    # Narration humaine adaptée au statut
    if status == "CRITIQUE":
        if sensors_in_alert:
            alert_names = ", ".join(s["label"] for s in sensors_in_alert[:3])
            narrative = (
                f"Le modèle IA prédit une probabilité de panne de {global_risk:.1f}% "
                f"dans les {peak_minute} prochaines minutes. "
                f"Capteurs actuellement hors seuils : {alert_names}. "
                f"Le modèle anticipe une dégradation combinée des variables {', '.join(c['label'] for c in top_contributors[:2])}."
            )
        else:
            narrative = (
                f"Le modèle prédit une panne probable à +{peak_minute} min ({global_risk:.1f}% de probabilité), "
                f"même si tous les capteurs semblent dans les seuils actuellement. "
                f"L'IA détecte un schéma précurseur dans les trajectoires combinées de {', '.join(c['label'] for c in top_contributors[:2])} — "
                f"signal faible que les seuils statiques ne captent pas."
            )
    elif status == "ALERTE":
        narrative = (
            f"Anomalie en formation : probabilité de {global_risk:.1f}% à +{peak_minute} min. "
            f"Le modèle pondère principalement {', '.join(c['label'] for c in top_contributors[:2])}. "
            f"Surveillance renforcée recommandée."
        )
    else:
        narrative = (
            f"Système nominal — probabilité maximale de panne {global_risk:.1f}% sur l'horizon. "
            f"Aucune action requise."
        )

    explanation = {
        "narrative":         str(narrative),
        "peak_minute":       int(peak_minute),
        "peak_probability":  round(float(global_risk), 1),
        "top_contributors":  top_contributors,
        "sensors_in_alert_count": int(len(sensors_in_alert)),
    }

    return {
        "predicted_at":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "global_risk_percent": round(global_risk, 1),
        "status":              status,
        "horizon_minutes":     HORIZON_LEN,
        "risk_timeline":       [round(float(p) * 100, 2) for p in future_proba],
        "sensors":             sensor_list,
        "model_used":          f"TimesFM (Google) + {model_name}",
        "best_model":          model_name,
        "risk_explanation":    explanation,
    }
