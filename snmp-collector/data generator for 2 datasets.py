import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

ROWS = 20000 

def generate_normal_data(n_rows, filename, seed_offset=0):
    np.random.seed(42 + seed_offset) # for reproducibility but different for each file
    print(f"Generation du dataset {filename}...")
    
    start_time = datetime.now() - timedelta(seconds=n_rows * 20)
    timestamps = [start_time + timedelta(seconds=i*20) for i in range(n_rows)]

    season_mask = np.sin(np.linspace(0, 2 * np.pi, n_rows))
    temp_ext = np.where(season_mask > 0, 
                        np.random.normal(32, 3, n_rows), 
                        np.random.normal(18, 3, n_rows))
    
    humidity = np.where(season_mask > 0, 
                        np.random.normal(40, 5, n_rows), 
                        np.random.normal(55, 8, n_rows)) 

    base_rack_temp = np.where(season_mask > 0, 23, 21)
    r1_h = np.random.normal(base_rack_temp + 2,  0.5, n_rows)
    r1_m = np.random.normal(base_rack_temp + 1,  0.5, n_rows)
    r1_b = np.random.normal(base_rack_temp,      0.5, n_rows)
    r2_h = np.random.normal(base_rack_temp + 2,  0.5, n_rows)
    r2_m = np.random.normal(base_rack_temp + 1,  0.5, n_rows)
    r2_b = np.random.normal(base_rack_temp,      0.5, n_rows)

    pwr_cons = np.random.normal(10, 1, n_rows) 
    fuel = np.linspace(98, 80, n_rows) 
    bat_health = np.random.normal(99, 0.1, n_rows)
    pwr_source = np.ones(n_rows, dtype=int) 
    ac_status = np.ones(n_rows, dtype=int)  

    door_status = np.zeros(n_rows, dtype=int) 
    smoke_sensor = np.zeros(n_rows, dtype=int)
    water_leak = np.zeros(n_rows, dtype=int)
    cyber_alert = np.zeros(n_rows, dtype=int) 
    target = np.zeros(n_rows, dtype=int)

    # INJECTION DES SCÉNARIOS "NORMAUX" / PETITES ALERTES
    print("ATTENTION : Injection des petites alertes (petites variations)...")
    
    # 1. Petite micro-coupure
    idx = np.random.randint(0, n_rows-10)
    pwr_source[idx:idx+2] = 0
    target[idx:idx+2] = 1

    # 2. Petite hausse de température sur un rack
    idx = np.random.randint(0, n_rows-15)
    r1_h[idx:idx+10] += 3
    target[idx:idx+10] = 1
    
    # 3. Ouverture de porte momentanée
    idx = np.random.randint(0, n_rows-5)
    door_status[idx:idx+2] = 1

    df = pd.DataFrame({
        'timestamp': pd.to_datetime(timestamps),
        'temp_ext': temp_ext.round(2),
        'humidity': humidity.round(2),
        'rack1_h': r1_h.round(2), 'rack1_m': r1_m.round(2), 'rack1_b': r1_b.round(2),
        'rack2_h': r2_h.round(2), 'rack2_m': r2_m.round(2), 'rack2_b': r2_b.round(2),
        'pwr_consumption': pwr_cons.round(2),
        'fuel_level': fuel.round(2),
        'battery_health': bat_health.round(2),
        'pwr_source': pwr_source.astype(str),
        'ac_status': ac_status.astype(str),
        'door_open': door_status,
        'smoke_detected': smoke_sensor,
        'water_leak': water_leak,
        'cyber_alert': cyber_alert,
        'target': target
    })

    filepath = os.path.join(DATA_DIR, filename)
    df.to_csv(filepath, index=False)
    print(f"SUCCES : Fichier CSV généré : {filepath} ({os.path.getsize(filepath)/1e6:.2f} MB)")

if __name__ == "__main__":
    generate_normal_data(ROWS, "dataset_normal_1.csv", seed_offset=10)
    generate_normal_data(ROWS, "dataset_normal_2.csv", seed_offset=20)
