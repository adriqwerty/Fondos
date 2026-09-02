import requests
import pandas as pd
import re
import gspread
import os
import json
import datetime  # 🚨 CORREGIDO: Importación que faltaba
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials
from concurrent.futures import ThreadPoolExecutor  # 🚀 Multihilo

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# =========================
# CLEANERS CORREGIDOS
# =========================
def clean_vl(x):
    if not x or str(x).strip() in ["--", ""]:
        return None
    # Eliminar comas de miles y símbolos de moneda
    cleaned = re.sub(r'[^\d\.]', '', str(x).replace(",", "."))
    try:
        return float(cleaned)
    except ValueError:
        return None

def clean_date(x):
    """Convierte fechas como 'Feb 28, 2026' o 'Feb 28' a formato YYYY-MM-DD."""
    if not x:
        return None
    x = str(x).strip()
    match = re.search(r'([A-Za-z]{3}\s+\d{1,2}(?:,\s+\d{4})?)', x)
    if not match:
        return None
        
    date_str = match.group(1)
    if "," not in date_str:
        current_year = datetime.datetime.now().year
        date_str = f"{date_str}, {current_year}"
        
    try:
        dt = datetime.datetime.strptime(date_str, "%b %d, %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None

# =========================
# EXTRAER DESDE FUENTES SECUNDARIAS
# =========================
def obtener_vl_fallback(isin):
    """
    Extracción de emergencia para ISINs no indexados en FT (ej. Capital Group LU1295551144).
    """
    # 1. Intento en QueFondos.com
    url_qf = f"https://www.quefondos.com/es/fondos/ficha/index.html?isin={isin}"
    try:
        r = requests.get(url_qf, headers=HEADERS, timeout=6)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "lxml")
            vl_span = soup.find("span", {"id": "vliquidativo"})
            date_span = soup.find("span", {"id": "fechavl"})
            
            if vl_span:
                vl = clean_vl(vl_span.get_text(strip=True))
                if vl is not None:
                    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
                    if date_span:
                        d_match = re.search(r'\d{2}/\d{2}/\d{4}', date_span.get_text())
                        if d_match:
                            date_str = datetime.datetime.strptime(d_match.group(0), "%d/%m/%Y").strftime("%Y-%m-%d")
                    
                    return [{"date_str": date_str, "isin": isin, "vl": round(vl, 6)}]
    except Exception:
        pass

    # 2. Intento en Morningstar ES
    url_ms = f"https://www.morningstar.es/es/funds/snapshot/snapshot.aspx?id={isin}"
    try:
        r = requests.get(url_ms, headers=HEADERS, timeout=6)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "lxml")
            td_target = soup.find("td", text=re.compile(r"NAV|Valor Liquidativo", re.I))
            if td_target:
                val_td = td_target.find_next_sibling("td")
                if val_td:
                    vl = clean_vl(val_td.get_text(strip=True))
                    if vl is not None:
                        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                        return [{"date_str": today_str, "isin": isin, "vl": round(vl, 6)}]
    except Exception:
        pass

    return None

# =========================
# CONFIG & AUTH GOOGLE SHEETS
# =========================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1QA6bpWTw_uILBwO3-z7GXfA3QOGor_EoX4m-ljdsTe4"

def get_service_account_info():
    if "GOOGLE_CREDS" in os.environ:
        return json.loads(os.environ["GOOGLE_CREDS"])
    try:
        import streamlit as st
        return st.secrets["gcp_service_account"]
    except Exception:
        raise RuntimeError("No credentials found (Streamlit secrets or GOOGLE_CREDS env var)")

def connect_gsheets():
    info = get_service_account_info()
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)

client = None
sh = None
ws_fondos = None
ws_hist = None

def init_sheets():
    global client, sh, ws_fondos, ws_hist
    if client is not None:
        return
    client = connect_gsheets()
    sh = client.open_by_key(SPREADSHEET_ID)
    ws_fondos = sh.worksheet("Fondos")
    ws_hist = sh.worksheet("HistoricoVL")

# =========================
# FT SCRAPER (TRABAJADOR MULTIHILO)
# =========================
def procesar_un_isin(row, existing_keys):
    isin = str(row["isin"]).strip()
    data = []
    
    urls_ft = [
        f"https://markets.ft.com/data/funds/tearsheet/historical?s={isin}:EUR",
        f"https://markets.ft.com/data/funds/tearsheet/historical?s={isin}:USD",
        f"https://markets.ft.com/data/funds/tearsheet/historical?s={isin}"
    ]
    
    for url in urls_ft:
        try:
            r = requests.get(url, headers=HEADERS, timeout=6)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "lxml")
                table = soup.find("table", {"class": re.compile(r".*mod-ui-table.*")}) or soup.find("table")
                
                if table:
                    rows = table.find_all("tr")
                    for r_node in rows[1:]:
                        cols = r_node.find_all("td")
                        if len(cols) >= 5:
                            raw_date = cols[0].get_text(strip=True)
                            raw_vl = cols[4].get_text(strip=True)
                            
                            p_date = clean_date(raw_date)
                            p_vl = clean_vl(raw_vl)
                            
                            if p_date and p_vl is not None:
                                key = f"{p_date}_{isin}"
                                if key not in existing_keys:
                                    data.append({
                                        "date_str": p_date,
                                        "isin": isin,
                                        "vl": round(p_vl, 6)
                                    })
                    if data:
                        break
        except Exception:
            continue

    # Rescate para ISINs como LU1295551144 si FT no devuelve filas
    if not data:
        fallback_res = obtener_vl_fallback(isin)
        if fallback_res:
            for item in fallback_res:
                key = f"{item['date_str']}_{isin}"
                if key not in existing_keys:
                    data.append(item)

    if not data:
        return None

    return [[item["date_str"], item["isin"], item["vl"]] for item in data]

# =========================
# GOOGLE SHEETS HELPERS
# =========================
def load_fondos():
    init_sheets()
    return pd.DataFrame(ws_fondos.get_all_records())

def load_existing_keys():
    init_sheets()
    try:
        data = ws_hist.get_all_records()
        df = pd.DataFrame(data)
        if df.empty:
            return set()
        df["key"] = df["date"].astype(str) + "_" + df["isin"].astype(str)
        return set(df["key"])
    except Exception:
        return set()

# =========================
# MAIN
# =========================
def actualizar_valores():
    print("📥 Cargando datos iniciales de Google Sheets...")
    fondos = load_fondos()
    existing_keys = load_existing_keys()
    
    print(f"📊 Fondos: {len(fondos)} | 🔑 Registros en histórico: {len(existing_keys)}")
    print("🚀 Lanzando extracción en paralelo...")

    filas_a_insertar = []

    with ThreadPoolExecutor(max_workers=5) as executor:  # Reducido a 5 para evitar bloqueos
        resultados = executor.map(lambda r: procesar_un_isin(r, existing_keys), [row for _, row in fondos.iterrows()])
        
        for res in resultados:
            if res is not None:
                filas_a_insertar.extend(res)

    if filas_a_insertar:
        print(f"📤 Subiendo {len(filas_a_insertar)} nuevas filas a Google Sheets...")
        init_sheets()
        ws_hist.append_rows(filas_a_insertar, value_input_option="RAW")
        print("✔ Datos subidos con éxito.")
    else:
        print("✔ Sin nuevos datos que añadir hoy.")

    print("\n✅ PROCESO COMPLETADO")

if __name__ == "__main__":
    actualizar_valores()
