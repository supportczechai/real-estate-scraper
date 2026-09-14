import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8959387983:AAEDIJAco1Db7dOOTRWORLVCCYXo8MjR1mc")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1732988572")

USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "fb_user_data")

DEMAND_KEYWORDS = [
    "koupím", "koupim", "hledám", "hledam", "sháním", "shanim", 
    "poptávám", "poptavam", "poptávka", "poptavka", "koupíme", "koupime",
    "mám zájem", "mam zajem", "hledáme", "hledame", "odkup", "odkoupim",
    "poptavam byt", "koupim byt", "shanim byt", "koupim dum", "shanim dum"
]

FB_GROUPS = [
    "https://www.facebook.com/groups/1399191310329117",
    "https://www.facebook.com/groups/830134260424064",
    "https://www.facebook.com/groups/253347711682148",
    "https://www.facebook.com/groups/1558511207695874",
    "https://www.facebook.com/groups/123180986382772"
]