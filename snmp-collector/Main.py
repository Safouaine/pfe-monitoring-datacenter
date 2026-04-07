import os
import time
import logging
from pysnmp.hlapi import (
    SnmpEngine,
    nextCmd,
    CommunityData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity
)
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# --- Configuration du logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- CONFIGURATION ---
# Utilisation de variables d'environnement (ex: avec Docker)
IP_AKCP = os.getenv("IP_AKCP", "192.168.1.100")
COMMUNITY = os.getenv("SNMP_COMMUNITY", "public")

# Configuration InfluxDB
TOKEN = os.getenv(
    "INFLUXDB_TOKEN",
    "-ifTMHhawX5DuysgqTP5ik7K0UyWiqKH3fNPyaQbp4GNTKqQHT0kgmrvNAGfHjZIJw-DzNeKIrgNEP7nYbnKCA=="
)
ORG = os.getenv("INFLUXDB_ORG", "Nouvameq")
BUCKET = os.getenv("INFLUXDB_BUCKET", "datacenter_metrics")
URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))

# OID AKCP pour lister les descriptions des capteurs et les valeurs réelles
OID_DESCRIPTIONS = "1.3.6.1.4.1.3854.1.2.2.1.16.1.1"
OID_VALEURS = "1.3.6.1.4.1.3854.1.2.2.1.16.1.3"


def get_all_sensors(snmp_engine, ip, base_oid):
    """Effectue un SNMP WALK pour lister tous les capteurs."""
    sensors = {}
    iterator = nextCmd(
        snmp_engine,
        CommunityData(COMMUNITY),
        UdpTransportTarget((ip, 161), timeout=2, retries=1),
        ContextData(),
        ObjectType(ObjectIdentity(base_oid)),
        lexicographicMode=False
    )

    for (errorIndication, errorStatus, errorIndex, varBinds) in iterator:
        if errorIndication:
            logging.error(f"Erreur SNMP (Indication) : {errorIndication}")
            break
        elif errorStatus:
            logging.error(
                f"Erreur SNMP (Statut) : {errorStatus.prettyPrint()} "
                f"at index {errorIndex}"
            )
            break
        else:
            for varBind in varBinds:
                oid = str(varBind[0])
                val = str(varBind[1])
                # Extraction de l'index final (ex: .0, .1)
                index = oid.split('.')[-1]
                sensors[index] = val
    return sensors


def run_pipeline():
    logging.info("--- DÉMARRAGE DU SCAN AUTO AKCP ---")

    # OPTIMISATION: Instanciation unique pour éviter les fuites de mémoire
    snmp_engine = SnmpEngine()

    with InfluxDBClient(url=URL, token=TOKEN, org=ORG) as client:
        write_api = client.write_api(write_options=SYNCHRONOUS)

        while True:
            try:
                # 1. Détection automatique des noms et valeurs
                noms = get_all_sensors(snmp_engine, IP_AKCP, OID_DESCRIPTIONS)
                valeurs = get_all_sensors(snmp_engine, IP_AKCP, OID_VALEURS)

                if not valeurs:
                    logging.warning(
                        "[RETRY] Aucun capteur détecté ou AKCP hors ligne..."
                    )
                else:
                    points = []
                    current_time = time.time_ns()

                    for index, val in valeurs.items():
                        nom_capteur = noms.get(index, f"sensor_{index}")
                        try:
                            val_float = float(val)

                            # 2. Préparation du point pour InfluxDB
                            point = (
                                Point("data_center_sensors")
                                .tag("sensor_name", nom_capteur)
                                .field("value", val_float)
                                .time(current_time, WritePrecision.NS)
                            )
                            points.append(point)

                            logging.debug(f"[DATA] {nom_capteur}: {val_float}")
                        except ValueError:
                            # Ignore les valeurs non-numériques
                            continue

                    # OPTIMISATION: Envoi par lots (Batch)
                    if points:
                        write_api.write(bucket=BUCKET, record=points)
                        logging.info(
                            f"[{len(points)}] métriques envoyées à InfluxDB."
                        )

            except Exception as e:
                # Éviter le crash global
                logging.error(f"Erreur dans la boucle principale: {e}")

            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run_pipeline()
