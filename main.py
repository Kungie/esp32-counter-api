from flask import Flask, request, jsonify
import time

app = Flask(__name__)

# Her sensor_id için EN SON ölçümü tutan sözlük
# Örnek içerik:
# {
#   "esp32-sniffer-1": {"device_count": 24, "time": 1764584000},
#   "esp32-sniffer-2": {"device_count": 31, "time": 1764584102},
# }
latest_measurements = {}


@app.route("/api/measure", methods=["POST"])
def measure():
    """
    ESP32'lerden gelen ölçümleri alır.
    Beklenen JSON:
    {
        "device_count": 27.2,
        "sensor_id": "esp32-sniffer-1"
    }
    """
    data = request.get_json() or {}

    device_count = data.get("device_count")
    sensor_id    = data.get("sensor_id")

    if sensor_id is None:
        return jsonify({"status": "error", "message": "sensor_id eksik"}), 400

    entry = {
        "device_count": device_count,
        "time": time.time()  # sunucunun zamanı (UNIX timestamp, saniye)
    }

    # Bu sensor_id için en son ölçümü güncelle
    latest_measurements[sensor_id] = entry

    print(f"Gelen veri [{sensor_id}]:", entry)

    return jsonify({"status": "ok"})


@app.route("/api/latest", methods=["GET"])
def latest():
    """
    Tüm sensörlerin en son ölçümlerini döndürür.
    Örnek çıktı:
    {
      "esp32-sniffer-1": {"device_count": 24, "time": 1764584000},
      "esp32-sniffer-2": {"device_count": 31, "time": 1764584102}
    }
    """
    return jsonify(latest_measurements)


# app.run() YOK – cloud ortamında gunicorn main:app ile çalıştırılacak
