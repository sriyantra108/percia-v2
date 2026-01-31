#!/usr/bin/env python3
from flask import Flask, render_template, request, jsonify
import json, sys, os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

app = Flask(__name__)
BASE_PATH = Path(__file__).parent.parent

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/system/status')
def api_system_status():
    try:
        snapshot_file = BASE_PATH / "mcp" / "snapshot.json"
        if not snapshot_file.exists():
            return jsonify({"status": "not_initialized"})
        
        with open(snapshot_file, 'r') as f:
            snapshot = json.load(f)
        
        return jsonify({"status": "ok", "data": snapshot})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    print("PERCIA v2.0 - http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
