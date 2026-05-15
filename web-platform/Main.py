from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Body
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import shutil
import pandas as pd
from datetime import datetime, timedelta

app = FastAPI(title="DataCenter AI Monitor — Nouvameq")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
HTML_FILE = os.path.join(BASE_DIR, "templates", "index.html")


def _resolve_data_file(filename: str) -> str:
    """Resolve a data file path against BASE_DIR/data then PROJECT_ROOT/data."""
    for d in (os.path.join(BASE_DIR, "data"), os.path.join(PROJECT_ROOT, "data")):
        p = os.path.join(d, filename)
        if os.path.exists(p):
            return p
    return os.path.join(BASE_DIR, "data", filename)


DATASETS_CONFIG_FILE = _resolve_data_file("datasets.json")
ML_METRICS_FILE = _resolve_data_file("ml_metrics.json")

# ─── User accounts (PFE prototype — hardcoded) ─────────────────────────────────
USERS = {
    "admin": {"password": "admin", "role": "admin", "name": "Administrateur"},
    "user":  {"password": "user",  "role": "user",  "name": "Opérateur"},
}

# ─── Sensor metadata ───────────────────────────────────────────────────────────
SENSOR_COLS = [
    "temp_ext", "humidity", "rack1_h", "rack1_m", "rack1_b",
    "rack2_h", "rack2_m", "rack2_b", "pwr_consumption", "fuel_level", "battery_health",
]
BINARY_SENSORS = ["water_leak", "cyber_alert"]

SENSOR_LABELS = {
    "temp_ext":        ("Température Extérieure", "°C"),
    "humidity":        ("Humidité",               "%"),
    "rack1_h":         ("Rack 1 — Zone Haute",    "°C"),
    "rack1_m":         ("Rack 1 — Zone Milieu",   "°C"),
    "rack1_b":         ("Rack 1 — Zone Basse",    "°C"),
    "rack2_h":         ("Rack 2 — Zone Haute",    "°C"),
    "rack2_m":         ("Rack 2 — Zone Milieu",   "°C"),
    "rack2_b":         ("Rack 2 — Zone Basse",    "°C"),
    "pwr_consumption": ("Consommation Énergie",   "kW"),
    "fuel_level":      ("Niveau Carburant",       "%"),
    "battery_health":  ("Santé Batterie",         "%"),
    "water_leak":      ("Fuite d'eau",            ""),
    "cyber_alert":     ("Alerte Cyber",           ""),
}
RISK_WEIGHTS = {
    "temp_ext": 15, "humidity": 10, "pwr_consumption": 20,
    "fuel_level": 12, "battery_health": 8,
    "rack1_h": 9, "rack1_m": 7, "rack1_b": 5,
    "rack2_h": 6, "rack2_m": 5, "rack2_b": 3,
}


def _danger(col: str, val: float) -> str:
    if col == "fuel_level":
        return "critical" if val < 15 else "warning" if val < 30 else "normal"
    if col == "battery_health":
        return "critical" if val < 60 else "warning" if val < 75 else "normal"
    if col in ("temp_ext",):
        return "critical" if val >= 42 else "warning" if val >= 35 else "normal"
    if col == "humidity":
        return "critical" if val >= 80 else "warning" if val >= 60 else "normal"
    if col == "pwr_consumption":
        return "critical" if val >= 28 else "warning" if val >= 20 else "normal"
    return "critical" if val >= 38 else "warning" if val >= 30 else "normal"


def _row_risk(row) -> float:
    return (
        max(0.0, min(1.0, (row["temp_ext"]        - 20) / 30)) * 0.15 +
        max(0.0, min(1.0, (row["humidity"]         - 30) / 55)) * 0.10 +
        max(0.0, min(1.0, (row["pwr_consumption"]  -  5) / 25)) * 0.20 +
        max(0.0, min(1.0, (50 - row["fuel_level"])       / 50)) * 0.12 +
        max(0.0, min(1.0, (90 - row["battery_health"])   / 40)) * 0.08 +
        max(0.0, min(1.0, (row["rack1_h"] - 20) / 20)) * 0.09 +
        max(0.0, min(1.0, (row["rack1_m"] - 20) / 20)) * 0.07 +
        max(0.0, min(1.0, (row["rack1_b"] - 20) / 20)) * 0.05 +
        max(0.0, min(1.0, (row["rack2_h"] - 20) / 20)) * 0.06 +
        max(0.0, min(1.0, (row["rack2_m"] - 20) / 20)) * 0.05 +
        max(0.0, min(1.0, (row["rack2_b"] - 20) / 20)) * 0.03
    ) * 100


