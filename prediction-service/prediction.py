import os
import re
import json
import joblib
import numpy as np
from datetime import datetime, timedelta, timezone
from input_properties import compute_input_properties
import statistics  # <- for exact mean/std verification
from flask import Flask, jsonify, request
import logging
import random

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

MODEL_PATH = "./decision_tree_models_bundle.pkl"
DATASET_PATH = "./dataset.json"
OUTPUT_DATASTREAM_PATH = "./generated_datastream.json"

DT = 0.5  

#Load models and dataset
logger.info("Loading model bundle and dataset...")
model_bundle = joblib.load(MODEL_PATH)
models = model_bundle["models"]
input_features_base = model_bundle["input_features_base"]
#hf_accel_feature = model_bundle["hf_accel_feature"]
target_keys = model_bundle["target_keys"]
target_feature_map = model_bundle.get("target_feature_map", {})

with open(DATASET_PATH, "r", encoding="utf-8") as f:
    dataset = json.load(f)
logger.info("Model and dataset loaded successfully.")

#Parse coordinates preserving order
def parse_gcode_sequence(gcode_str):
    logger.debug("Parsing G-code sequence...")
    pattern = re.compile(r"([XYZ])(-?\d+(?:\.\d+)?)", re.IGNORECASE)
    seq = []
    for line in gcode_str.splitlines():
        matches = pattern.findall(line)
        for axis, value in matches:
            seq.append((axis.upper(), float(value)))
    logger.debug(f"Parsed {len(seq)} coordinate entries.")
    return seq

#Interpolation 
def interpolate_sequence(seq, n_updates):
    if not seq:
        logger.warning("Empty sequence passed to interpolate_sequence.")
        return []
    axes = sorted(list({axis for axis, _ in seq}))
    axis_values = {axis: [val for a, val in seq if a == axis] for axis in axes}
    interpolated = []
    for axis in axes:
        vals = axis_values[axis]
        x_orig = np.linspace(0, 1, len(vals))
        x_new = np.linspace(0, 1, n_updates)
        axis_values[axis] = np.interp(x_new, x_orig, vals)
    for i in range(n_updates):
        entry = {axis: float(axis_values[axis][i]) for axis in axes}
        interpolated.append(entry)
    return interpolated

# Distribute accel/decel 
def distribute_alternating_indices(num_updates_minus_one, accel_phases, decel_phases):
    total_phases = accel_phases + decel_phases
    if total_phases <= 0 or num_updates_minus_one <= 0:
        return [], []

    raw_positions = np.linspace(0, num_updates_minus_one - 1, total_phases)
    pos_indices = [int(round(x)) for x in raw_positions]
    seen = set()
    unique_positions = []
    for p in pos_indices:
        p = max(0, min(num_updates_minus_one - 1, p))
        if p not in seen:
            seen.add(p)
            unique_positions.append(p)

    needed = total_phases - len(unique_positions)
    if needed > 0:
        all_slots = list(range(num_updates_minus_one))
        available = [s for s in all_slots if s not in seen]
        if available:
            step = max(1, len(available) / needed)
            idx = 0.0
            for _ in range(needed):
                pick = available[int(round(idx)) % len(available)]
                if pick not in seen:
                    unique_positions.append(pick)
                    seen.add(pick)
                idx += step

    unique_positions = sorted(unique_positions)
    accel_indices = []
    decel_indices = []
    a_rem = accel_phases
    d_rem = decel_phases
    turn_accel = True
    for pos in unique_positions:
        if turn_accel and a_rem > 0:
            accel_indices.append(pos)
            a_rem -= 1
            turn_accel = False if d_rem > 0 else True
        elif (not turn_accel) and d_rem > 0:
            decel_indices.append(pos)
            d_rem -= 1
            turn_accel = True if a_rem > 0 else False
        else:
            if a_rem > 0:
                accel_indices.append(pos)
                a_rem -= 1
            elif d_rem > 0:
                decel_indices.append(pos)
                d_rem -= 1

    accel_indices = sorted(accel_indices)
    decel_indices = sorted(decel_indices)
    return accel_indices, decel_indices

