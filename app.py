"""ตัวหลัก — REST API + SocketIO push ราคา realtime + ระบบป้องกัน Sleep + Password Protect"""
from dotenv import load_dotenv
load_dotenv()  # โหลดค่าจากไฟล์ .env เข้าสู่ระบบ
import os
import threading
import time
import requests
from functools import wraps
from flask import Flask, jsonify, send_from_directory, request, make_response
from flask_socketio import SocketIO

import config
from oanda_client import get_history, stream_prices
from candles import CandleBuilder

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

builder = None
_started_pid = None
_lock = threading.Lock()

# ตั้งรหัสผ่านหน้าเว็บจาก Environment Variable บน Render (ถ้าไม่ตั้ง จะใช้รหัสผ่านค่าเริ่มต้น "1234")
WEB_PASSWORD = os.environ.get("WEB_PASSWORD", "1234")


# ---------- ระบบป้องกันการหลับ (Self-ping ชั้นที่ 1) ----------
def self_ping_loop():
    """ยิงเรียกตัวเองทุกๆ 9 นาที เพื่อเลี้ยงระบบไม่ให้ Render หลับ"""
    time.sleep(30) # รอให้เซิร์ฟเวอร์ตั้งไข่สักครู่
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not render_url:
        return
    
    while True:
        try:
            requests.get(f"{render_url}/health", timeout=10)
        except Exception:
            pass
        time.sleep(540) # 9 นาที


# ---------- ระบบตรวจสอบสิทธิ์ (Password Protection) ----------
def check_auth():
    """เช็คว่าผู้ใช้กรอกรหัสผ่านถูกต้องผ่าน Cookie หรือยัง"""
    auth_cookie = request.cookies.get("auth_token")
    return auth_cookie == WEB_PASSWORD


@app.route("/login", methods=["POST", "GET"])
def login():
    """หน้าล็อกอินเข้าใช้งานเว็บ"""
    if request.method == "POST":
        data = request.form or request.json or {}
        password = data.get("password", "")
        if password == WEB_PASSWORD:
            resp = make_response(jsonify({"success": True}))
            # ตั้ง Cookie ให้จำสิทธิ์ไว้ 30 วัน
            resp.set_cookie("auth_token", WEB_PASSWORD, max_age=60*60*24*30)
            return resp
        return jsonify({"success": False, "error": "รหัสผ่านไม่ถูกต้อง"}), 401

    # หน้าจอ Login อย่างง่าย
    return """
    <!DOCTYPE html>
    <html lang="th">
    <head>
        <meta charset="UTF-8">
        <title>Login - GSM Trading</title>
        <style>
            body { background: #131722; color: #d1d4dc; font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .box { background: #1e222d; padding: 30px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.5); width: 300px; text-align: center; }
            input { width: 100%; padding: 10px; margin: 15px 0; background: #2a2e39; border: 1px solid #363c4e; color: white; border-radius: 4px; box-sizing: border-box; }
            button { width: 100%; padding: 10px; background: #2962ff; border: none; color: white; border-radius: 4px; font-weight: bold; cursor: pointer; }
            button:hover { background: #1e53e5; }
            .err { color: #f7525f; font-size: 14px; margin-top: 10px; }
        </style>
    </head>
    <body>
        <div class="box">
            <h2>GSM Protected</h2>
            <input type="password" id="pwd" placeholder="กรอกรหัสผ่านเว็บ">
            <button onclick="doLogin()">เข้าสู่ระบบ</button>
            <div id="err" class="err"></div>
        </div>
        <script>
            async function doLogin() {
                let p = document.getElementById('pwd').value;
                let res = await fetch('/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({password: p})
                });
                let data = await res.json();
                if(data.success) { location.reload(); }
                else { document.getElementById('err').innerText = data.error; }
            }
        </script>
    </body>
    </html>
    """


# ---------- Background: seed ประวัติ + streaming จาก OANDA ----------
def feed_worker():
    global builder
    pid = os.getpid()

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

    def on_price(tick):
        builder.on_tick(tick)
        socketio.emit("candle", builder.latest())

    stream_prices(on_price)


def ensure_started():
    global _started_pid, builder
    pid = os.getpid()
    if _started_pid == pid:
        return
    with _lock:
        if _started_pid == pid:
            return
        _started_pid = pid
        builder = None
        print(f"[pid {pid}] เริ่ม feed_worker", flush=True)
        threading.Thread(target=feed_worker, daemon=True).start()
        # เริ่ม thread ชั้นที่ 1 (Self-ping)
        threading.Thread(target=self_ping_loop, daemon=True).start()


@app.before_request
def _start_feed_once():
    # ข้อยกเว้นให้ health check และหน้า login เข้าถึงได้ทันทีโดยไม่ต้องเช็ค auth
    if request.path in ["/health", "/login"]:
        return
    ensure_started()
    # ถ้ายังไม่ล็อกอิน ให้ดีดไปหน้า login
    if not check_auth():
        return login()


# ---------- REST API ----------
@app.route("/health")
def health():
    """Endpoint สำหรับให้ Google Apps Script และ Self-ping เรียกเช็คสถานะ"""
    status = "ready" if builder is not None else "loading"
    return jsonify({"status": status, "candles_count": len(builder.snapshot(500)) if builder else 0}), 200


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