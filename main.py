from flask import Flask, request, jsonify, render_template
import time

app = Flask(__name__)

# Gelen ölçümleri burada tutacağız (en basit çözüm)
measurements = []   # her eleman: {"device_count": ..., "sensor_id": ..., "time": ...}

@app.route("/api/measure", methods=["POST"])
def measure():
    data = request.get_json() or {}
    device_count = data.get("device_count")
    sensor_id    = data.get("sensor_id")

    entry = {
        "device_count": device_count,
        "sensor_id": sensor_id,
        "time": time.time()
    }
    measurements.append(entry)

    print("Gelen veri:", entry)

    return jsonify({"status": "ok", "time": entry["time"]})


# Frontend’in okuyacağı “son değer” endpoint’i
@app.route("/api/latest")
def latest():
    if not measurements:
        return jsonify({"device_count": None, "sensor_id": None, "time": None})
    return jsonify(measurements[-1])


# İstersen basit bir HTML sayfası da buradan servis edebiliriz
@app.route("/")
def index():
    return render_template("index.html")
