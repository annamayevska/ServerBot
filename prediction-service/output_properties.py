import datetime
import yaml
import math
import statistics

def parse_timestamp(ts):
   
    if isinstance(ts, datetime.datetime):
        return ts
    if isinstance(ts, str):
        ts_clean = str(ts).strip().replace("\ufeff", "").rstrip()
        try:
            return datetime.datetime.fromisoformat(ts_clean)
        except ValueError:
            ts_clean_no_tz = ts_clean.split("+")[0].strip()
            return datetime.datetime.fromisoformat(ts_clean_no_tz)
    return None

def calculate_overall(file_path):
 
    first_ts = None
    last_ts = None

    time_xy = 0.0
    time_z = 0.0

    distance_xy = 0.0
    distance_z = 0.0

    last_axes_timestamped = None
    last_axes = set()

    last_x = None
    last_y = None
    last_z = None

    feedrates = []
    feedrate_timestamps = []
    currents = []
    powers = []

    print(f"\n[DEBUG] Loading YAML file for overall time and motion efficiency: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
            if not docs:
                print("[DEBUG] YAML file empty.")
                return {}

            for doc in docs:
                if not isinstance(doc, dict):
                    continue
                event = doc.get("event")
                if not isinstance(event, dict):
                    continue
                datastream = event.get("stream:datastream", [])
                if not datastream:
                    continue

                for sp in datastream:
                    point = sp.get("stream:point")
                    if not isinstance(point, dict):
                        continue

                    ts = parse_timestamp(point.get("stream:timestamp"))
                    if not ts:
                        continue

                    axis_id = point.get("stream:id", "").lower()
                    value_str = point.get("stream:value")
                    try:
                        value = float(value_str) if value_str is not None else None
                    except ValueError:
                        value = None

                    # feed rate handling
                    if axis_id == "feedrate" and value is not None:
                        feedrates.append(value)
                        feedrate_timestamps.append(ts)
                        continue

                    # current power handling
                    if axis_id == "current" and value is not None:
                        currents.append(value)
                        continue
                    if axis_id == "power" and value is not None:
                        powers.append(value)
                        continue

                    # axis handling
                    axes_changed = set()
                    x = y = z = None
                    if axis_id == 'x':
                        axes_changed.add('X')
                        x = value
                    elif axis_id == 'y':
                        axes_changed.add('Y')
                        y = value
                    elif axis_id == 'z':
                        axes_changed.add('Z')
                        z = value

                    if not axes_changed:
                        continue

                    if first_ts is None:
                        first_ts = ts
                    last_ts = ts

                    if last_axes_timestamped is not None:
                        delta = (ts - last_axes_timestamped).total_seconds()
                        if 'Z' in last_axes:
                            time_z += delta
                        if 'X' in last_axes or 'Y' in last_axes:
                            time_xy += delta

                    if 'X' in axes_changed or 'Y' in axes_changed:
                        dx = (x - last_x) if x is not None and last_x is not None else 0
                        dy = (y - last_y) if y is not None and last_y is not None else 0
                        distance_xy += math.sqrt(dx * dx + dy * dy)

                    if 'Z' in axes_changed and z is not None and last_z is not None:
                        dz = z - last_z
                        distance_z += abs(dz)

                    if x is not None:
                        last_x = x
                    if y is not None:
                        last_y = y
                    if z is not None:
                        last_z = z

                    last_axes_timestamped = ts
                    last_axes = axes_changed

    except Exception as e:
        print(f"[ERROR] Failed to load or parse YAML: {e}")
        return {}

    if not first_ts or not last_ts:
        return {}

    total_duration = (last_ts - first_ts).total_seconds()
    efficiency_xy = distance_xy / time_xy if time_xy > 0 else 0
    efficiency_z = distance_z / time_z if time_z > 0 else 0

    # feed rate features
    feedrate_mean = feedrate_std = None
    accel_phases = 0
    decel_phases = 0

    if feedrates:
        feedrate_mean = statistics.mean(feedrates)
        feedrate_std = statistics.pstdev(feedrates) if len(feedrates) > 1 else 0

        if len(feedrates) > 1:
            deltas = [feedrates[i] - feedrates[i - 1] for i in range(1, len(feedrates))]
            for d in deltas:
                if d > 0:
                    accel_phases += 1
                elif d < 0:
                    decel_phases += 1

    # current features 
    current_mean = current_std = None
    current_spike_count = None

    if currents:
        current_mean = statistics.mean(currents)
        current_std = statistics.pstdev(currents) if len(currents) > 1 else 0

        if len(currents) > 1:
            deltas = [abs(currents[i] - currents[i - 1]) for i in range(1, len(currents))]
            if deltas:
                med_delta = statistics.median(deltas)
                mad_delta = statistics.median([abs(d - med_delta) for d in deltas])
                k_current = 3
                current_spike_count = sum(
                    1 for d in deltas if d > med_delta + k_current * mad_delta
                )

    # power features
    power_mean = power_std = None
    power_spike_count = None

    if powers:
        power_mean = statistics.mean(powers)
        power_std = statistics.pstdev(powers) if len(powers) > 1 else 0

        if len(powers) > 1:
            deltas = [abs(powers[i] - powers[i - 1]) for i in range(1, len(powers))]
            if deltas:
                med_delta = statistics.median(deltas)
                mad_delta = statistics.median([abs(d - med_delta) for d in deltas])
                k_power = 1
                power_spike_count = sum(
                    1 for d in deltas if d > med_delta + k_power * mad_delta
                )

    return {
        "overall_time": total_duration,
        "time_xy": time_xy,
        "time_z": time_z,
        "efficiency_xy": efficiency_xy,
        "efficiency_z": efficiency_z,
        "feedrate_mean": feedrate_mean,
        "feedrate_std": feedrate_std,
        "accel_phases": accel_phases,
        "decel_phases": decel_phases,
        "current_mean": current_mean,
        "current_std": current_std,
        "current_spike_count": current_spike_count,
        "power_mean": power_mean,
        "power_std": power_std,
        "power_spike_count": power_spike_count
    }
