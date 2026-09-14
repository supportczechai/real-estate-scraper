import os
import time
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, redirect, render_template_string, request, url_for

# Zkusíme importovat tvůj telegram bot a skraper, pokud existují
try:
    from telegram_bot import posli_zpravu
except ImportError:
    try:
        from telegram_bot import send_telegram_message as posli_zpravu
    except ImportError:
        posli_zpravu = None

try:
    from main import spustit_skraper
except ImportError:
    spustit_skraper = None

app = Flask(__name__)
EXCEL_FILE = "leads.xlsx"


def load_leads():
  if not os.path.exists(EXCEL_FILE):
    return pd.DataFrame(
        columns=[
            "Čas",
            "Zdroj",
            "Typ nemovitosti",
            "Klíčové slovo",
            "Text",
            "Odkaz",
            "Stav",
        ]
    )

  df = pd.read_excel(EXCEL_FILE)
  col_mapping = {}
  for col in df.columns:
    col_lower = col.lower()
    if "čas" in col_lower or "datum" in col_lower:
      col_mapping[col] = "Čas"
    elif "zdroj" in col_lower:
      col_mapping[col] = "Zdroj"
    elif "typ" in col_lower:
      col_mapping[col] = "Typ nemovitosti"
    elif "klíč" in col_lower or "slovo" in col_lower or "hled" in col_lower:
      col_mapping[col] = "Klíčové slovo"
    elif "text" in col_lower:
      col_mapping[col] = "Text"
    elif "odkaz" in col_lower or "url" in col_lower:
      col_mapping[col] = "Odkaz"

  df = df.rename(columns=col_mapping)

  if "Stav" not in df.columns:
    df["Stav"] = "Nenapsáno"
  for col in [
      "Čas",
      "Zdroj",
      "Typ nemovitosti",
      "Klíčové slovo",
      "Text",
      "Odkaz",
      "Stav",
  ]:
    if col not in df.columns:
      df[col] = "-"

  return df


def save_leads(df):
  if "orig_index" in df.columns:
    df = df.drop(columns=["orig_index"])
  df.to_excel(EXCEL_FILE, index=False)


def generate_outreach(prop_type):
  return (
      f"Dobrý den, narazil jsem na váš inzerát/příspěvek, že sháníte"
      f" {prop_type}.\n\nV Hypostars.cz spojujeme náš AI systém s týmem"
      " vyjednavačů. Kupujícím pomáháme hledat nemovitosti, srážet jejich kupní"
      " cenu u makléřů a řešit nejlepší hypotéku.\n\nFungujeme bez rizika –"
      " neplatíte nic předem a naši odměnu tvoří jen část z peněz, které vám"
      f" reálně ušetříme z ceny.\n\nMám vám sem hodit 2-3 tipy na {prop_type},"
      " nebo už máte vytipovanou konkrétní nemovitost a chcete na ní spíš"
      " pomoct srazit cenu?"
  )


# --- AUTOMATICKÝ BACKGROUND SKRAPER (Běží automaticky 3x denně) ---
def background_scraping_job():
  print("[+] Spouštím automatický skraper v cloudu...")
  try:
    if spustit_skraper:
      spustit_skraper()
    else:
      os.system("python main.py")
    print("[+] Automatický sběr dat dokončen.")
    if posli_zpravu:
      posli_zpravu(
          "🤖 Automatický skraper proběhl a zkontroloval nové inzeráty."
      )
  except Exception as e:
    print(f"[-] Chyba při automatickém skrapování: {e}")


scheduler = BackgroundScheduler()
scheduler.add_job(
    func=background_scraping_job, trigger="interval", hours=8, id="scraping_job"
)
scheduler.start()


