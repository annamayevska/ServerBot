import json
import numpy as np
from sklearn.svm import SVR
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.inspection import permutation_importance
import joblib


with open("dataset_test_large.json", "r") as f:
    dataset = json.load(f)

all_possible_features = [
    "total_path_length_xy",
    "total_path_length_z",
    "mean_path_segment_length_xy",
    "mean_path_segment_length_z",
    "average_acceleration_proxy",
    "mean_vel_ratio",
    "planar_switch_count",
    "move_count_xy",
    "move_count_z",
    "dense_to_long_move_ratio",
    "high_frequency_accel_events",
    "xy_z_path_ratio",
    "vel_var"
]


target_keys = [
    "overall_time",
    "time_xy",
    "time_z",
    "accel_phases",
    "decel_phases",
    "current_spike_count",
    "power_spike_count",
    "feedrate_mean",
    "current_mean",
    "power_mean",
    "feedrate_std",
    "current_std",
    "power_std"
]

# Map to targets
target_feature_map = {
    "overall_time": ["total_path_length_xy", "total_path_length_z", "mean_path_segment_length_xy", "mean_path_segment_length_z", "planar_switch_count"],
    "time_xy": ["total_path_length_xy", "mean_path_segment_length_xy", "planar_switch_count"],
    "time_z": ["total_path_length_z", "mean_path_segment_length_z"],
    "accel_phases": ["total_path_length_xy", "planar_switch_count"],
    "decel_phases": ["total_path_length_xy", "planar_switch_count"],
    "current_spike_count": ["total_path_length_xy", "total_path_length_z", "high_frequency_accel_events"],
    "power_spike_count": ["total_path_length_xy", "total_path_length_z", "high_frequency_accel_events"],
    "feedrate_mean": ["mean_path_segment_length_xy", "mean_path_segment_length_z", "high_frequency_accel_events", "average_acceleration_proxy", "xy_z_path_ratio"],
    "current_mean": ["mean_path_segment_length_xy", "mean_path_segment_length_z", "mean_vel_ratio", "vel_var", "high_frequency_accel_events"],
    "power_mean": ["mean_path_segment_length_xy", "mean_vel_ratio", "vel_var", "high_frequency_accel_events"],
    "feedrate_std": ["mean_path_segment_length_xy", "mean_path_segment_length_z", "mean_vel_ratio", "xy_z_path_ratio", "planar_switch_count"],
    "current_std": ["mean_path_segment_length_xy", "mean_path_segment_length_z", "mean_vel_ratio",  "xy_z_path_ratio", "planar_switch_count"],
    "power_std": ["mean_path_segment_length_xy", "mean_path_segment_length_z", "mean_vel_ratio", "xy_z_path_ratio", "planar_switch_count"]
}

print(f"[INFO] Target features configured: {len(target_keys)} total")

input_data = []
output_data = {key: [] for key in target_keys}

for obj in dataset:
    feats = obj["input_features"]
    outs = obj["output_features"]
    input_data.append(feats)
    for key in target_keys:
        output_data[key].append(outs.get(key, np.nan))

print(f"[INFO] Loaded {len(input_data)} samples.")

train_idx, test_idx = train_test_split(np.arange(len(input_data)), test_size=0.2, random_state=42)

def build_X(features, indices=None):
    X = np.array([[sample[f] for f in features] for sample in input_data])
    if indices is not None:
        X = X[indices]
    return X


scalers_dict = {}
models_dict = {}
performance = {}

print("\n=== SVR Model Training & Evaluation ===")
for key in target_keys:
    features = target_feature_map[key]
    X = build_X(features)
    y = np.array(output_data[key])
    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]

    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    scalers_dict[key] = scaler

    # Grid search for best SVR hyperparameters
    param_grid = {
        "C": [0.1, 1, 10, 100, 300, 1000],
        "epsilon": [0.001, 0.01, 0.1, 0.5, 1],
        "gamma": [0.001, 0.01, 0.1, 'scale', 'auto']
    }
    grid_search = GridSearchCV(SVR(kernel="rbf"), param_grid, cv=5, scoring="r2", n_jobs=-1)
    grid_search.fit(X_train_scaled, y_train)

    svr_model = grid_search.best_estimator_
    models_dict[key] = svr_model
    X_test_used = X_test_scaled

    y_pred = svr_model.predict(X_test_used)

    # Metrics 
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    mae_percentage = (mae / np.mean(np.abs(y_test))) * 100 if np.mean(np.abs(y_test)) != 0 else np.nan
    epsilon_val = 1e-8
    mape = np.mean(np.abs((y_test - y_pred) / (y_test + epsilon_val))) * 100

    performance[key] = {
        "MAE": mae,
        "MAE_percent": mae_percentage,
        "MAPE": mape,
        "R2": r2,
        "Used_features": features,
        "Best_params": grid_search.best_params_
    }

    print(f"{key}:")
    print(f"  MAE: {mae:.2f}")
    print(f"  MAE (% of mean): {mae_percentage:.2f}%")
    print(f"  MAPE: {mape:.2f}%")
    print(f"  R² Score: {r2:.2f}")
    print(f"  Features used: {features}")
    print(f"  Best params: {grid_search.best_params_}")
    print("-" * 50)

# Feature Contribution via Permutation Importance 
print("\n=== Feature Contribution (Permutation Importance) ===")
for key in target_keys:
    features = target_feature_map[key]
    X_test = build_X(features, indices=test_idx)
    y_test = np.array(output_data[key])[test_idx]

    model = models_dict[key]
    X_test_scaled = scalers_dict[key].transform(X_test)

    result = permutation_importance(model, X_test_scaled, y_test, n_repeats=10, random_state=42, scoring="r2")
    importances = result.importances_mean
    sorted_idx = np.argsort(importances)[::-1]

    print(f"\nOutput: {key}")
    print("Top contributing features:")
    for idx in sorted_idx[:5]:
        print(f"  {features[idx]:<25}: {importances[idx]:.5f}")
    print("Least contributing features:")
    for idx in sorted_idx[-5:]:
        print(f"  {features[idx]:<25}: {importances[idx]:.5f}")

# Save all models and metadata 
model_bundle = {
    "models": models_dict,
    "scalers": scalers_dict,
    "target_keys": target_keys,
    "target_feature_map": target_feature_map,
    "performance": performance,
    "input_features": all_possible_features
}

joblib.dump(model_bundle, "svr_models_bundle.pkl")
print("\n[INFO] All SVR models and metadata saved as 'svr_models_bundle.pkl'")