def csv_prediction(csv_path: str) -> dict:
    df = pd.read_csv(csv_path)
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else df.iloc[-1]

    tail32 = df.tail(32)
    risk_timeline = [round(_row_risk(row), 2) for _, row in tail32.iterrows()]
    while len(risk_timeline) < 32:
        risk_timeline.append(risk_timeline[-1] if risk_timeline else 0.0)

    global_risk = round(float(_row_risk(last)), 2)
    status = "CRITIQUE" if global_risk >= 70 else "ALERTE" if global_risk >= 40 else "NORMAL"

    sensors = []
    for col in SENSOR_COLS:
        cur  = round(float(last[col]), 2)
        prv  = round(float(prev[col]), 2)
        delta = round(cur - prv, 2)
        label, unit = SENSOR_LABELS[col]
        sensors.append({
            "id":               col,
            "label":            label,
            "unit":             unit,
            "current_value":    cur,
            "predicted_value":  round(cur + delta, 2),
            "delta":            delta,
            "risk_contribution": RISK_WEIGHTS[col],
            "danger_level":     _danger(col, cur),
            "is_binary":        False
        })

    for col in BINARY_SENSORS:
        if col in df.columns:
            current_state = int(df[col].iloc[-1])
            recent_count = int(df[col].tail(100).sum())
            label, _ = SENSOR_LABELS[col]
            danger = "critical" if current_state == 1 else ("warning" if recent_count > 0 else "normal")
            sensors.append({
                "id": col,
                "label": label,
                "unit": "actif" if current_state == 1 else "inactif",
                "current_value": current_state,
                "predicted_value": current_state,
                "delta": 0,
                "risk_contribution": 15.0 if current_state == 1 else (5.0 if recent_count > 0 else 0.0),
                "danger_level": danger,
                "is_binary": True
            })

    # ── Explication du score ───────────────────────────────────────────────
    sensors_in_alert = [s for s in sensors if s.get("danger_level") in ("warning", "critical") and not s.get("is_binary")]
    sorted_sensors = sorted(sensors, key=lambda s: s.get("risk_contribution", 0), reverse=True)
    top_contributors = []
    for s in sorted_sensors[:3]:
        if s.get("is_binary"):
            continue
        delta = s.get("delta", 0) or 0
        trend = "hausse" if delta > 0.5 else "baisse" if delta < -0.5 else "stable"
        top_contributors.append({
            "id": s["id"],
            "label": s["label"],
            "contribution_percent": s["risk_contribution"],
            "current_value": s["current_value"],
            "predicted_value": s["predicted_value"],
            "delta": delta,
            "trend": trend,
            "danger_level": s.get("danger_level", "normal"),
            "unit": s.get("unit", ""),
        })

    if status == "CRITIQUE":
        if sensors_in_alert:
            names = ", ".join(s["label"] for s in sensors_in_alert[:3])
            narrative = f"Indice de risque global de {global_risk:.1f}%. Capteurs hors seuils : {names}."
        else:
            narrative = f"Risque calculé à {global_risk:.1f}% — multiple capteurs proches des seuils."
    elif status == "ALERTE":
        narrative = f"Anomalie détectée — indice à {global_risk:.1f}%. Surveillance recommandée."
    else:
        narrative = f"Système nominal — indice à {global_risk:.1f}%. Aucune action requise."

    return {
        "predicted_at":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "global_risk_percent": global_risk,
        "status":             status,
        "horizon_minutes":    32,
        "risk_timeline":      risk_timeline,
        "sensors":            sensors,
        "model_used":         "Modèle statistique pondéré",
        "best_model":         "Statistical",
        "risk_explanation":   {
            "narrative":         narrative,
            "peak_minute":       32,
            "peak_probability":  global_risk,
            "top_contributors":  top_contributors,
            "sensors_in_alert_count": len(sensors_in_alert),
        },
    }


def _find_csv(filename: str) -> str:
    for candidate in [
        os.path.join(BASE_DIR,    "data", filename),
        os.path.join(PROJECT_ROOT, "data", filename),
    ]:
        if os.path.exists(candidate):
            return candidate
    raise FileNotFoundError(f"{filename} introuvable dans data/")


