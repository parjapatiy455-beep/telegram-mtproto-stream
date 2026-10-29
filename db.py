import os
import json
import logging

logger = logging.getLogger("db")
DB_FILE = os.path.join(os.path.dirname(__file__), "files_db.json")

def load_files_db() -> dict:
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading files_db.json: {e}")
    return {}

def save_file_record(msg_id: int, file_data: dict):
    try:
        db = load_files_db()
        db[str(msg_id)] = file_data
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving file record {msg_id}: {e}")

def delete_file_record(msg_id: int):
    try:
        db = load_files_db()
        if str(msg_id) in db:
            del db[str(msg_id)]
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(db, f, indent=2)
    except Exception as e:
        logger.error(f"Error deleting file record {msg_id}: {e}")
