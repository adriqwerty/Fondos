import requests
import pandas as pd
import re
import gspread
import os
import json
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials
from concurrent.futures import ThreadPoolExecutor  # 🚀 Multihilo

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# =========================
# EXTRAER DESDE FUENTES SECUNDARIAS
# =========================
def obtener_vl_fallback(isin):
    """
    Extracción de emergencia para ISINs no indexados en FT (ej. LU1295551144).
    Analiza QueFondos o Morningstar España.
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
                # Limpiar valor numérico
                raw_vl = vl_span.get_text(strip=True).replace(".", "").replace(",", ".")
                vl = float(raw_vl)
                
                # Extraer la fecha (Formato DD/MM/YYYY en QueFondos)
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
                    parts = val_td.get_text(strip=True).split()
                    raw_val = parts[1] if len(parts) > 1 else parts[0]
                    vl = float(raw_val.replace(".", "").replace(",", "."))
                    
                    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                    return [{"date_str": today_str, "isin": isin, "vl": round(vl, 6)}]
    except Exception:
        pass

    return None


# =========================
# CONFIG
# =========================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1QA6bpWTw_uILBwO3-z7GXfA3QOGor_EoX4m-ljdsTe4"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# =========================
# AUTH GOOGLE SHEETS
# =========================
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

# =========================
# LAZY INIT SHEETS
# =========================
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
# CLEANERS
# =========================
def clean_vl(x):
    # Optimizado: Limpieza limpia en cadena en lugar de múltiples asignaciones
    x = str(x).strip().replace(",", "")
    try:
        return float(x)
    except:
        return None

def clean_date(x):
    match = re.search(r'([A-Za-z]{3,9}\s\d{1,2},\s\d{4})', str(x))
    return match.group(1) if match else x

# =========================
# FT SCRAPER (TRABAJADOR MULTIHILO)
# =========================
def procesar_un_isin(row, existing_keys):
    isin = str(row["isin"]).strip()
    data = []
    
    # 1. Probar URLs alternativas de FT
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
                        break # Si obtuvimos datos válidos de FT, detenemos los reintentos
        except Exception:
            continue

    # 2. Si Financial Times no entregó registros (caso LU1295551144), invocar fallback
    if not data:
        data = obtener_vl_fallback(isin)

    if not data:
        return None

    # Formatear el resultado como array directo para append_rows de gspread
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
    except:
        return set()

# =========================
# MAIN
# =========================
def actualizar_valores():
    print("📥 Cargando datos iniciales de Google Sheets...")
    fondos = load_fondos()
    existing_keys = load_existing_keys()
    
    print(f"📊 Fondos: {len(fondos)} | 🔑 Registros en histórico: {len(existing_keys)}")
    print("🚀 Lanzando extracción en paralelo a Financial Times...")

    filas_a_insertar = []

    # 🎯 CLAVE 1: Multihilo (Lanza hasta 10 peticiones concurrentes a la vez)
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Mapeamos los fondos al pool de hilos
        resultados = executor.map(lambda r: procesar_un_isin(r, existing_keys), [row for _, row in fondos.iterrows()])
        
        for res in resultados:
            if res is not None:
                filas_a_insertar.extend(res)

    # 🎯 CLAVE 2: Inserción Masiva (Batch Upload)
    if filas_a_insertar:
        print(f"📤 Subiendo {len(filas_a_insertar)} nuevas filas a Google Sheets en un solo bloque...")
        init_sheets()
        ws_hist.append_rows(filas_a_insertar, value_input_option="RAW")
        print("✔ Datos subidos con éxito.")
    else:
        print("✔ Sin nuevos datos que añadir hoy.")

    print("\n✅ PROCESO COMPLETADO")

if __name__ == "__main__":
    actualizar_valores()
