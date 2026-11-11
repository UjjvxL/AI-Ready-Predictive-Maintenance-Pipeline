# Power BI Solution Architecture & Dashboard Specification
## AI-Ready Predictive Maintenance Platform | L&T EduTech Project 6

---

### 1. Architectural Overview & Data Modeling Strategy
The Power BI analytical dashboard is engineered following the **Kimball Dimensional Modeling** methodology. A dedicated **Star Schema** architecture is implemented to ensure sub-second analytical query performance, seamless DAX time-intelligence calculations, and row-level security (RLS) across industrial plant hierarchies.

```
                      +-------------------+
                      |     Dim_Date      |
                      +-------------------+
                      | DateKey (PK)      |
                      | FullDate          |
                      | Month, Year, Qtr  |
                      | Shift (A/B/C)     |
                      +---------+---------+
                                | 1
                                |
                                | *
+--------------------+ 1        |        * 1 +---------------------+
|    Dim_Machine     +----------+-----------+   Dim_FailureMode   |
+--------------------+          |           +---------------------+
| MachineKey (PK)    |          |           | FailureTypeKey (PK) |
| MachineID (EQ-101) |          |           | FailureCategory     |
| MachineType        |          |           | SeverityRating      |
| InstallationDate   |          v           | RecommendedAction   |
| RatedRPM, MaxTemp  |  +----------------+  +---------------------+
+--------------------+  | Fact_Telemetry |
                        +----------------+
                        | FactID (PK)    |
                        | MachineKey(FK) |
                        | DateKey (FK)   |
                        | FailureKey(FK) |
                        | Timestamp      |
                        | Vib_Magnitude  |
                        | Bearing_Temp   |
                        | Power_kW       |
                        | HealthIndex_%  |
                        | RUL_Hours      |
                        | Alert_24h_Lead |
                        +----------------+
```

---

### 2. Comprehensive DAX Measure Library (Production-Ready)

#### 2.1 Core Reliability & Operational Metrics
```dax
// 1. Fleet Composite Health Index
[Fleet Health Index %] = 
AVERAGE(Fact_Telemetry[health_index_pct])

// 2. Active High-Risk Machine Count
[High Risk Machines] = 
CALCULATE(
    DISTINCTCOUNT(Fact_Telemetry[MachineKey]),
    Fact_Telemetry[health_index_pct] < 50.0,
    Fact_Telemetry[DateKey] = MAX(Fact_Telemetry[DateKey])
)

// 3. Early-Warning Failure Alerts (Next 24 Hours)
[Active 24h Failure Alerts] = 
CALCULATE(
    DISTINCTCOUNT(Fact_Telemetry[MachineKey]),
    Fact_Telemetry[failure_in_next_24h] = 1,
    Fact_Telemetry[DateKey] = MAX(Fact_Telemetry[DateKey])
)

// 4. Mean Time Between Failures (MTBF in Hours)
[Total Operating Hours] = SUM(Fact_Telemetry[operational_hours])
[Total Failure Events] = CALCULATE(COUNTROWS(Fact_Telemetry), Fact_Telemetry[failure_occurred] = 1)
[MTBF (Hours)] = 
DIVIDE([Total Operating Hours], [Total Failure Events], BLANK())

// 5. Overall Equipment Effectiveness (OEE Estimate)
[Availability %] = 
DIVIDE(
    COUNTROWS(FILTER(Fact_Telemetry, Fact_Telemetry[failure_occurred] = 0)),
    COUNTROWS(Fact_Telemetry),
    0
) * 100

[Performance Efficiency %] = 
DIVIDE(
    AVERAGE(Fact_Telemetry[rotational_speed_rpm]),
    AVERAGE(Dim_Machine[RatedRPM]),
    0
) * 100

[OEE Estimated %] = 
([Availability %] / 100) * ([Performance Efficiency %] / 100) * (AVERAGE(Fact_Telemetry[power_efficiency])) * 100
```

#### 2.2 Financial & Maintenance Optimization Impact
```dax
// 6. Cost Avoidance from Predictive Intervention ($)
// Baseline: Emergency catastrophic repair = $28,000; Planned corrective maintenance = $3,500
[Cost Savings ($)] = 
VAR PreventedFailures = CALCULATE(COUNTROWS(Fact_Telemetry), Fact_Telemetry[failure_in_next_24h] = 1 && Fact_Telemetry[failure_occurred] = 0)
RETURN
    PreventedFailures * (28000 - 3500)

// 7. Predictive Remaining Useful Life (Days)
[Average RUL (Days)] = 
DIVIDE(AVERAGE(Fact_Telemetry[rul_hours]), 24, 0)
```

---

### 3. Visual Dashboard Page Specifications

#### Page 1: Executive Fleet Health & Predictive Risk Overview
* **Target Audience:** Plant Operations Director, Maintenance VP.
* **Top KPI Scorecard Row:**
  - Card 1: `Fleet Health Index %` (77.8% - Colored Green >75%, Amber 50-75%, Red <50%).
  - Card 2: `Active 24h Failure Alerts` (Count: 3 critical units requiring immediate scheduling).
  - Card 3: `Fleet MTBF` (1,142 Operating Hours).
  - Card 4: `Cost Avoidance YTD` ($142,500 achieved through early anomaly alerts).
* **Center Matrix Chart:** Fleet Machine Risk Grid (`MachineID`, `Type`, `Health Index`, `Predicted RUL`, `Action Required`).
* **Degradation Distribution Treemap:** Machines categorized by Risk Level (`Normal`, `Warning`, `Elevated Risk`, `Critical`).

#### Page 2: Machine Diagnostic & High-Frequency Sensor Waveforms
* **Target Audience:** Reliability Engineer, Condition Monitoring Specialist.
* **Filter Slicers:** `Machine ID` (Dropdown), `Date Range` (Time Slider), `Sensor Parameter`.
* **Multi-Axis Time-Series Waveform Visual:**
  - Line 1: `1-Hour Rolling Vibration RMS (g)` vs `6-Hour Baseline Mean`.
  - Line 2: `Thermal Gradient ΔT (°C)` (Bearing Temp minus Ambient).
  - Bar Highlight: Anomaly / Missing Packet Imputation flags.
* **Gauge Visual:** Instantaneous Crest Factor & Kurtosis indicating impulsive bearing ball/race impact.

#### Page 3: AI Feature Explorer & Root Cause Analysis
* **Target Audience:** Data Science Lead, Maintenance Systems Analyst.
* **Feature Importance Tornado Chart:** Relative importance weights from the trained Random Forest classifier.
* **Scatter Plot (Physics Clustering):** `Motor Torque (Nm)` vs `Vibration RMS (g)` color-coded by `Failure Type`.
* **RUL Degradation Trajectory:** Actual vs Model Predicted Remaining Useful Life curves across lifecycle hours.

