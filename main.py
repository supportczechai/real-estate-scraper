import asyncio
from bazos_scraper import scrape_bazos
from annonce_scraper import scrape_annonce
from scraper import scrape_facebook_groups

async def main():
    print("🚀 START MULTI-SOURCE MONITORINGU POPTÁVEK\n")
    
    # Bazoš - 15 stránek do hloubky
    try:
        await scrape_bazos(max_pages=15)
    except Exception as e:
        print(f"[!] Chyba při skenování Bazoš: {e}")

    # Annonce - 10 stránek do hloubky
    try:
        await scrape_annonce(max_pages=10)
    except Exception as e:
        print(f"[!] Chyba při skenování Annonce: {e}")

    # Facebook Skupiny
    try:
        await scrape_facebook_groups()
    except Exception as e:
        print(f"[!] Chyba při skenování Facebooku: {e}")

    print("\n✅ HOTOVO: Kompletní kontrola dokončena.")

if __name__ == "__main__":
    asyncio.run(main())