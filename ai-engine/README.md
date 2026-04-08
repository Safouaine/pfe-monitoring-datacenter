# AI Engine Deep Dive

## Overview
The `ai-engine` module is the predictive core of the `pfe-monitoring-predictif-datacenter` application. Its purpose is to consume historical and real-time operational data from InfluxDB locally, train or utilize pre-trained Machine Learning models, and infer potential disruptions, thermal anomalies, or hardware degradation in the datacenter.

## Current Implementation
The file `ai-engine/model.py` provides the skeletal structure necessary to ensure the container launches properly and keeps the service alive in the `docker-compose` stack.

### Key Logic
- An infinite `while True` loop that runs every 60 seconds (`time.sleep(60)`).
- Outputs early startup logs indicating the AI engine has booted successfully.

## Integration Points
Within the overall ecosystem (as defined in `docker-compose.yml`), the `ai-engine` is dependent on:
- **InfluxDB**: Added via the `depends_on: - influxdb` mapping. It will read time-series data populated by the `snmp-collector` module.

### Future Development Requirements
- Connect to InfluxDB using an InfluxDB Python client.
- Fetch accumulated temperature time-series data.
- Apply Predictive Analytics models (ARIMA, LSTMs, or simpler regression models) to anticipate temperature spikes.
- Send alerts or flag conditions back to a database or messaging queue for the web platform to consume.
