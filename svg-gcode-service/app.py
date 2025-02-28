import os
import json
import subprocess
import re
import xml.etree.ElementTree as ET
from flask import Flask, request, jsonify

app = Flask(__name__)

# Path configuration for svg2gcode executable
SVG2GCODE_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), 'svg2gcode'))
SVG2GCODE_EXECUTABLE = os.path.abspath(os.path.join(SVG2GCODE_FOLDER, "target", "release", "svg2gcode"))
CONFIG_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config.json'))

config = {}
try:
    with open(CONFIG_FILE_PATH, 'r') as config_file:
        config = json.load(config_file)
    required_keys = [
        'lower_left_corner_x', 'lower_left_corner_y',
        'upper_right_corner_x', 'upper_right_corner_y',
        'feedrate', 'z_drawing_height', 'z_safe_height'
    ]
    if not all(key in config for key in required_keys):
        raise KeyError("Missing required keys in config.json.")
except Exception as e:
    config = {}


@app.route('/svg2gcode', methods=['POST'])
def svg_to_gcode():
    svg_code = None

    if request.content_type == 'application/x-www-form-urlencoded':
        svg_code = request.form.get('logo')  
    elif request.content_type == 'application/json':
        data = request.get_json()
        svg_code = data.get('logo')  
    
    if not svg_code:
        return jsonify({"status": "error", "message": "SVG code is required."}), 400

    if not config:
        return jsonify({"status": "error", "message": "Configuration file is missing or invalid."}), 500

    try:
        # Parse SVG to get the width and height attributes
        tree = ET.ElementTree(ET.fromstring(svg_code))
        root = tree.getroot()
        def extract_dimension(value):
            return float(re.sub(r'[a-zA-Z]', '', value))  

        svg_width = extract_dimension(root.attrib['width'])
        svg_height = extract_dimension(root.attrib['height'])
 
        # Set the images to the specific size to fit within dimensions
        target_size = 200
        if svg_width > svg_height:
            manual_scaling_factor = target_size / svg_width
        else:
            manual_scaling_factor = target_size / svg_height

        resized_width = svg_width * manual_scaling_factor
        resized_height = svg_height * manual_scaling_factor

        # Apply scaling factor for proper positioning and offsets
        scaling_factor = 16 / 64  
        scaled_width = resized_width * scaling_factor
        scaled_height = resized_height * scaling_factor
        
        coaster_height = config['upper_right_corner_y'] - config['lower_left_corner_y']
        available_svg_height = coaster_height * 3 / 4  

        # Calculate the X origin for centering SVG horizontally and vertically 
        coaster_width = config['upper_right_corner_x'] - config['lower_left_corner_x']
        offset_x = (coaster_width - scaled_width) / 2
        origin_x = config['lower_left_corner_x'] + offset_x
        offset_y = (available_svg_height - scaled_height) / 2
        origin_y = config['lower_left_corner_y'] + (coaster_height * 1 / 4) + offset_y  

        origin = f"{origin_x},{origin_y}"  
        dimensions = f"{scaled_width}mm,{scaled_height}mm"


        command = [
            SVG2GCODE_EXECUTABLE,
            f"--origin={origin}",
            f"--dimensions={dimensions}",
            f"--feedrate={config['feedrate']}",
            "--on", f"G0 Z{config['z_drawing_height']} ",
            "--off", f"G0 Z{config['z_safe_height']} ",
            "--end", "G0 Z-30 \n M2"
        ]

        result = subprocess.run(
            command,
            input=svg_code,  
            capture_output=True,
            text=True,
            cwd=SVG2GCODE_FOLDER
        )

        if result.returncode == 0:
            gcode_content = result.stdout.strip()
            valid_gcode = re.sub(r'[^G0-9.\-XYZF;M2]', ' ', gcode_content)
            valid_gcode = re.sub(r'\s+', ' ', valid_gcode)
            return jsonify({"status": "success", "gcode": valid_gcode.strip()}), 200
        else:
            return jsonify({"status": "error", "message": result.stderr.strip()}), 500
        
    except FileNotFoundError:
        return jsonify({"status": "error", "message": "svg2gcode executable not found."}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5003)
