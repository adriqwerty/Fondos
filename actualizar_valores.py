import requests
import pandas as pd
import re
import gspread
import os
import json
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials
from concurrent.futures import ThreadPoolExecutor  # 🚀 Multihilo

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
    """
    Función optimizada para ejecutarse en paralelo por cada ISIN.
    """
    isin = row["isin"]
    fondo = row["fondo"]
    
    url = f"https://markets.ft.com/data/funds/tearsheet/historical?s={isin}:EUR"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10) # Timeout de seguridad añadido
        if r.status_code != 200:
            return None
    except Exception:
        return None

    soup = BeautifulSoup(r.text, "lxml")
    table = soup.find("table")
    if not table:
        return None

    rows = table.find_all("tr")
    data = []

    for r_node in rows[1:]:
        cols = r_node.find_all("td")
        if len(cols) < 5:
            continue
        data.append({
            "date": cols[0].get_text(strip=True),
            "vl": cols[4].get_text(strip=True)
        })

    if not data:
        return None

    df = pd.DataFrame(data)
    df["date"] = df["date"].apply(clean_date)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["vl"] = df["vl"].apply(clean_vl)
    df = df.dropna(subset=["date"])
    
    # Añadir metadatos de Google Sheets aquí mismo en memoria
    df["isin"] = isin
    df["date_str"] = df["date"].dt.strftime("%Y-%m-%d")
    df["key"] = df["date_str"] + "_" + df["isin"]
    
    # Filtrar duplicados antes de juntar los datos
    df = df[~df["key"].isin(existing_keys)]
    
    if df.empty:
        return None
        
    df["vl"] = df["vl"].astype(float).round(6)
    return df[["date_str", "isin", "vl"]].values.tolist()

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