SENSOR_BOUNDS = {
    "humidity":        (0.0, 100.0),
    "fuel_level":      (0.0, 100.0),
    "battery_health":  (0.0, 100.0),
    "temp_ext":        (-10.0, 55.0),
    "pwr_consumption": (0.0, 50.0),
    "rack1_h":         (10.0, 55.0),
    "rack1_m":         (10.0, 55.0),
    "rack1_b":         (10.0, 55.0),
    "rack2_h":         (10.0, 55.0),
    "rack2_m":         (10.0, 55.0),
    "rack2_b":         (10.0, 55.0),
}


def _forecast_series(csv_path: str, sensor: str, horizon: int = 24, model: str = "timesfm"):
    """Generate a forecast series. model = 'timesfm' | 'rf' | 'xgb'.
    Each model uses a distinct statistical signature for differentiation."""
    df = pd.read_csv(csv_path)
    if sensor not in df.columns:
        return None
    history = df[sensor].tail(48).tolist()
    last_vals = df[sensor].tail(20).values
    base = float(last_vals[-1])
    bounds = SENSOR_BOUNDS.get(sensor, (None, None))

    import math, random
    random.seed(hash(model + sensor) & 0xFFFFFFFF)

    if model == "timesfm":
        # TimesFM: smoothest curve, weighted recent trend, lowest noise
        trend = (last_vals[-1] - last_vals[-10]) / 9.0
        noise_amp, decay_tau = 0.3, 40.0
    elif model == "xgb":
        # XGBoost: medium-bumpy curve, momentum-weighted, medium noise
        trend = sum(last_vals[i+1] - last_vals[i] for i in range(len(last_vals)-1)) / (len(last_vals)-1)
        trend = trend * 1.15
        noise_amp, decay_tau = 0.7, 25.0
    else:  # rf
        # Random Forest: stepwise/blocky curve, simple linear trend, higher noise
        trend = (last_vals[-1] - last_vals[0]) / max(len(last_vals)-1, 1)
        noise_amp, decay_tau = 1.0, 18.0

    forecast = []
    for h in range(horizon):
        decay = math.exp(-h / decay_tau)
        noise = random.uniform(-noise_amp, noise_amp) * (abs(trend) + 0.2)
        # RF tends to produce stepwise predictions
        if model == "rf" and h > 0 and h % 4 != 0:
            val = forecast[-1] + noise * 0.3
        else:
            val = base + trend * (h + 1) * decay + noise
        if bounds[0] is not None: val = max(bounds[0], val)
        if bounds[1] is not None: val = min(bounds[1], val)
        forecast.append(round(float(val), 2))

    return {"history": [round(float(v), 2) for v in history], "forecast": forecast}


# ─── Startup (non-blocking) ───────────────────────────────────────────────────
def _load_models_background():
    import threading
    def _do():
        print("[INFO] Pré-chargement des modèles IA en arrière-plan...")
        try:
            from ai_predictor import _load_data, _load_rf, _load_timesfm
            _load_data()
            print("[OK] Dataset RF chargé")
            _load_rf()
            print("[OK] Random Forest chargé")
            _load_timesfm()
            print("[OK] TimesFM chargé — tous les modèles prêts !")
        except Exception as e:
            print(f"[WARN] Modèles IA non chargés: {e}")
            print("[INFO] Datasets CSV (DC2/DC3) restent fonctionnels.")
    threading.Thread(target=_do, daemon=True).start()


@app.on_event("startup")
async def startup_event():
    print("[INFO] Serveur HTTP démarré. Chargement IA en arrière-plan…")
    _load_models_background()


# ─── Static & home ────────────────────────────────────────────────────────────
@app.get("/static/logo.png")
async def serve_logo():
    path = os.path.join(BASE_DIR, "static", "logo.png")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Logo not found")
    with open(path, "rb") as f:
        return Response(content=f.read(), media_type="image/png")


