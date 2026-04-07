import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import WriteOptions

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
FILENAME = os.path.join(DATA_DIR, "datacenter_tunisia_2M.csv")

# Réduit le nombre de ligne temporairement si l'insertion de 2 Millions de lignes est trop longue.
ROWS = 200000 

# Configuration InfluxDB
TOKEN = os.getenv(
    "INFLUXDB_TOKEN",
    "-ifTMHhawX5DuysgqTP5ik7K0UyWiqKH3fNPyaQbp4GNTKqQHT0kgmrvNAGfHjZIJw-DzNeKIrgNEP7nYbnKCA=="
)
ORG = os.getenv("INFLUXDB_ORG", "Nouvameq")
BUCKET = os.getenv("INFLUXDB_BUCKET", "datacenter_metrics")
URL = os.getenv("INFLUXDB_URL", "http://localhost:8086") # Ajuster à `http://influxdb:8086` si lancé dans Docker

def generate_tunisian_dc_data(n_rows):
    print(f"Generation du dataset (Normes Tunisie - Nouvameq)...")
    
    # 1. Base de temps (1 mesure toutes les 20 secondes)
    start_time = datetime.now() - timedelta(seconds=n_rows * 20)
    timestamps = [start_time + timedelta(seconds=i*20) for i in range(n_rows)]

    # 2. Simulation Climatique Tunisienne (Saisonnalité)
    season_mask = np.sin(np.linspace(0, 2 * np.pi, n_rows)) # > 0: Été, < 0: Hiver
    temp_ext = np.where(season_mask > 0, 
                        np.random.normal(38, 5, n_rows), # Été
                        np.random.normal(16, 4, n_rows)) # Hiver
    
    humidity = np.where(season_mask > 0, 
                        np.random.normal(30, 5, n_rows), 
                        np.random.normal(65, 10, n_rows)) 

    # 3. Infrastructure Racks (2 Racks, 3 niveaux chacun)
    base_rack_temp = np.where(season_mask > 0, 24, 21)
    r1_h = np.random.normal(base_rack_temp + 3,  0.5, n_rows)
    r1_m = np.random.normal(base_rack_temp + 1,  0.5, n_rows)
    r1_b = np.random.normal(base_rack_temp,      0.5, n_rows)
    r2_h = np.random.normal(base_rack_temp + 3,  0.5, n_rows)
    r2_m = np.random.normal(base_rack_temp + 1,  0.5, n_rows)
    r2_b = np.random.normal(base_rack_temp,      0.5, n_rows)

    # 4. Énergie
    pwr_cons = np.random.normal(12, 2, n_rows) 
    fuel = np.linspace(98, 15, n_rows) 
    bat_health = np.random.normal(99, 0.1, n_rows)
    pwr_source = np.ones(n_rows, dtype=int) 
    ac_status = np.ones(n_rows, dtype=int)  

    # 5. Sécurité & Access
    door_status = np.zeros(n_rows, dtype=int) 
    smoke_sensor = np.zeros(n_rows, dtype=int)
    water_leak = np.zeros(n_rows, dtype=int)
    cyber_alert = np.zeros(n_rows, dtype=int) 
    
    target = np.zeros(n_rows, dtype=int)

    # 6. INJECTION DES SCÉNARIOS CRITIQUES
    print("ATTENTION : Injection des scenarios critiques (Coupures, Incendies, Cyber)...")
    
    for _ in range(max(1, int(n_rows * 0.0001))): # Scénario A : Coupure STEG
        idx = np.random.randint(0, n_rows-200)
        pwr_source[idx:idx+150] = 0
        fuel[idx:idx+150] -= np.linspace(0, 10, 150)
        target[idx:idx+150] = 1

    for _ in range(max(1, int(n_rows * 0.000025))): # Scénario B : Incendie 
        idx = np.random.randint(0, n_rows-100)
        smoke_sensor[idx:idx+50] = 1
        r1_h[idx:idx+50] += 35
        target[idx:idx+50] = 1

    for _ in range(max(1, int(n_rows * 0.00005))): # Scénario C : Piratage
        idx = np.random.randint(0, n_rows-300)
        cyber_alert[idx:idx+300] = 1
        pwr_cons[idx:idx+300] *= 1.8
        target[idx:idx+300] = 2

    for _ in range(max(1, int(n_rows * 0.000015))): # Scénario D : Fuite d'eau
        idx = np.random.randint(0, n_rows-100)
        water_leak[idx:idx+50] = 1
        target[idx:idx+50] = 1

    # 7. Assemblage Final
    df = pd.DataFrame({
        'timestamp': pd.to_datetime(timestamps),
        'temp_ext': temp_ext.round(2),
        'humidity': humidity.round(2),
        'rack1_h': r1_h.round(2), 'rack1_m': r1_m.round(2), 'rack1_b': r1_b.round(2),
        'rack2_h': r2_h.round(2), 'rack2_m': r2_m.round(2), 'rack2_b': r2_b.round(2),
        'pwr_consumption': pwr_cons.round(2),
        'fuel_level': fuel.round(2),
        'battery_health': bat_health.round(2),
        'pwr_source': pwr_source.astype(str), # Transformé en string pour être un "tag"
        'ac_status': ac_status.astype(str),   # Transformé en string pour être un "tag"
        'door_open': door_status,
        'smoke_detected': smoke_sensor,
        'water_leak': water_leak,
        'cyber_alert': cyber_alert,
        'target': target
    })

    # Optionnel: Sauvegarde CSV pour archive
    df.to_csv(FILENAME, index=False)
    print(f"SUCCES : Fichier CSV généré : {FILENAME} ({os.path.getsize(FILENAME)/1e6:.2f} MB)")
    
    # 8. Export vers InfluxDB
    print(f"DEBUT de l'insertion ({n_rows} lignes) vers InfluxDB...")
    print(f"URL: {URL} | Bucket: {BUCKET}")
    
    # 8.1 InfluxDB python_client supporte nativement l'insertion de DataFrame Pandas!
    # Il suffit de mettre le timestamp en index :
    df.set_index('timestamp', inplace=True)
    
    # Configuration du client pour traiter en grands lots (Performance maximale)
    with InfluxDBClient(url=URL, token=TOKEN, org=ORG, timeout=600_000) as client:
        # L'option WriteOptions(batch_size=X) est primordiale pour injecter de la data massive en asynchrone
        with client.write_api(write_options=WriteOptions(batch_size=50_000, 
                                                         flush_interval=10_000,
                                                         retry_interval=5000)) as write_api:
            
            # En utilisant pandas DataFrame, les colonnes deviennent des "fields", et les index devient le "time"
            # on précise `data_frame_measurement_name` pour lier aux mêmes métriques que l'AKCP
            write_api.write(bucket=BUCKET, 
                            record=df, 
                            data_frame_measurement_name='data_center_sensors',
                            data_frame_tag_columns=['pwr_source', 'ac_status'])
            
    print("SUCCES : Données massives insérées avec succès dans InfluxDB !")

if __name__ == "__main__":
    generate_tunisian_dc_data(ROWS)
