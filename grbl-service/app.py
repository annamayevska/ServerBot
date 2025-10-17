from flask import Flask, jsonify, request
import os
import time
import threading
import serial
import requests
import re
import queue
import paho.mqtt.client as mqtt
from functools import wraps

app = Flask(__name__)

#PORT = "COM5"
PORT =  "/dev/ttyUSB_lab"
BAUD_RATE = 115200
POLL_INTERVAL = 0.5

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CALLBACKS_FILE_PATH = os.path.join(BASE_DIR, "drawing_callbacks.json")

MQTT_BROKER = "lab.bpm.in.tum.de"
MQTT_PORT = 1883
MQTT_TOPIC_BASE = "myproject/grbl"

TASMOTA_URL = "http://131.159.6.241:8080/cm?cmnd=STATUS%2010"
TASMOTA_TOPIC = "/lab-power/socket-3"

execution_state = {"running": False}
execution_lock = threading.Lock()  # Added lock for safer concurrent access


# --- Helper Decorator to avoid code repetition in endpoints ---
def require_idle(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        with execution_lock:
            if execution_state["running"]:
                return jsonify({"status": "error", "message": "Busy"}), 400
            execution_state["running"] = True
        try:
            return f(*args, **kwargs)
        finally:
            with execution_lock:
                execution_state["running"] = False
    return wrapper


class SerialCommManager:
    def __init__(self, port, baudrate, poll_interval=POLL_INTERVAL):
        self.port = port
        self.baudrate = baudrate
        self.poll_interval = poll_interval
        self.ser = None
        self.lock = threading.Lock()

        self.status_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.send_error = None
        self.program_end_received = threading.Event()

        self.reader_thread = None
        self.reader_stop_event = threading.Event()
        self.poll_thread = None
        self.poll_stop_event = threading.Event()

        self.mqtt_client = mqtt.Client()
        self.last_status_values = {}

        self.tasmota_thread = None
        self.tasmota_stop_event = threading.Event()
        self.tasmota_last_state = None

        self.open()
        self._start_mqtt()
        self.start_reader()

    # --- MQTT ---
    def _start_mqtt(self):
        try:
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.mqtt_client.loop_start()
            print("[MQTT] Connected to broker.")
        except Exception as e:
            print(f"[MQTT] Connection failed: {e}")

    def _publish_if_changed(self, status_data):
        for key, value in status_data.items():
            if self.last_status_values.get(key) != value:
                topic = f"{MQTT_TOPIC_BASE}/{key}"
                self.mqtt_client.publish(topic, str(value))
                print(f"[MQTT] Published {key}: {value}")
        self.last_status_values.update(status_data)

    # --- SERIAL STATUS PARSING ---
    def _parse_status_line(self, line):
        if not line.startswith('<') or not line.endswith('>'):
            return {}
        content = line[1:-1]
        parts = content.split('|')
        status_data = {}
        for part in parts:
            if part in ['Idle', 'Run', 'Hold', 'Alarm']:
                status_data['status'] = part
            elif part.startswith('MPos:'):
                try:
                    x, y, z = map(float, part[5:].split(','))
                    status_data.update({'x': x, 'y': y, 'z': z})
                except:
                    continue
            elif part.startswith('FS:'):
                try:
                    feed, _ = map(float, part[3:].split(','))
                    status_data['feed'] = feed
                except:
                    continue
        return status_data

    # --- SERIAL PORT CONTROL ---
    def open(self):
        if self.ser is None or not self.ser.is_open:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            print("[INFO] Serial port opened.")

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("[INFO] Serial port closed.")

    # --- THREAD HELPERS ---
    def _start_thread(self, target, stop_event, thread_attr):
        thread = getattr(self, thread_attr)
        if thread is None or not thread.is_alive():
            stop_event.clear()
            thread = threading.Thread(target=target, daemon=True)
            setattr(self, thread_attr, thread)
            thread.start()

    def _stop_thread(self, stop_event, thread_attr):
        thread = getattr(self, thread_attr)
        if thread and thread.is_alive():
            stop_event.set()
            thread.join()

    # --- READER THREAD ---
    def start_reader(self):
        self._start_thread(self._reader_loop, self.reader_stop_event, "reader_thread")

    def stop_reader(self):
        self._stop_thread(self.reader_stop_event, "reader_thread")

    def _reader_loop(self):
        try:
            while not self.reader_stop_event.is_set():
                if self.ser.in_waiting:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if not line:
                        continue
                    if line.startswith('<'):
                        self.status_queue.put(line)
                        self._publish_if_changed(self._parse_status_line(line))
                    else:
                        self.response_queue.put(line)
                        if re.match(r'^\[MSG:pgm end\]$', line.strip(), re.IGNORECASE):
                            self.program_end_received.set()
                            time.sleep(1)
                else:
                    time.sleep(0.01)
        except Exception as e:
            print(f"[ERROR] Serial reader thread error: {e}")

    # --- POLLING THREAD ---
    def start_polling(self):
        self._start_thread(self._polling_loop, self.poll_stop_event, "poll_thread")

    def stop_polling(self):
        self._stop_thread(self.poll_stop_event, "poll_thread")

    def _polling_loop(self):
        try:
            while not self.poll_stop_event.is_set():
                with self.lock:
                    self.ser.write(b'?')
                time.sleep(self.poll_interval)
        except Exception as e:
            print(f"[ERROR] Polling thread error: {e}")

    # --- TASMOTA THREAD ---
    def start_tasmota_publisher(self):
        self._start_thread(self._tasmota_loop, self.tasmota_stop_event, "tasmota_thread")

    def stop_tasmota_publisher(self):
        self._stop_thread(self.tasmota_stop_event, "tasmota_thread")

    def _tasmota_loop(self):
        while not self.tasmota_stop_event.is_set():
            try:
                resp = requests.get(TASMOTA_URL, timeout=5)
                if resp.status_code == 200:
                    state = resp.json()
                    if state != self.tasmota_last_state:
                        self.mqtt_client.publish(TASMOTA_TOPIC, str(state))
                        self.tasmota_last_state = state
                        print(f"[TASMOTA] Published state to {TASMOTA_TOPIC}")
                if self.program_end_received.is_set() or self.send_error:
                    break
            except Exception as e:
                print(f"[ERROR] Tasmota polling failed: {e}")
            time.sleep(0.5)
        print("[TASMOTA] Polling stopped automatically.")

    # --- GCODE UTILS ---
    def split_gcode_lines(self, gcode_text):
        gcode_text = re.sub(r';.*|\(.*?\)', '', gcode_text)
        gcode_text = gcode_text.replace('\n', ' ')
        tokens = gcode_text.strip().split()
        lines, current = [], []
        for token in tokens:
            if re.match(r'^[GM]\d+', token, re.IGNORECASE):
                if current:
                    lines.append(' '.join(current))
                current = [token]
            else:
                current.append(token)
        if current:
            lines.append(' '.join(current))
        return lines

    def _write_serial(self, line):
        with self.lock:
            self.ser.write((line.strip() + '\n').encode('utf-8'))

    def _send_lines(self, lines):
        for i, line in enumerate(lines):
            if self.send_error:
                break
            self._write_serial(line)
            timeout = 185 if i == len(lines) - 1 else 5
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    response = self.response_queue.get(timeout=0.1)
                    if response.lower().startswith('error'):
                        self.send_error = response
                        break
                    if response.lower() == 'ok':
                        break
                except queue.Empty:
                    continue
            else:
                self.send_error = "Timeout waiting for ok from GRBL"
                break
        self.stop_polling()
        self.stop_tasmota_publisher()

    def send_gcode(self, gcode_text):
        self.send_error = None
        self.program_end_received.clear()
        lines = self.split_gcode_lines(gcode_text)

        self.start_polling()
        self.start_tasmota_publisher()

        threading.Thread(target=self._send_lines, args=(lines,), daemon=True).start()
        return {"status": "started", "message": "G-code sending started asynchronously."}

    def send_command(self, command, timeout=20):
        self._write_serial(command)
        return self.wait_for_ok_or_error(timeout)

    def wait_for_ok_or_error(self, timeout=20):
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                line = self.response_queue.get(timeout=0.1)
                if line.lower() == 'ok' or line.lower().startswith('error'):
                    return line
            except queue.Empty:
                continue
        return None


serial_manager = SerialCommManager(PORT, BAUD_RATE)


def send_callback(callback_url):
    try:
        print(f"[INFO] Sending callback to {callback_url}")
        requests.put(callback_url, json={"status": "done"})
    except Exception as e:
        print(f"[ERROR] Callback sending failed: {e}")


# --- FLASK ENDPOINTS ---
@app.route('/executeGcode', methods=['POST'])
@require_idle
def execute_gcode_endpoint():
    cb = request.headers.get('Cpee-Callback')
    if not cb:
        return jsonify({"error": "Missing Cpee-Callback header"}), 400

    gcode = (
        request.form.get('gcode')
        if request.content_type == 'application/x-www-form-urlencoded'
        else request.get_json().get('gcode')
    )

    def monitor():
        res = serial_manager.send_gcode(gcode)
        print(f"[INFO] G-code execution result: {res}")
        serial_manager.program_end_received.wait()
        time.sleep(2)
        send_callback(cb)

    threading.Thread(target=monitor, daemon=True).start()
    return '', 200, {'CPEE-CALLBACK': 'true'}


@app.route('/home', methods=['POST'])
@require_idle
def home():
    res = serial_manager.send_command("$H", timeout=40)
    if res is None:
        return jsonify({"status": "error", "output": "Timeout"}), 500
    return jsonify({"status": "success", "output": res})


@app.route('/robot', methods=['POST'])
@require_idle
def robot():
    if not os.path.exists("robot-position.gcode"):
        return jsonify({"status": "error", "message": "Missing file"}), 500
    with open("robot-position.gcode") as f:
        gcode = f.read()
    return jsonify(serial_manager.send_gcode(gcode))


if __name__ == "__main__":
    app.run(debug=True, use_reloader =False, host="0.0.0.0", port=5004)
