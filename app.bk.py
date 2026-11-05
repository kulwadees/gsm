# app.py
"""ตัวหลัก — REST API + SocketIO push ราคา realtime"""
import os
import threading
import time

from flask import Flask, jsonify, send_from_directory
from flask_socketio import SocketIO

import config
from oanda_client import get_history, stream_prices
from candles import CandleBuilder

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

builder = None          # จะถูกสร้างใน background หลังโหลดประวัติเสร็จ
_started = False
_lock = threading.Lock()


# ---------- REST API ----------
@app.route("/api/config")
def public_config():
    return jsonify({"instrument": config.get("OANDA_INSTRUMENT", "XAU_USD")})


@app.route("/api/history")
def history():
    if builder is None:
        return jsonify({"candles": [], "error": "loading"}), 503
    return jsonify({"candles": builder.snapshot(500)})


@app.route("/api/price")
def price():
    if builder is None:
        return jsonify({}), 503
    return jsonify(builder.latest() or {})


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


# ---------- Background: seed ประวัติ + streaming จาก OANDA ----------
def feed_worker():
    global builder

    # 1) seed ประวัติก่อน (ถ้าพลาดจะลองใหม่ ไม่ทำให้ server ล่ม)
    while builder is None:
        try:
            print("กำลังโหลดประวัติ M1 จาก OANDA...", flush=True)
            seed = get_history("M1", 500)
            builder = CandleBuilder(seed)
            print(f"พร้อม — มี {len(seed)} แท่งเริ่มต้น", flush=True)
        except Exception as e:
            print(f"[seed] โหลดประวัติไม่สำเร็จ: {e} — ลองใหม่ใน 10 วินาที", flush=True)
            time.sleep(10)

    # 2) เริ่ม stream
    def on_price(tick):
        builder.on_tick(tick)
        socketio.emit("candle", builder.latest())   # push ทุก tick ไป frontend

    stream_prices(on_price)                          # loop reconnect ในตัว


#def init_stream():
 #   """เริ่ม background ครั้งเดียว — ทำงานทั้ง python app.py และ gunicorn"""
 #   global _started
 #   with _lock:
 #       if _started:
 #           return
 #       _started = True
 #   print("[INIT] กำลังเริ่ม background feed_worker...", flush=True)
 #   print(f"[config] instrument = {config.get('OANDA_INSTRUMENT')}", flush=True)
 #   print(f"[config] env        = {config.get('OANDA_ENV')}", flush=True)
 #   print(f"[config] token set  = {bool(config.get('OANDA_API_TOKEN'))}", flush=True)
 #   socketio.start_background_task(feed_worker)

def init_stream():
    print("[INIT] กำลังเริ่ม background feed_worker...", flush=True)
    # ใช้ Thread ปกติแทน start_background_task ของ socketio
    t = threading.Thread(target=feed_worker, daemon=True)
    t.start()


# เรียกตอน import → gunicorn ก็รันส่วนนี้
init_stream()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Server รันที่ http://localhost:{port}")
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)