# --- HTML ŠABLONA ---
TEMPLATE = """
<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="utf-8">
    <title>Hypostars - Správa Leadů</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f4f6f9; margin: 0; padding: 20px; color: #333; }
        .container { max-width: 1600px; margin: auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
        h1 { color: #1a73e8; margin-top: 0; font-size: 24px; }
        .header-controls { margin: 20px 0; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px; }
        .tabs { display: flex; gap: 10px; }
        .tab { padding: 8px 16px; background: #e1e4e8; color: #333; text-decoration: none; border-radius: 5px; font-weight: 500; font-size: 14px; }
        .tab.active { background: #1a73e8; color: white; }
        .sort-box { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 500; color: #555; }
        .sort-btn { padding: 6px 12px; background: #fff; border: 1px solid #ccc; color: #333; text-decoration: none; border-radius: 5px; font-size: 13px; }
        .sort-btn.active { background: #34a853; color: white; border-color: #34a853; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 14px; border-bottom: 1px solid #e1e4e8; text-align: left; font-size: 13px; vertical-align: top; }
        th { background-color: #1a73e8; color: white; font-weight: 600; }
        tr:hover { background-color: #f8f9fa; }
        .btn { padding: 8px 12px; background: #34a853; color: white; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; font-size: 12px; font-weight: 500; display: inline-block; text-align: center; }
        .btn:hover { opacity: 0.9; }
        .btn-done { background: #9aa0a6; }
        .link-btn { background: #1a73e8; display: block; margin-bottom: 6px; }
        .copy-btn { background: #f9ab00; color: #000; margin-top: 6px; }
        .text-box { max-height: 120px; overflow-y: auto; background: #f1f3f4; padding: 8px; border-radius: 4px; font-size: 12px; white-space: pre-wrap; word-break: break-word; margin-bottom: 6px; }
        .outreach-box { background: #e8f0fe; padding: 8px; border-radius: 4px; font-size: 11px; white-space: pre-wrap; color: #174ea6; margin-top: 4px; border: 1px dashed #aecbfa; }
        .badge-fb { background: #e8f0fe; color: #1a73e8; padding: 3px 6px; border-radius: 4px; font-weight: bold; }
        .badge-bazos { background: #fef7e0; color: #b06000; padding: 3px 6px; border-radius: 4px; font-weight: bold; }
        .badge-annonce { background: #e6f4ea; color: #137333; padding: 3px 6px; border-radius: 4px; font-weight: bold; }
    </style>
    <script>
        function copyText(text, btnElement) {
            navigator.clipboard.writeText(text).then(function() {
                let originalText = btnElement.innerText;
                btnElement.innerText = "✔ Zkopírováno!";
                btnElement.style.background = "#137333";
                btnElement.style.color = "#fff";
                setTimeout(function() {
                    btnElement.innerText = originalText;
                    btnElement.style.background = "#f9ab00";
                    btnElement.style.color = "#000";
                }, 2000);
            }, function(err) {
                alert('Chyba při kopírování: ', err);
            });
        }
    </script>
</head>
<body>
    <div class="container">
        <h1>🚀 Hypostars – Cloudový Dashboard & Skraper</h1>
        <p>Běží automaticky v cloudu 3x denně. Leady ti chodí na Telegram i sem.</p>
        
        <div class="header-controls">
            <div class="tabs">
                <a href="/?sort={{ sort_order }}" class="tab {% if current_filter == 'vse' %}active{% endif %}">Všechny ({{ counts.vse }})</a>
                <a href="/filter/Nenapsáno?sort={{ sort_order }}" class="tab {% if current_filter == 'Nenapsáno' %}active{% endif %}">Nenapsáno ({{ counts.nenapsano }})</a>
                <a href="/filter/Napsáno?sort={{ sort_order }}" class="tab {% if current_filter == 'Napsáno' %}active{% endif %}">Napsáno ({{ counts.napsano }})</a>
            </div>
            
            <div class="sort-box">
                <span>Řazení podle času:</span>
                <a href="?filter_path={{ current_filter }}&sort=desc" class="sort-btn {% if sort_order == 'desc' %}active{% endif %}">↓ Nejnovější</a>
                <a href="?filter_path={{ current_filter }}&sort=asc" class="sort-btn {% if sort_order == 'asc' %}active{% endif %}">↑ Nejstarší</a>
            </div>
        </div>

        <table>
            <tr>
                <th>Čas / Zdroj</th>
                <th>Typ / Hledání</th>
                <th>Text inzerátu</th>
                <th>Hotová zpráva pro klienta</th>
                <th>Odkaz</th>
                <th>Stav / Akce</th>
            </tr>
            {% for index, row in leads.iterrows() %}
            <tr>
                <td>
                    <div style="margin-bottom: 4px; font-weight: bold; color: #555;">{{ row['Čas'] }}</div>
                    <div>
                        {% if 'Facebook' in row['Zdroj']|string %}
                            <span class="badge-fb">Facebook</span>
                        {% elif 'Bazoš' in row['Zdroj']|string %}
                            <span class="badge-bazos">Bazoš</span>
                        {% else %}
                            <span class="badge-annonce">{{ row['Zdroj'] }}</span>
                        {% endif %}
                    </div>
                </td>
                <td>
                    <div style="font-size: 14px; font-weight: bold; color: #1a73e8; margin-bottom: 4px;">{{ row['Typ nemovitosti'] }}</div>
                    <div style="color: #666; font-size: 11px;">Klíč: {{ row['Klíčové slovo'] }}</div>
                </td>
                <td>
                    <div class="text-box">{{ row['Text'] }}</div>
                </td>
                <td>
                    {% set msg = generate_outreach(row['Typ nemovitosti']) %}
                    <div class="outreach-box">{{ msg }}</div>
                    <button class="btn copy-btn" onclick="copyText(`{{ msg | replace('`', '\\`') }}`, this)">📋 Zkopírovat zprávu</button>
                </td>
                <td>
                    <a href="{{ row['Odkaz'] }}" target="_blank" class="btn link-btn">Otevřít inzerát</a>
                </td>
                <td>
                    {% if row['Stav'] == 'Napsáno' %}
                        <div style="color: #137333; font-weight: bold; margin-bottom: 6px;">✔ Napsáno</div>
                        <a href="/status/{{ row['orig_index'] }}/Nenapsáno?filter={{ current_filter }}&sort={{ sort_order }}" class="btn btn-done" style="padding: 4px 8px; font-size:11px;">Vrátit zpět</a>
                    {% else %}
                        <a href="/status/{{ row['orig_index'] }}/Napsáno?filter={{ current_filter }}&sort={{ sort_order }}" class="btn">Označit jako napsáno</a>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </table>
    </div>
</body>
</html>
"""


