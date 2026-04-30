import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import WriteOptions

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
FILENAME = os.path.join(DATA_DIR, "datacenter_tunisia_rf_dataset.csv")

# ============================================================
#  CONFIGURATION PRINCIPALE
# ============================================================
ROWS       = 100_000                        # Nombre de lignes
START_TIME = datetime(2026, 3, 20, 10, 23)  # Début : 20/03/2026 à 10h23
INTERVAL   = 10                             # 1 mesure toutes les 10 secondes

# Configuration InfluxDB
TOKEN = os.getenv(
    "INFLUXDB_TOKEN",
    "-ifTMHhawX5DuysgqTP5ik7K0UyWiqKH3fNPyaQbp4GNTKqQHT0kgmrvNAGfHjZIJw-DzNeKIrgNEP7nYbnKGA=="
)
ORG    = os.getenv("INFLUXDB_ORG",    "Nouvameq")
BUCKET = os.getenv("INFLUXDB_BUCKET", "datacenter_metrics")
URL    = os.getenv("INFLUXDB_URL",    "http://localhost:8086")

# ============================================================
#  COLONNES UTILISÉES PAR LE RANDOM FOREST
# ============================================================
FEATURES = [
    'temp_ext', 'humidity',
    'rack1_h', 'rack1_m', 'rack1_b',
    'rack2_h', 'rack2_m', 'rack2_b',
    'pwr_consumption', 'fuel_level', 'battery_health',
    'door_open', 'smoke_detected', 'water_leak', 'cyber_alert'
]

# ============================================================
def inject_gradual_drift(arr, idx, length, delta, noise=0.3):
    """
    Ajoute une dérive progressive AVANT une panne pour que le
    Random Forest apprenne les signes avant-coureurs.
    La valeur monte/descend graduellement sur 'length' points.
    """
    ramp = np.linspace(0, delta, length) + np.random.normal(0, noise, length)
    end  = min(idx + length, len(arr))
    arr[idx:end] += ramp[:end - idx]
    return arr