# Datastream generation 
def generate_datastream_from_gcode(gcode_str):
    logger.info("Generating datastream from G-code...")
    try:
        input_features = compute_input_properties(gcode_str=gcode_str)
        if not input_features:
            raise ValueError("No input features extracted from provided G-code.")
        logger.debug(f"Input features: {input_features}")

        output_features = {}
        for target_name in target_keys:
            try:
                model = models[target_name]
                features_for_target = target_feature_map.get(target_name, input_features_base)
                X_input = [input_features.get(f, 0) for f in features_for_target]
                pred = model.predict([X_input])
                output_features[target_name] = float(pred[0])
                logger.debug(f"Predicted {target_name}: {output_features[target_name]:.4f}")
            except Exception as e:
                output_features[target_name] = None
                logger.error(f"Prediction failed for {target_name}: {e}")

        gcode_sequence = parse_gcode_sequence(gcode_str)
        if not gcode_sequence:
            raise ValueError("No XYZ coordinates found in G-code.")

        overall_time = float(output_features.get("overall_time", 60.0))
        time_xy = float(output_features.get("time_xy", overall_time * 0.8))
        time_z = float(output_features.get("time_z", overall_time * 0.2))

        num_updates = max(1, int(round(overall_time / DT)))
        num_xy_updates = max(1, int(round(time_xy / DT)))
        num_z_updates = max(1, int(round(time_z / DT)))

        xy_sequence = [(axis, val) for axis, val in gcode_sequence if axis in ("X", "Y")]
        z_sequence = [(axis, val) for axis, val in gcode_sequence if axis == "Z"]

        xy_updates = interpolate_sequence(xy_sequence, num_xy_updates)
        z_updates = interpolate_sequence(z_sequence, num_z_updates)

        distances = []
        for i in range(1, num_updates):
            prev = {**xy_updates[min(i-1, num_xy_updates-1)], **z_updates[min(i-1, num_z_updates-1)]}
            curr = {**xy_updates[min(i, num_xy_updates-1)], **z_updates[min(i, num_z_updates-1)]}
            step_dist = np.sqrt(sum((curr.get(ax, 0) - prev.get(ax, 0))**2 for ax in ["X", "Y", "Z"]))
            distances.append((i, step_dist))
        distances_sorted = sorted(distances, key=lambda x: x[1], reverse=True)

        num_current_spikes = int(round(output_features.get("current_spike_count", 0)))
        num_power_spikes = int(round(output_features.get("power_spike_count", 0)))
        max_possible_spikes = len(distances_sorted)
        num_current_spikes = min(num_current_spikes, max_possible_spikes)
        num_power_spikes = min(num_power_spikes, max_possible_spikes)

        current_spike_indices = [idx for idx, _ in distances_sorted[:num_current_spikes]]
        power_spike_indices = [idx for idx, _ in distances_sorted[:num_power_spikes]]

        timestamps = [datetime.now(tz=timezone(timedelta(hours=1))) + timedelta(seconds=i * DT) for i in range(num_updates)]

        datastream = []
        last_values = {"X": None, "Y": None, "Z": None}

        feedrate_mean = float(output_features.get("feedrate_mean", 100.0))
        feedrate_std = float(output_features.get("feedrate_std", 1.0))
        current_mean_pred = float(output_features.get("current_mean", 0.5))
        power_mean_pred = float(output_features.get("power_mean", 20.0))
        current_std = float(output_features.get("current_std", 0.05))
        power_std = float(output_features.get("power_std", 1.0))

        accel_phases = int(round(output_features.get("accel_phases", 0)))
        decel_phases = int(round(output_features.get("decel_phases", 0)))

        # Feedrate
        feedrate_sequence = np.full(num_updates, feedrate_mean, dtype=float)
        remaining = max(1, num_updates - 1)
        total_phases = accel_phases + decel_phases
        if total_phases > 0 and remaining > 0:
            accel_indices, decel_indices = distribute_alternating_indices(remaining, accel_phases, decel_phases)
            step_mag = feedrate_std * np.sqrt(num_updates) / np.sqrt(max(1, total_phases))
            deltas = np.zeros(remaining, dtype=float)
            for idx in accel_indices:
                deltas[idx] = +step_mag
            for idx in decel_indices:
                deltas[idx] = -step_mag
            for i in range(1, num_updates):
                feedrate_sequence[i] = feedrate_sequence[i - 1] + deltas[i - 1]
            feedrate_offset = feedrate_mean - statistics.mean(feedrate_sequence)
            feedrate_sequence += feedrate_offset

        # Power:deterministic spike placement
        power_values = np.full(num_updates, power_mean_pred, dtype=float)
        if num_power_spikes > 0 and num_updates > 1:
            spike_mag = power_std / np.sqrt(num_updates)
            deltas = np.zeros(num_updates-1)
            spike_positions = np.linspace(0, num_updates-2, num_power_spikes, dtype=int)
            for pos in spike_positions:
                deltas[pos] = spike_mag
            for i in range(1, num_updates):
                power_values[i] = power_values[i-1] + deltas[i-1]
            power_values += (power_mean_pred - np.mean(power_values))
            power_values = np.clip(power_values, 0, None)

        # Current: deterministic spike placement
        current_values_arr = np.full(num_updates, current_mean_pred, dtype=float)
        if num_current_spikes > 0 and num_updates > 1:
            spike_mag = current_std / np.sqrt(num_updates)
            deltas = np.zeros(num_updates-1)
            spike_positions = np.linspace(0, num_updates-2, num_current_spikes, dtype=int)
            for pos in spike_positions:
                deltas[pos] = spike_mag
            for i in range(1, num_updates):
                current_values_arr[i] = current_values_arr[i-1] + deltas[i-1]
            current_values_arr += (current_mean_pred - np.mean(current_values_arr))
            current_values_arr = np.clip(current_values_arr, 0, None)

        # Build datastream entries 
        for i, ts in enumerate(timestamps):
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " +01:00"

            if xy_updates:
                xy_idx = min(int(round(i / max(num_updates - 1, 1) * (num_xy_updates - 1))), num_xy_updates - 1)
                for axis, val in xy_updates[xy_idx].items():
                    if last_values[axis] is None or val != last_values[axis]:
                        datastream.append({"name": axis, "value": val, "timestamp": ts_str})
                        last_values[axis] = val

            if z_updates:
                z_idx = min(int(round(i / max(num_updates - 1, 1) * (num_z_updates - 1))), num_z_updates - 1)
                val = z_updates[z_idx].get("Z")
                if val is not None and (last_values["Z"] is None or val != last_values["Z"]):
                    datastream.append({"name": "Z", "value": val, "timestamp": ts_str})
                    last_values["Z"] = val

            datastream.append({"name": "feedrate", "value": float(feedrate_sequence[i]), "timestamp": ts_str})
            datastream.append({"name": "current", "value": float(current_values_arr[i]), "timestamp": ts_str})
            datastream.append({"name": "power", "value": float(power_values[i]), "timestamp": ts_str})

        with open(OUTPUT_DATASTREAM_PATH, "w", encoding="utf-8") as fh:
            json.dump(datastream, fh, indent=2)

        logger.info(f"✅ Datastream generated with {len(datastream)} entries and saved to {OUTPUT_DATASTREAM_PATH}")
        return datastream

    except Exception as e:
        logger.exception("Error during datastream generation")
        raise

app = Flask(__name__)

@app.route("/generateDatastream", methods=["POST"])
def generate_datastream_endpoint():
    gcode_str = ""
    try:
        if request.content_type == 'application/x-www-form-urlencoded':
            gcode_str = request.form.get('gcode', '')
        elif request.is_json:
            gcode_str = request.json.get('gcode', '')
        logger.info(f"Received G-code input: {gcode_str[:100]}...")
        if not gcode_str:
            return jsonify({"status": "error", "message": "G-code is required."}), 400

        datastream = generate_datastream_from_gcode(gcode_str)
        return jsonify({"status": "success", "datastream": datastream})

    except Exception as e:
        logger.exception("Exception in /generateDatastream endpoint")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005)
