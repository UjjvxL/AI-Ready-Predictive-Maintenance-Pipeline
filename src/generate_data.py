"""
AI-Ready Data Engineering Pipeline for Predictive Maintenance
Module: Synthetic Multi-Source Telemetry Generator (Reproducible with Seed)
Generates:
1. data/raw/sensor_readings.csv (57,311 rows across 20 machines over 120 days with 7 injected defect classes)
2. data/raw/machine_master.csv (20 machines asset registry)
3. data/raw/maintenance_logs.json (95 semi-structured work order events: 37 failures, 58 preventive)
"""

import os
import json
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

def generate_all_raw_data(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    raw_dir = os.path.join(base_dir, 'data', 'raw')
    os.makedirs(raw_dir, exist_ok=True)
    
    print("[Data Generator] Generating 20 industrial machine asset registry...")
    # 1. Machine Master
    machine_types = ['Pump', 'Compressor', 'Motor', 'Turbine']
    locations = ['Bay-A', 'Bay-B', 'Bay-C', 'Bay-D']
    machines = []
    
    for i in range(1, 21):
        m_id = f"M{i:03d}"
        m_type = machine_types[(i - 1) // 5]
        rated_rpm = 1750 if m_type == 'Pump' else (3000 if m_type == 'Compressor' else (1500 if m_type == 'Motor' else 3600))
        power_kw = 45.0 if m_type == 'Pump' else (90.0 if m_type == 'Compressor' else (30.0 if m_type == 'Motor' else 150.0))
        install_date = (datetime(2020, 1, 1) + timedelta(days=int(np.random.uniform(0, 1200)))).strftime('%Y-%m-%d')
        loc = locations[(i - 1) % len(locations)]
        machines.append({
            'machine_id': m_id,
            'machine_type': m_type,
            'model': f"{m_type[:4].upper()}-{100 + i}",
            'installation_date': install_date,
            'location': loc,
            'rated_rpm': rated_rpm,
            'rated_power_kw': power_kw
        })
        
    df_machines = pd.DataFrame(machines)
    master_path = os.path.join(raw_dir, 'machine_master.csv')
    df_machines.to_csv(master_path, index=False)
    print(f"  -> Saved {len(df_machines)} machines to {master_path}")
    
    # 2. Maintenance Logs (95 events: 37 failures, 58 preventive)
    print("[Data Generator] Simulating 95 maintenance log work orders (37 failures, 58 preventive)...")
    start_date = datetime(2025, 1, 1, 0, 0, 0)
    end_date = datetime(2025, 4, 30, 23, 0, 0)
    total_hours = int((end_date - start_date).total_seconds() / 3600) + 1 # 2880 hours
    
    failure_modes = ['Bearing wear', 'Imbalance', 'Electrical fault', 'Seal leak', 'Overheating']
    events = []
    
    # Distribute 37 failures across machines
    fail_machines = [f"M{i:03d}" for i in range(1, 21)]
    failure_timestamps = {}
    
    # Guarantee M001 has frequent failures as mentioned in doc
    m_fail_counts = {f"M{i:03d}": 1 for i in range(1, 21)}
    m_fail_counts['M001'] = 4
    m_fail_counts['M004'] = 3
    m_fail_counts['M007'] = 3
    m_fail_counts['M012'] = 3
    m_fail_counts['M015'] = 3
    m_fail_counts['M018'] = 3
    # Balance remaining to 37
    current_fails = sum(m_fail_counts.values())
    extra_fails = 37 - current_fails
    for _ in range(extra_fails):
        pick_m = random.choice(fail_machines)
        m_fail_counts[pick_m] += 1
        
    for m_id, f_count in m_fail_counts.items():
        failure_timestamps[m_id] = []
        # Generate spaced failure hours
        step = total_hours // (f_count + 1)
        for fc in range(1, f_count + 1):
            h_offset = int(step * fc + np.random.uniform(-40, 40))
            h_offset = max(100, min(total_hours - 50, h_offset))
            f_ts = start_date + timedelta(hours=h_offset)
            failure_timestamps[m_id].append((h_offset, f_ts))
            f_mode = random.choice(failure_modes)
            down_h = round(float(np.random.uniform(8.0, 36.0)), 1)
            cost = int(np.random.uniform(80000, 450000))
            events.append({
                'machine_id': m_id,
                'event_ts': f_ts.strftime('%Y-%m-%d %H:%M:%S'),
                'event_type': 'FAILURE',
                'failure_mode': f_mode,
                'downtime_hours': down_h,
                'cost_inr': cost
            })
            
    # 58 Preventive maintenance events
    for _ in range(58):
        m_id = random.choice(fail_machines)
        h_offset = int(np.random.uniform(48, total_hours - 24))
        p_ts = start_date + timedelta(hours=h_offset)
        down_h = round(float(np.random.uniform(2.0, 8.0)), 1)
        cost = int(np.random.uniform(15000, 60000))
        events.append({
            'machine_id': m_id,
            'event_ts': p_ts.strftime('%Y-%m-%d %H:%M:%S'),
            'event_type': 'PREVENTIVE',
            'failure_mode': 'Routine overhaul / lubrication',
            'downtime_hours': down_h,
            'cost_inr': cost
        })
        
    events = sorted(events, key=lambda x: x['event_ts'])
    logs_path = os.path.join(raw_dir, 'maintenance_logs.json')
    with open(logs_path, 'w', encoding='utf-8') as f:
        json.dump(events, f, indent=2)
    print(f"  -> Saved {len(events)} maintenance work orders to {logs_path}")
    
    # 3. Sensor Readings (Hourly over 120 days = 2880 steps x 20 = 57,600 base rows)
    print("[Data Generator] Generating hourly sensor time-series for 20 machines...")
    rows = []
    
    # 3 machines report temperature in Fahrenheit: M004, M011, M017
    fahrenheit_machines = {'M004', 'M011', 'M017'}
    
    for m in machines:
        m_id = m['machine_id']
        m_type = m['machine_type']
        rated_rpm = m['rated_rpm']
        f_times = failure_timestamps.get(m_id, [])
        
        base_temp = 58.0 if m_type in ['Motor', 'Pump'] else 68.0
        base_vib = 2.4 if m_type == 'Pump' else (3.1 if m_type == 'Compressor' else 2.1)
        base_pres = 6.0 if m_type == 'Pump' else (8.5 if m_type == 'Compressor' else 4.0)
        base_cur = 42.0 if m_type == 'Pump' else (65.0 if m_type == 'Compressor' else 35.0)
        
        oil_deg = 0.0
        
        for h in range(total_hours):
            ts = start_date + timedelta(hours=h)
            
            # Check proximity to nearest future failure
            next_fails = [ft for ft in f_times if ft[0] >= h]
            if next_fails:
                hours_to_fail = next_fails[0][0] - h
            else:
                hours_to_fail = 9999
                
            # Degradation ramp (starts ~10 days / 240h before failure)
            if hours_to_fail <= 240:
                prog = (240 - hours_to_fail) / 240.0
                deg = np.power(prog, 1.8)
            else:
                deg = 0.0
                
            # Physics calculations
            temp_c = base_temp + 28.0 * deg + np.random.normal(0, 1.2) + 4.0 * np.sin(h * 2 * np.pi / 24)
            vib_val = base_vib + (12.0 * deg if deg > 0 else 0) + np.random.normal(0, 0.18)
            pres_val = base_pres - 1.8 * deg + np.random.normal(0, 0.12)
            cur_val = base_cur + 8.5 * deg + np.random.normal(0, 0.8)
            rpm_val = rated_rpm - 65.0 * deg + np.random.normal(0, rated_rpm * 0.005)
            
            oil_deg += 0.02
            if hours_to_fail == 0:
                oil_deg = 0.0 # reset after failure repair
            oil_val = max(10.0, 95.0 - oil_deg - 25.0 * deg + np.random.normal(0, 1.0))
            
            # Unit error: Fahrenheit for M004, M011, M017
            if m_id in fahrenheit_machines:
                temp_report = round(temp_c * 9.0 / 5.0 + 32.0, 1)
            else:
                temp_report = round(temp_c, 1)
                
            # Format timestamp with 3 mixed formats:
            # 80% ISO 'YYYY-MM-DD HH:MM:SS', 10% US 'MM/DD/YYYY HH:MM:SS', 10% UK 'DD-MM-YYYY HH:MM:SS'
            r_fmt = random.random()
            if r_fmt < 0.80:
                ts_str = ts.strftime('%Y-%m-%d %H:%M:%S')
            elif r_fmt < 0.90:
                ts_str = ts.strftime('%m/%d/%Y %H:%M:%S')
            else:
                ts_str = ts.strftime('%d-%m-%Y %H:%M:%S')
                
            # Messy ID formatting: 2% lowercase or trailing whitespace
            if random.random() < 0.02:
                m_id_str = f" {m_id.lower()} "
            else:
                m_id_str = m_id
                
            rows.append({
                'machine_id': m_id_str,
                'timestamp': ts_str,
                'temperature': temp_report,
                'vibration': round(vib_val, 3),
                'pressure': round(pres_val, 2),
                'rpm': round(rpm_val, 1),
                'current': round(cur_val, 1),
                'oil_quality': round(oil_val, 1)
            })

    df_sensors = pd.DataFrame(rows)
    print(f"  Base sensor grid created: {len(df_sensors)} rows.")
    
    # -------------------------------------------------------------
    # Deliberate Defect Injections (Target: exactly 57,311 raw rows)
    # -------------------------------------------------------------
    total_len = len(df_sensors)
    
    # 1. Missing Values (~3% random per sensor + 25 dropout blocks)
    for col in ['temperature', 'vibration', 'pressure', 'rpm', 'current', 'oil_quality']:
        nan_idx = np.random.choice(total_len, size=int(total_len * 0.030), replace=False)
        df_sensors.loc[nan_idx, col] = np.nan
        
    # 25 multi-hour dropout blocks
    block_starts = np.random.choice(total_len - 20, size=25, replace=False)
    for b in block_starts:
        df_sensors.loc[b:b+10, ['temperature', 'vibration', 'pressure']] = np.nan
        
    # 2. Out-of-Range & Impossible Values
    # rpm = -999, pressure = -1, oil_quality = 180, temp = 250
    df_sensors.loc[np.random.choice(total_len, 215, replace=False), 'temperature'] = 250.0
    df_sensors.loc[np.random.choice(total_len, 80, replace=False), 'pressure'] = -1.0
    df_sensors.loc[np.random.choice(total_len, 254, replace=False), 'rpm'] = -999.0
    df_sensors.loc[np.random.choice(total_len, 60, replace=False), 'oil_quality'] = 180.0
    df_sensors.loc[np.random.choice(total_len, 9, replace=False), 'vibration'] = -5.0
    
    # 3. Spikes / Outliers (~0.4% per sensor multiplied by 5-10x)
    for col, mult in [('temperature', 2.5), ('vibration', 5.0), ('pressure', 3.0), ('current', 2.8), ('oil_quality', 2.0)]:
        spk_idx = np.random.choice(total_len, size=215, replace=False)
        df_sensors.loc[spk_idx, col] = df_sensors.loc[spk_idx, col] * mult
        
    # 4. Stuck / Frozen sensor (vibration on M002 frozen for 72 consecutive hours)
    m002_mask = df_sensors['machine_id'].str.strip().str.upper() == 'M002'
    m002_indices = df_sensors[m002_mask].index[200:272]
    df_sensors.loc[m002_indices, 'vibration'] = 2.450
    
    # 5. Duplicates (~1% = ~567 duplicate rows)
    dup_indices = np.random.choice(total_len, size=567, replace=False)
    dupes = df_sensors.iloc[dup_indices].copy()
    
    # Subsample to exact volume of 57,311 rows
    # Current len is total_len + 567
    combined = pd.concat([df_sensors, dupes], ignore_index=True)
    if len(combined) > 57311:
        drop_count = len(combined) - 57311
        drop_idx = np.random.choice(len(combined), size=drop_count, replace=False)
        combined = combined.drop(drop_idx).reset_index(drop=True)
    elif len(combined) < 57311:
        add_count = 57311 - len(combined)
        add_dupes = combined.iloc[:add_count].copy()
        combined = pd.concat([combined, add_dupes], ignore_index=True)
        
    sensor_path = os.path.join(raw_dir, 'sensor_readings.csv')
    combined.to_csv(sensor_path, index=False)
    print(f"[Data Generator] Successfully generated {len(combined):,} raw sensor readings -> {sensor_path}")
    return master_path, logs_path, sensor_path

if __name__ == '__main__':
    generate_all_raw_data()
