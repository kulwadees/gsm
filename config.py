# config.py
import os
from dotenv import dotenv_values
from pathlib import Path

ALLOWED_KEYS = {
    'OANDA_API_TOKEN',
    'OANDA_ACCOUNT_ID',
    'OANDA_ENV',
    'TG_TOKEN',
    'TG_CHAT_ID',
    'WEB_TOKEN',
    'OANDA_INSTRUMENT',
}

DEFAULTS = {
    'OANDA_API_TOKEN': '',
    'OANDA_ACCOUNT_ID': '',
    'OANDA_ENV': 'practice',
    'TG_TOKEN': '',
    'TG_CHAT_ID': '',
    'WEB_TOKEN': '',
    'OANDA_INSTRUMENT': 'XAU_USD',
}

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / '.env'

# ถ้ามีไฟล์ .env ในเครื่องให้อ่านมาสำรอง (บน Render จะไม่มีไฟล์นี้)
_raw = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}


def _resolve(key: str) -> str:
    # ลำดับ: os.environ (Render Dashboard) > .env (Local) > default
    val = os.environ.get(key)
    if val in (None, ''):
        val = _raw.get(key)
    if val in (None, ''):
        val = DEFAULTS.get(key, '')
    return val


config = {key: _resolve(key) for key in ALLOWED_KEYS}


def get(key: str, default=None):
    """ฟังก์ชันกลางสำหรับอ่าน config"""
    val = config.get(key)
    return val if val not in (None, '') else default