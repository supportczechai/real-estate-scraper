import asyncio
import random
import re
import unicodedata
import urllib.parse
from playwright.async_api import async_playwright
from config import FB_GROUPS, DEMAND_KEYWORDS, USER_DATA_DIR
from telegram_bot import send_telegram_message
from db import load_processed_ids, save_processed_id
from excel_logger import log_lead_to_excel

def strip_accents(text: str) -> str:
    if not text:
        return ""
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

def clean_text(raw_text: str) -> str:
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
    ignore_words = {
        "facebook", "líbí se mi", "to se mi líbí", "komentovat", 
        "sdílet", "sdílejte", "napsat komentář...", "všechny komentáře",
        "zobrazit další komentáře", "sledovat", "připojit se ke skupině",
        "answer as adam", "napsat odpověď..."
    }
    return "\n".join([line for line in lines if line.lower() not in ignore_words and not line.startswith("Answer as")])

async def get_fb_link_or_profile(article, group_url) -> str:
    try:
        links = await article.locator('a[href]').all()
        for link in links:
            href = await link.get_attribute("href")
            if not href:
                continue
            if href.startswith("/"):
                full_href = f"https://www.facebook.com{href}"
            elif href.startswith("http"):
                full_href = href
            else:
                continue

            if any(ind in full_href for ind in ["/posts/", "/permalink/", "story_fbid", "multi_permalinks", "pfbid"]):
                if "?" in full_href:
                    return full_href.split("?")[0]
                return full_href

        for link in links:
            href = await link.get_attribute("href")
            if not href:
                continue
            if "profile.php" in href or "/user/" in href or ("/groups/" not in href and "/permalink/" not in href and "marketplace" not in href and len(href) > 15):
                if href.startswith("/"):
                    return f"https://www.facebook.com{href}"
                elif href.startswith("http"):
                    return href
    except Exception:
        pass
    return group_url

# ==================== BAZOŠ SCRAPER ====================
async def scrape_bazos():
    print("\n[+] Spouštím hloubkové skenování Bazoš.cz...")
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

        search_terms = ["sháním byt", "koupím byt", "hledám byt", "sháním dům", "koupím dům", "hledám pozemek", "koupím"]
        
        for term in search_terms:
            encoded_term = urllib.parse.quote(term)
            url = f"https://reality.bazos.cz/hledat.php?hledat={encoded_term}&rubriky=reality"
            
            try:
                res = await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                if not res or res.status != 200:
                    continue
                
                await asyncio.sleep(1)
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

                        log_lead_to_excel("Bazoš", prop_type, term, full_text, full_link)

                        copy_outreach_msg = (
                            f"Dobrý den, narazil jsem na váš inzerát na Bazoši, že sháníte {prop_type}.\n\n"
                            "V Hypostars.cz spojujeme náš AI systém s týmem vyjednavačů. "
                            "Kupujícím pomáháme hledat nemovitosti, srážet jejich kupní cenu u makléřů a řešit nejlepší hypotéku.\n\n"
                            "Fungujeme bez rizika – neplatíte nic předem a naši odměnu tvoří jen část z peněz, které vám reálně ušetříme z ceny.\n\n"
                            f"Mám vám sem hodit 2-3 tipy na {prop_type}, nebo už máte vytipovanou konkrétní nemovitost a chcete na ní spíš pomoct srazit cenu?"
                        )

                        msg = (
                            "🎯 *POPTÁVKA (BAZOŠ)*\n"
                            "━━━━━━━━━━━━━━━━━━━━━\n"
                            f"🏷 *Hledaný výraz:* `{term}`\n"
                            f"🏠 *Typ nemovitosti:* `{prop_type}`\n\n"
                            "💬 *Text inzerátu:*\n"
                            f"_{safe_snippet}_\n\n"
                            "📋 *ZPRÁVA KE ZKOPÍROVÁNÍ:*\n"
                            f"`{copy_outreach_msg}`\n\n"
                            f"🔗 [👉 OTEVŘÍT INZERÁT]({full_link})\n"
                            "━━━━━━━━━━━━━━━━━━━━━"
                        )

                        print(f"    [✅] BAZOŠ POPTÁVKA: {title_text[:40]}...")
                        send_telegram_message(msg)
                        await asyncio.sleep(0.3)

                    except Exception:
                        continue
            except Exception as e:
                print(f"    [!] Bazoš chyba pro výraz '{term}': {e}")

        await browser.close()
    print(f"[+] Bazoš dokončen: Odesláno {found_count} leadů.")

