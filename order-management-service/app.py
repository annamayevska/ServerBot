from flask import Flask, jsonify, request
import os
import json

app = Flask(__name__)

ORDER_CREATION_SERVICE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../order-creation-service/orders'))  
CALLBACKS_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'callbacks.json'))
os.makedirs(ORDER_CREATION_SERVICE_DIR, exist_ok=True)

@app.route('/manageOrders', methods=['GET'])
#Fetch and return the first available order, or store the callback if no orders found
def manage_orders():

    try:
        orders = os.listdir(ORDER_CREATION_SERVICE_DIR)
    except FileNotFoundError:
        return jsonify({"error": f"Directory '{ORDER_CREATION_SERVICE_DIR}' not found"}), 404

    if orders:
        order_file = orders[0]
        order_path = os.path.join(ORDER_CREATION_SERVICE_DIR, order_file)
        with open(order_path, 'r') as f:
            order_data = json.load(f)
        
        os.remove(order_path)
        return jsonify(order_data), 200

    # If no orders are found, save the callback ID
    cb = request.headers.get('Cpee-Callback')
    if not cb:
        return jsonify({"error": "Cpee-Callback header is missing"}), 400

    try:
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

    except Exception as e:
        return jsonify({"error": "Failed to save callback ID"}), 500

    response_headers = {'CPEE-CALLBACK': 'true'}
    return '', 200, response_headers


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
