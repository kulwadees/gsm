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

builder = None           # สร้างใน background หลังโหลดประวัติเสร็จ
_started_pid = None      # pid ของ process ที่เริ่ม feed แล้ว
_lock = threading.Lock()


# ---------- Background: seed ประวัติ + streaming จาก OANDA ----------
def feed_worker():
    global builder
    pid = os.getpid()

    # 1) seed ประวัติ (พลาดแล้วลองใหม่ ไม่ทำให้ server ล่ม)
    while True:
        try:
            print(f"[pid {pid}] กำลังโหลดประวัติ M1 จาก OANDA...", flush=True)
            seed = get_history("M1", 500)
            builder = CandleBuilder(seed)
            print(f"[pid {pid}] พร้อม — มี {len(seed)} แท่งเริ่มต้น", flush=True)
            break
        except Exception as e:
            print(f"[pid {pid}] [seed] โหลดประวัติไม่สำเร็จ: {e} — ลองใหม่ใน 10 วินาที", flush=True)
            time.sleep(10)

    # 2) เริ่ม stream
    def on_price(tick):
        builder.on_tick(tick)
        socketio.emit("candle", builder.latest())

    stream_prices(on_price)   # loop reconnect ในตัว


def ensure_started():
    """เริ่ม feed ครั้งเดียวต่อ process — เรียกจากใน process ที่รับ request จริง"""
    global _started_pid, builder
    pid = os.getpid()
    if _started_pid == pid:
        return
    with _lock:
        if _started_pid == pid:
            return
        _started_pid = pid
        builder = None  # กันค่าที่ติดมาจาก process แม่ mother process
        print(f"[pid {pid}] เริ่ม feed_worker", flush=True)
        print(f"[config] instrument = {config.get('OANDA_INSTRUMENT')}", flush=True)
        print(f"[config] env        = {config.get('OANDA_ENV')}", flush=True)
        print(f"[config] token set  = {bool(config.get('OANDA_API_TOKEN'))}", flush=True)
        threading.Thread(target=feed_worker, daemon=True).start()


@app.before_request
def _start_feed_once():
    ensure_started()


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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Server รันที่ http://localhost:{port}")
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)