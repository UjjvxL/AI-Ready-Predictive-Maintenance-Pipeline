"""
AI-Ready Data Engineering Pipeline for Predictive Maintenance
Module: Data Cleaning, Validation & Quality Assurance Engine
Performs deduplication, schema validation, physical boundary checking,
statistical outlier winsorization, temporal interpolation, and noise smoothing.
"""

import os
import numpy as np
import pandas as pd

class IndustrialDataCleaner:
    def __init__(self, raw_csv_path=None):
        self.raw_csv_path = raw_csv_path or os.path.join(
            os.path.dirname(__file__), '..', 'data', 'raw', 'raw_machine_telemetry.csv'
        )
        self.output_csv_path = os.path.join(
            os.path.dirname(__file__), '..', 'data', 'processed', 'cleaned_machine_telemetry.csv'
        )
        self.output_parquet_path = os.path.join(
            os.path.dirname(__file__), '..', 'data', 'processed', 'cleaned_machine_telemetry.parquet'
        )
        self.quality_audit = {}

    def run_cleaning_pipeline(self):
        print(f"[Cleaning Pipeline] Loading raw telemetry from {self.raw_csv_path}...")
        df = pd.read_csv(self.raw_csv_path)
        initial_rows = len(df)
        self.quality_audit['initial_record_count'] = initial_rows
        self.quality_audit['initial_null_counts'] = df.isnull().sum().to_dict()
        
        # 1. Schema Validation & Datetime Parsing
        print("[Cleaning Pipeline] 1. Enforcing schema and converting timestamps...")
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # 2. Deduplication
        print("[Cleaning Pipeline] 2. Checking and purging duplicate telemetry packets...")
        duplicates_count = df.duplicated(subset=['machine_id', 'timestamp']).sum()
        df = df.drop_duplicates(subset=['machine_id', 'timestamp'], keep='first')
        self.quality_audit['duplicates_removed'] = int(duplicates_count)
        print(f"  -> Removed {duplicates_count} duplicate records. Current rows: {len(df)}")
        
        # Sort chronologically per machine
        df = df.sort_values(by=['machine_id', 'timestamp']).reset_index(drop=True)
        
        # 3. Domain & Physical Boundary Sanity Validation
        print("[Cleaning Pipeline] 3. Applying physical constraint filtering...")
        sensor_bounds = {
            'bearing_temperature_c': (-10.0, 180.0), # Extreme values like -999, 999 or 450 C are sensor faults
            'vibration_x_g': (0.0, 20.0),           # Physical sensor limit for vibration baseline
            'vibration_y_g': (0.0, 20.0),
            'vibration_z_g': (0.0, 20.0),
            'hydraulic_pressure_bar': (0.0, 25.0),
            'rotational_speed_rpm': (0.0, 6000.0),
            'motor_torque_nm': (0.0, 300.0),
            'acoustic_emission_db': (20.0, 140.0),
            'power_consumption_kw': (0.0, 150.0)
        }
        
        outliers_replaced = 0
        for col, (lower_b, upper_b) in sensor_bounds.items():
            if col in df.columns:
                invalid_mask = (df[col] < lower_b) | (df[col] > upper_b)
                count_invalid = invalid_mask.sum()
                if count_invalid > 0:
                    df.loc[invalid_mask, col] = np.nan
                    outliers_replaced += int(count_invalid)
                    
        self.quality_audit['physical_outliers_nullified'] = outliers_replaced
        print(f"  -> Flagged and nullified {outliers_replaced} physical constraint violations.")
        
        # 4. Statistical Outlier Capping (IQR / Z-Score Winsorization)
        print("[Cleaning Pipeline] 4. Statistical Winsorization on sensor variables...")
        stat_outliers_capped = 0
        for col in sensor_bounds.keys():
            if col in df.columns:
                q25 = df[col].quantile(0.01)
                q75 = df[col].quantile(0.99)
                iqr = q75 - q25
                upper_bound = q75 + 3.0 * iqr
                lower_bound = max(0.0, q25 - 3.0 * iqr)
                
                over_mask = df[col] > upper_bound
                under_mask = df[col] < lower_bound
                capped_count = over_mask.sum() + under_mask.sum()
                
                df.loc[over_mask, col] = upper_bound
                df.loc[under_mask, col] = lower_bound
                stat_outliers_capped += int(capped_count)
                
        self.quality_audit['statistical_outliers_capped'] = stat_outliers_capped
        print(f"  -> Capped {stat_outliers_capped} statistical extreme points.")
        
        # 5. Missing Value Imputation (Time-Series Continuity Aware)
        print("[Cleaning Pipeline] 5. Time-series interpolation & imputation per machine...")
        
        cleaned_dfs = []
        for m_id, group in df.groupby('machine_id'):
            group = group.copy().sort_values('timestamp')
            
            # Numeric columns to interpolate
            numeric_cols = list(sensor_bounds.keys()) + ['operational_hours', 'tool_wear_min', 'rul_hours']
            for col in numeric_cols:
                if col in group.columns:
                    # Mark if imputed
                    group[f'{col}_was_imputed'] = group[col].isna().astype(int)
                    
                    # Short gap linear interpolation preserving temporal slope
                    group[col] = group[col].interpolate(method='linear', limit=12, limit_direction='both')
                    
                    # Backward/forward fill for remaining edge gaps
                    group[col] = group[col].bfill().ffill()
            
            # Categorical fill
            group['failure_occurred'] = group['failure_occurred'].fillna(0).astype(int)
            group['failure_type'] = group['failure_type'].fillna('No_Failure')
            
            cleaned_dfs.append(group)
            
        clean_df = pd.concat(cleaned_dfs, ignore_index=True)
        
        # 6. Overall Imputed Flag
        imputed_cols = [c for c in clean_df.columns if c.endswith('_was_imputed')]
        clean_df['data_was_imputed'] = (clean_df[imputed_cols].sum(axis=1) > 0).astype(int)
        clean_df = clean_df.drop(columns=imputed_cols)
        
        # 7. Final Validation Audit
        final_nulls = clean_df.isnull().sum().sum()
        self.quality_audit['final_null_count'] = int(final_nulls)
        self.quality_audit['final_record_count'] = len(clean_df)
        self.quality_audit['data_completeness_pct'] = 100.0 if final_nulls == 0 else round((1 - final_nulls / (len(clean_df) * clean_df.shape[1])) * 100, 2)
        
        print(f"[Cleaning Pipeline] Validation Complete: Total Records: {len(clean_df)}, Remaining Nulls: {final_nulls}")
        print(f"  -> Data Completeness Score: {self.quality_audit['data_completeness_pct']}%")
        
        # Save output datasets
        os.makedirs(os.path.dirname(self.output_csv_path), exist_ok=True)
        clean_df.to_csv(self.output_csv_path, index=False)
        try:
            clean_df.to_parquet(self.output_parquet_path, index=False)
            print(f"[Cleaning Pipeline] Cleaned dataset saved to:\n  - CSV: {self.output_csv_path}\n  - Parquet: {self.output_parquet_path}")
        except Exception as e:
            print(f"[Cleaning Pipeline] Parquet export note ({e}). Saved CSV to: {self.output_csv_path}")
        
        return clean_df, self.quality_audit

if __name__ == '__main__':
    cleaner = IndustrialDataCleaner()
    cleaned_df, audit = cleaner.run_cleaning_pipeline()
    print("Audit Summary:", audit)
