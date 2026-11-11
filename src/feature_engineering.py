"""
AI-Ready Data Engineering Pipeline for Predictive Maintenance
Module: Advanced Feature Engineering & Signal Physics Engine
Computes time-domain statistical aggregates, frequency/crest indicators,
thermodynamic stresses, composite health indices, and AI target labels.
"""

import os
import numpy as np
import pandas as pd
from scipy.stats import kurtosis, skew

class IndustrialFeatureEngineer:
    def __init__(self, cleaned_input_path=None):
        self.cleaned_input_path = cleaned_input_path or os.path.join(
            os.path.dirname(__file__), '..', 'data', 'processed', 'cleaned_machine_telemetry.parquet'
        )
        self.output_feature_csv = os.path.join(
            os.path.dirname(__file__), '..', 'data', 'processed', 'engineered_features.csv'
        )
        self.output_feature_parquet = os.path.join(
            os.path.dirname(__file__), '..', 'data', 'processed', 'engineered_features.parquet'
        )
        self.feature_report_path = os.path.join(
            os.path.dirname(__file__), '..', 'reports', 'feature_engineering_summary.json'
        )

    def extract_features(self):
        print(f"[Feature Engineering] Reading cleaned telemetry from {self.cleaned_input_path}...")
        df = pd.read_parquet(self.cleaned_input_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values(by=['machine_id', 'timestamp']).reset_index(drop=True)
        
        print("[Feature Engineering] 1. Computing physics and thermodynamic interactions...")
        # Vibration Tri-axial magnitude
        df['vibration_magnitude_g'] = np.sqrt(
            df['vibration_x_g']**2 + df['vibration_y_g']**2 + df['vibration_z_g']**2
        )
        
        # Thermal Rise (Bearing temp relative to ambient)
        df['temp_difference_c'] = df['bearing_temperature_c'] - df['ambient_temperature_c']
        
        # Mechanical Power in kW = (Torque * RPM * 2*pi/60) / 1000
        df['mechanical_power_kw'] = (df['motor_torque_nm'] * (2.0 * np.pi * df['rotational_speed_rpm'] / 60.0)) / 1000.0
        
        # Power Efficiency Ratio = Mechanical Power / Electrical Power
        df['power_efficiency'] = np.clip(df['mechanical_power_kw'] / (df['power_consumption_kw'] + 1e-4), 0.0, 1.0)
        
        # Thermal Stress Index
        df['thermal_stress_index'] = df['temp_difference_c'] * df['motor_torque_nm']
        
        # Mechanical Specific Torque Ratio
        df['specific_torque'] = df['motor_torque_nm'] / (df['hydraulic_pressure_bar'] + 1e-4)
        
        print("[Feature Engineering] 2. Computing multi-scale rolling statistics per machine...")
        engineered_groups = []
        
        # Windows: 6 steps = 1 Hour; 36 steps = 6 Hours
        w_short = 6
        w_long = 36
        
        for m_id, group in df.groupby('machine_id'):
            group = group.copy().sort_values('timestamp')
            
            # Short-term rolling mean & std
            group['vib_mag_roll_mean_1h'] = group['vibration_magnitude_g'].rolling(w_short, min_periods=1).mean()
            group['vib_mag_roll_std_1h'] = group['vibration_magnitude_g'].rolling(w_short, min_periods=1).std().fillna(0)
            group['temp_diff_roll_mean_1h'] = group['temp_difference_c'].rolling(w_short, min_periods=1).mean()
            group['torque_roll_mean_1h'] = group['motor_torque_nm'].rolling(w_short, min_periods=1).mean()
            group['acoustic_roll_mean_1h'] = group['acoustic_emission_db'].rolling(w_short, min_periods=1).mean()
            
            # Long-term rolling mean & std (trend indicators)
            group['vib_mag_roll_mean_6h'] = group['vibration_magnitude_g'].rolling(w_long, min_periods=1).mean()
            group['vib_mag_roll_std_6h'] = group['vibration_magnitude_g'].rolling(w_long, min_periods=1).std().fillna(0)
            group['temp_diff_roll_mean_6h'] = group['temp_difference_c'].rolling(w_long, min_periods=1).mean()
            
            # Peak-to-Peak (P2P) Vibration
            roll_max_vib = group['vibration_magnitude_g'].rolling(w_short, min_periods=1).max()
            roll_min_vib = group['vibration_magnitude_g'].rolling(w_short, min_periods=1).min()
            group['vib_peak_to_peak_1h'] = roll_max_vib - roll_min_vib
            
            # Root Mean Square (RMS) Vibration
            group['vib_rms_1h'] = np.sqrt(
                (group['vibration_magnitude_g']**2).rolling(w_short, min_periods=1).mean()
            )
            
            # Crest Factor = Peak / RMS (Vibration shock pulse detector)
            group['crest_factor_1h'] = roll_max_vib / (group['vib_rms_1h'] + 1e-4)
            
            # Fast Vectorized Rolling Kurtosis (Tailedness of vibration distribution - early bearing spall marker)
            # z = (x - mu) / sigma, kurtosis = E[z^4] - 3
            v_mean = group['vib_mag_roll_mean_6h']
            v_std = group['vib_mag_roll_std_6h'] + 1e-4
            z_score = (group['vibration_magnitude_g'] - v_mean) / v_std
            group['vib_kurtosis_6h'] = ((z_score**4).rolling(w_long, min_periods=5).mean() - 3.0).fillna(0.0)
            
            # Rate of Change (Velocity of degradation)
            group['vib_roc_1h'] = group['vib_mag_roll_mean_1h'].diff(periods=w_short).fillna(0)
            group['temp_roc_1h'] = group['temp_diff_roll_mean_1h'].diff(periods=w_short).fillna(0)
            
            # Composite Machine Health Index (100% = Healthy, 0% = Failed)
            # Baseline norm: healthy vibration ~1.8g, critical > 6.0g; healthy temp diff ~22C, critical > 65C
            norm_vib = np.clip((group['vib_mag_roll_mean_1h'] - 1.5) / (6.0 - 1.5), 0.0, 1.0)
            norm_temp = np.clip((group['temp_diff_roll_mean_1h'] - 20.0) / (65.0 - 20.0), 0.0, 1.0)
            norm_acoustic = np.clip((group['acoustic_roll_mean_1h'] - 60.0) / (95.0 - 60.0), 0.0, 1.0)
            
            degradation_score = 0.45 * norm_vib + 0.35 * norm_temp + 0.20 * norm_acoustic
            group['health_index_pct'] = np.clip(100.0 * (1.0 - degradation_score), 0.0, 100.0)
            
            # AI Predictive Maintenance Targets
            # Binary Early Warning: Failure in next 24 Hours (144 samples ahead)
            # Shift backward by up to 144 steps
            lead_window = 144
            has_future_failure = group['failure_occurred'].rolling(window=lead_window, min_periods=1).max().shift(-lead_window).fillna(0)
            group['failure_in_next_24h'] = has_future_failure.astype(int)
            
            # Operational Risk Category
            def assign_risk(hi):
                if hi >= 75.0:
                    return 'Normal'
                elif hi >= 50.0:
                    return 'Warning'
                elif hi >= 25.0:
                    return 'Elevated_Risk'
                else:
                    return 'Critical'
                    
            group['risk_category'] = group['health_index_pct'].apply(assign_risk)
            
            engineered_groups.append(group)
            
        feat_df = pd.concat(engineered_groups, ignore_index=True)
        
        print(f"[Feature Engineering] Generated {feat_df.shape[1]} total columns across {len(feat_df)} records.")
        
        # Save output datasets
        os.makedirs(os.path.dirname(self.output_feature_csv), exist_ok=True)
        feat_df.to_csv(self.output_feature_csv, index=False)
        feat_df.to_parquet(self.output_feature_parquet, index=False)
        print(f"[Feature Engineering] Saved engineered features to:\n  - CSV: {self.output_feature_csv}\n  - Parquet: {self.output_feature_parquet}")
        
        # Generate feature summary metrics
        summary = {
            'total_features': int(feat_df.shape[1]),
            'total_samples': int(len(feat_df)),
            'failure_distribution': feat_df['failure_type'].value_counts().to_dict(),
            'early_warning_24h_positives': int(feat_df['failure_in_next_24h'].sum()),
            'early_warning_24h_rate_pct': round(float(feat_df['failure_in_next_24h'].mean() * 100), 2),
            'risk_category_breakdown': feat_df['risk_category'].value_counts().to_dict(),
            'mean_health_index': round(float(feat_df['health_index_pct'].mean()), 2)
        }
        
        import json
        os.makedirs(os.path.dirname(self.feature_report_path), exist_ok=True)
        with open(self.feature_report_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
            
        print("[Feature Engineering] Summary report saved to:", self.feature_report_path)
        return feat_df, summary

if __name__ == '__main__':
    fe = IndustrialFeatureEngineer()
    df_feat, summ = fe.extract_features()
    print("Feature Engineering Summary:", summ)
