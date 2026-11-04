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
    'OANDA_INSTRUMENT': '',
}

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / '.env'

# .env ใช้ตอนรันในเครื่อง (บน Render จะไม่มีไฟล์นี้ → ได้ dict ว่าง)
_file_values = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}


def _resolve(key: str) -> str:
    # ลำดับความสำคัญ: os.environ (Render) > .env (local) > default
    value = os.environ.get(key)
    if value in (None, ''):
        value = _file_values.get(key)
    if value in (None, ''):
        value = DEFAULTS.get(key, '')
    return value


config = {key: _resolve(key) for key in ALLOWED_KEYS}


def get(key: str, default=None):
    """ฟังก์ชันกลางสำหรับอ่าน config"""
    value = config.get(key)
    return value if value not in (None, '') else default
