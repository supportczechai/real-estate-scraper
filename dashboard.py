import os
import time
from flask import Flask, render_template_string
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from playwright.sync_api import sync_playwright

app = Flask(__name__)

# Konfigurace Telegramu (pokud máš token/chat ID, můžeš je zapsat sem nebo nechat v proměnných prostředí)
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
    STRICTNÍ FILTR: Vrací True POUZE pokud jde o koupi. 
    Jakmile text obsahuje cokoliv o pronájmu, okamžitě a bez výjimky zahodí.
    """
    if not text:
        return False
        
    text_lower = text.lower()
    
    # 1. Zakázaná slova - jakmile zazní cokoli o nájmu, končíme (False)
    rental_keywords = [
        "pronájem", "pronajmout", "podnájem", "k pronájmu", 
        "pronajmu", "pronajmeme", "pronájmu", "pronajímám", 
        "hledám pronájem", "podnájmu", "nájemci", "nájem", 
        "pronajímá se", "hledám podnájem", "neplatí provizi"
    ]
    for word in rental_keywords:
        if word in text_lower:
            return False  # Je to pronájem -> NECHCEME
            
    # 2. Povolovací slova - text MUSÍ obsahovat nákupní záměr
    purchase_keywords = [
        "koupím", "koupit", "koupi", "ke koupi", "koupíme", 
        "sháním dům", "sháním byt", "hledám dům", "hledám byt", 
        "hledám pozemek", "koupím pozemek", "vlastní bydlení", 
        "investiční byt", "koupím nemovitost", "koupím chatu",
        "koupím stavební parcelu", "koupím byt v"
    ]
    
    # Zkontrolujeme, zda text obsahuje alespoň jedno kupní slovo
    has_purchase_intent = any(kw in text_lower for kw in purchase_keywords)
    
    return has_purchase_intent

def run_scraper():
    print("[+] Spouštím skraper s přísným filtrem na kupce...")
    new_leads = []
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Tady probíhá samotné stahování inzerátů (např. z Facebooku / skupin / Annonce)
            # Příklad pro ukázku:
            # page.goto("https://www.facebook.com/groups/...")
            # posts = page.locator(".entry").all_text_contents()
            #
            # Pro každý nalezený text inzerátu (nazveme ho třeba raw_text) provedeme filtr:
            # if is_valid_buyer_lead(raw_text):
            #     new_leads.append({"text": raw_text, "source": "Facebook"})
            #     send_telegram_notification(f"🏠 *Nový zájemce o koupi!*\n\n{raw_text}")
            
            browser.close()
    except Exception as e:
        print(f"[!] Chyba při skenování: {e}")

    # Uložení platných kupců do CSV
    if new_leads:
        df_new = pd.DataFrame(new_leads)
        if os.path.exists(DATA_FILE):
            df_old = pd.read_csv(DATA_FILE)
            df_final = pd.concat([df_old, df_new]).drop_duplicates()
        else:
            df_final = df_new
        df_final.to_csv(DATA_FILE, index=False)
        print(f"[+] Uloženo {len(new_leads)} nových kupců.")

# HTML vzhled webového dashboardu
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="UTF-8">
    <title>Realitní CRM - Pouze Kupci</title>
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
    <h1>📊 Realitní CRM Dashboard (Filtrováno: Pouze Kupci)</h1>
    <div class="info-box">
        <p>🟢 Systém běží 24/7 v cloudu. Pronájmy jsou kompletně blokovány, ukládají se a hlásí se pouze zájemci o koupi.</p>
    </div>
    
    <h2>Seznam poptávek</h2>
    <table>
        <tr>
            <th>Text inzerátu / Poptávky</th>
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
        # Výchozí ukázkový řádek, pokud soubor ještě prázdný
        df = pd.DataFrame([
            {"text": "Ukázkový lead: Hledám ke koupi rodinný dům se zahradou.", "source": "Systém (Filtrováno)"}
        ])
    return render_template_string(HTML_TEMPLATE, leads=df)

# Automatický plánovač na pozadí (spustí skraper každých 6 hodin)
scheduler = BackgroundScheduler()
scheduler.add_job(func=run_scraper, trigger="interval", hours=6)
scheduler.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)