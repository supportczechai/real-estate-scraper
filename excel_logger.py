import os
import openpyxl
from datetime import datetime

EXCEL_FILE = "leads.xlsx"

def log_lead_to_excel(source: str, prop_type: str, keyword: str, text_snippet: str, url: str):
    file_exists = os.path.exists(EXCEL_FILE)

    if not file_exists:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Leady"
        ws.append(["Datum a čas", "Zdroj", "Typ nemovitosti", "Klíčová slova", "Text inzerátu", "Odkaz na inzerát"])
        wb.save(EXCEL_FILE)

    try:
        wb = openpyxl.load_workbook(EXCEL_FILE)
        ws = wb.active
        now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        clean_snippet = str(text_snippet).replace("\n", " ")[:500]
        ws.append([now, source, prop_type, keyword, clean_snippet, url])
        wb.save(EXCEL_FILE)
    except Exception as e:
        print(f"    [!] Chyba zápisu do Excelu: {e}")