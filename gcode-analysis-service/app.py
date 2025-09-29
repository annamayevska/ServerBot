import math
import re
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- Helper functions ---
def distance(p1, p2):
    """Euclidean distance in XY plane."""
    return math.hypot(p2[0]-p1[0], p2[1]-p1[1])

def angle_between(v1, v2):
    """Interior angle in degrees between two vectors (0 = straight, 180 = U-turn)."""
    dot = v1[0]*v2[0] + v1[1]*v2[1]
    mag1 = math.hypot(v1[0], v1[1])
    mag2 = math.hypot(v2[0], v2[1])
    if mag1 == 0 or mag2 == 0:
        return 0
    cosang = max(min(dot/(mag1*mag2), 1), -1)
    angle = math.degrees(math.acos(cosang))
    # Use the smaller interior angle
    return min(angle, 180 - angle)

# --- Parse G-code ---
def parse_gcode(gcode):
    xmin = ymin = xmax = ymax = None
    points = []
    total_path = 0.0
    num_lifts = 0
    g1_count = 0
    g0_count = 0

    current_x = current_y = current_z = None
    last_point = None
    last_z = None
    last_g = None

    # Tokenize G-code
    commands = re.findall(r'([GMT]\d+|[XYZF]-?\d*\.?\d*)', gcode, re.IGNORECASE)

    for token in commands:
        t = token.upper()
        if t.startswith('G'):
            last_g = int(t[1:])
            if last_g == 1:
                g1_count += 1
            elif last_g == 0:
                g0_count += 1

        elif t.startswith('X'):
            current_x = float(t[1:])
        elif t.startswith('Y'):
            current_y = float(t[1:])
        elif t.startswith('Z'):
            z_new = float(t[1:])
            if last_z is None or z_new != last_z:
                num_lifts += 1
                last_z = z_new
            current_z = z_new
        elif t.startswith('F'):
            continue

        # Process XY moves
        if last_g in [0,1] and (current_x is not None or current_y is not None):
            if current_x is None or current_y is None:
                continue
            point = (current_x, current_y)
            
            if last_point is not None:
                total_path += distance(last_point, point)
            last_point = point
            points.append(point)

            if xmin is None:
                xmin = xmax = current_x
                ymin = ymax = current_y
            else:
                xmin = min(xmin, current_x)
                xmax = max(xmax, current_x)
                ymin = min(ymin, current_y)
                ymax = max(ymax, current_y)

            current_x = current_y = None

    return {
        "points": points,
        "xmin": xmin, "xmax": xmax,
        "ymin": ymin, "ymax": ymax,
        "num_lifts": num_lifts,
        "total_path": total_path,
        "g1_count": g1_count,
        "g0_count": g0_count
    }

# --- Compute features ---
def compute_features(parsed):
    points = parsed['points']
    num_points = len(points)
    if num_points < 2:
        return {}

    path_length = parsed['total_path']
    g1_total = parsed['g1_count']
    g0_total = parsed['g0_count']
    segment_count = g1_total + g0_total
    g1_prop = g1_total / segment_count if segment_count > 0 else 0
    g0_prop = g0_total / segment_count if segment_count > 0 else 0
    avg_seg_length = path_length / segment_count if segment_count > 0 else 0

    # --- Direction changes and sharp turns only ---
    dir_change_sum = 0.0
    sharp_turns = 0

    for i in range(2, num_points):
        v1 = (points[i-1][0]-points[i-2][0], points[i-1][1]-points[i-2][1])
        v2 = (points[i][0]-points[i-1][0], points[i][1]-points[i-1][1])
        ang = angle_between(v1, v2)
        dir_change_sum += ang
        if ang > 30:
            sharp_turns += 1

    # --- Bounding box area ---
    xmin, xmax = parsed['xmin'], parsed['xmax']
    ymin, ymax = parsed['ymin'], parsed['ymax']
    bbox_area = (xmax - xmin)*(ymax - ymin) if xmin is not None else 0

    return {
        "status": "success",
        "path_length": path_length,
        "segment_count": segment_count,
        "avg_segment_length": avg_seg_length,
        "direction_change_sum_deg": dir_change_sum,
        "sharp_turns": sharp_turns,
        "bbox_area": bbox_area,
        "num_lifts": parsed['num_lifts'],
        "g1_proportion": g1_prop,
        "g0_proportion": g0_prop
    }

# --- Flask endpoint ---
@app.route('/', methods=['POST'])
def analyze_gcode_endpoint():
    gcode = None
    if request.content_type == 'application/x-www-form-urlencoded':
        gcode = request.form.get('gcode')
    elif request.content_type == 'application/json':
        gcode = request.json.get('gcode')

    if not gcode:
        return jsonify({"status": "error", "message": "G-code is required"}), 400

    parsed = parse_gcode(gcode)
    features = compute_features(parsed)
    return jsonify(features), 200

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=5005)
