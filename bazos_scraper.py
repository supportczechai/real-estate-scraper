import asyncio
import re
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
    elif any(w in normalized_text for w in ["dum", "domu", "domka", "barak", "chalup"]):
        return "dům"
    elif any(w in normalized_text for w in ["pozemek", "parcel", "zahrad"]):
        return "pozemek"
    elif any(w in normalized_text for w in ["chatu", "chata"]):
        return "chatu"
    return "nemovitost"

async def scrape_bazos(max_pages=3):
    print(f"\n[+] Spouštím skenování Bazoš.cz...")
    found_count = 0
    processed_ids = load_processed_ids()

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

        url = "https://reality.bazos.cz/"
        try:
            res = await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            if not res or res.status != 200:
                print(f"    [!] Bazoš vrátil status: {res.status if res else 'None'}")
                await browser.close()
                return
        except Exception as e:
            print(f"    [!] Chyba při načítání Bazoš: {e}")
            await browser.close()
            return

        listings = await page.locator(".inzeraty").all()

        for listing in listings:
            try:
                title_elem = listing.locator(".inzeratynadpis a").first
                if await title_elem.count() == 0:
                    continue

                title_text = await title_elem.inner_text()
                href = await title_elem.get_attribute("href")
                if not href:
                    continue

                desc_elem = listing.locator(".popis")
                desc_text = await desc_elem.inner_text() if await desc_elem.count() > 0 else ""
                
                full_text = f"{title_text} {desc_text}"
                normalized_text = strip_accents(full_text)

                # Hledáme poptávková slova přímo v inzerátech na hlavní stránce reality bazos
                if not any(w in normalized_text for w in ["koupim", "shanim", "poptavam", "koupime", "hledame"]):
                    continue

                full_link = f"https://reality.bazos.cz{href}" if href.startswith("/") else href
                listing_id_match = re.search(r'/inzerat/(\d+)/', full_link)
                item_id = listing_id_match.group(1) if listing_id_match else full_link

                if str(item_id) in processed_ids:
                    continue

                save_processed_id(item_id)
                processed_ids.add(str(item_id))
                found_count += 1
                
                prop_type = detect_property_type(normalized_text)
                safe_snippet = sanitize_markdown(full_text[:350])

                log_lead_to_excel("Bazoš", prop_type, "Poptávka", full_text, full_link)

                copy_outreach_msg = (
                    f"Dobrý den, narazil jsem na váš inzerát na Bazoši, že sháníte {prop_type}.\n\n"
                    "V Hypostars.cz spojujeme náš AI systém z CzechAI.io (který 24/7 skenuje trh i neveřejné nabídky) s týmem vyjednavačů. "
                    "Kupujícím pomáháme hledat nemovitosti, srážet jejich kupní cenu u makléřů a řešit nejlepší hypotéku.\n\n"
                    "Fungujeme bez rizika – neplatíte nic předem a naši odměnu tvoří jen část z peněz, které vám reálně ušetříme z ceny.\n\n"
                    f"Mám vám sem hodit 2-3 tipy na {prop_type}, nebo už máte vytipovanou konkrétní nemovitost a chcete na ní spíš pomoct srazit cenu?"
                )

                msg = (
                    "🎯 *POPTÁVKA (BAZOŠ)*\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🏠 *Typ nemovitosti:* `{prop_type}`\n\n"
                    "💬 *Text inzerátu:*\n"
                    f"_{safe_snippet}_\n\n"
                    "📋 *ZPRÁVA KE ZKOPÍROVÁNÍ (Klepni na text):*\n"
                    f"`{copy_outreach_msg}`\n\n"
                    f"🔗 [👉 OTEVŘÍT INZERÁT]({full_link})\n"
                    "━━━━━━━━━━━━━━━━━━━━━"
                )

                print(f"    [✅] BAZOŠ POPTÁVKA: {title_text[:40]}...")
                send_telegram_message(msg)
                await asyncio.sleep(0.3)

            except Exception:
                continue

        await browser.close()
    print(f"[+] Bazoš dokončen: Odesláno {found_count} leadů.")