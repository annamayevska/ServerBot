import requests
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import uuid

app = Flask(__name__)

CORS(app, origins="*", methods=["GET", "POST", "OPTIONS"])

ORDER_CREATION_SERVICE_DIR = os.path.dirname(__file__)
JSON_STORAGE_DIR = os.path.join(ORDER_CREATION_SERVICE_DIR, 'orders')
os.makedirs(JSON_STORAGE_DIR, exist_ok=True)
CALLBACKS_FILE_PATH = os.path.join(ORDER_CREATION_SERVICE_DIR, '../order-management-service/callbacks.json')

@app.route('/createOrder', methods=['POST', 'OPTIONS'])
def create_order():
    if request.method == 'OPTIONS':
        response = jsonify({'message': 'CORS preflight success'})
        response.status_code = 200
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    try:
        data = request.json
        svg = data.get('svg')
        text = data.get('text')
        if not svg or not text:
            return jsonify({'error': 'SVG and text are required'}), 400

        order_id = str(uuid.uuid4())
        order_data = {'order_id': order_id, 'svg': svg, 'text': text}

        
        if os.path.exists(CALLBACKS_FILE_PATH):
            with open(CALLBACKS_FILE_PATH, 'r') as callbacks_file:
                callback_data = json.load(callbacks_file)
                callback_ids = [callback["callback_id"] for callback in callback_data]

            if callback_ids:
                callback_url = callback_ids[0]  
                try:
                    # Send a PUT request to the callback URL with the order data 
                    callback_response = requests.put(callback_url, json=order_data, timeout=10)

                    if callback_response.status_code == 200:
                        callback_data = [callback for callback in callback_data if callback["callback_id"] != callback_url]
                        with open(CALLBACKS_FILE_PATH, 'w') as callbacks_file:
                            json.dump(callback_data, callbacks_file)
                        return jsonify({'message': 'Order sent to callback successfully'}), 200

                except requests.exceptions.Timeout:
                    return jsonify({'error': f'Request to callback URL {callback_url} timed out'}), 504
                except requests.exceptions.RequestException as e:
                     return jsonify({'error': f'Error during callback request: {str(e)}'}), 500

                order_file_path = os.path.join(JSON_STORAGE_DIR, f"{order_id}.json")
                with open(order_file_path, 'w') as order_file:
                    json.dump(order_data, order_file)
                return jsonify({'message': 'Callback triggered or failed, order saved to directory'}), 200
            
            else:
                # Save to the orders directory when no callback found
                order_file_path = os.path.join(JSON_STORAGE_DIR, f"{order_id}.json")
                with open(order_file_path, 'w') as order_file:
                    json.dump(order_data, order_file)
                return jsonify({'message': 'No callback available, order saved to directory'}), 200
        else:
            return jsonify({'error': 'Failed to retrieve callback list'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
