"""
AI-Ready Data Engineering Pipeline for Predictive Maintenance
Module: Synthetic Industrial Sensor Telemetry Generator
Generates realistic multi-sensor machine telemetry with authentic physics,
stochastic degradation profiles, missing data patterns, and sensor anomalies.
"""

import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

def generate_industrial_telemetry(num_machines=10, operational_hours=1200, sample_interval_min=10, seed=42):
    np.random.seed(seed)
    
    records = []
    start_time = datetime(2026, 1, 1, 0, 0, 0)
    samples_per_machine = int((operational_hours * 60) / sample_interval_min)
    
    machine_types = ['Centrifugal_Pump', 'CNC_Milling_Spindle', 'Industrial_Compressor']
    
    print(f"Generating telemetry for {num_machines} machines, {samples_per_machine} samples each ({operational_hours} hours)...")
    
    for m_idx in range(1, num_machines + 1):
        machine_id = f"EQ-{100 + m_idx}"
        machine_type = machine_types[(m_idx - 1) % len(machine_types)]
        
        # Machine operational parameters
        base_rpm = 1750.0 if machine_type == 'Centrifugal_Pump' else (2800.0 if machine_type == 'CNC_Milling_Spindle' else 3100.0)
        base_torque = 45.0 if machine_type == 'Centrifugal_Pump' else (25.0 if machine_type == 'CNC_Milling_Spindle' else 60.0)
        base_pressure = 6.2 if machine_type == 'Centrifugal_Pump' else (4.5 if machine_type == 'CNC_Milling_Spindle' else 8.5)
        
        # Decide if this machine will experience a failure during its lifecycle
        will_fail = (m_idx % 2 == 1) or (m_idx == 8) # Machines 1, 3, 5, 7, 8, 9 will experience failure
        fail_point = int(np.random.uniform(0.70, 0.95) * samples_per_machine) if will_fail else samples_per_machine + 1000
        
        # Select failure mode
        fail_types = ['Bearing_Degradation', 'Heat_Dissipation_Failure', 'Power_Overstrain', 'Tool_Wear_Failure']
        assigned_fail_type = fail_types[(m_idx * 3) % len(fail_types)] if will_fail else 'No_Failure'
        
        current_time = start_time + timedelta(hours=(m_idx - 1) * 24)
        
        # Cumulative degradation state
        degradation = 0.0
        tool_wear = 0.0
        
        for step in range(samples_per_machine):
            timestamp = current_time + timedelta(minutes=step * sample_interval_min)
            op_hours = round(step * (sample_interval_min / 60.0), 2)
            
            # Ambient temperature daily cycle (18 C to 34 C)
            hour_of_day = (timestamp.hour + timestamp.minute / 60.0)
            ambient_temp = 25.0 + 7.0 * np.sin((hour_of_day - 9) * np.pi / 12) + np.random.normal(0, 0.4)
            
            # Machine degradation onset
            if step > (fail_point - int(samples_per_machine * 0.35)):
                # Progressive exponential degradation
                progression = (step - (fail_point - int(samples_per_machine * 0.35))) / (fail_point - (fail_point - int(samples_per_machine * 0.35)))
                degradation = min(1.0, np.power(progression, 2.2))
            else:
                # Normal aging wear
                degradation = 0.05 * (step / samples_per_machine)
            
            # Sensor physics calculations
            # 1. Rotational speed (RPM) with load fluctuations and degradation slip
            rpm_noise = np.random.normal(0, base_rpm * 0.008)
            rpm_slip = -150.0 * degradation if assigned_fail_type in ['Power_Overstrain', 'Bearing_Degradation'] else -20.0 * degradation
            rotational_speed = base_rpm + rpm_noise + rpm_slip
            
            # 2. Hydraulic / System Pressure (bar)
            pressure_noise = np.random.normal(0, 0.15)
            pressure = base_pressure + pressure_noise - (1.8 * degradation if assigned_fail_type == 'Power_Overstrain' else 0.2 * degradation)
            
            # 3. Motor Torque (Nm)
            torque_noise = np.random.normal(0, 1.2)
            torque_increase = 30.0 * degradation if assigned_fail_type in ['Bearing_Degradation', 'Power_Overstrain'] else 5.0 * degradation
            motor_torque = base_torque + torque_noise + torque_increase
            
            # 4. Bearing Temperature (deg C) - strongly driven by ambient, load, and bearing wear
            bearing_temp = ambient_temp + 22.0 + (0.35 * (motor_torque - base_torque)) + (38.0 * degradation) + np.random.normal(0, 0.6)
            
            # 5. Tri-axial Vibration (g): X (radial), Y (axial), Z (tangential)
            # Normal baseline is 0.8g - 1.4g RMS; degraded bearings exhibit impulsive spikes and high harmonics
            vib_base = 1.1 + (3.8 * np.power(degradation, 1.8))
            vib_x = vib_base * (1.0 + np.random.normal(0, 0.08 + 0.25 * degradation))
            vib_y = (vib_base * 0.85) * (1.0 + np.random.normal(0, 0.07 + 0.20 * degradation))
            vib_z = (vib_base * 0.70) * (1.0 + np.random.normal(0, 0.06 + 0.18 * degradation))
            
            # 6. Acoustic Emissions (dB)
            acoustic_db = 62.0 + (32.0 * degradation) + np.random.normal(0, 1.5)
            
            # 7. Tool Wear / Component Wear (minutes equivalent)
            tool_wear += (sample_interval_min / 60.0) * (1.0 + 2.5 * degradation)
            
            # 8. Power Consumption (kW) = Torque (Nm) * RPM * 2*pi / 60000 / efficiency
            mechanical_power_kw = (motor_torque * (2.0 * np.pi * rotational_speed / 60.0)) / 1000.0
            power_consumption = (mechanical_power_kw / 0.88) + np.random.normal(0, 0.2)
            
            # Determine failure state & RUL
            if step >= fail_point:
                failure_active = 1
                failure_type = assigned_fail_type
                rul = 0.0
            else:
                failure_active = 0
                failure_type = 'No_Failure'
                rul = max(0.0, (fail_point - step) * (sample_interval_min / 60.0)) if will_fail else 999.0
            
            records.append({
                'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'machine_id': machine_id,
                'machine_type': machine_type,
                'operational_hours': op_hours,
                'rotational_speed_rpm': round(rotational_speed, 2),
                'bearing_temperature_c': round(bearing_temp, 2),
                'ambient_temperature_c': round(ambient_temp, 2),
                'vibration_x_g': round(vib_x, 4),
                'vibration_y_g': round(vib_y, 4),
                'vibration_z_g': round(vib_z, 4),
                'hydraulic_pressure_bar': round(pressure, 3),
                'motor_torque_nm': round(motor_torque, 2),
                'acoustic_emission_db': round(acoustic_db, 2),
                'tool_wear_min': round(tool_wear, 2),
                'power_consumption_kw': round(power_consumption, 2),
                'rul_hours': round(rul, 2),
                'failure_occurred': failure_active,
                'failure_type': failure_type
            })
            
            # If machine failed catastrophically, stop or reset after short downtime
            if step == fail_point:
                # Add minor downtime then machine is restored or taken offline
                pass

    df = pd.DataFrame(records)
    print(f"Base telemetry generated: {df.shape[0]} rows, {df.shape[1]} columns.")
    
    # -------------------------------------------------------------
    # Inject Real-World Industrial Data Impurities (for Data Engineering Pipeline to solve)
    # -------------------------------------------------------------
    print("Injecting industrial telemetry flaws (nulls, spikes, duplicates, sensor dropouts)...")
    
    total_len = len(df)
    
    # 1. Missing Values (Packet Loss / Sensor Connection Interruption)
    # Inject ~4.2% NaNs randomly across primary sensors
    sensor_cols = ['rotational_speed_rpm', 'bearing_temperature_c', 'vibration_x_g', 
                   'hydraulic_pressure_bar', 'motor_torque_nm', 'acoustic_emission_db']
    for col in sensor_cols:
        nan_indices = np.random.choice(total_len, size=int(total_len * 0.038), replace=False)
        df.loc[nan_indices, col] = np.nan
        
    # Inject consecutive sensor blackout blocks (e.g. 5-10 consecutive missing readings)
    blackout_starts = np.random.choice(total_len - 15, size=25, replace=False)
    for b_start in blackout_starts:
        df.loc[b_start:b_start+6, ['bearing_temperature_c', 'vibration_x_g', 'vibration_y_g', 'vibration_z_g']] = np.nan
        
    # 2. Outliers / Electrical Impulse Noise (Extreme impossible spikes)
    spike_indices_vib = np.random.choice(total_len, size=35, replace=False)
    df.loc[spike_indices_vib, 'vibration_x_g'] = np.random.uniform(25.0, 65.0, size=35) # True sensor max is ~8g
    
    spike_indices_temp = np.random.choice(total_len, size=25, replace=False)
    df.loc[spike_indices_temp, 'bearing_temperature_c'] = np.random.choice([-999.0, 999.0, 450.0], size=25)
    
    # 3. Duplicate Records (Network re-transmission retry buffer)
    dup_indices = np.random.choice(total_len, size=int(total_len * 0.015), replace=False)
    duplicate_rows = df.iloc[dup_indices].copy()
    df = pd.concat([df, duplicate_rows], ignore_index=True)
    
    # Shuffle slightly or sort by timestamp/machine
    df = df.sort_values(by=['machine_id', 'timestamp']).reset_index(drop=True)
    
    # Save raw uncleaned dataset
    output_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw', 'raw_machine_telemetry.csv')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Raw dataset with industrial flaws saved to: {output_path} (Total records: {len(df)})")
    return output_path

if __name__ == '__main__':
    generate_industrial_telemetry()