@app.route("/")
def index():
  status = request.args.get("filter_path", "vse")
  if status not in ["vse", "Nenapsáno", "Napsáno"]:
    status = "vse"
  return render_filtered(status)


@app.route("/filter/<status>")
def filter_status(status):
  return render_filtered(status)


def render_filtered(status_filter):
  sort_order = request.args.get("sort", "desc")
  df = load_leads()
  df["orig_index"] = df.index

  counts = {
      "vse": len(df),
      "nenapsano": len(df[df["Stav"] != "Napsáno"]),
      "napsano": len(df[df["Stav"] == "Napsáno"]),
  }

  if status_filter != "vse":
    filtered_df = df[df["Stav"] == status_filter]
  else:
    filtered_df = df

  if sort_order == "desc":
    filtered_df = filtered_df.iloc[::-1]

  return render_template_string(
      TEMPLATE,
      leads=filtered_df,
      current_filter=status_filter,
      sort_order=sort_order,
      counts=counts,
      generate_outreach=generate_outreach,
  )


@app.route("/status/<int:orig_index>/<status>")
def update_status(orig_index, status):
  current_filter = request.args.get("filter", "vse")
  sort_order = request.args.get("sort", "desc")
  df = load_leads()
  if orig_index in df.index:
    df.at[orig_index, "Stav"] = status
    save_leads(df)

  if current_filter == "vse":
    return redirect(url_for("index", filter_path="vse", sort=sort_order))
  else:
    return redirect(
        url_for("filter_status", status=current_filter, sort=sort_order)
    )


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0" if "PORT" in os.environ else "127.0.0.1", port=port)