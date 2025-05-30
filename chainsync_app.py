
from flask import Flask, jsonify, request, render_template_string
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from datetime import datetime
import threading
import os
import atexit

app = Flask(__name__)

# Environment variables
ORACLE_BASE_URL = os.getenv("ORACLE_BASE_URL", "https://api.placeholder.com")
ORACLE_API_KEY = os.getenv("ORACLE_API_KEY", "your_fallback_key")

class OracleEBSConnector:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

    def update_shipment(self, shipment_id, status, timestamp):
        url = f"{self.base_url}/shipments/{shipment_id}/update"
        payload = {"status": status, "timestamp": timestamp}
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return {"success": True, "response": response.json()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_inventory(self, sku, location_id, quantity, batch_number=None, expiry_date=None):
        url = f"{self.base_url}/inventory/{sku}/update"
        payload = {
            "location_id": location_id,
            "quantity": quantity,
            "batch_number": batch_number,
            "expiry_date": expiry_date
        }
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return {"success": True, "response": response.json()}
        except Exception as e:
            return {"success": False, "error": str(e)}

oracle_connector = OracleEBSConnector(ORACLE_BASE_URL, ORACLE_API_KEY)

sync_logs = []
log_lock = threading.Lock()

def log_sync(action, data, result):
    with log_lock:
        sync_logs.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "data": data,
            "result": result
        })
        if len(sync_logs) > 100:
            sync_logs.pop(0)

@app.route('/api/shipments/update', methods=['POST'])
def api_update_shipment():
    data = request.json
    shipment_id = data.get("shipment_id")
    status = data.get("status")
    timestamp = data.get("timestamp")
    result = oracle_connector.update_shipment(shipment_id, status, timestamp)
    log_sync("shipment_update", data, result)
    return jsonify(result)

@app.route('/api/inventory/update', methods=['POST'])
def api_update_inventory():
    data = request.json
    sku = data.get("sku")
    location_id = data.get("location_id")
    quantity = data.get("quantity")
    batch_number = data.get("batch_number")
    expiry_date = data.get("expiry_date")
    result = oracle_connector.update_inventory(sku, location_id, quantity, batch_number, expiry_date)
    log_sync("inventory_update", data, result)
    return jsonify(result)

@app.route('/api/sync_logs', methods=['GET'])
def api_get_sync_logs():
    with log_lock:
        return jsonify(sync_logs[::-1])

@app.route('/')
def index():
    return render_template_string("""
    <html>
    <head>
        <title>ChainSync Dashboard</title>
        
    <style>
        body {
            font-family: Arial, sans-serif;
            padding: 20px;
            background-color: #f4f9ff;
            color: #002b5c;
        }
        h1 {
            color: #004aad;
        }
        pre {
            background: #ffffff;
            padding: 15px;
            border: 1px solid #cce0ff;
            border-radius: 6px;
            max-height: 300px;
            overflow-y: auto;
            font-size: 13px;
        }
        button {
            background-color: #007bff;
            color: white;
            border: none;
            border-radius: 5px;
            padding: 10px 15px;
            margin: 5px;
            cursor: pointer;
            font-size: 14px;
        }
        button:hover {
            background-color: #0056b3;
        }
        input, select {
            padding: 8px;
            width: 300px;
            margin-bottom: 10px;
            border: 1px solid #ccc;
            border-radius: 4px;
        }
    
            body { font-family: Arial; padding: 20px; }
            h1 { color: #333; }
            pre { background: #f8f8f8; padding: 10px; border-radius: 5px; max-height: 300px; overflow-y: auto; }
            form { margin-top: 20px; }
            input, select { margin-bottom: 10px; display: block; width: 300px; }
            button { margin-top: 10px; padding: 10px; }
        </style>
    </head>
    <body>
        <h1>ChainSync Dashboard</h1>
        
    <p>This is your live system monitor. Logs refresh automatically every 10 seconds.</p>
    <p><strong>Quick Links:</strong></p>
    
    <div style="margin-top: 20px;">
        <a href="/" style="text-decoration:none;">
            <button>🏠 Homepage Dashboard</button>
        </a>
        <a href="/api/sync_logs" target="_blank" style="text-decoration:none;">
            <button>📄 View JSON Logs</button>
        </a>
        <a href="https://hoppscotch.io" target="_blank" style="text-decoration:none;">
            <button>📦 POST to /api/inventory/update</button>
        </a>
        <a href="https://hoppscotch.io" target="_blank" style="text-decoration:none;">
            <button>🚚 POST to /api/shipments/update</button>
        </a>
    </div>
    <ul style="display:none;">
    
        <li><a href="/">🏠 Homepage Dashboard</a></li>
        <li><a href="/api/sync_logs" target="_blank">📄 View JSON Logs</a></li>
        <li><a href="https://httpie.io/docs#post" target="_blank">📦 POST to /api/inventory/update</a></li>
        <li><a href="https://httpie.io/docs#post" target="_blank">🚚 POST to /api/shipments/update</a></li>
    </ul>
    
        <button onclick="loadLogs()">Refresh Logs Now</button>
        <pre id="logs">Loading...</pre>

        <h2>Manual Inventory Sync</h2>
        <form id="inventoryForm" onsubmit="submitInventory(); return false;">
            <input type="text" id="sku" placeholder="SKU" required />
            <input type="text" id="location_id" placeholder="Location ID" required />
            <input type="number" id="quantity" placeholder="Quantity" required />
            <input type="text" id="batch_number" placeholder="Batch Number (optional)" />
            <input type="date" id="expiry_date" placeholder="Expiry Date (optional)" />
            <button type="submit">Submit Inventory Sync</button>
        </form>

        <script>
            function loadLogs() {
                fetch('/api/sync_logs')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('logs').textContent = JSON.stringify(data, null, 2);
                    });
            }

            function submitInventory() {
                const data = {
                    sku: document.getElementById("sku").value,
                    location_id: document.getElementById("location_id").value,
                    quantity: parseInt(document.getElementById("quantity").value),
                    batch_number: document.getElementById("batch_number").value || null,
                    expiry_date: document.getElementById("expiry_date").value || null
                };
                fetch('/api/inventory/update', {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(data)
                }).then(() => loadLogs());
            }

            loadLogs();
            setInterval(loadLogs, 10000);
        </script>
    </body>
    </html>
    """)

def automated_shipment_sync():
    shipment_id = "SHIP12345"
    status = "In Transit"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = oracle_connector.update_shipment(shipment_id, status, timestamp)
    log_sync("auto_shipment_sync", {"shipment_id": shipment_id, "status": status, "timestamp": timestamp}, result)

def automated_inventory_sync():
    sku = "SKU9876"
    location_id = "LOC1"
    quantity = 150
    batch_number = "BATCH202505"
    expiry_date = "2025-12-31"
    result = oracle_connector.update_inventory(sku, location_id, quantity, batch_number, expiry_date)
    log_sync("auto_inventory_sync", {"sku": sku, "location_id": location_id, "quantity": quantity, "batch_number": batch_number, "expiry_date": expiry_date}, result)

scheduler = BackgroundScheduler()
scheduler.add_job(automated_shipment_sync, 'interval', minutes=5)
scheduler.add_job(automated_inventory_sync, 'interval', minutes=5)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
