#app.py
"""ตัวหลัก — REST API + SocketIO push ราคา realtime"""
import threading
from flask import Flask, jsonify, send_from_directory
from flask_socketio import SocketIO

from oanda_client import get_history, stream_prices
from candles import CandleBuilder

app = Flask(__name__)
# local ใช้ "threading", deploy บน Render/Railway เปลี่ยนเป็น "gevent"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

builder = None   # สร้างใน main ก่อนเริ่ม stream


# ---------- REST API ----------
@app.route("/api/history")
def history():
    return jsonify({"candles": builder.snapshot(500)})

@app.route("/api/price")
def price():
    return jsonify(builder.latest() or {})

@app.route("/")
def index():
    return send_from_directory(".", "index.html")


# ---------- Background: streaming จาก OANDA ----------
def feed_worker():
    def on_price(tick):
        builder.on_tick(tick)
        c = builder.latest()
        socketio.emit("candle", c)   # push ทุก tick ไป frontend
    stream_prices(on_price)          # loop reconnect ในตัว


if __name__ == "__main__":
    # ลำดับสำคัญ: seed ประวัติก่อน แล้วค่อยเริ่ม stream
    print("กำลังโหลดประวัติ M1 จาก OANDA...")
    seed = get_history("M1", 500)
    builder = CandleBuilder(seed)
    print(f"พร้อม — มี {len(seed)} แท่งเริ่มต้น")

    socketio.start_background_task(feed_worker)
    print("Server รันที่ http://localhost:5000")
    socketio.run(app, host="0.0.0.0", port=5000,
                 allow_unsafe_werkzeug=True)