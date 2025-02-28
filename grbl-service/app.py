from flask import Flask, jsonify, request
import tempfile
import subprocess
import os
import json
import time
import requests
import threading

app = Flask(__name__)

# Port Configuration
PORT = "COM5"
BAUD_RATE = "115200"
execution_state = {"running": False}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CALLBACKS_FILE_PATH = os.path.join(BASE_DIR, "drawing_callbacks.json")

# ------------------ Functions ------------------

#Preprocess the G-code text to ensure each command starts on a new line.
def preprocess_gcode(gcode_text):

    commands = []
    current_command = []

    for line in gcode_text.splitlines():
        line = line.strip()
        if not line:
            continue
        i = 0
        while i < len(line):
            if line[i].upper() == 'G' and (i == 0 or line[i - 1].isspace() or line[i - 1] in [';', '(']):
                if current_command:
                    commands.append("".join(current_command).strip())
                    current_command = []
            current_command.append(line[i])
            i += 1

        if current_command:
            commands.append("".join(current_command).strip())
            current_command = []

    processed_gcode = "\n".join(commands)
    return processed_gcode


def send_gcode_file_to_grbl(gcode_file):
    try:
        command = [
            "java", "-cp", "UniversalGcodeSender.jar",
            "com.willwinder.ugs.cli.TerminalClient",
            "--controller", "GRBL",
            "--port", PORT,
            "--baud", BAUD_RATE,
            "--print-stream",
            "--file", gcode_file
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            return {"status": "success", "message": f"G-code executed successfully from {gcode_file}."}
        else:
            return {"status": "error", "message": result.stderr}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def execute_gcode(gcode_text):

    try:
        processed_gcode = preprocess_gcode(gcode_text)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".gcode", dir=".") as temp_file:
            temp_file.write(processed_gcode.encode('utf-8'))
            temp_file_name = temp_file.name

        response = send_gcode_file_to_grbl(temp_file_name)

        return response

    except Exception as e:
        return {"status": "error", "message": str(e)}

    finally:
        try:
            if os.path.exists(temp_file_name):
                os.remove(temp_file_name)
        except Exception:
            return {"status": "error", "message": str(e)}

        execution_state["running"] = False


def get_callback_url():
    if os.path.exists(CALLBACKS_FILE_PATH):
            with open(CALLBACKS_FILE_PATH, 'r') as callbacks_file:
                callback_data = json.load(callbacks_file)
                callback_ids = [callback["callback_id"] for callback in callback_data]

            if callback_ids:
                callback_url = callback_ids[0] 
                return callback_url


#send a put request to continue with process after executing
def send_callback(callback_url):
    """Send a callback to the specified URL."""
    try:
        response = requests.put(callback_url, json={"status": "done"})

        if response.status_code == 200:
            with open(CALLBACKS_FILE_PATH, 'r') as f:
                callbacks = json.load(f)
            callbacks = [cb for cb in callbacks if cb["callback_id"] != callback_url]
            with open(CALLBACKS_FILE_PATH, 'w') as f:
                json.dump(callbacks, f, indent=4)

    except Exception as e:
        return {"status": "error", "message": str(e)}

#launch gcode execution and send callback afterwards 
def monitor_execution_and_callback(gcode_text):
    try:
        execute_gcode(gcode_text)
        while execution_state["running"]:
            time.sleep(1)

        callback_url = get_callback_url()
        if callback_url:
            send_callback(callback_url)

        execution_state["running"] = False
    except Exception as e:
        return {"status": "error", "message": str(e)}



# ------------------ Endpoints ------------------

@app.route('/executeGcode', methods=['POST'])
def execute_gcode_endpoint():
    global execution_state
    if execution_state["running"]:
        return jsonify({"status": "error", "message": "Another G-code execution is already in progress."}), 400
    execution_state["running"] = True

    cb = request.headers.get('Cpee-Callback')
    if not cb:
        execution_state["running"] = False
        return jsonify({"error": "Cpee-Callback header is missing"}), 400

    if os.path.exists(CALLBACKS_FILE_PATH):
            try:
                with open(CALLBACKS_FILE_PATH, 'r') as f:
                    callbacks = json.load(f)
            except json.JSONDecodeError:
                callbacks = [] 
    else:
        callbacks = []

    callbacks.append({"callback_id": cb})
    with open(CALLBACKS_FILE_PATH, 'w') as f:
        json.dump(callbacks, f, indent=4)

    try:
        # Get gcode_text from request and execute it 
        if request.content_type == 'application/x-www-form-urlencoded':
            gcode_text = request.form.get('gcode')
        elif request.content_type == 'application/json':
            data = request.get_json()
            gcode_text = data.get('gcode')
        else:
            execution_state["running"] = False
            return jsonify({"error": "Unsupported Content-Type."}), 400

        threading.Thread(target=monitor_execution_and_callback, args=(gcode_text,), daemon=True).start()

        response_headers = {'CPEE-CALLBACK': 'true'}
        return '', 200, response_headers

    except Exception as e:
        execution_state["running"] = False
        return jsonify({"error": "An error occurred"}), 500


@app.route('/home', methods=['POST'])
def home():
    global execution_state
    if execution_state["running"]:
        return jsonify({"status": "error", "message": "Another operation is in progress."}), 400
    execution_state["running"] = True
    try:
        command = [
            "java", "-cp", "UniversalGcodeSender.jar",
            "com.willwinder.ugs.cli.TerminalClient",
            "--controller", "GRBL",
            "--port", PORT,
            "--baud", BAUD_RATE,
            "--home"
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            return jsonify({"status": "success", "output": result.stdout})
        else:
            return jsonify({"status": "error", "output": result.stderr}), 500

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        execution_state["running"] = False


@app.route('/robot', methods=['POST'])
def robot():
    global execution_state
    if execution_state["running"]:
        return jsonify({"status": "error", "message": "Another operation is in progress."}), 400
    execution_state["running"] = True
    try:
        response = send_gcode_file_to_grbl("robot-position.gcode")
        return jsonify(response)
    finally:
        execution_state["running"] = False


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5004)
