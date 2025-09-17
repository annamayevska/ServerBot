import math
import re
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- Distance and angle helpers ---
def distance(p1, p2):
    return math.hypot(p2[0]-p1[0], p2[1]-p1[1])

def angle_between(v1, v2):
    dot = v1[0]*v2[0] + v1[1]*v2[1]
    mag1 = math.hypot(v1[0], v1[1])
    mag2 = math.hypot(v2[0], v2[1])
    if mag1 == 0 or mag2 == 0:
        return 0
    cosang = max(min(dot/(mag1*mag2), 1), -1)
    return math.degrees(math.acos(cosang))

# --- Parse G-code in sequence ---
def parse_gcode_full(gcode):
    """
    Parse full G-code, track XY points, bounding box, path length, and count all Z movements as lifts.
    """
    xmin = ymin = xmax = ymax = None
    points = []

    current_x = current_y = None
    current_z = None
    last_point = None
    total_path = 0.0
    num_lifts = 0
    last_z = None

    tokens = re.findall(r'([XYZ])(-?\d+\.?\d*)', gcode, re.IGNORECASE)
    for axis, val in tokens:
        val = float(val)

        if axis.upper() == 'X':
            current_x = val
        elif axis.upper() == 'Y':
            current_y = val
        elif axis.upper() == 'Z':
            current_z = val
            if last_z is None or current_z != last_z:
                num_lifts += 1
                last_z = current_z

        # Only process a "point" when we have X and Y
        if current_x is not None and current_y is not None:
            point = (current_x, current_y)
            points.append(point)

            if xmin is None:
                xmin = xmax = current_x
                ymin = ymax = current_y
            else:
                xmin = min(xmin, current_x)
                xmax = max(xmax, current_x)
                ymin = min(ymin, current_y)
                ymax = max(ymax, current_y)

            # Update XY path length
            if last_point:
                total_path += distance(last_point, point)
            last_point = point

            current_x = current_y = None

    return {
        "points": points,
        "xmin": xmin, "xmax": xmax,
        "ymin": ymin, "ymax": ymax,
        "num_lifts": num_lifts,
        "total_path": total_path
    }

# --- Main analysis ---
def analyze_gcode(gcode, overlap_tol=0.2):
    data = parse_gcode_full(gcode)
    points = data['points']
    num_points = len(points)
    if not points:
        return {"num_points": 0}

    path_length = data['total_path']

    dir_change_sum = 0.0
    sharp_turns = 0
    for i in range(2, num_points):
        v1 = (points[i-1][0]-points[i-2][0], points[i-1][1]-points[i-2][1])
        v2 = (points[i][0]-points[i-1][0], points[i][1]-points[i-1][1])
        ang = angle_between(v1, v2)
        dir_change_sum += ang
        if ang > 30:
            sharp_turns += 1

    # Overlap detection (approximate)
    overlap_length = 0.0
    for i in range(1, num_points):
        seg_len = distance(points[i-1], points[i])
        for j in range(max(0, i-20), i-1):
            if distance(points[i], points[j]) < overlap_tol and distance(points[i-1], points[j]) < overlap_tol:
                overlap_length += seg_len
                break
    overlap_ratio = overlap_length / path_length if path_length > 0 else 0

    return {
        "num_points": num_points,
        "bounding_box_xmin": data['xmin'],
        "bounding_box_xmax": data['xmax'],
        "bounding_box_ymin": data['ymin'],
        "bounding_box_ymax": data['ymax'],
        "path_length": path_length,
        "direction_change_sum_deg": dir_change_sum,
        "sharp_turns": sharp_turns,
        "overlap_ratio": overlap_ratio,
        "num_lifts": data['num_lifts']
    }

# --- Flask endpoint ---
@app.route('/analyzeGcode', methods=['POST'])
def analyze_gcode_endpoint():
    gcode = None
    if request.content_type == 'application/x-www-form-urlencoded':
        gcode = request.form.get('gcode')

    if not gcode:
        return jsonify({"status": "error", "message": "G-code is required"}), 400

    result = analyze_gcode(gcode)

    response_data = {
        "status": "success",
        **result,
    }
    return jsonify(response_data), 200

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=5005)
