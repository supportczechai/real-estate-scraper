import os
import time
import threading
import requests
import pandas as pd
from flask import Flask, render_template_string
from playwright.sync_api import sync_playwright

app = Flask(__name__)

# --- TVOJE NASTAVENÍ ---
TELEGRAM_TOKEN = "8959387983:AAEDIJAco1Db7dOOTRWORLVCCYXo8MjR1mcT"
TELEGRAM_CHAT_ID = "1732988572"

FACEBOOK_SKUPINY = [
    "https://www.facebook.com/groups/253347711682148",
    "https://www.facebook.com/groups/830134260424064",
    "https://www.facebook.com/groups/123180986382772",
    "https://www.facebook.com/groups/1558511207695874",
    "https://www.facebook.com/groups/1399191310329117",
    "https://www.facebook.com/groups/999404481313519"
]

DATA_FILE = "leads.csv"

# Globální paměť pro web (aby se to ukazovalo hned)
scraped_leads = []

# Načtení historie ze souboru při startu (aby tam zůstaly i po restartu)
if os.path.exists(DATA_FILE):
    try:
        df_old = pd.read_csv(DATA_FILE)
        scraped_leads = df_old.to_dict('records')
    except:
        pass

def filtrovat_jen_koupi(text):
    if not text: 
        return False
    text_lower = text.lower()
    
    # ZAKÁZANÁ SLOVA (odpad)
    zakazana_slova = ["prodám", "nabízím", "pronajmu", "odstoupím", "k pronájmu", "pronájem", "podnájem", "provize", "pronajímám", "k prodeji"]
    for slovo in zakazana_slova:
        if slovo in text_lower:
            return False
            
    # POVOLENÁ SLOVA (to co chceme)
    klicova_slova = ["koupím", "hledám ke koupi", "koupíme", "sháním", "poptávám", "hledáme ke koupi", "hledám byt", "hledám dům", "koupit"]
    for slovo in klicova_slova:
        if slovo in text_lower:
            return True
            
    return False

def odeslat_na_telegram(autor, autor_url, text, prispevek_url):
    msg = (
        f"🚨 <b>Nová poptávka - KOUPĚ!</b>\n\n"
        f"👤 <b>Od:</b> <a href='{autor_url}'>{autor}</a>\n"
        f"📝 <b>Text:</b> <i>{text[:300]}...</i>\n\n"
        f"🔗 <a href='{prispevek_url}'>Odkaz na příspěvek</a>"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"})
    except Exception as e:
        print(f"Chyba při odesílání na Telegram: {e}")

def run_scraper():
    print("[+] Spouštím skraper Facebook skupin...")
    novi_zajemci = []
    
    try:
        with sync_playwright() as p:
            # Spuštění prohlížeče (headless pro server)
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            for group_url in FACEBOOK_SKUPINY:
                try:
                    print(f"[*] Projíždím: {group_url}")
                    page.goto(group_url)
                    time.sleep(5) # Čekání na načtení
                    
                    # Najde všechny bloky příspěvků na stránce
                    prispevky_elementy = page.locator("div[role='feed'] > div").all()
                    
                    for element in prispevky_elementy:
                        try:
                            # Získání textu
                            text_element = element.locator("div[data-ad-preview='message']")
                            if text_element.count() > 0:
                                post_text = text_element.first.inner_text()
                            else:
                                post_text = element.inner_text()

                            if not post_text:
                                continue

                            # Filtrujeme POUZE KOUPI
                            if filtrovat_jen_koupi(post_text):
                                odkazy = element.locator("a[role='link']").all()
                                
                                autor = "Neznámý autor"
                                autor_url = group_url
                                prispevek_url = group_url 

                                if len(odkazy) > 0:
                                    # Vydolování autora a odkazů z HTML Facebooku
                                    autor = odkazy[0].inner_text()
                                    if not autor.strip() and len(odkazy) > 1:
                                        autor = odkazy[1].inner_text()
                                        
                                    for link in odkazy:
                                        href = link.get_attribute("href")
                                        if href:
                                            if "user" in href or "profile" in href:
                                                autor_url = href
                                            if "/posts/" in href or "/permalink/" in href:
                                                prispevek_url = href

                                if autor_url.startswith("/"): autor_url = "https://www.facebook.com" + autor_url
                                if prispevek_url.startswith("/"): prispevek_url = "https://www.facebook.com" + prispevek_url

                                lead = {
                                    "autor": autor.replace("\n", " "),
                                    "autor_url": autor_url,
                                    "text": post_text,
                                    "prispevek_url": prispevek_url
                                }
                                
                                # Zabránit duplicitám, aby ti to nechodilo dvakrát
                                if not any(l.get("text") == post_text for l in scraped_leads) and lead not in novi_zajemci:
                                    novi_zajemci.append(lead)
                                    odeslat_na_telegram(lead["autor"], lead["autor_url"], post_text, lead["prispevek_url"])

                        except Exception:
                            pass 
                            
                except Exception as group_err:
                    print(f"[!] Chyba ve skupině {group_url}: {group_err}")
            
            browser.close()
            
            # Uložíme nové leady do paměti a do souboru
            if novi_zajemci:
                scraped_leads.extend(novi_zajemci)
                df = pd.DataFrame(scraped_leads)
                df.drop_duplicates(subset=["text"], inplace=True)
                df.to_csv(DATA_FILE, index=False)
                print(f"[+] Uloženo {len(novi_zajemci)} nových kupců.")
                
    except Exception as e:
        print(f"[!] Hlavní chyba Playwrightu: {e}")

def skraper_na_pozadi():
    """Tohle běží 3x denně (každých 8 hodin) bez blokování webu"""
    while True:
        run_scraper()
        print("Čekám 8 hodin do dalšího spuštění...")
        time.sleep(28800) # 8 hodin

@app.route('/')
def index():
    html = """
    <!DOCTYPE html>
    <html lang="cs">
    <head>
        <meta charset="UTF-8">
        <title>Leady - Koupě</title>
        <style>
            body { font-family: Arial, sans-serif; background: #f4f4f9; padding: 20px; }
            h2 { color: #333; }
            table { width: 100%; border-collapse: collapse; background: #fff; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
            th, td { padding: 12px; border: 1px solid #ddd; text-align: left; }
            th { background: #007bff; color: white; }
            a { color: #007bff; text-decoration: none; font-weight: bold; }
            a:hover { text-decoration: underline; }
            .leady-text { white-space: pre-wrap; font-size: 14px; }
        </style>
    </head>
    <body>
        <h2>🏠 Zachycené poptávky - Koupě nemovitostí</h2>
        <table>
            <tr>
                <th>Autor</th>
                <th>Text příspěvku</th>
                <th>Odkaz</th>
            </tr>
            {% for lead in leads %}
            <tr>
                <td><a href="{{ lead['autor_url'] }}" target="_blank">{{ lead['autor'] }}</a></td>
                <td class="leady-text">{{ lead['text'] }}</td>
                <td><a href="{{ lead['prispevek_url'] }}" target="_blank">Otevřít na FB</a></td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    """
    # Prohodíme pořadí, ať jsou nejnovější na webu nahoře
    return render_template_string(html, leads=reversed(scraped_leads))

# Bezpečně nastartujeme vlákno pro skraper
t = threading.Thread(target=skraper_na_pozadi, daemon=True)
t.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))