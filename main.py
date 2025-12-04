from flask import Flask, request, jsonify
import time
import re
import threading
import requests

RESEND_API_KEY = "re_67gvWUmb_3wHCTZ45Cy3W6StydigYZQDD"

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
#   "triggered_at": None,
#   "starting_level": 3
# }
alerts = []
_next_alert_id = 1

EMAIL_REGEX = re.compile(r"^[^@]+@[^@]+\.[^@]+$")


# -------------------------------------------------------------------
# Yardımcı: Bina için "kademe" hesapla (1–5)
# Bu tamamen örnek eşikler; kendine göre ayarla.
# -------------------------------------------------------------------
def compute_building_level():
    """
    Tüm sensörlerin toplam device_count'ından 1–5 arası bir kademe üretir.
    Eşikler tamamen örnek: bunları kendi kalibrasyonuna göre değiştir.
    """
    if not latest_measurements:
        return None

    total = 0.0
    for entry in latest_measurements.values():
        try:
            dc = float(entry.get("device_count") or 0)
        except (TypeError, ValueError):
            dc = 0.0
        total += dc

    # ÖRNEK: eşikleri kendin değiştirebilirsin
    # 0–10  → 1 (çok boş)
    # 10–20 → 2
    # 20–35 → 3
    # 35–50 → 4
    # 50+   → 5 (çok dolu)
    if total < 21:
        return 1
    elif total < 41:
        return 2
    elif total < 61:
        return 3
    elif total < 81:
        return 4
    else:
        return 5


# -------------------------------------------------------------------
# Yardımcı: E-mail gönderme (şimdilik stub, gerçek SMTP / provider ekleyebilirsin)
# -------------------------------------------------------------------
def send_email(to_email: str, subject: str, body: str):
    url = "https://api.resend.com/emails"

    html_body = f"""
    <div style="font-family:Arial; padding:20px;">
        <h2 style="color:#1a73e8;">{subject}</h2>
        <p style="font-size:15px; color:#333; line-height:1.5;">
            {body.replace("\n", "<br>")}
        </p>
        <p style="font-size:13px; color:#888;">Gesendet von <b>bib.</b></p>
    </div>
    """

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "from": "bib <onboarding@resend.dev>",
            "to": to_email,
            "subject": subject,
            "html": html_body
        }
    )

    print("Resend yanıtı:", response.status_code, response.text)



# -------------------------------------------------------------------
# ESP32 ölçüm endpoint'i
# -------------------------------------------------------------------
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


# -------------------------------------------------------------------
# Alert oluşturma endpoint'i
# -------------------------------------------------------------------
@app.route("/api/alerts", methods=["POST"])
def create_alert():
    """
    Frontend'den gelen e-mail alarm isteğini kaydeder.
    Beklenen JSON:
    {
        "hours": <number>,          # slider'dan (1–8)
        "email": "kullanici@... "
    }
    Bina için o anki "kademe"yi starting_level olarak kaydeder.
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

    starting_level = compute_building_level()
    # Ölçüm yoksa None dönebilir; o durumda ilk check'te current_level'i starting_level olarak set edebilirsin.
    # Şimdilik direkt kaydediyoruz.

    alert = {
        "id": _next_alert_id,
        "email": email,
        "hours": hours,
        "created_at": now,
        "expires_at": expires_at,
        "is_active": True,
        "triggered_at": None,
        "starting_level": starting_level,
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
    Prod'da kapatmak isteyebilirsin.
    """
    return jsonify(alerts)


# -------------------------------------------------------------------
# Her 10 dakikada bir alert'leri kontrol eden fonksiyon
# -------------------------------------------------------------------
def check_alerts_loop():
    """
    Sonsuz döngü:
    - her 10 dakikada bir aktif alert'lere bakar
    - eğer alert hala geçerliyse (expires_at > now)
      ve bina kademesi, starting_level'den EN AZ 1 düşükse
      e-mail gönderir ve alert'i listeden çıkarır.
    """
    global alerts

    while True:
        try:
            now = time.time()
            current_level = compute_building_level()

            # Ölçüm yoksa kontrol etmenin anlamı yok; direkt pas geç
            if current_level is None:
                print("[AlertChecker] Henüz ölçüm yok, bekleniyor...")
            else:
                print(f"[AlertChecker] Mevcut kademe: {current_level}, aktif alert sayısı: {len(alerts)}")

                new_alerts = []
                for alert in alerts:
                    # Zaten tetiklenmiş veya süresi geçmişleri atla
                    if not alert.get("is_active", True):
                        continue
                    if now > alert["expires_at"]:
                        print(f"[AlertChecker] Alert süresi doldu, siliyorum: id={alert['id']}")
                        continue

                    starting_level = alert.get("starting_level")
                    # Eğer starting_level yoksa, ilk gördüğümüz anda set edelim
                    if starting_level is None:
                        starting_level = current_level
                        alert["starting_level"] = starting_level

                    # En az 1 kademe azaldı mı?
                    if current_level <= starting_level - 1:
                        # E-mail gönder
                        subject = "bib. – Deine Bibliothek ist ruhiger geworden"
                        body = (
                            f"Hallo,\n\n"
                            f"Die aktuelle Auslastung hat sich von Level {starting_level} "
                            f"auf Level {current_level} reduziert (mindestens 1 Stufe).\n"
                            f"Du hast einen Alert für die nächsten {alert['hours']} Stunden gesetzt.\n\n"
                            f"Viele Grüße\n"
                            f"bib."
                        )
                        send_email(alert["email"], subject, body)

                        alert["is_active"] = False
                        alert["triggered_at"] = now
                        print(f"[AlertChecker] Alert tetiklendi ve silindi: id={alert['id']}")
                        # Bu alert'i listede tutmuyoruz (tek seferlik)
                        continue

                    # Hâlâ aktif ama tetiklenmedi: listede tut
                    new_alerts.append(alert)

                alerts = new_alerts

        except Exception as e:
            # Hata olsa bile loop'un tamamen ölmemesi için
            print("[AlertChecker] Hata:", e)

        # 1 dakika bekle
        time.sleep(60)


# Uygulama başlarken alert kontrol thread'ini başlat
def start_background_worker():
    t = threading.Thread(target=check_alerts_loop, daemon=True)
    t.start()


start_background_worker()

# app.run() YOK – cloud ortamında gunicorn main:app ile çalıştırılacak
