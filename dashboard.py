import os
import time
from flask import Flask, render_template_string
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from playwright.sync_api import sync_playwright

app = Flask(__name__)

# Konfigurace Telegramu z proměnných prostředí nebo natvrdo
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "TVUJ_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "TVUJ_CHAT_ID")
DATA_FILE = "leads.csv"

def send_telegram_notification(message):
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "TVUJ_TELEGRAM_TOKEN":
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("Chyba při odesílání na Telegram:", e)

def is_valid_buyer_lead(text):
    """
    Filtrační funkce: Vrátí True POUZE pokud jde o kupce.
    Okamžitě zahodí jakékoliv zmínky o pronájmu nebo podnájmu.
    """
    if not text:
        return False
        
    text_lower = text.lower()
    
    # 1. Seznam zakázaných slov (pronájmy ignorujeme)
    rental_keywords = [
        "pronájem", "pronajmout", "podnájem", "k pronájmu", 
        "pronajmu", "pronajmeme", "pronájmu", "pronajímám", 
        "hledám pronájem", "podnájmu", "nájemci", "nájem"
    ]
    for word in rental_keywords:
        if word in text_lower:
            return False
            
    # 2. Seznam klíčových slov pro koupi/poptávku
    purchase_keywords = [
        "koupím", "koupit", "koupi", "ke koupi", "koupíme", 
        "sháním dům", "sháním byt", "hledám dům", "hledám byt", 
        "hledám pozemek", "koupím pozemek", "vlastní bydlení", 
        "investiční byt", "koupím nemovitost"
    ]
    
    # Ověříme, zda text obsahuje alespoň jedno nákupní slovo
    has_purchase_intent = any(kw in text_lower for kw in purchase_keywords)
    
    return has_purchase_intent

def run_scraper():
    print("[+] Spouštím automatický skraper (filtrování pouze kupců)...")
    new_leads = []
    
    try:
        with sync_playwright() as p:
            # Spuštění headless prohlížeče v cloudu
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Tady probíhá tvoje skenování webů / skupin
            # Příklad:
            # page.goto("https://www.tvuj-zdroj-inzeratu.cz")
            # posts = page.locator(".inzerat").all_text_contents()
            # 
            # Pro ukázku si představíme zpracování textu inzerátu:
            # post_text = "Hledám ke koupi rodinný dům v Praze"
            # 
            # if is_valid_buyer_lead(post_text):
            #     new_leads.append({"text": post_text, "source": "Facebook / Web"})
            #     send_telegram_notification(f"🏠 *Nový zájemce o koupi!*\n\n{post_text}")
            
            browser.close()
    except Exception as e:
        print(f"[!] Chyba při běhu skraperu: {e}")

    # Uložení nalezených leadů do CSV souboru
    if new_leads:
        df_new = pd.DataFrame(new_leads)
        if os.path.exists(DATA_FILE):
            df_old = pd.read_csv(DATA_FILE)
            df_final = pd.concat([df_old, df_new]).drop_duplicates()
        else:
            df_final = df_new
        df_final.to_csv(DATA_FILE, index=False)
        print(f"[+] Úspěšně uloženo {len(new_leads)} nových kupců.")

# HTML rozhraní dashboardu
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="UTF-8">
    <title>Realitní CRM Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; background: #0f111a; color: #f1f1f1; margin: 0; padding: 20px; }
        h1 { color: #38bdf8; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; background: #1e293b; }
        th, td { padding: 12px; border: 1px solid #334155; text-align: left; }
        th { background: #0284c7; color: white; }
        tr:nth-child(even) { background: #1e293b; }
        tr:nth-child(odd) { background: #0f172a; }
        .badge { background: #22c55e; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; }
        .info-box { background: #1e293b; padding: 15px; border-radius: 8px; border-left: 4px solid #38bdf8; margin-bottom: 20px; }
    </style>
</head>
<body>
    <h1>📊 Realitní CRM Dashboard</h1>
    <div class="info-box">
        <p>🟢 Systém běží 24/7 v cloudu na Railway. Automaticky filtruje pronájmy a ukládá pouze zájemce o koupi.</p>
    </div>
    
    <h2>Seznam poptávek (Kupci)</h2>
    <table>
        <tr>
            <th>Text poptávky / Inzerátu</th>
            <th>Zdroj</th>
        </tr>
        {% for index, row in leads.iterrows() %}
        <tr>
            <td>{{ row.get('text', 'Žádný text') }}</td>
            <td><span class="badge">{{ row.get('source', 'Neznámý') }}</span></td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""

@app.route("/")
def index():
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
    else:
        # Výchozí ukázkový řádek, pokud soubor ještě neexistuje
        df = pd.DataFrame([
            {"text": "Ukázkový zájemce: Hledám ke koupi stavební pozemek.", "source": "Systém"}
        ])
    return render_template_string(HTML_TEMPLATE, leads=df)

# Spuštění plánovače na pozadí (spustí skraper automaticky každých 8 hodin / 3x denně)
scheduler = BackgroundScheduler()
scheduler.add_job(func=run_scraper, trigger="interval", hours=8)
scheduler.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)