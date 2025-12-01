from flask import Flask, request, jsonify
import time

app = Flask(__name__)

@app.route("/api/measure", methods=["POST"])
def measure():
    data = request.get_json()
    print("Gelen veri:", data)
    return jsonify({"status": "ok", "time": time.time()})
