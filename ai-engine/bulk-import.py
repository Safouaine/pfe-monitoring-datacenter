import os
import pandas as pd
from influxdb_client import InfluxDBClient, Point, WriteOptions
from datetime import datetime

# --- CONFIGURATION ---
TOKEN = os.getenv("INFLUXDB_TOKEN", "-ifTMHhawX5DuysgqTP5ik7K0UyWiqKH3fNPyaQbp4GNTKqQHT0kgmrvNAGfHjZIJw-DzNeKIrgNEP7nYbnKCA==")
ORG = os.getenv("INFLUXDB_ORG", "Nouvameq")
BUCKET = os.getenv("INFLUXDB_BUCKET", "datacenter_data")

# Utilise localhost si on l'exécute depuis la machine hôte (comme vous venez de le faire), sinon influxdb en local Docker
URL = os.getenv("INFLUXDB_URL", "http://localhost:8086") 

# Auto-détection du fichier CSV généré par l'autre script
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_FILE = os.path.join(BASE_DIR, "data", "datacenter_tunisia_2M.csv")

def import_csv():
    # Vérification anti-crash si le fichier n'existe pas
    if not os.path.exists(CSV_FILE):
        print(f"❌ ERREUR : Le script ne trouve pas de fichier à l'adresse -> {CSV_FILE}")
        print("Avez-vous bien lancé 'dataset-generator.py' en premier ?")
        return

    client = InfluxDBClient(url=URL, token=TOKEN, org=ORG)
    
    # Mode Batch pour la performance
    with client.write_api(write_options=WriteOptions(batch_size=5000, flush_interval=10_000)) as write_api:
        print(f"Lecture de {CSV_FILE}...")
        
        # Lecture par morceaux (chunks) pour ne pas saturer la RAM
        for chunk in pd.read_csv(CSV_FILE, chunksize=10000):
            points = []
            for _, row in chunk.iterrows():
                p = (Point("data_center_sensors")
                    .tag("source", "digital_twin")
                    .field("temp_ext", float(row['temp_ext']))
                    .field("rack1_h", float(row['rack1_h']))
                    .field("fuel_level", float(row['fuel_level']))
                    .field("pwr_cons", float(row['pwr_consumption']))
                    .field("target", int(row['target']))
                    .time(pd.to_datetime(row['timestamp'])))
                points.append(p)
            
            write_api.write(bucket=BUCKET, record=points)
            print(f"Lot de {len(points)} lignes envoyé...")

    print("Importation terminée !")

if __name__ == "__main__":
    import_csv()