def generate_dataset(n_rows: int = ROWS) -> pd.DataFrame:
    print(f"[1/4] Génération du dataset ({n_rows} lignes, intervalle={INTERVAL}s)...")
    print(f"      Période : {START_TIME}  →  {START_TIME + timedelta(seconds=n_rows * INTERVAL)}")

    # ----------------------------------------------------------
    # 1. TIMESTAMPS — début fixe au 20/03/2026 10:23:00
    # ----------------------------------------------------------
    timestamps = [START_TIME + timedelta(seconds=i * INTERVAL) for i in range(n_rows)]

    # ----------------------------------------------------------
    # 2. CONDITIONS NORMALES (baseline)
    # ----------------------------------------------------------
    # Simulation saisonnière légère sur la durée du dataset
    t = np.linspace(0, 2 * np.pi, n_rows)
    season = np.sin(t)                          # variation douce jour/nuit

    temp_ext     = np.where(season > 0,
                            np.random.normal(36, 3, n_rows),   # journée chaude
                            np.random.normal(22, 2, n_rows))   # nuit fraîche

    humidity     = np.where(season > 0,
                            np.random.normal(32, 4, n_rows),
                            np.random.normal(60, 8, n_rows))

    base_rack    = np.where(season > 0, 24.0, 21.0)
    rack1_h      = np.random.normal(base_rack + 3, 0.4, n_rows)
    rack1_m      = np.random.normal(base_rack + 1, 0.4, n_rows)
    rack1_b      = np.random.normal(base_rack,     0.4, n_rows)
    rack2_h      = np.random.normal(base_rack + 3, 0.4, n_rows)
    rack2_m      = np.random.normal(base_rack + 1, 0.4, n_rows)
    rack2_b      = np.random.normal(base_rack,     0.4, n_rows)

    pwr_cons     = np.random.normal(12, 1.5, n_rows)           # kW
    fuel         = np.linspace(98, 20, n_rows)                  # % décroissant normalement
    bat_health   = np.random.normal(99, 0.1, n_rows)
    pwr_source   = np.ones(n_rows, dtype=int)                   # 1 = réseau STEG
    ac_status    = np.ones(n_rows, dtype=int)                   # 1 = climatisation ON

    door_open      = np.zeros(n_rows, dtype=int)
    smoke_detected = np.zeros(n_rows, dtype=int)
    water_leak     = np.zeros(n_rows, dtype=int)
    cyber_alert    = np.zeros(n_rows, dtype=int)

    # target : 0 = Normal | 1 = Panne physique | 2 = Cyber | 3 = Risque imminence (pré-défaillance)
    target = np.zeros(n_rows, dtype=int)

    # ----------------------------------------------------------
    # 3. INJECTION DES SCÉNARIOS D'ERREUR (avec dérives progressives)
    #    Chaque scénario = pré-alerte douce (class 3) + panne franche (class 1 ou 2)
    # ----------------------------------------------------------
    print("[2/4] Injection des scénarios critiques avec dérives pré-panne...")

    rng = np.random.default_rng(seed=42)   # reproductible

    # --- SCÉNARIO A : Coupure STEG (réseau électrique) ---
    nb_steg = max(3, int(n_rows * 0.0003))
    for _ in range(nb_steg):
        idx = rng.integers(200, n_rows - 300)
        pre = 60    # 60 x 10s = 10 min de dérive avant panne
        dur = 150   # durée de la panne

        # Pré-alerte : légère hausse conso + légère baisse carburant
        pwr_cons  = inject_gradual_drift(pwr_cons,  idx - pre, pre, +3.0, 0.2)
        fuel      = inject_gradual_drift(fuel,      idx - pre, pre, -2.0, 0.1)
        target[idx - pre : idx] = 3          # pré-défaillance détectable

        # Panne franche
        end = min(idx + dur, n_rows)
        pwr_source[idx:end]  = 0
        fuel[idx:end]       -= np.linspace(0, 15, end - idx)
        target[idx:end]      = 1

    # --- SCÉNARIO B : Incendie / Surchauffe ---
    nb_fire = max(2, int(n_rows * 0.00005))
    for _ in range(nb_fire):
        idx = rng.integers(120, n_rows - 150)
        pre = 90    # 15 min de montée en température
        dur = 60

        # Pré-alerte : montée douce des racks + légère fumée
        rack1_h = inject_gradual_drift(rack1_h, idx - pre, pre, +18.0, 0.5)
        rack2_h = inject_gradual_drift(rack2_h, idx - pre, pre, +10.0, 0.4)
        temp_ext = inject_gradual_drift(temp_ext, idx - pre, pre, +5.0, 0.3)
        target[idx - pre : idx] = 3

        # Panne franche
        end = min(idx + dur, n_rows)
        smoke_detected[idx:end] = 1
        rack1_h[idx:end]       += 35
        rack2_h[idx:end]       += 20
        ac_status[idx:end]      = 0
        target[idx:end]         = 1

    # --- SCÉNARIO C : Attaque Cyber ---
    nb_cyber = max(3, int(n_rows * 0.0001))
    for _ in range(nb_cyber):
        idx = rng.integers(120, n_rows - 400)
        pre = 120   # 20 min d'activité suspecte progressive
        dur = 300

        # Pré-alerte : légère hausse conso électrique (serveurs sollicités)
        pwr_cons = inject_gradual_drift(pwr_cons, idx - pre, pre, +4.0, 0.3)
        target[idx - pre : idx] = 3

        # Attaque franche
        end = min(idx + dur, n_rows)
        cyber_alert[idx:end] = 1
        pwr_cons[idx:end]   *= 1.9
        target[idx:end]      = 2

    # --- SCÉNARIO D : Fuite d'eau ---
    nb_water = max(2, int(n_rows * 0.00003))
    for _ in range(nb_water):
        idx = rng.integers(60, n_rows - 120)
        pre = 60
        dur = 80

        # Pré-alerte : légère hausse humidité
        humidity = inject_gradual_drift(humidity, idx - pre, pre, +12.0, 0.5)
        target[idx - pre : idx] = 3

        end = min(idx + dur, n_rows)
        water_leak[idx:end] = 1
        target[idx:end]     = 1

    # --- SCÉNARIO E : Batterie dégradée ---
    nb_bat = max(2, int(n_rows * 0.00005))
    for _ in range(nb_bat):
        idx = rng.integers(60, n_rows - 180)
        pre = 90
        dur = 120

        bat_health = inject_gradual_drift(bat_health, idx - pre, pre, -15.0, 0.2)
        target[idx - pre : idx] = 3

        end = min(idx + dur, n_rows)
        bat_health[idx:end] -= 25
        target[idx:end]      = 1

    # --- SCÉNARIO F : Porte datacenter ouverte trop longtemps ---
    nb_door = max(3, int(n_rows * 0.0002))
    for _ in range(nb_door):
        idx = rng.integers(0, n_rows - 80)
        dur = rng.integers(20, 60)
        end = min(idx + dur, n_rows)
        door_open[idx:end] = 1
        # pas critique seul, mais contribue aux features

    # ----------------------------------------------------------
    # 4. ASSEMBLAGE FINAL
    # ----------------------------------------------------------
    print("[3/4] Assemblage du DataFrame...")

    df = pd.DataFrame({
        'timestamp':      pd.to_datetime(timestamps),
        'temp_ext':       temp_ext.round(2),
        'humidity':       humidity.round(2),
        'rack1_h':        rack1_h.round(2),
        'rack1_m':        rack1_m.round(2),
        'rack1_b':        rack1_b.round(2),
        'rack2_h':        rack2_h.round(2),
        'rack2_m':        rack2_m.round(2),
        'rack2_b':        rack2_b.round(2),
        'pwr_consumption': pwr_cons.round(2),
        'fuel_level':     fuel.round(2),
        'battery_health': bat_health.round(2),
        'pwr_source':     pwr_source.astype(str),   # tag InfluxDB
        'ac_status':      ac_status.astype(str),    # tag InfluxDB
        'door_open':      door_open,
        'smoke_detected': smoke_detected,
        'water_leak':     water_leak,
        'cyber_alert':    cyber_alert,
        'target':         target                    # 0=Normal 1=Panne 2=Cyber 3=Pré-alerte
    })

    # Sauvegarde CSV
    df.to_csv(FILENAME, index=False)
    size_mb = os.path.getsize(FILENAME) / 1e6
    print(f"[3/4] CSV sauvegardé : {FILENAME}  ({size_mb:.2f} MB)")

    # Distribution des classes pour vérification
    dist = df['target'].value_counts().sort_index()
    labels = {0: 'Normal', 1: 'Panne physique', 2: 'Cyber', 3: 'Pré-alerte'}
    print("\n      Distribution des classes :")
    for k, v in dist.items():
        pct = v / n_rows * 100
        print(f"        class {k} ({labels.get(k,'?')}) : {v:>7} lignes  ({pct:.2f}%)")

    return df


def push_to_influxdb(df: pd.DataFrame):
    print(f"\n[4/4] Insertion vers InfluxDB → {URL} / {BUCKET} ...")
    df_influx = df.copy()
    df_influx.set_index('timestamp', inplace=True)

    with InfluxDBClient(url=URL, token=TOKEN, org=ORG, timeout=600_000) as client:
        with client.write_api(write_options=WriteOptions(
            batch_size=50_000,
            flush_interval=10_000,
            retry_interval=5_000
        )) as write_api:
            write_api.write(
                bucket=BUCKET,
                record=df_influx,
                data_frame_measurement_name='data_center_sensors',
                data_frame_tag_columns=['pwr_source', 'ac_status']
            )

    print("      Données insérées avec succès dans InfluxDB ✓")


if __name__ == "__main__":
    df = generate_dataset(ROWS)
    push_to_influxdb(df)
    print("\n=== TERMINÉ ===")
    print(f"Dataset prêt pour l'entraînement Random Forest : {FILENAME}")
    print(f"Features disponibles : {FEATURES}")
    print(f"Colonne cible        : 'target'  (0=Normal | 1=Panne | 2=Cyber | 3=Pré-alerte)")