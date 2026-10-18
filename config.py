import os
from dotenv import load_dotenv

ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")

def load_environment():
    if os.path.exists(ENV_FILE):
        load_dotenv(ENV_FILE, override=True)

def safe_int(val, default=0):
    try:
        if val is None:
            return default
        s = str(val).strip()
        return int(s) if s else default
    except (ValueError, TypeError):
        return default

load_environment()

class Config:
    API_ID = safe_int(os.getenv("API_ID"), 0)
    API_HASH = (os.getenv("API_HASH") or "").strip()
    BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
    BIN_CHANNEL = safe_int(os.getenv("BIN_CHANNEL"), 0)
    
    HOST = (os.getenv("HOST") or "0.0.0.0").strip()
    PORT = safe_int(os.getenv("PORT"), 8000)
    
    BASE_URL = (os.getenv("BASE_URL") or "http://localhost:8000").strip().rstrip("/")
    CHUNK_SIZE = safe_int(os.getenv("CHUNK_SIZE"), 512 * 1024)
    
    ADMIN_PASSWORD = (os.getenv("ADMIN_PASSWORD") or "admin123").strip()
    SECRET_KEY = (os.getenv("SECRET_KEY") or "tg-stream-secret-token-key-987654321").strip()
    
    ADMINS = [
        int(x.strip()) 
        for x in (os.getenv("ADMINS") or "").split(",") 
        if x.strip().isdigit()
    ]

    @classmethod
    def reload(cls):
        load_environment()
        cls.API_ID = safe_int(os.getenv("API_ID"), 0)
        cls.API_HASH = (os.getenv("API_HASH") or "").strip()
        cls.BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
        cls.BIN_CHANNEL = safe_int(os.getenv("BIN_CHANNEL"), 0)
        cls.HOST = (os.getenv("HOST") or "0.0.0.0").strip()
        cls.PORT = safe_int(os.getenv("PORT"), 8000)
        cls.BASE_URL = (os.getenv("BASE_URL") or "http://localhost:8000").strip().rstrip("/")
        cls.ADMIN_PASSWORD = (os.getenv("ADMIN_PASSWORD") or "admin123").strip()
        cls.SECRET_KEY = (os.getenv("SECRET_KEY") or "tg-stream-secret-token-key-987654321").strip()

    @classmethod
    def save_to_env(cls, updates: dict):
        current_lines = []
        if os.path.exists(ENV_FILE):
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                current_lines = f.readlines()

        keys_present = set()
        new_lines = []
        for line in current_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k, _ = stripped.split("=", 1)
                k = k.strip()
                if k in updates:
                    new_lines.append(f"{k}={updates[k]}\n")
                    keys_present.add(k)
                    continue
            new_lines.append(line)

        # Add any keys that weren't in file
        for k, v in updates.items():
            if k not in keys_present:
                new_lines.append(f"{k}={v}\n")

        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        cls.reload()

    @classmethod
    def validate(cls):
        missing = []
        if not cls.API_ID:
            missing.append("API_ID")
        if not cls.API_HASH:
            missing.append("API_HASH")
        if not cls.BOT_TOKEN:
            missing.append("BOT_TOKEN")
        if not cls.BIN_CHANNEL:
            missing.append("BIN_CHANNEL")
        return missing