# ==================== ANNONCE SCRAPER ====================
async def scrape_annonce():
    print("\n[+] Spouštím vyhledávání na Annonce.cz...")
    processed_ids = load_processed_ids()
    sent_count = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for keyword in DEMAND_KEYWORDS[:3]:
            encoded_kw = urllib.parse.quote(keyword)
            # Opravená realitní/hlavní cesta pro Annonci, aby nevracela 404
            search_url = f"https://www.annonce.cz/reality/{encoded_kw}.html"

            try:
                response = await page.goto(search_url, timeout=30000)
                if response and response.status >= 400:
                    # Alternativní fallback vyhledávání
                    search_url = f"https://www.annonce.cz/s/hledat?q={encoded_kw}"
                    response = await page.goto(search_url, timeout=30000)
                    if response and response.status >= 400:
                        continue

                await asyncio.sleep(2)
                items = await page.locator('.c-item-list__item, .inzerat-item, article, .item').all()
                
                for item in items:
                    try:
                        text = await item.inner_text()
                        link_elem = item.locator('a[href]').first
                        if await link_elem.count() == 0:
                            continue
                        link = await link_elem.get_attribute("href")
                        
                        norm_text = strip_accents(text)
                        if any(w in norm_text for w in ["shanim", "hledam", "koupim"]):
                            post_url = f"https://www.annonce.cz{link}" if link.startswith("/") else link
                            post_hash = str(hash(post_url))

                            if post_hash in processed_ids:
                                continue

                            save_processed_id(post_hash)
                            processed_ids.add(post_hash)
                            sent_count += 1

                            prop_type = detect_property_type(norm_text)
                            safe_snippet = sanitize_markdown(text[:300])

                            copy_outreach_msg = (
                                f"Dobrý den, narazil jsem na váš inzerát, že sháníte {prop_type}.\n\n"
                                "V Hypostars.cz spojujeme náš AI systém s týmem vyjednavačů. Pomáháme kupujícím hledat nemovitosti a srážet cenu.\n\n"
                                f"Mám vám poslat tipy na {prop_type}?"
                            )

                            msg = (
                                "🎯 *POPTÁVKA (ANNONCE)*\n"
                                "━━━━━━━━━━━━━━━━━━━━━\n"
                                f"🏷 *Hledáno:* `{keyword}`\n"
                                f"💬 *Text:* _{safe_snippet}_\n\n"
                                f"🔗 [👉 OTEVŘÍT NA ANNONCI]({post_url})\n"
                                "━━━━━━━━━━━━━━━━━━━━━"
                            )
                            send_telegram_message(msg)
                            print(f"    [✅ ANNONCE] Nalezen lead!")
                    except Exception:
                        continue
            except Exception as e:
                print(f"    [!] Annonce chyba: {e}")

        await browser.close()
    print(f"[+] Annonce dokončena: Odesláno {sent_count} leadů.")

