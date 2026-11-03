"""รวม tick -> candle (ค่าเริ่มต้น M1 = 60 วินาที)"""
import threading
from collections import OrderedDict

GRANULARITY = 60   # วินาทีต่อแท่ง: 60=M1, 300=M5, 900=M15, 3600=H1


class CandleBuilder:
    def __init__(self, seed_candles=None):
        seed = seed_candles or []
        self.candles = OrderedDict((c["time"], dict(c)) for c in seed)
        self.lock = threading.Lock()

    def on_tick(self, tick):
        """tick = {"time": unix_float, "bid": float, "ask": float}"""
        price = (tick["bid"] + tick["ask"]) / 2   # mid price
        bucket = int(tick["time"] // GRANULARITY * GRANULARITY)

        with self.lock:
            c = self.candles.get(bucket)
            if c is None:
                self.candles[bucket] = {
                    "time": bucket, "open": price, "high": price,
                    "low": price, "close": price,
                }
            else:
                c["high"] = max(c["high"], price)
                c["low"] = min(c["low"], price)
                c["close"] = price

            # จำกัดหน่วยความจำ — เก็บไม่เกิน 2000 แท่ง
            while len(self.candles) > 2000:
                self.candles.popitem(last=False)

    def snapshot(self, limit=500):
        """คืน candle ล่าสุด N แท่ง (ปลอดภัยต่อ multi-thread)"""
        with self.lock:
            items = list(self.candles.values())
        return items[-limit:]

    def latest(self):
        with self.lock:
            items = list(self.candles.values())
        return items[-1] if items else None