"""
Seed InfluxDB with realistic datacenter metrics from the CSV dataset.
- Backfills the last 30 minutes with one point per 5 seconds from the dataset tail
- Then writes a live point every 5 seconds with small drift (so Grafana shows movement)

Usage:
    python seed_influxdb.py             # seed + live loop
    python seed_influxdb.py --once      # only backfill, exit
"""
import os
import sys
import time
import random
import argparse
from datetime import datetime, timedelta, timezone

import pandas as pd
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

INFLUX_URL   = os.environ.get("INFLUX_URL",   "http://localhost:8086")
INFLUX_TOKEN = os.environ.get("INFLUX_TOKEN", "nouvameq-pfe-admin-token-2026")
INFLUX_ORG   = os.environ.get("INFLUX_ORG",   "Nouvameq")
INFLUX_BUCKET= os.environ.get("INFLUX_BUCKET","datacenter_metrics")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_CANDIDATES = [
    os.path.join(BASE_DIR, "data", "datacenter_tunisia_rf_dataset.csv"),
    os.path.join(BASE_DIR, "data", "dataset_normal_1.csv"),
]

SENSORS = [
    "temp_ext", "humidity",
    "rack1_h", "rack1_m", "rack1_b",
    "rack2_h", "rack2_m", "rack2_b",
    "pwr_consumption", "fuel_level", "battery_health",
]


def load_df():
    for p in DATA_CANDIDATES:
        if os.path.exists(p):
            print(f"[INFO] Lecture {p}")
            return pd.read_csv(p)
    raise FileNotFoundError("Aucun CSV trouvé")


def write_point(client, sensor, value, ts):
    p = (Point("data_center_sensors")
         .tag("sensor_name", sensor)
         .field("value", float(value))
         .time(ts, WritePrecision.S))
    client.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=p)


def backfill(client, df, minutes=30, step_seconds=5):
    n_points = (minutes * 60) // step_seconds
    rows = df.tail(n_points)
    if len(rows) < n_points:
        rows = pd.concat([rows] * (n_points // len(rows) + 1)).head(n_points)

    now = datetime.now(timezone.utc).replace(microsecond=0)
    start = now - timedelta(seconds=step_seconds * (n_points - 1))

    print(f"[INFO] Backfill {n_points} points × {len(SENSORS)} capteurs (de {start} à {now})")
    for i, (_, row) in enumerate(rows.iterrows()):
        ts = start + timedelta(seconds=i * step_seconds)
        for sensor in SENSORS:
            if sensor in row:
                write_point(client, sensor, row[sensor], ts)
        if i % 50 == 0 and i > 0:
            print(f"  {i}/{n_points}")
    print(f"[OK] Backfill terminé.")


def live_loop(client, df, step_seconds=5):
    last = df.iloc[-1].to_dict()
    print(f"[INFO] Boucle live — un point toutes les {step_seconds}s. CTRL+C pour arrêter.")
    while True:
        ts = datetime.now(timezone.utc).replace(microsecond=0)
        for sensor in SENSORS:
            if sensor not in last:
                continue
            base = float(last[sensor])
            # Small natural drift
            drift = random.uniform(-0.5, 0.5)
            value = base + drift
            # Apply physical bounds
            if sensor in ("humidity", "fuel_level", "battery_health"):
                value = max(0.0, min(100.0, value))
            elif sensor.startswith("rack"):
                value = max(10.0, min(55.0, value))
            elif sensor == "temp_ext":
                value = max(-10.0, min(55.0, value))
            elif sensor == "pwr_consumption":
                value = max(0.0, min(50.0, value))
            write_point(client, sensor, value, ts)
            last[sensor] = value
        print(f"  [{ts.strftime('%H:%M:%S')}] écrit {len(SENSORS)} capteurs")
        time.sleep(step_seconds)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="Backfill only, exit")
    ap.add_argument("--minutes", type=int, default=30, help="Minutes to backfill")
    ap.add_argument("--step", type=int, default=5, help="Step in seconds between points")
    args = ap.parse_args()

    df = load_df()
    print(f"[INFO] Dataset chargé ({len(df)} lignes)")

    print(f"[INFO] Connexion à {INFLUX_URL} (org={INFLUX_ORG}, bucket={INFLUX_BUCKET})")
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    backfill(write_api, df, minutes=args.minutes, step_seconds=args.step)

    if not args.once:
        try:
            live_loop(write_api, df, step_seconds=args.step)
        except KeyboardInterrupt:
            print("\n[STOP] Boucle arrêtée par l'utilisateur.")

    client.close()
    print("[DONE]")


if __name__ == "__main__":
    main()
