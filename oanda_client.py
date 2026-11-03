#oanda_client.py
"""ดึงข้อมูล XAU_USD จาก OANDA v20 API — streaming + history"""
import json
import time
import requests
import config  # อ่านค่าจาก config.py เท่านั้น — ไม่แตะ os.environ

# ====== ตั้งค่า (มาจาก config.py / .env ทั้งหมด) ======
API_TOKEN   = config.get("OANDA_API_TOKEN", "OANDA_API_TOKEN")
ACCOUNT_ID  = config.get("OANDA_ACCOUNT_ID", "OANDA_ACCOUNT_ID")
INSTRUMENT  = config.get("OANDA_INSTRUMENT", "OANDA_INSTRUMENT")
ENV         = config.get("OANDA_ENV", "OANDA_ENV")
# practice = บัญชี demo (ฟรี), live = บัญชีจริง
# =====================================================

BASE   = f"https://api-fx{ENV}.oanda.com"
STREAM = f"https://stream-fx{ENV}.oanda.com"
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Accept-Datetime-Format": "UNIX",
}


def get_history(granularity="M1", count=500):
    """ดึง candle ย้อนหลังจาก OANDA (ใช้เป็น seed ตอน server เพิ่งเปิด)"""
    r = requests.get(
        f"{BASE}/v3/instruments/{INSTRUMENT}/candles",
        headers=HEADERS,
        params={"granularity": granularity, "count": count, "price": "MBA"},
        timeout=15,
    )
    r.raise_for_status()
    out = []
    for c in r.json().get("candles", []):
        if not c["complete"]:
            continue
        m = c["mid"]
        t = int(float(c["time"]))   # unix seconds
        out.append({
            "time": t,
            "open": float(m["o"]), "high": float(m["h"]),
            "low": float(m["l"]), "close": float(m["c"]),
        })
    return out


def get_current_price():
    """ราคา bid/ask ล่าสุด (REST ครั้งเดียว — ใช้ทดสอบ key)"""
    r = requests.get(
        f"{BASE}/v3/accounts/{ACCOUNT_ID}/pricing",
        headers=HEADERS,
        params={"instruments": INSTRUMENT},
        timeout=10,
    )
    p = r.json()["prices"][0]
    return {"bid": float(p["bids"][0]["price"]),
            "ask": float(p["asks"][0]["price"])}


def stream_prices(on_price, reconnect_wait=5):
    """
    Streaming ราคา realtime — on_price(dict) ถูกเรียกทุก tick
    on_price รับ: {"time": unix_float, "bid": float, "ask": float}
    reconnect อัตโนมัติถ้าเน็ตหลุด
    """
    url = (f"{STREAM}/v3/accounts/{ACCOUNT_ID}/pricing/stream"
           f"?instruments={INSTRUMENT}")
    while True:
        try:
            with requests.get(url, headers=HEADERS,
                              stream=True, timeout=(10, None)) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    d = json.loads(line.decode())
                    if d.get("type") == "PRICE":
                        on_price({
                            "time": float(d["time"]),
                            "bid": float(d["bids"][0]["price"]),
                            "ask": float(d["asks"][0]["price"]),
                        })
        except Exception as e:
            print(f"[stream] หลุด: {e} — เชื่อมใหม่ใน {reconnect_wait} วิ")
            time.sleep(reconnect_wait)


# ทดสอบ standalone:  python oanda_client.py
if __name__ == "__main__":
    print("ราคาปัจจุบัน:", get_current_price())
    print("ประวัติ 3 แท่งล่าสุด:", get_history()[-3:])
    print("--- streaming (กด Ctrl+C หยุด) ---")
    stream_prices(lambda t: print(t))
