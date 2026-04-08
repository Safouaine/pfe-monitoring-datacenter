# System Architecture Deep Dive

## Project Overview
The `pfe-monitoring-predictif-datacenter` project represents a predictive monitoring platform designed for a datacenter scenario, specifically targeted at Nouvameq infrastructure. It relies on a containerized microservices architecture to collect, store, analyze, and present datacenter operational data.

## Infrastructure Map
Based on the `docker-compose.yml`, the system currently runs 5 interconnected services.

### 1. InfluxDB (`influxdb`)
- **Role**: Core Time-Series Database
- **Configuration**: Uses version `2.7`
- **Networking**: Exposed on port `8086`.
- **Storage**: Uses Docker volume binding (`influxdb_data:/var/lib/influxdb2`) to persist metric data robustly across restarts. 
- **Dependencies**: None. This is the foundation that other services depend on.

### 2. Grafana (`grafana`)
- **Role**: Data Visualization Dashboard
- **Configuration**: Exposes on `3000:3000`.
- **Dependencies**: Needs `influxdb` to be up. Grafana typically serves as the primary visual display for InfluxDB time-series metrics. 

### 3. SNMP Collector (`snmp-collector`)
- **Role**: Hardware Data Intake
- **Configuration**: Custom-built Python container.
- **Networking**: `network_mode: "host"` is a critical setup for enabling the container to discover and reach a local physical AKCP environmental sensor unit efficiently via PySNMP.
- **Data flow**: Once fully implemented, it reads temperature values and writes them back into InfluxDB.

### 4. AI Engine (`ai-engine`)
- **Role**: Predictive Analytics
- **Configuration**: Custom-built Python container.
- **Dependencies**: Depends on `influxdb`.
- **Data flow**: Constantly polling data from InfluxDB to compute trends or failures in datacenter equipment automatically. 

### 5. Web Platform (`web-platform`)
- **Role**: Primary API & User Interface
- **Configuration**: Custom FastAPI project exposed on `8000:8000`.
- **Data Flow**: Will act as the frontend gateway displaying stats, predictions, and interacting with users for alerting configurations.

## The Overall Data Pipeline
1. **Intake**: `snmp-collector` retrieves metrics (Temperature, etc.).
2. **Storage**: Data is pushed into `influxdb`.
3. **Analysis**: `ai-engine` fetches data from `influxdb`, computes models, and sends predictions back or alerts the user.
4. **Visualization/UI**: The user can view the data either through beautiful built-in `grafana` dashboards or custom routes provided by the `web-platform`.
