from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(title="DataCenter AI Monitor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_FILE = os.path.join(BASE_DIR, "templates", "index.html")

# ─── Chargement des modèles au démarrage (une seule fois) ──────────────────────
@app.on_event("startup")
async def startup_event():
    print("[INFO] Pré-chargement des modèles IA...")
    from ai_predictor import _load_data, _load_rf, _load_timesfm
    _load_data()
    _load_rf()
    _load_timesfm()
    print("[OK] Modèles chargés et prêts !")


# ─── Route principale : interface web ──────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    with open(HTML_FILE, encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# ─── Route API : prédiction ────────────────────────────────────────────────────
@app.get("/api/predict")
async def predict():
    from ai_predictor import run_prediction
    result = run_prediction()
    return result