# ==================== FACEBOOK SCRAPER ====================
async def scrape_facebook_groups():
    print("\n[+] Spouštím hloubkové skenování Facebook skupin...")
    processed_ids = load_processed_ids()
    norm_demands = list(set([strip_accents(kw) for kw in DEMAND_KEYWORDS]))
    OFFER_STARTS = ["prodam", "nabizim", "k pronajmu", "pronajmu", "drazba", "exkluzivni prodej", "developersky projekt", "nabidka"]

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
            viewport={"width": 1366, "height": 900},
            args=["--disable-notifications", "--disable-blink-features=AutomationControlled", "--no-sandbox"],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"
        )

        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

        try:
            await page.goto("https://www.facebook.com", wait_until="domcontentloaded", timeout=60000)
        except Exception:
            pass

        await asyncio.sleep(3)

        if "login" in page.url or await page.locator("input[name='email']").count() > 0:
            print("\n[!] Přihlas se ručně na FB a po přihlášení stiskni ENTER v terminálu...")
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, input)

        for group_url in FB_GROUPS:
            if page.is_closed():
                break

            print(f"\n  [~] Skenuji FB Skupinu: {group_url}")
            try:
                target_url = group_url if "?" in group_url else f"{group_url}?sorting_setting=CHRONOLOGICAL"
                await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(random.uniform(4, 6))

                await page.keyboard.press("Escape")

                for _ in range(6):
                    await page.keyboard.press("PageDown")
                    await asyncio.sleep(random.uniform(1.2, 1.8))

                articles = await page.locator('div[role="feed"] > div, div[role="article"]').all()
                found_in_group = 0

                for article in articles:
                    try:
                        raw_text = await article.inner_text()
                        cleaned_text = clean_text(raw_text)

                        if not cleaned_text or len(cleaned_text) < 15:
                            continue

                        normalized_text = strip_accents(cleaned_text)
                        
                        matched_demands = [kw for kw in norm_demands if kw in normalized_text]
                        starts_as_offer = any(normalized_text.startswith(start) for start in OFFER_STARTS)

                        if starts_as_offer:
                            continue

                        if matched_demands:
                            post_hash = str(hash(cleaned_text[:150]))

                            if post_hash in processed_ids:
                                continue

                            post_url = await get_fb_link_or_profile(article, group_url)
                            
                            save_processed_id(post_hash)
                            save_processed_id(post_url)
                            processed_ids.add(post_hash)

                            found_in_group += 1

                            safe_snippet = sanitize_markdown(cleaned_text[:350])
                            kw_formatted = ", ".join([f"`{kw}`" for kw in matched_demands[:3]])
                            prop_type = detect_property_type(normalized_text)

                            log_lead_to_excel("Facebook", prop_type, ", ".join(matched_demands[:3]), cleaned_text, post_url)

                            copy_outreach_msg = (
                                f"Dobrý den, narazil jsem na váš příspěvek, že sháníte {prop_type}.\n\n"
                                "V Hypostars.cz spojujeme náš AI systém s týmem vyjednavačů. "
                                "Kupujícím pomáháme hledat nemovitosti, srážet jejich kupní cenu u makléřů a řešit nejlepší hypotéku.\n\n"
                                "Fungujeme bez rizika – neplatíte nic předem a naši odměnu tvoří jen část z peněz, které vám reálně ušetříme z ceny.\n\n"
                                f"Mám vám sem do zprávy hodit 2-3 tipy na {prop_type}, nebo už máte vytipovanou konkrétní nemovitost a chcete na ní spíš pomoct srazit cenu?"
                            )

                            msg = (
                                "🎯 *POPTÁVKA (FACEBOOK)*\n"
                                "━━━━━━━━━━━━━━━━━━━━━\n"
                                f"🏷 *Klíčové slovo:* {kw_formatted}\n"
                                f"🏠 *Typ nemovitosti:* `{prop_type}`\n\n"
                                "💬 *Text inzerátu:*\n"
                                f"_{safe_snippet}_\n\n"
                                "📋 *ZPRÁVA KE ZKOPÍROVÁNÍ:*\n"
                                f"`{copy_outreach_msg}`\n\n"
                                f"🔗 [👉 OTEVŘÍT PŘÍSPĚVEK / PROFIL NA FB]({post_url})\n"
                                "━━━━━━━━━━━━━━━━━━━━━"
                            )

                            print(f"    [✅] ÚSPĚCH! Odesílám lead na Telegram: {post_url}")
                            send_telegram_message(msg)
                            await asyncio.sleep(1)

                    except Exception:
                        continue

                print(f"  [📊] Z této skupiny odesláno leadů: {found_in_group}")

            except Exception as e:
                print(f"  [!] Chyba při procházení skupiny: {e}")

        if not page.is_closed():
            await context.close()
    print("[+] Skenování Facebook skupin dokončeno.")