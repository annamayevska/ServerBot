import os
import subprocess
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config.json"))
with open(CONFIG_PATH, 'r') as config_file:
    config = json.load(config_file)

FONT_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "text2gcode", "fontSizes.json")
with open(FONT_DATA_PATH, 'r') as font_data_file:
    font_data = json.load(font_data_file)

@app.route('/text2gcode', methods=['POST'])
def text_to_gcode():

    if request.content_type == 'application/x-www-form-urlencoded':
        text = request.form.get('text')

    if not text:
        return jsonify({"status": "error", "message": "Text is required."}), 400

    # Calculate font size based on text length
    text_length = len(text)
    if text_length <= 5:
        fontSize = 16
    elif text_length == 6:
        fontSize = 12
    elif text_length == 7:
        fontSize = 11
    elif text_length == 8:
        fontSize = 10
    elif text_length == 9:
        fontSize = 9
    else:
        fontSize = 8

    if str(fontSize) in font_data:
        font_settings = font_data[str(fontSize)]

        lineScale = font_settings["lineScale"]
    else:
        return jsonify({"status": "error", "message": f"Font size {fontSize} not found"}), 400

    def generate_gcode(line_text, offset_x, offset_y, scale, angle=0):
        text2gcode_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "text2gcode")
        command = ["java", "-cp", os.path.dirname(os.path.abspath(__file__)), "text2gcode.Romans", line_text, str(offset_x), str(offset_y), str(scale), str(angle)]
        
        result = subprocess.run(command, capture_output=True, text=True, cwd=text2gcode_folder)
        
        if result.returncode == 0:
            return result.stdout
        else:
            raise Exception(f"Error generating G-code: {result.stderr}")

    def get_maximum_x_for_line(lineText):
        gcode = generate_gcode(lineText, 0, 0, lineScale)
        max_x = float('-inf')
        for line in gcode.splitlines():
            if "X" in line:
                parts = line.split()
                for part in parts:
                    if part.startswith("X"):
                        x = float(part[1:])
                        max_x = max(max_x, x)
        return max_x

    line = text  
    try:
        maximumX = get_maximum_x_for_line(line)
        mid_x = (config['lower_left_corner_x'] + config['upper_right_corner_x']) / 2
        offsetX = mid_x - (maximumX / 2)  
        offsetY = config['lower_left_corner_y'] + 5 
        gcode_for_line = generate_gcode(line, offsetX, offsetY, lineScale)
        gcode_output = gcode_for_line + "\n"
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to generate G-code for the text: {e}"}), 500

    # Post-process the G-code
    processed_gcode = []
    for line in gcode_output.splitlines():
        if "G21" in line:
            continue
        line = line.replace('Z-72.685', f'Z{config["z_drawing_height"]}')
        line = line.replace('Z-70', f'Z{config["z_safe_height"]}')
        if "G1" in line:
            line += f" F{config['feedrate']}"
        processed_gcode.append(line)

    processed_gcode.insert(0, "G90")
    processed_gcode.insert(1, "G21")
    processed_gcode.append("G0 Z-30")
    processed_gcode.append("M2")

    return jsonify({"status": "success", "gcode": " ".join(processed_gcode)}), 200


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5002)
