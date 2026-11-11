"""
AI-Ready Data Engineering Pipeline for Predictive Maintenance
Module: Baseline Model Evaluator & Readiness Verification
Trains Random Forest classifiers & regressors (Raw vs Engineered),
measures ROC-AUC, PR-AUC, Precision, Recall, F1, RUL MAE, and extracts feature importances.
"""

import os
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import roc_auc_score, precision_recall_curve, auc, precision_score, recall_score, f1_score, mean_absolute_error
from sklearn.model_selection import KFold

def evaluate_baseline_models():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    data_path = os.path.join(base_dir, 'data', 'ai_ready_dataset_scaled.csv')
    reports_dir = os.path.join(base_dir, 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    
    print("[Model Check] Loading AI-Ready scaled dataset from:", data_path)
    df = pd.read_csv(data_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Raw sensors
    raw_sensors = ['temperature', 'vibration', 'pressure', 'rpm', 'current', 'oil_quality']
    
    # Exclude metadata and target columns to get engineered features
    exclude_cols = ['machine_id', 'timestamp', 'installation_date', 'fail_within_72h', 'RUL_hours', 'RUL_capped']
    impute_cols = [c for c in df.columns if c.endswith('_imputed_flag')]
    feature_cols = [c for c in df.columns if c not in exclude_cols and c not in impute_cols]
    
    print(f"[Model Check] Comparing Raw ({len(raw_sensors)}) vs Engineered ({len(feature_cols)}) features...")
    
    # Split
    train_end = pd.to_datetime('2025-03-21 23:00:00')
    test_start = pd.to_datetime('2025-03-25 00:00:00')
    
    train_df = df[df['timestamp'] <= train_end]
    test_df = df[df['timestamp'] >= test_start]
    
    X_train_raw = train_df[raw_sensors]
    X_test_raw = test_df[raw_sensors]
    
    X_train_eng = train_df[feature_cols]
    X_test_eng = test_df[feature_cols]
    
    y_train_cls = train_df['fail_within_72h']
    y_test_cls = test_df['fail_within_72h']
    
    # ---------------------------------------------------------
    # Baseline 1: Raw Sensors Only
    # ---------------------------------------------------------
    print("  Evaluating Baseline 1: Raw Sensors Only...")
    clf_raw = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42, n_jobs=-1)
    clf_raw.fit(X_train_raw, y_train_cls)
    probs_raw = clf_raw.predict_proba(X_test_raw)[:, 1]
    preds_raw = (probs_raw >= 0.5).astype(int)
    
    p_prec_raw, p_rec_raw, _ = precision_recall_curve(y_test_cls, probs_raw)
    raw_results = {
        'roc_auc': round(float(roc_auc_score(y_test_cls, probs_raw)), 4),
        'pr_auc': round(float(auc(p_rec_raw, p_prec_raw)), 4),
        'precision': round(float(precision_score(y_test_cls, preds_raw, zero_division=0)), 3),
        'recall': round(float(recall_score(y_test_cls, preds_raw, zero_division=0)), 3),
        'f1': round(float(f1_score(y_test_cls, preds_raw, zero_division=0)), 3)
    }
    
    # ---------------------------------------------------------
    # Baseline 2: Engineered Features
    # ---------------------------------------------------------
    print("  Evaluating Baseline 2: Engineered Features (59)...")
    clf_eng = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
    clf_eng.fit(X_train_eng, y_train_cls)
    probs_eng = clf_eng.predict_proba(X_test_eng)[:, 1]
    preds_eng = (probs_eng >= 0.5).astype(int)
    
    p_prec_eng, p_rec_eng, _ = precision_recall_curve(y_test_cls, probs_eng)
    eng_results = {
        'roc_auc': round(float(roc_auc_score(y_test_cls, probs_eng)), 4),
        'pr_auc': round(float(auc(p_rec_eng, p_prec_eng)), 4),
        'precision': round(float(precision_score(y_test_cls, preds_eng, zero_division=0)), 3),
        'recall': round(float(recall_score(y_test_cls, preds_eng, zero_division=0)), 3),
        'f1': round(float(f1_score(y_test_cls, preds_eng, zero_division=0)), 3)
    }
    
    # ---------------------------------------------------------
    # Baseline 3: RUL Regression (MAE)
    # ---------------------------------------------------------
    print("  Evaluating Remaining Useful Life (RUL) Regressor...")
    y_train_rul = train_df['RUL_capped']
    y_test_rul = test_df['RUL_capped']
    
    # Naive baseline: predicting training average
    naive_pred = np.full(len(y_test_rul), y_train_rul.mean())
    naive_mae = round(float(mean_absolute_error(y_test_rul, naive_pred)), 1)
    
    reg = RandomForestRegressor(n_estimators=50, max_depth=8, random_state=42, n_jobs=-1)
    reg.fit(X_train_eng, y_train_rul)
    rul_pred = reg.predict(X_test_eng)
    model_mae = round(float(mean_absolute_error(y_test_rul, rul_pred)), 1)
    
    # ---------------------------------------------------------
    # Feature Importance Export
    # ---------------------------------------------------------
    importances = pd.Series(clf_eng.feature_importances_, index=feature_cols).sort_values(ascending=False)
    df_imp = pd.DataFrame({'Feature': importances.index, 'Importance': importances.values})
    df_imp['Importance'] = df_imp['Importance'].round(4)
    df_imp.to_csv(os.path.join(reports_dir, 'feature_importance.csv'), index=False)
    
    # Baseline Metrics JSON
    baseline_metrics = {
        'classification_test_period': {
            'raw_sensors_only': raw_results,
            'engineered_features': eng_results
        },
        'rul_regression': {
            'naive_baseline_mae_hours': naive_mae,
            'model_mae_hours': model_mae
        },
        'top_10_features': df_imp.head(10).to_dict(orient='records')
    }
    
    metrics_path = os.path.join(reports_dir, 'model_baseline.json')
    with open(metrics_path, 'w', encoding='utf-8') as f:
        json.dump(baseline_metrics, f, indent=2)
        
    print("[Model Check] Completed! Summary:")
    print(json.dumps(baseline_metrics, indent=2))
    return baseline_metrics

if __name__ == '__main__':
    evaluate_baseline_models()
