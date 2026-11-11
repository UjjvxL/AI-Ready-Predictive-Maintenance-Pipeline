"""
AI-Ready Data Engineering Pipeline for Predictive Maintenance
Master Pipeline Orchestrator (End-to-End Execution)
Coordinates: Telemetry Ingestion -> MongoDB Storage -> Cleaning & Validation -> 
Feature Engineering -> AI Preparation & Benchmark Validation.
"""

import os
import sys
import argparse
import time
from datetime import datetime

# Import modular components
from generate_dataset import generate_industrial_telemetry
from mongodb_handler import MongoDBPipelineHandler
from cleaning_validation import IndustrialDataCleaner
from feature_engineering import IndustrialFeatureEngineer
from ai_preparation import AIDataPreparator

def run_end_to_end_pipeline(force_generate=False):
    start_total = time.time()
    print("=" * 75)
    print("  L&T EDUTECH - PROJECT STATEMENT 6")
    print("  AI-READY DATA ENGINEERING PIPELINE FOR PREDICTIVE MAINTENANCE")
    print(f"  Execution Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 75)

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    raw_csv = os.path.join(base_dir, 'data', 'raw', 'raw_machine_telemetry.csv')

    # STAGE 1: Data Ingestion & Raw Telemetry Provisioning
    print("\n>>> STAGE 1: Industrial Machine Telemetry Ingestion")
    if force_generate or not os.path.exists(raw_csv):
        print("  Generating fresh multi-machine telemetry...")
        generate_industrial_telemetry(num_machines=10, operational_hours=1200)
    else:
        print(f"  Found existing raw telemetry: {raw_csv}")

    # STAGE 2: MongoDB Document Store Ingestion (Raw Stream)
    print("\n>>> STAGE 2: MongoDB NoSQL Document Storage Ingestion")
    mongo = MongoDBPipelineHandler()
    import pandas as pd
    raw_df = pd.read_csv(raw_csv)
    mongo.ingest_dataframe(raw_df, 'raw_telemetry')

    # STAGE 3: Data Cleaning, Validation & Anomaly Correction
    print("\n>>> STAGE 3: Data Quality, Cleaning & Anomaly Correction")
    cleaner = IndustrialDataCleaner(raw_csv_path=raw_csv)
    cleaned_df, audit_summary = cleaner.run_cleaning_pipeline()

    # Ingest clean records to MongoDB clean collection
    mongo.ingest_dataframe(cleaned_df, 'clean_telemetry')

    # STAGE 4: Signal Physics & Feature Engineering
    print("\n>>> STAGE 4: Time-Domain, Vibration & Thermodynamic Feature Engineering")
    fe = IndustrialFeatureEngineer()
    features_df, fe_summary = fe.extract_features()

    # STAGE 5: AI Data Preparation & Model Benchmarking
    print("\n>>> STAGE 5: AI-Ready Dataset Partitioning & Model Benchmark")
    ai_prep = AIDataPreparator()
    benchmark_metrics = ai_prep.prepare_and_benchmark()

    elapsed = round(time.time() - start_total, 2)
    print("\n" + "=" * 75)
    print(f"  PIPELINE EXECUTION SUCCESSFUL in {elapsed} seconds!")
    print(f"  - Total Ingested Telemetry Records: {audit_summary['initial_record_count']:,}")
    print(f"  - Verified Cleaned Records:        {audit_summary['final_record_count']:,} (100% Complete)")
    print(f"  - Extracted Predictive Features:   {features_df.shape[1]}")
    print(f"  - AI Classifier ROC-AUC Score:      {benchmark_metrics['classification_metrics']['roc_auc_score']:.4f}")
    print(f"  - AI Classifier F1-Score:           {benchmark_metrics['classification_metrics']['f1_score_failure']:.4f}")
    print(f"  - AI RUL Regressor RMSE:            {benchmark_metrics['rul_regression_metrics']['rmse_hours']:.2f} hours")
    print("=" * 75)
    
    return {
        'audit': audit_summary,
        'feature_summary': fe_summary,
        'benchmark': benchmark_metrics,
        'execution_time_sec': elapsed
    }

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="AI-Ready Data Engineering Pipeline")
    parser.add_argument('--generate', action='store_true', help="Force regenerate raw telemetry")
    args = parser.parse_args()
    
    run_end_to_end_pipeline(force_generate=args.generate)

