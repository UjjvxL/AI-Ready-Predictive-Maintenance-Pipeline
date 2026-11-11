"""
AI-Ready Data Engineering Pipeline for Predictive Maintenance
Module: Visual Artifact & Diagnostic Plot Generator
Produces publication-grade figures:
1. Raw vs Cleaned sensor waveforms (handling outliers & interpolation)
2. Machine Health Index degradation trajectory over time
3. Feature correlation matrix heatmap
4. AI feature importance rankings
5. RUL Prediction vs Actual curve
"""

import os
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def generate_visual_artifacts():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    img_dir = os.path.join(base_dir, 'reports', 'figures')
    os.makedirs(img_dir, exist_ok=True)
    
    print(f"[Visuals] Generating publication-grade figures in {img_dir}...")
    
    # 1. Load Data
    raw_csv = os.path.join(base_dir, 'data', 'raw', 'raw_machine_telemetry.csv')
    clean_parquet = os.path.join(base_dir, 'data', 'processed', 'cleaned_machine_telemetry.parquet')
    feat_parquet = os.path.join(base_dir, 'data', 'processed', 'engineered_features.parquet')
    metrics_json = os.path.join(base_dir, 'reports', 'ai_benchmark_metrics.json')
    
    df_raw = pd.read_csv(raw_csv)
    df_clean = pd.read_parquet(clean_parquet)
    df_feat = pd.read_parquet(feat_parquet)
    
    with open(metrics_json, 'r') as f:
        metrics = json.load(f)
        
    # Style setup
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    plt.rcParams['font.sans-serif'] = 'Arial'
    plt.rcParams['axes.edgecolor'] = '#333333'
    plt.rcParams['axes.linewidth'] = 0.8
    
    # -----------------------------------------------------------------
    # Figure 1: Raw vs Cleaned Sensor Telemetry (Noise, Outliers, Interpolation)
    # -----------------------------------------------------------------
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True, dpi=300)
    
    # Pick Machine EQ-101 (failed machine)
    raw_m = df_raw[df_raw['machine_id'] == 'EQ-101'].iloc[1500:1900].reset_index(drop=True)
    clean_m = df_clean[df_clean['machine_id'] == 'EQ-101'].iloc[1500:1900].reset_index(drop=True)
    
    time_steps = np.arange(len(raw_m))
    
    # Bearing Temperature subplot
    axes[0].plot(time_steps, raw_m['bearing_temperature_c'], color='#E63946', alpha=0.5, linestyle='--', label='Raw Telemetry (With Outlier Spikes & Nulls)')
    axes[0].scatter(time_steps[raw_m['bearing_temperature_c'].isna()], [35]*raw_m['bearing_temperature_c'].isna().sum(), 
                    color='#D90429', marker='x', s=25, label='Missing Packet Drops')
    axes[0].plot(time_steps, clean_m['bearing_temperature_c'], color='#1D3557', linewidth=1.8, label='Cleaned & Interpolated Signal')
    axes[0].set_ylabel('Bearing Temp (°C)', fontsize=11, fontweight='bold', color='#1D3557')
    axes[0].set_title('Telemetry Quality Validation: Bearing Temperature (Raw vs Cleaned)', fontsize=13, fontweight='bold')
    axes[0].legend(loc='upper left', frameon=True)
    axes[0].set_ylim(20, 95)
    
    # Vibration subplot
    axes[1].plot(time_steps, raw_m['vibration_x_g'], color='#E63946', alpha=0.45, label='Raw Vibration (Radial X Spike Noise)')
    axes[1].plot(time_steps, clean_m['vibration_x_g'], color='#2A9D8F', linewidth=1.8, label='Cleaned Vibration Signal (Denoised & Imputed)')
    axes[1].set_ylabel('Vibration X (g)', fontsize=11, fontweight='bold', color='#1D3557')
    axes[1].set_xlabel('Operational Sample Sequence (10-min increments)', fontsize=11, fontweight='bold')
    axes[1].set_title('Telemetry Quality Validation: Vibration Radial X (Raw vs Cleaned)', fontsize=13, fontweight='bold')
    axes[1].legend(loc='upper left', frameon=True)
    axes[1].set_ylim(0, 8.5)
    
    plt.tight_layout()
    fig1_path = os.path.join(img_dir, 'fig1_data_cleaning_validation.png')
    plt.savefig(fig1_path)
    plt.close()
    print(f"  -> Generated: {fig1_path}")
    
    # -----------------------------------------------------------------
    # Figure 2: Degradation Signature & Composite Health Index vs RUL
    # -----------------------------------------------------------------
    fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True, dpi=300)
    full_m = df_feat[df_feat['machine_id'] == 'EQ-101'].reset_index(drop=True)
    hours = full_m['operational_hours']
    
    axes[0].plot(hours, full_m['vib_rms_1h'], color='#E76F51', linewidth=1.8, label='1h Rolling Vibration RMS (g)')
    axes[0].plot(hours, full_m['vib_mag_roll_mean_6h'], color='#264653', linewidth=2.0, linestyle='--', label='6h Vibration Mean Baseline (g)')
    axes[0].axvline(x=hours.iloc[-1] - 24, color='#D62828', linestyle=':', label='24-Hour Early Warning Lead')
    axes[0].set_ylabel('Vibration RMS (g)', fontsize=10, fontweight='bold')
    axes[0].set_title('Degradation Profile: Progressive Bearing Wear on Centrifugal Pump (EQ-101)', fontsize=13, fontweight='bold')
    axes[0].legend(loc='upper left')
    
    axes[1].plot(hours, full_m['temp_diff_roll_mean_1h'], color='#F4A261', linewidth=1.8, label='Bearing Thermal Gradient ΔT (°C)')
    axes[1].set_ylabel('Thermal Gradient (°C)', fontsize=10, fontweight='bold')
    axes[1].legend(loc='upper left')
    
    axes[2].plot(hours, full_m['health_index_pct'], color='#2A9D8F', linewidth=2.2, label='Composite Machine Health Index (%)')
    axes[2].axhline(y=75, color='#E9C46A', linestyle='--', label='Warning Threshold (75%)')
    axes[2].axhline(y=50, color='#E76F51', linestyle='--', label='High Risk Threshold (50%)')
    axes[2].axhline(y=25, color='#E63946', linestyle='--', label='Critical Replacement Threshold (25%)')
    axes[2].set_ylabel('Health Index (%)', fontsize=10, fontweight='bold')
    axes[2].set_xlabel('Operational Lifecycle (Hours)', fontsize=11, fontweight='bold')
    axes[2].set_ylim(-5, 105)
    axes[2].legend(loc='lower left')
    
    plt.tight_layout()
    fig2_path = os.path.join(img_dir, 'fig2_degradation_health_index.png')
    plt.savefig(fig2_path)
    plt.close()
    print(f"  -> Generated: {fig2_path}")
    
    # -----------------------------------------------------------------
    # Figure 3: Top Feature Importance Bar Chart
    # -----------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    top_feats = metrics['top_15_important_features']
    names = list(top_feats.keys())[::-1]
    values = [top_feats[k] * 100 for k in names]
    
    colors = ['#2A9D8F' if v > 7.0 else '#457B9D' for v in values]
    bars = ax.barh(names, values, color=colors, edgecolor='#1D3557', height=0.65)
    
    for bar in bars:
        w = bar.get_width()
        ax.text(w + 0.3, bar.get_y() + bar.get_height()/2, f"{w:.1f}%", va='center', ha='left', fontsize=9, fontweight='bold', color='#1D3557')
        
    ax.set_xlabel('Random Forest Relative Importance (%)', fontsize=11, fontweight='bold')
    ax.set_title('Top 15 Predictive Features for Failure Early-Warning (24h Ahead)', fontsize=13, fontweight='bold')
    ax.set_xlim(0, max(values) + 3.5)
    
    plt.tight_layout()
    fig3_path = os.path.join(img_dir, 'fig3_feature_importance.png')
    plt.savefig(fig3_path)
    plt.close()
    print(f"  -> Generated: {fig3_path}")
    
    # -----------------------------------------------------------------
    # Figure 4: Feature Correlation Matrix Heatmap
    # -----------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
    selected_corr_cols = [
        'vibration_magnitude_g', 'vib_rms_1h', 'temp_difference_c', 'motor_torque_nm',
        'acoustic_emission_db', 'mechanical_power_kw', 'health_index_pct', 'rul_hours', 'failure_in_next_24h'
    ]
    corr_matrix = df_feat[selected_corr_cols].corr()
    
    cax = ax.matshow(corr_matrix, cmap='coolwarm', vmin=-1, vmax=1)
    fig.colorbar(cax, shrink=0.8)
    
    ax.set_xticks(range(len(selected_corr_cols)))
    ax.set_yticks(range(len(selected_corr_cols)))
    ax.set_xticklabels(selected_corr_cols, rotation=45, ha='left', fontsize=9)
    ax.set_yticklabels(selected_corr_cols, fontsize=9)
    
    # Annotate values
    for i in range(len(selected_corr_cols)):
        for j in range(len(selected_corr_cols)):
            val = corr_matrix.iloc[i, j]
            text_col = 'white' if abs(val) > 0.55 else 'black'
            ax.text(j, i, f"{val:.2f}", ha='center', va='center', color=text_col, fontsize=8, fontweight='bold')
            
    ax.set_title('Inter-Feature Pearson Correlation Heatmap', fontsize=13, fontweight='bold', pad=30)
    plt.tight_layout()
    fig4_path = os.path.join(img_dir, 'fig4_correlation_heatmap.png')
    plt.savefig(fig4_path)
    plt.close()
    print(f"  -> Generated: {fig4_path}")
    
    print("[Visuals] All publication-grade figures successfully generated!")
    return [fig1_path, fig2_path, fig3_path, fig4_path]

if __name__ == '__main__':
    generate_visual_artifacts()

