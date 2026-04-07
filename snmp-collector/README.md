# SNMP Collector Deep Dive

## Overview
The `snmp-collector` module is responsible for fetching hardware and environmental metrics (such as temperature) via the SNMP (Simple Network Management Protocol) from an AKCP sensor. The collected data is intended to be stored in InfluxDB for time-series analysis and monitoring.

## Current Implementation
The `snmp-collector/main.py` file currently acts as a simulator to aid in the initial development and debugging of the Docker infrastructure without relying on actual physical AKCP sensor hardware. 

### Key Features
- **Simulation Loop**: An infinite loop generating simulated temperature values.
- **Randomization**: Uses Python's `random.uniform(20.0, 25.0)` to generate floating-point temperature values mimicking a standard datacenter or server room environment.
- **Immediate Logging**: Employs `print(..., flush=True)` to ensure that Docker captures the logs instantaneously without buffering delays.
- **Timing**: Simulates a polling interval using `time.sleep(5)`.

### Future Implementation Notes
The file contains commented-out blueprint code detailing the planned transition to an actual SNMP polling mechanism using the `pysnmp` library:
- Import `from pysnmp.hlapi import *`
- Polling an AKCP device configured at IP `192.168.1.100`.
- Handling PySNMP polling tasks asynchronously or synchronously in loops.

## Docker Configuration
The service is explicitly configured in `docker-compose.yml` to run gracefully within the ecosystem:
- Depends on `influxdb` to ensure the database is up before data collection starts.
- Uses `network_mode: "host"`, establishing a direct connection between the host machine's network interface and the container, which is critical for local discovery and low-level SNMP polling.
