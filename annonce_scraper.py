import asyncio
import unicodedata
from playwright.async_api import async_playwright
from telegram_bot import send_telegram_message
from db import load_processed_ids, save_processed_id
from excel_logger import log_lead_to_excel

def strip_accents(text: str) -> str:
    text = unicodedata.normalize('NFKD', text)
    return ''.join([c for c in text if not unicodedata.combining(c)]).lower()

def sanitize_markdown(text: str) -> str:
    for char in ['*', '_', '`', '[']:
        text = text.replace(char, '')
    return text.strip()

def detect_property_type(normalized_text: str) -> str:
    if any(w in normalized_text for w in ["byt", "1kk", "2kk", "3kk", "4kk", "1+1", "2+1", "3+1", "4+1", "garsonk"]):
        return "byt"
    elif any(w in normalized_text for w in ["dum", "domu", "domka", "barak"]):
        return "dům"
    elif any(w in normalized_text for w in ["pozemek", "parcel", "zahrad"]):
        return "pozemek"
    elif any(w in normalized_text for w in ["chatu", "chata"]):
        return "chatu"
    return "nemovitost"

async def scrape_annonce(max_pages=5):
    print(f"\n[+] Spouštím skenování POPTÁVEK na Annonce.cz...")
    found_count = 0
    processed_ids = load_processed_ids()
    
    # Stabilní vyhledávací URL pro reality poptávky na Annonce
    base_url = "https://www.annonce.cz/hledani/"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36",
            locale="cs-CZ"
        )
        page = await context.new_page()

        for page_num in range(1, max_pages + 1):
            if page_num == 1:
                url = f"{base_url}?q=poptavka+reality&rubrika=10"
            else:
                url = f"{base_url}?q=poptavka+reality&rubrika=10&strana={page_num}"

            try:
                res = await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                if not res or res.status != 200:
                    print(f"    [!] Annonce str. {page_num} vrátila status: {res.status if res else 'None'}")
                    continue
            except Exception as e:
                print(f"    [!] Chyba při načítání Annonce str. {page_num}: {e}")
                continue

            items = await page.locator(".item-title a, .inzerat-head a, h2 a, .result-item a").all()
            
            if not items:
                print(f"    [!] Annonce str. {page_num}: Nenalezeny žádné inzeráty (možná změna selektoru).")
                break

            for item in items:
                try:
                    title_text = await item.inner_text()
                    href = await item.get_attribute("href")
                    
                    if not href or not title_text or len(title_text.strip()) < 5:
                        continue

                    full_link = f"https://www.annonce.cz{href}" if href.startswith("/") else href
                    
                    if href in processed_ids or full_link in processed_ids:
                        continue

                    normalized_text = strip_accents(title_text)

                    save_processed_id(href)
                    save_processed_id(full_link)
                    processed_ids.add(href)
                    processed_ids.add(full_link)

                    found_count += 1
                    prop_type = detect_property_type(normalized_text)
                    safe_snippet = sanitize_markdown(title_text[:350])

                    log_lead_to_excel("Annonce Poptávka", prop_type, "Poptávka", title_text, full_link)

                    copy_outreach_msg = (
                        f"Dobrý den, narazil jsem na váš inzerát na Annonce, že sháníte {prop_type}.\n\n"
                        "V Hypostars.cz spojujeme náš AI systém z CzechAI.io (který 24/7 skenuje trh i neveřejné nabídky) s týmem vyjednavačů. "
                        "Kupujícím pomáháme hledat nemovitosti, srážet jejich kupní cenu u makléřů a řešit nejlepší hypotéku.\n\n"
                        "Fungujeme bez rizika – neplatíte nic předem a naši odměnu tvoří jen část z peněz, které vám reálně ušetříme z ceny.\n\n"
                        f"Mám vám sem hodit 2-3 tipy na {prop_type}, nebo už máte vytipovanou konkrétní nemovitost a chcete na ní spíš pomoct srazit cenu?"
                    )

                    msg = (
                        "🎯 *POPTÁVKA (ANNONCE)*\n"
                        "━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🏠 *Typ nemovitosti:* `{prop_type}`\n\n"
                        "💬 *Text inzerátu:*\n"
                        f"_{safe_snippet}_\n\n"
                        "📋 *ZPRÁVA KE ZKOPÍROVÁNÍ (Klepni na text):*\n"
                        f"`{copy_outreach_msg}`\n\n"
                        "🔗 [👉 OTEVŘÍT INZERÁT]({full_link})\n"
                        "━━━━━━━━━━━━━━━━━━━━━"
                    )

                    print(f"    [✅] ANNONCE POPTÁVKA: {title_text[:40]}...")
                    send_telegram_message(msg)
                    await asyncio.sleep(0.3)

                except Exception:
                    continue

        await browser.close()
    print(f"[+] Annonce dokončena: Odesláno {found_count} leadů.")