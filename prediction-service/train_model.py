import json
import numpy as np
from sklearn.tree import DecisionTreeRegressor
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.inspection import permutation_importance
import joblib

with open("test_large.json", "r") as f:
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
    "power_mean"
]

target_feature_map = {
    "overall_time": ["total_path_length_xy", "total_path_length_z", "mean_path_segment_length_xy", "mean_path_segment_length_z", "planar_switch_count"],
    "time_xy": ["total_path_length_xy", "mean_path_segment_length_xy", "planar_switch_count"],
    "time_z": ["total_path_length_z", "mean_path_segment_length_z"],
    "accel_phases": ["total_path_length_xy", "planar_switch_count"],
    "decel_phases": ["total_path_length_xy", "planar_switch_count"],
    "current_spike_count": ["total_path_length_xy", "total_path_length_z", "high_frequency_accel_events", "planar_switch_count"],
    "power_spike_count": ["total_path_length_xy", "total_path_length_z", "high_frequency_accel_events", "planar_switch_count"],
    "feedrate_mean": ["mean_path_segment_length_xy", "mean_path_segment_length_z", "high_frequency_accel_events"],
    "current_mean": ["mean_path_segment_length_xy", "mean_path_segment_length_z", "high_frequency_accel_events"],
    "power_mean": ["mean_path_segment_length_xy", "mean_path_segment_length_z", "high_frequency_accel_events"]
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

train_idx, test_idx = train_test_split(
    np.arange(len(input_data)), test_size=0.2, random_state=42
)

def build_X(features, indices=None):
    X = np.array([[sample[f] for f in features] for sample in input_data])
    if indices is not None:
        X = X[indices]
    return X

models_dict = {}
performance = {}

print("\n=== Model Training & Evaluation ===")
for key in target_keys:
    features = target_feature_map[key]
    X = build_X(features)
    y = np.array(output_data[key])
    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]

    param_grid = {
        "max_depth": [4, 6, 8],
        "min_samples_leaf": [2, 5, 10],
    }

    grid_search = GridSearchCV(
        DecisionTreeRegressor(random_state=42),
        param_grid,
        cv=5,
        scoring="r2",
        n_jobs=-1
    )
    grid_search.fit(X_train, y_train)

    model = grid_search.best_estimator_
    models_dict[key] = model

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    mae_percentage = (mae / np.mean(np.abs(y_test))) * 100 if np.mean(np.abs(y_test)) != 0 else np.nan
    epsilon = 1e-8
    mape = np.mean(np.abs((y_test - y_pred) / (y_test + epsilon))) * 100

    performance[key] = {
        "MAE": mae,
        "MAE_percent": mae_percentage,
        "MAPE": mape,
        "R2": r2,
        "Best_params": grid_search.best_params_
    }

    print(f"{key}:")
    print(f"  MAE: {mae:.2f}")
    print(f"  MAE (% of mean): {mae_percentage:.2f}%")
    print(f"  MAPE: {mape:.2f}%")
    print(f"  R² Score: {r2:.2f}")
    print(f"  Used features: {features}")
    print(f"  Best params: {grid_search.best_params_}")
    print("-" * 50)

print("\n=== Feature Contribution (Raw Values, Ranked) ===")
for key in target_keys:
    features = target_feature_map[key]
    X_test = build_X(features, indices=test_idx)
    y_test = np.array(output_data[key])[test_idx]

    result = permutation_importance(
        estimator=models_dict[key],
        X=X_test,
        y=y_test,
        n_repeats=10,
        random_state=42,
        scoring="r2"
    )

    importances = result.importances_mean
    sorted_idx = np.argsort(importances)[::-1]

    print(f"\nOutput: {key}")
    print("Top contributing features:")
    for idx in sorted_idx[:5]:
        print(f"  {features[idx]:<25}: {importances[idx]:8.5f}")
    print("Least contributing features:")
    for idx in sorted_idx[-5:]:
        print(f"  {features[idx]:<25}: {importances[idx]:8.5f}")

input_features_base = [
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

model_bundle = {
    "models": models_dict,
    "target_keys": target_keys,
    "target_feature_map": target_feature_map,
    "performance": performance,
    "input_features_base": input_features_base
}

joblib.dump(model_bundle, "decision_tree_models_bundle.pkl")
print("\n[INFO] All models and metadata saved as 'decision_tree_models_bundle.pkl'")
