"""
AI-Ready Data Engineering Pipeline for Predictive Maintenance
Module: AI-Ready Dataset Preparation & Model Benchmark Evaluator
Performs temporal train/test splitting, robust normalization, multi-task labeling,
trains baseline AI models, evaluates ROC-AUC / F1 / RMSE, and extracts feature importances.
"""

import os
import json
import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix, mean_squared_error, r2_score

class AIDataPreparator:
    def __init__(self, feature_parquet_path=None):
        self.feature_parquet_path = feature_parquet_path or os.path.join(
            os.path.dirname(__file__), '..', 'data', 'processed', 'engineered_features.parquet'
        )
        self.ai_ready_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'ai_ready')
        self.reports_dir = os.path.join(os.path.dirname(__file__), '..', 'reports')
        os.makedirs(self.ai_ready_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)

    def prepare_and_benchmark(self):
        print(f"[AI Preparation] Loading engineered features from {self.feature_parquet_path}...")
        df = pd.read_parquet(self.feature_parquet_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values(by=['machine_id', 'timestamp']).reset_index(drop=True)
        
        # 1. Feature Selection
        exclude_cols = [
            'timestamp', 'machine_id', 'machine_type', 'failure_occurred', 
            'failure_type', 'failure_in_next_24h', 'rul_hours', 'risk_category'
        ]
        feature_cols = [c for c in df.columns if c not in exclude_cols]
        print(f"[AI Preparation] Selected {len(feature_cols)} predictor features for AI modelling.")
        
        # 2. Temporal Machine-Wise Splitting (to strictly prevent data leakage)
        # Train on machines 1 to 7 (70%), Val on machine 8 (10%), Test on machines 9 & 10 (20%)
        train_mask = df['machine_id'].isin([f'EQ-{100+i}' for i in range(1, 8)])
        val_mask = df['machine_id'].isin(['EQ-108'])
        test_mask = df['machine_id'].isin(['EQ-109', 'EQ-110'])
        
        X_train_raw = df.loc[train_mask, feature_cols].copy()
        y_train_cls = df.loc[train_mask, 'failure_in_next_24h'].copy()
        y_train_reg = df.loc[train_mask, 'rul_hours'].copy()
        
        X_val_raw = df.loc[val_mask, feature_cols].copy()
        y_val_cls = df.loc[val_mask, 'failure_in_next_24h'].copy()
        y_val_reg = df.loc[val_mask, 'rul_hours'].copy()
        
        X_test_raw = df.loc[test_mask, feature_cols].copy()
        y_test_cls = df.loc[test_mask, 'failure_in_next_24h'].copy()
        y_test_reg = df.loc[test_mask, 'rul_hours'].copy()
        
        print(f"[AI Preparation] Split completed: Train={len(X_train_raw)}, Val={len(X_val_raw)}, Test={len(X_test_raw)}")
        
        # 3. Robust Feature Scaling (fitted strictly on training set)
        scaler = RobustScaler()
        X_train_scaled = pd.DataFrame(scaler.fit_transform(X_train_raw), columns=feature_cols, index=X_train_raw.index)
        X_val_scaled = pd.DataFrame(scaler.transform(X_val_raw), columns=feature_cols, index=X_val_raw.index)
        X_test_scaled = pd.DataFrame(scaler.transform(X_test_raw), columns=feature_cols, index=X_test_raw.index)
        
        # Save AI-Ready datasets
        X_train_scaled.to_parquet(os.path.join(self.ai_ready_dir, 'X_train.parquet'))
        X_val_scaled.to_parquet(os.path.join(self.ai_ready_dir, 'X_val.parquet'))
        X_test_scaled.to_parquet(os.path.join(self.ai_ready_dir, 'X_test.parquet'))
        pd.DataFrame({'failure_in_next_24h': y_train_cls, 'rul_hours': y_train_reg}).to_parquet(
            os.path.join(self.ai_ready_dir, 'y_train.parquet')
        )
        pd.DataFrame({'failure_in_next_24h': y_test_cls, 'rul_hours': y_test_reg}).to_parquet(
            os.path.join(self.ai_ready_dir, 'y_test.parquet')
        )
        print(f"[AI Preparation] Standardized AI datasets saved to {self.ai_ready_dir}")
        
        # 4. Train Baseline AI Classification Model (Random Forest Classifier for 24h Early Warning)
        print("[AI Benchmark] Training Random Forest Early-Warning Classifier...")
        clf = RandomForestClassifier(n_estimators=100, max_depth=12, random_state=42, n_jobs=-1)
        clf.fit(X_train_scaled, y_train_cls)
        
        y_pred_cls = clf.predict(X_test_scaled)
        y_prob_cls = clf.predict_proba(X_test_scaled)[:, 1]
        
        cls_rep = classification_report(y_test_cls, y_pred_cls, output_dict=True)
        roc_auc = roc_auc_score(y_test_cls, y_prob_cls)
        conf_mat = confusion_matrix(y_test_cls, y_pred_cls).tolist()
        
        print(f"[AI Benchmark] Classification ROC-AUC: {roc_auc:.4f}, Macro F1: {cls_rep['macro avg']['f1-score']:.4f}")
        
        # 5. Train Baseline AI Regression Model (Random Forest Regressor for RUL Estimation)
        print("[AI Benchmark] Training Random Forest RUL Regressor...")
        # Cap RUL at 500 hours for realistic regression benchmark
        y_train_reg_clipped = np.clip(y_train_reg, 0, 500)
        y_test_reg_clipped = np.clip(y_test_reg, 0, 500)
        
        reg = RandomForestRegressor(n_estimators=75, max_depth=10, random_state=42, n_jobs=-1)
        reg.fit(X_train_scaled, y_train_reg_clipped)
        
        y_pred_reg = reg.predict(X_test_scaled)
        rul_rmse = float(np.sqrt(mean_squared_error(y_test_reg_clipped, y_pred_reg)))
        rul_r2 = float(r2_score(y_test_reg_clipped, y_pred_reg))
        
        print(f"[AI Benchmark] RUL Regression RMSE: {rul_rmse:.2f} hours, R2 Score: {rul_r2:.4f}")
        
        # 6. Feature Importance Extraction
        feature_importances = pd.Series(clf.feature_importances_, index=feature_cols).sort_values(ascending=False)
        top_15_features = feature_importances.head(15).to_dict()
        
        # Save metrics report
        benchmark_results = {
            'features_count': len(feature_cols),
            'train_samples': len(X_train_scaled),
            'val_samples': len(X_val_scaled),
            'test_samples': len(X_test_scaled),
            'classification_metrics': {
                'roc_auc_score': round(float(roc_auc), 4),
                'precision_failure': round(float(cls_rep['1']['precision']), 4),
                'recall_failure': round(float(cls_rep['1']['recall']), 4),
                'f1_score_failure': round(float(cls_rep['1']['f1-score']), 4),
                'accuracy': round(float(cls_rep['accuracy']), 4),
                'confusion_matrix': conf_mat
            },
            'rul_regression_metrics': {
                'rmse_hours': round(rul_rmse, 2),
                'r2_score': round(rul_r2, 4)
            },
            'top_15_important_features': {k: round(float(v), 5) for k, v in top_15_features.items()}
        }
        
        metrics_file = os.path.join(self.reports_dir, 'ai_benchmark_metrics.json')
        with open(metrics_file, 'w', encoding='utf-8') as f:
            json.dump(benchmark_results, f, indent=2)
            
        print(f"[AI Benchmark] Metrics and Feature Importances saved to: {metrics_file}")
        return benchmark_results

if __name__ == '__main__':
    preparator = AIDataPreparator()
    results = preparator.prepare_and_benchmark()
    print("AI Benchmark Complete. Results:")
    print(json.dumps(results, indent=2))

