import math
import re
import json
import yaml
import statistics
import numpy as np
from sklearn.cluster import DBSCAN

# -------------------- Helper functions --------------------
def distance_2d(p1, p2):
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    return math.hypot(dx, dy)

def distance_1d(p1, p2):
    return abs(p2 - p1)

def inner_turning_angle(p_prev, p_curr, p_next):
    if p_prev is None or p_curr is None or p_next is None:
        return 0
    v1 = (p_prev[0] - p_curr[0], p_prev[1] - p_curr[1])
    v2 = (p_next[0] - p_curr[0], p_next[1] - p_curr[1])
    mag1 = math.hypot(*v1)
    mag2 = math.hypot(*v2)
    if mag1 == 0 or mag2 == 0:
        return 0
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    cosang = max(min(dot / (mag1 * mag2), 1), -1)
    angle = math.degrees(math.acos(cosang))
    return max(angle, 1e-6)

# -------------------- Helper: load G-code from YAML --------------------
def load_gcode_from_yaml(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            docs = yaml.safe_load_all(f)
            for doc in docs:
                if not isinstance(doc, dict):
                    continue
                event = doc.get("event")
                if not event or event.get("concept:name") != "Create gcode":
                    continue
                for entry in event.get("data", []):
                    if entry.get("name") != "result":
                        continue
                    try:
                        gjson = json.loads(entry.get("data", "{}"))
                    except Exception:
                        continue
                    gcode_str = gjson.get("gcode", "")
                    if gcode_str:
                        return gcode_str
    except Exception as e:
        print(f"[ERROR] loading YAML {file_path}: {e}")
    return ""

# -------------------- Engineered features --------------------
def xy_path_density(points, cell_size=1.0):
    xy_points = np.array([[p[0], p[1]] for p in points if p[0] is not None and p[1] is not None])
    if len(xy_points) == 0:
        return 0
    xmin, ymin = xy_points.min(axis=0)
    x_bins = np.floor((xy_points[:, 0] - xmin) / cell_size).astype(int)
    y_bins = np.floor((xy_points[:, 1] - ymin) / cell_size).astype(int)
    counts = {}
    for xb, yb in zip(x_bins, y_bins):
        counts[(xb, yb)] = counts.get((xb, yb), 0) + 1
    return np.mean(list(counts.values()))

# -------------------- Main computation --------------------
def compute_input_properties(
    gcode_str=None,
    file_path=None,
    sharp_turn_threshold=45,
    min_xy_dist=0.4,
    const_time_step=0.5
):
    if gcode_str is not None:
        print("[INFO] Using provided G-code string directly.")
    elif file_path is not None:
        print(f"[INFO] Loading G-code from file: {file_path}")
        gcode_str = load_gcode_from_yaml(file_path)
    else:
        raise ValueError("Cannot process: both gcode_str and file_path are None.")

    total_xy = total_z = 0.0
    move_count_xy = move_count_z = 0
    segment_lengths_xy, segment_lengths_z, turning_angles = [], [], []
    sharp_turns = 0
    xmin = ymin = zmin = xmax = ymax = zmax = None

    last_point = [None, None, None]
    points = []
    velocities = []
    planar_switch_count = 0
    last_plane = None

    commands = re.split(r'\s*(?=G\d+|M\d+)', gcode_str.upper())

    for cmd in commands:
        x_val = y_val = z_val = None
        for token in re.findall(r'[XYZ]-?\d*\.?\d*', cmd):
            if token.startswith('X'):
                x_val = float(token[1:])
            elif token.startswith('Y'):
                y_val = float(token[1:])
            elif token.startswith('Z'):
                z_val = float(token[1:])

        if x_val is None and y_val is None and z_val is None:
            continue

        new_point = [
            x_val if x_val is not None else last_point[0],
            y_val if y_val is not None else last_point[1],
            z_val if z_val is not None else last_point[2]
        ]

        for i, val in enumerate(new_point):
            if val is not None:
                if i == 0:
                    xmin = val if xmin is None else min(xmin, val)
                    xmax = val if xmax is None else max(xmax, val)
                elif i == 1:
                    ymin = val if ymin is None else min(ymin, val)
                    ymax = val if ymax is None else max(ymax, val)
                else:
                    zmin = val if zmin is None else min(zmin, val)
                    zmax = val if zmax is None else max(zmax, val)

        dx = (new_point[0] - last_point[0]) if last_point[0] is not None else 0
        dy = (new_point[1] - last_point[1]) if last_point[1] is not None else 0
        dz = (new_point[2] - last_point[2]) if last_point[2] is not None else 0

        xy_moved = (last_point[0] is None or last_point[1] is None) or (dx != 0 or dy != 0)
        if xy_moved:
            dist_xy = math.hypot(dx, dy)
            total_xy += dist_xy
            move_count_xy += 1
            segment_lengths_xy.append(dist_xy)
            velocities.append(dist_xy / const_time_step if const_time_step > 0 else 0)

        z_moved = (last_point[2] is None and z_val is not None) or dz != 0
        if z_moved:
            dist_z = abs(dz)
            total_z += dist_z
            move_count_z += 1
            segment_lengths_z.append(dist_z)

        if xy_moved and z_moved:
            current_plane = 'XYZ'
        elif xy_moved:
            current_plane = 'XY'
        elif z_moved:
            current_plane = 'Z'
        else:
            current_plane = None

        if last_plane is not None and current_plane is not None and current_plane != last_plane:
            planar_switch_count += 1
        last_plane = current_plane

        if None not in new_point:
            points.append(new_point)

        if len(points) >= 3:
            angle = inner_turning_angle(points[-3], points[-2], points[-1])
            if (
                math.hypot(points[-2][0] - points[-3][0], points[-2][1] - points[-3][1]) >= min_xy_dist
                and math.hypot(points[-1][0] - points[-2][0], points[-1][1] - points[-2][1]) >= min_xy_dist
            ):
                turning_angles.append(angle)
                if angle <= sharp_turn_threshold:
                    sharp_turns += 1

        last_point = new_point

    mean_segment_xy = sum(segment_lengths_xy) / len(segment_lengths_xy) if segment_lengths_xy else 0
    mean_segment_z = sum(segment_lengths_z) / len(segment_lengths_z) if segment_lengths_z else 0
    xy_z_path_ratio = total_xy / total_z if total_z > 0 else float("inf")

    bbox_x = (xmax - xmin) if xmax is not None else 0
    bbox_y = (ymax - ymin) if ymax is not None else 0
    bbox_z = (zmax - zmin) if zmax is not None else 0

    curvature_accel = sum(abs(180 - a) / 180 for a in turning_angles) / len(turning_angles) if turning_angles else 0
    mean_len = mean_segment_xy
    length_accel = (
        math.sqrt(sum((l - mean_len) ** 2 for l in segment_lengths_xy) / len(segment_lengths_xy)) / mean_len
        if len(segment_lengths_xy) > 1 and mean_len > 0
        else 0
    )
    curvature_change = (
        sum(abs(turning_angles[i] - turning_angles[i - 1]) / 180 for i in range(1, len(turning_angles)))
        / (len(turning_angles) - 1)
        if len(turning_angles) > 1
        else 0
    )
    avg_accel_proxy = 0.4 * curvature_accel + 0.4 * length_accel + 0.2 * curvature_change
    mean_turning_angle = sum(turning_angles) / len(turning_angles) if turning_angles else 0

    diag_count = 0
    long_move_threshold = 5 * mean_segment_xy if mean_segment_xy > 0 else 0
    for i in range(1, len(points)):
        dx = points[i][0] - points[i - 1][0]
        dy = points[i][1] - points[i - 1][1]
        dist = math.hypot(dx, dy)
        if abs(dx) > 0 and abs(dy) > 0 and dist > long_move_threshold:
            diag_count += 1
    diag_intensity = diag_count / move_count_xy if move_count_xy > 0 else 0

    vel_var = statistics.variance(velocities) if len(velocities) > 1 else 0
    sorted_vel = sorted(velocities)
    if sorted_vel:
        mid = len(sorted_vel) // 2
        slow_mean = sum(sorted_vel[:mid]) / max(mid, 1)
        fast_mean = sum(sorted_vel[mid:]) / max(len(sorted_vel) - mid, 1)
        mean_vel_ratio = fast_mean / slow_mean if slow_mean > 0 else 0
    else:
        mean_vel_ratio = 0

    accels = [velocities[i] - velocities[i - 1] for i in range(1, len(velocities))] if len(velocities) > 1 else []
    high_freq_accel_events = sum(
        1 for i in range(1, len(accels)) if accels[i] * accels[i - 1] < 0
    ) if len(accels) > 1 else 0

    xy_density = xy_path_density(points)

    short_moves = [d for d in segment_lengths_xy if d < mean_segment_xy]
    long_moves = [d for d in segment_lengths_xy if d >= mean_segment_xy]
    dense_to_long_ratio = (sum(short_moves) / max(sum(long_moves), 1)) if long_moves else 0

    return {
        "total_path_length_xy": total_xy,
        "total_path_length_z": total_z,
        "move_count_xy": move_count_xy,
        "move_count_z": move_count_z,
        "mean_path_segment_length_xy": mean_segment_xy,
        "mean_path_segment_length_z": mean_segment_z,
        "xy_z_path_ratio": xy_z_path_ratio,
        "bbox_x": bbox_x,
        "bbox_y": bbox_y,
        "bbox_z": bbox_z,
        "average_acceleration_proxy": avg_accel_proxy,
        "mean_inner_turning_angle_deg": mean_turning_angle,
        "sharp_turn_count": sharp_turns,
        "diag_intensity": diag_intensity,
        "vel_var": vel_var,
        "mean_vel_ratio": mean_vel_ratio,
        "planar_switch_count": planar_switch_count,
        "high_frequency_accel_events": high_freq_accel_events,
        "xy_path_density": xy_density,
        "dense_to_long_move_ratio": dense_to_long_ratio
    }
