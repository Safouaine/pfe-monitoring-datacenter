# AI Monitoring & Forecasting Platform — Claude Code Prompt

## Project Overview

Create a complete local prototype web platform for an AI-powered monitoring and forecasting system.

The platform combines:
- Business Intelligence
- Machine Learning
- Forecasting
- Real-time monitoring
- Role-based access control
- Interactive dashboards

The platform will work completely locally for a PFE (final year project) prototype.

---

# Main Objective

The goal is to build an intelligent monitoring platform capable of:

- Collecting and visualizing real-time data
- Predicting future values using AI models
- Comparing Machine Learning models
- Displaying forecasting dashboards
- Providing decision support
- Managing different user roles

---

# Technologies Stack

Use the following technologies:

| Component | Technology |
|---|---|
| Backend API | FastAPI |
| Frontend | Streamlit |
| Database | PostgreSQL and/or InfluxDB |
| Dashboard | Grafana |
| Machine Learning | Scikit-learn |
| Forecasting | TimesFM |
| ML Models | RandomForest, XGBoost |
| Visualization | Plotly / Matplotlib |
| Authentication | Local session authentication |

---

# Platform Architecture

```text
Sensors / CSV / Dataset
        ↓
PostgreSQL / InfluxDB
        ↓
Python ETL Processing
        ↓
Machine Learning Engine
(RandomForest / XGBoost)
        ↓
Forecasting Engine
(TimeFM)
        ↓
Predictions Storage
        ↓
Web Platform
(Streamlit + Grafana)
```

---

# Required Features

## 1. Authentication System

Implement a login system with two roles:

### Admin
Admin users can:
- Access all dashboards
- Access ML models information
- Compare model performances
- View MAE, RMSE, Accuracy
- View feature importance
- Access forecasting analysis
- Access system monitoring
- View training status

### User
Normal users can:
- View real-time data
- View monitoring dashboards
- View forecasting dashboards
- View alerts
- Access prediction results only

Users must NOT see:
- ML model details
- Training metrics
- Hyperparameters
- Technical ML information

---

# Dashboard Requirements

## Dashboard 1 — Real-Time Monitoring

Accessible by:
- Admin
- User

Display:
- Temperature
- Humidity
- CPU load
- Energy consumption
- Historical data
- Real-time monitoring charts
- Live system status

Embed Grafana dashboards inside Streamlit.

---

## Dashboard 2 — Forecasting Dashboard

Accessible by:
- Admin
- User

Display:
- Future predictions
- Consumption forecasting
- Forecasting curves
- Historical vs predicted values
- 24-hour prediction
- 7-day prediction
- Trend analysis

Use TimeFM forecasting results.

---

## Dashboard 3 — Machine Learning Dashboard

Accessible ONLY by:
- Admin

Display:
- RandomForest model information
- XGBoost model information
- Model comparison
- MAE
- RMSE
- Accuracy score
- Training status
- Feature importance
- Best model selected
- Model performance charts
- Prediction comparison

---

# Machine Learning Requirements

## RandomForest

Implement:
- Model training
- Prediction
- Evaluation
- Save/load model

Use:
- RandomForestRegressor

---

## XGBoost

Implement:
- Model training
- Prediction
- Evaluation
- Save/load model

Use:
- XGBRegressor

---

## TimeFM

Implement:
- Time series forecasting
- Forecast visualization
- Prediction horizon
- Future forecasting

Use TimesFM pretrained model.

---

# ML Evaluation Requirements

Calculate and display:

- MAE
- RMSE
- R² score
- Accuracy comparison
- Prediction curves
- Real vs predicted charts

---

# Data Pipeline

Implement:

1. Data loading
2. Data cleaning
3. Feature engineering
4. Train/test split
5. Model training
6. Prediction generation
7. Forecast generation
8. Dashboard visualization

---

# Database Requirements

Use PostgreSQL and/or InfluxDB.

Store:
- Sensor data
- Historical data
- Predictions
- Forecast results
- ML metrics
- Logs

---

# Grafana Integration

Embed Grafana dashboards inside Streamlit using iframe integration.

Example:

```python
st.components.v1.iframe(
    "http://localhost:3000/d/dashboard-id",
    height=800
)
```

---

# Streamlit Interface Requirements

The UI must:

- Be modern and clean
- Use a dashboard layout
- Include sidebar navigation
- Include login page
- Support role-based rendering
- Display charts and KPIs
- Display prediction metrics
- Display forecasting graphs

---

# Suggested Streamlit Pages

## Public/Login
- Login form

## User Pages
- Monitoring Dashboard
- Forecast Dashboard
- Alerts

## Admin Pages
- Monitoring Dashboard
- Forecast Dashboard
- ML Dashboard
- Models Comparison
- Training Status
- System Analytics

---

# Suggested KPIs

Display cards such as:

- Current Consumption
- Predicted Consumption
- Best Model
- Forecast Accuracy
- System Status
- Active Sensors
- Alerts Count

---

# Alerts System

Create an alert system capable of displaying:

- High energy consumption
- Abnormal behavior detection
- Prediction anomalies
- Forecast warnings

Example:

"Warning: High energy consumption predicted for the next 3 hours."

---

# Visualization Requirements

Use:
- Plotly
- Matplotlib
- Interactive charts
- Real-time charts
- Forecast curves
- Bar charts for model comparison
- Feature importance visualization

---

# Project Structure

Suggested structure:

```text
project/
│
├── app.py
├── backend/
│   ├── api.py
│   ├── auth.py
│   ├── ml/
│   │   ├── random_forest.py
│   │   ├── xgboost_model.py
│   │   ├── timefm_forecast.py
│   │   └── evaluation.py
│   └── database/
│       ├── postgres.py
│       └── influxdb.py
│
├── dashboards/
│   └── grafana/
│
├── models/
│   ├── randomforest.pkl
│   └── xgboost.pkl
│
├── data/
│   └── dataset.csv
│
└── requirements.txt
```

---

# Expected Final Result

The final prototype should provide:

- A complete local AI monitoring platform
- Interactive dashboards
- AI-based forecasting
- Machine Learning model comparison
- Real-time monitoring
- Admin/User role management
- Intelligent analytics
- Decision support system

---

# Important Notes

- The project is fully local.
- No cloud deployment is required.
- Focus on clean architecture.
- Focus on dashboard visualization.
- Focus on role separation.
- Focus on ML explainability.
- The system must look professional for PFE presentation.

---

# Additional Requirements

Please generate:

- Complete project structure
- Backend code
- Streamlit frontend
- Authentication system
- Database integration
- ML training scripts
- Forecasting scripts
- Dashboard integration
- Example datasets
- Requirements.txt
- Comments and explanations inside the code

The code should be modular, clean, and easy to present during a final-year project defense.

