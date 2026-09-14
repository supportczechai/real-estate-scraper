import json
import os

DB_FILE = "processed_ids.json"

def load_processed_ids() -> set:
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_processed_id(item_id: str):
    ids = load_processed_ids()
    ids.add(str(item_id))
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(list(ids), f, ensure_ascii=False, indent=2)