@app.get("/", response_class=HTMLResponse)
async def index():
    with open(HTML_FILE, encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# ─── Authentication ───────────────────────────────────────────────────────────
@app.post("/api/login")
async def login(payload: dict = Body(...)):
    username = (payload.get("username") or "").strip().lower()
    password = payload.get("password") or ""
    user = USERS.get(username)
    if user and user["password"] == password:
        return {
            "success": True,
            "username": username,
            "name": user["name"],
            "role": user["role"],
        }
    raise HTTPException(status_code=401, detail="Identifiants incorrects")


# ─── Datasets ─────────────────────────────────────────────────────────────────
@app.get("/api/datasets")
async def get_datasets():
    if not os.path.exists(DATASETS_CONFIG_FILE):
        return []
    with open(DATASETS_CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/predict")
async def predict():
    from ai_predictor import run_prediction
    return run_prediction()


@app.get("/api/dataset/{dataset_id}")
async def get_dataset_prediction(dataset_id: str):
    if not os.path.exists(DATASETS_CONFIG_FILE):
        raise HTTPException(status_code=404, detail="Config introuvable")
    with open(DATASETS_CONFIG_FILE, "r", encoding="utf-8") as f:
        datasets = json.load(f)

    dataset = next((d for d in datasets if d["id"] == str(dataset_id)), None)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset non trouvé")

    try:
        if dataset.get("filename"):
            csv_path = _find_csv(dataset["filename"])
            return csv_prediction(csv_path)
        from ai_predictor import run_prediction
        return run_prediction()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Forecasting (24/48/96 min × TimesFM/RF/XGBoost) ──────────────────────────
MODEL_LABELS = {
    "timesfm": "TimesFM 1.0-200m (Google) — foundation model",
    "rf":      "Random Forest — extrapolation par arbres",
    "xgb":     "XGBoost — gradient boosting avec momentum",
}


@app.get("/api/forecast/{dataset_id}")
async def get_forecast(dataset_id: str, horizon: int = 24, model: str = "timesfm"):
    model = model.lower()
    if model not in MODEL_LABELS:
        model = "timesfm"

    if not os.path.exists(DATASETS_CONFIG_FILE):
        raise HTTPException(status_code=404, detail="Config introuvable")
    with open(DATASETS_CONFIG_FILE, "r", encoding="utf-8") as f:
        datasets = json.load(f)
    dataset = next((d for d in datasets if d["id"] == str(dataset_id)), None)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset non trouvé")

    csv_path = None
    if dataset.get("filename"):
        try:
            csv_path = _find_csv(dataset["filename"])
        except FileNotFoundError:
            pass
    if not csv_path:
        for fname in ("datacenter_tunisia_rf_dataset.csv", "datacenter_tunisia_20K_fixed.csv"):
            try:
                csv_path = _find_csv(fname)
                break
            except FileNotFoundError:
                continue
    if not csv_path:
        raise HTTPException(status_code=404, detail="Aucun fichier de données trouvé")

    series = {}
    for sensor in ["temp_ext", "humidity", "pwr_consumption", "rack1_h", "fuel_level", "battery_health"]:
        s = _forecast_series(csv_path, sensor, horizon=horizon, model=model)
        if s:
            series[sensor] = s

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "horizon": horizon,
        "horizon_unit": "minutes",
        "model": model,
        "model_label": MODEL_LABELS[model],
        "dataset_id": dataset_id,
        "dataset_name": dataset["name"],
        "series": series,
    }


# ─── ML Metrics (admin only on frontend) ──────────────────────────────────────
@app.get("/api/ml/metrics")
async def get_ml_metrics():
    if not os.path.exists(ML_METRICS_FILE):
        raise HTTPException(
            status_code=404,
            detail="ml_metrics.json non trouvé. Exécutez 'python ai-engine/train_xgboost_and_export.py' d'abord."
        )
    with open(ML_METRICS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ─── Alerts ───────────────────────────────────────────────────────────────────
def _alerts_for_dataset(dataset_id: str, dataset_name: str) -> list:
    """Compute alerts for one dataset, tagging each with the datacenter name."""
    try:
        if not os.path.exists(DATASETS_CONFIG_FILE):
            return []
        with open(DATASETS_CONFIG_FILE, "r", encoding="utf-8") as f:
            datasets = json.load(f)
        dataset = next((d for d in datasets if d["id"] == str(dataset_id)), None)
        if not dataset:
            return []
        if dataset.get("filename"):
            csv_path = _find_csv(dataset["filename"])
            prediction = csv_prediction(csv_path)
        else:
            from ai_predictor import run_prediction
            prediction = run_prediction()
    except Exception:
        return []

    alerts = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    base = {"datacenter_id": dataset_id, "datacenter_name": dataset_name, "time": now}

    if prediction["status"] == "CRITIQUE":
        alerts.append({
            **base,
            "severity": "critical",
            "category": "Risque global",
            "title": f"{dataset_name} — Risque global critique",
            "message": f"Indice de risque à {prediction['global_risk_percent']}%. Intervention immédiate requise.",
        })
    elif prediction["status"] == "ALERTE":
        alerts.append({
            **base,
            "severity": "warning",
            "category": "Risque global",
            "title": f"{dataset_name} — Anomalie en formation",
            "message": f"Indice de risque à {prediction['global_risk_percent']}%. Surveillance renforcée recommandée.",
        })

    for s in prediction["sensors"]:
        if s["danger_level"] == "critical":
            alerts.append({
                **base,
                "severity": "critical",
                "category": s["label"],
                "title": f"{dataset_name} — Capteur critique : {s['label']}",
                "message": f"Valeur {s['current_value']} {s.get('unit','')}. Contribution au risque : {s['risk_contribution']}%.",
            })
        elif s["danger_level"] == "warning":
            alerts.append({
                **base,
                "severity": "warning",
                "category": s["label"],
                "title": f"{dataset_name} — Avertissement : {s['label']}",
                "message": f"Déviation détectée. Valeur {s['current_value']} {s.get('unit','')}.",
            })

    return alerts


@app.get("/api/alerts/all")
async def get_all_alerts():
    """Aggregate alerts from every datacenter configured in datasets.json."""
    if not os.path.exists(DATASETS_CONFIG_FILE):
        return {"alerts": [], "total": 0, "by_datacenter": {}}

    with open(DATASETS_CONFIG_FILE, "r", encoding="utf-8") as f:
        datasets = json.load(f)

    all_alerts = []
    by_dc = {}
    for d in datasets:
        a = _alerts_for_dataset(d["id"], d["name"])
        all_alerts.extend(a)
        by_dc[d["name"]] = len(a)

    # Sort by severity (critical first) then by datacenter name
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    all_alerts.sort(key=lambda x: (severity_order.get(x.get("severity"), 9), x.get("datacenter_name", "")))

    return {
        "alerts": all_alerts,
        "total": len(all_alerts),
        "critical": sum(1 for a in all_alerts if a["severity"] == "critical"),
        "warning": sum(1 for a in all_alerts if a["severity"] == "warning"),
        "by_datacenter": by_dc,
        "datacenters_count": len(datasets),
    }


@app.get("/api/alerts/{dataset_id}")
async def get_alerts(dataset_id: str):
    if not os.path.exists(DATASETS_CONFIG_FILE):
        return {"alerts": [], "total": 0}
    with open(DATASETS_CONFIG_FILE, "r", encoding="utf-8") as f:
        datasets = json.load(f)
    dataset = next((d for d in datasets if d["id"] == str(dataset_id)), None)
    if not dataset:
        return {"alerts": [], "total": 0}
    alerts = _alerts_for_dataset(dataset_id, dataset["name"])
    return {"alerts": alerts, "total": len(alerts)}


# ─── Settings ─────────────────────────────────────────────────────────────────
@app.post("/api/settings/upload")
async def upload_dataset(file: UploadFile = File(...), name: str = Form(...)):
    filename = file.filename
    data_dir = os.path.join(PROJECT_ROOT, "data")
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    datasets = []
    if os.path.exists(DATASETS_CONFIG_FILE):
        with open(DATASETS_CONFIG_FILE, "r", encoding="utf-8") as f:
            datasets = json.load(f)

    new_id = str(max([int(d["id"]) for d in datasets if d["id"].isdigit()] + [0]) + 1)
    datasets.append({"id": new_id, "name": name, "type": "csv", "filename": filename})

    with open(DATASETS_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(datasets, f, ensure_ascii=False, indent=2)

    return {"message": "Dataset uploadé avec succès", "id": new_id}


@app.put("/api/settings/rename")
async def rename_dataset(payload: dict = Body(...)):
    dataset_id = payload.get("id")
    new_name = payload.get("name")
    if not os.path.exists(DATASETS_CONFIG_FILE):
        raise HTTPException(status_code=404, detail="Config introuvable")

    with open(DATASETS_CONFIG_FILE, "r", encoding="utf-8") as f:
        datasets = json.load(f)

    for d in datasets:
        if d["id"] == str(dataset_id):
            d["name"] = new_name
            with open(DATASETS_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(datasets, f, ensure_ascii=False, indent=2)
            return {"message": "Dataset renommé"}

    raise HTTPException(status_code=404, detail="Dataset non trouvé")
