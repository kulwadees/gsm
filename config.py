# config.py
from dotenv import dotenv_values
from pathlib import Path

# Whitelist: ตัวแปรที่อนุญาตให้ใช้เท่านั้น
ALLOWED_KEYS = {
    'OANDA_API_TOKEN',
    'OANDA_ACCOUNT_ID',
    'OANDA_ENV',
    'TG_TOKEN',
    'TG_CHAT_ID',
    'WEB_TOKEN',
    'OANDA_INSTRUMENT',
}

# ค่า default ถ้าไม่ได้ระบุใน .env
DEFAULTS = {
    'OANDA_API_TOKEN': '',
    'OANDA_ACCOUNT_ID': '',
    'OANDA_ENV': 'practice',
    'TG_TOKEN': '',
    'TG_CHAT_ID': '',
    'WEB_TOKEN': '',
    'OANDA_INSTRUMENT': '',    
}

# หา path ของ .env จาก root ของโปรเจกต์ (ไม่งง เวลารันจาก directory อื่น)
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / '.env'

# อ่านค่าจาก .env เท่านั้น — ไม่แตะ os.environ เลย
_raw = dotenv_values(ENV_FILE)

# กรองเฉพาะ whitelist แล้วใส่ default ถ้าไม่มี
config = {
    key: _raw.get(key) if _raw.get(key) not in (None, '') else default
    for key, default in DEFAULTS.items()
    if key in ALLOWED_KEYS
}

# เพิ่มตัวแปร whitelist ที่ไม่มี default ด้วย
for key in ALLOWED_KEYS:
    if key not in config and _raw.get(key):
        config[key] = _raw[key]


def get(key: str, default=None):
    """ฟังก์ชันกลางสำหรับอ่าน config"""
    return config.get(key, default)
