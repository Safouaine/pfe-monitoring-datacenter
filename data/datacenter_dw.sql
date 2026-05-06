DROP TABLE IF EXISTS fact_readings CASCADE;
DROP TABLE IF EXISTS dim_alerts CASCADE;
DROP TABLE IF EXISTS dim_power CASCADE;
DROP TABLE IF EXISTS dim_rack CASCADE;
DROP TABLE IF EXISTS dim_environment CASCADE;
DROP TABLE IF EXISTS dim_time CASCADE;

TRUNCATE TABLE fact_readings, dim_time, dim_environment, dim_power, dim_rack, dim_alerts RESTART IDENTITY CASCADE;

CREATE TABLE dim_time (
    time_id     SERIAL      PRIMARY KEY,
    timestamp   TIMESTAMP   NOT NULL,
    hour        INT,
    day         INT,
    month       INT,
    year        INT
);

CREATE TABLE dim_environment (
    env_id      SERIAL  PRIMARY KEY,
    time_id     INT     REFERENCES dim_time(time_id),
    temp_ext    FLOAT,
    humidity    FLOAT
);

CREATE TABLE dim_rack (
    rack_id     SERIAL      PRIMARY KEY,
    time_id     INT         REFERENCES dim_time(time_id),
    rack_name   VARCHAR(10),
    temp_head   FLOAT,
    temp_middle FLOAT,
    temp_bottom FLOAT
);

CREATE TABLE dim_power (
    power_id        SERIAL      PRIMARY KEY,
    time_id         INT         REFERENCES dim_time(time_id),
    pwr_consumption FLOAT,
    fuel_level      FLOAT,
    battery_health  FLOAT,
    pwr_source      VARCHAR(20)
);

CREATE TABLE dim_alerts (
    alert_id        SERIAL  PRIMARY KEY,
    time_id         INT     REFERENCES dim_time(time_id),
    ac_status       BOOLEAN,
    door_open       BOOLEAN,
    smoke_detected  BOOLEAN,
    water_leak      BOOLEAN,
    cyber_alert     BOOLEAN
);

CREATE TABLE fact_readings (
    reading_id  SERIAL  PRIMARY KEY,
    time_id     INT     REFERENCES dim_time(time_id),
    env_id      INT     REFERENCES dim_environment(env_id),
    rack_id     INT     REFERENCES dim_rack(rack_id),
    power_id    INT     REFERENCES dim_power(power_id),
    alert_id    INT     REFERENCES dim_alerts(alert_id),
    target      VARCHAR(50)
);


SELECT * FROM fact_readings;
SELECT * FROM dim_environment;


SELECT COUNT(*) FROM dim_time;
SELECT COUNT(*) FROM dim_environment;
SELECT COUNT(*) FROM dim_rack;
SELECT COUNT(*) FROM dim_power;
SELECT COUNT(*) FROM dim_alerts;


ALTER TABLE dim_time ADD COLUMN weekday VARCHAR(20);
DROP TABLE IF EXISTS dim_time CASCADE;

CREATE TABLE dim_time (
    time_id     SERIAL      PRIMARY KEY,
    timestamp   TIMESTAMP   NOT NULL,
    hour        INT,
    day         INT,
    month       INT,
    year        INT,
    weekday     VARCHAR(20)
);


-- simuler 150 pannes de clim réparties au hasard
UPDATE dim_alerts 
SET ac_status = false 
WHERE alert_id IN (
    SELECT alert_id FROM dim_alerts ORDER BY RANDOM() LIMIT 150
);


CREATE TABLE ai_predictions (
    timestamp TIMESTAMP PRIMARY KEY,
    risk_percentage FLOAT,
    predicted_class INTEGER
);

SELECT count(*) FROM ai_predictions;
