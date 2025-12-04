from flask import Flask, request, jsonify
import time
import re

app = Flask(__name__)

# Her sensor_id için EN SON ölçümü tutan sözlük
# {
#   "esp32-sniffer-1": {"device_count": 24, "time": 1764584000},
#   ...
# }
latest_measurements = {}

# Basit alert listesi (in-memory)
# Her eleman:
# {
#   "id": 1,
#   "email": "kisi@example.com",
#   "hours": 3,
#   "created_at": 1700000000.0,
#   "expires_at": 1700010800.0,
#   "is_active": True,
#   "triggered_at": None
# }
alerts = []
_next_alert_id = 1

EMAIL_REGEX = re.compile(r"^[^@]+@[^@]+\.[^@]+$")


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


@app.route("/api/alerts", methods=["POST"])
def create_alert():
    """
    Frontend'den gelen e-mail alarm isteğini kaydeder.
    Beklenen JSON:
    {
        "hours": <number>,          # slider'dan (1–8)
        "email": "kullanici@... "
    }
    """
    global _next_alert_id

    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip()
    hours = data.get("hours")

    # Basit validasyon
    if not email:
        return jsonify({"status": "error", "message": "email_required"}), 400

    if not EMAIL_REGEX.match(email):
        return jsonify({"status": "error", "message": "invalid_email"}), 400

    try:
        hours = int(hours)
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "invalid_hours"}), 400

    if hours < 1 or hours > 8:
        return jsonify({
            "status": "error",
            "message": "hours_out_of_range",
            "allowed_min": 1,
            "allowed_max": 8
        }), 400

    now = time.time()
    expires_at = now + hours * 3600  # saniye

    alert = {
        "id": _next_alert_id,
        "email": email,
        "hours": hours,
        "created_at": now,
        "expires_at": expires_at,
        "is_active": True,
        "triggered_at": None,
    }
    _next_alert_id += 1

    alerts.append(alert)

    print("Yeni alert kaydedildi:", alert)

    return jsonify({
        "status": "ok",
        "alert_id": alert["id"],
        "expires_at": expires_at
    }), 201


@app.route("/api/alerts", methods=["GET"])
def list_alerts():
    """
    Debug/test için: kayıtlı tüm alert'leri döndürür.
    (Prod'da kapatmak isteyebilirsin.)
    """
    return jsonify(alerts)
