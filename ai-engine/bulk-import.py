import os
import pandas as pd
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import WriteOptions

# --- CONFIGURATION ---
TOKEN = os.getenv("INFLUXDB_TOKEN", "-ifTMHhawX5DuysgqTP5ik7K0UyWiqKH3fNPyaQbp4GNTKqQHT0kgmrvNAGfHjZIJw-DzNeKIrgNEP7nYbnKCA==")
ORG = os.getenv("INFLUXDB_ORG", "Nouvameq")
BUCKET = os.getenv("INFLUXDB_BUCKET", "datacenter_metrics")

# Utilise localhost si on l'exécute depuis la machine hôte (comme vous venez de le faire), sinon influxdb en local Docker
URL = os.getenv("INFLUXDB_URL", "http://localhost:8086") 

# Auto-détection du fichier CSV généré par l'autre script
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_FILE = os.path.join(BASE_DIR, "data", "datacenter_tunisia_rf_dataset.csv")

def import_csv():
    # Vérification anti-crash si le fichier n'existe pas
    if not os.path.exists(CSV_FILE):
        print(f"❌ ERREUR : Le script ne trouve pas de fichier à l'adresse -> {CSV_FILE}")
        print("Avez-vous bien lancé 'dataset-generator.py' en premier ?")
        return

    client = InfluxDBClient(url=URL, token=TOKEN, org=ORG, timeout=600_000)
    
    # Mode Batch pour la performance
    with client.write_api(write_options=WriteOptions(batch_size=50_000, flush_interval=10_000, retry_interval=5_000)) as write_api:
        print(f"Lecture de {CSV_FILE}...")
        
        # Lecture par morceaux (chunks) pour ne pas saturer la RAM
        for chunk in pd.read_csv(CSV_FILE, chunksize=50000):
            # Indexer par timestamp (obligatoire pour l'écriture DataFrame dans InfluxDB)
            chunk['timestamp'] = pd.to_datetime(chunk['timestamp'])
            chunk.set_index('timestamp', inplace=True)
            
            # Gérer les tags s'ils existent dans le dataset
            tag_columns = []
            for tag in ['pwr_source', 'ac_status']:
                if tag in chunk.columns:
                    tag_columns.append(tag)
                    chunk[tag] = chunk[tag].astype(str)
            
            print(f"Écriture d'un lot de {len(chunk)} lignes dans InfluxDB...")
            write_api.write(
                bucket=BUCKET,
                record=chunk,
                data_frame_measurement_name='data_center_sensors',
                data_frame_tag_columns=tag_columns
            )

    print("Importation terminée !")

if __name__ == "__main__":
    import_csv()
