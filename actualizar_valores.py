import requests
import pandas as pd
import re
import gspread
import os
import json
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials

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
    """
    Soporta:
    - Streamlit (st.secrets)
    - GitHub Actions / local (env var GOOGLE_CREDS)
    """
    if "GOOGLE_CREDS" in os.environ:
        return json.loads(os.environ["GOOGLE_CREDS"])

    try:
        import streamlit as st
        return st.secrets["gcp_service_account"]
    except Exception:
        raise RuntimeError("No credentials found (Streamlit secrets or GOOGLE_CREDS env var)")


def connect_gsheets():
    info = get_service_account_info()

    creds = Credentials.from_service_account_info(
        info,
        scopes=SCOPES
    )

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
    x=x.replace(",","")
    x=x.replace(".",",")
    

    x = str(x).strip()

    if "," in x and "." in x:
        x = x.replace(".", "").replace(",", ".")
    elif "," in x:
        x = x.replace(",", ".")

    try:
        return float(x)
    except:
        return None


def clean_date(x):
    match = re.search(r'([A-Za-z]{3,9}\s\d{1,2},\s\d{4})', str(x))
    return match.group(1) if match else x

# =========================
# FT SCRAPER
# =========================

def get_historico_ft(isin):

    url = f"https://markets.ft.com/data/funds/tearsheet/historical?s={isin}:EUR"
    r = requests.get(url, headers=HEADERS)

    if r.status_code != 200:
        print(f"❌ Error {r.status_code} en {isin}")
        return None

    soup = BeautifulSoup(r.text, "lxml")

    table = soup.find("table")
    if not table:
        print("❌ No se encontró la tabla")
        return None

    rows = table.find_all("tr")

    data = []

    for row in rows[1:]:
        cols = row.find_all("td")
        if len(cols) < 5:
            continue

        data.append({
            "date": cols[0].get_text(strip=True),
            "vl": cols[4].get_text(strip=True)
        })

    df = pd.DataFrame(data)

    if df.empty:
        return None

    df["date"] = df["date"].apply(clean_date)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    df["vl"] = df["vl"].apply(clean_vl)

    df = df.dropna(subset=["date"])
    df = df.sort_values("date")

    return df

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


def append_to_sheet(df, isin, existing_keys):

    init_sheets()

    df = df.copy()
    df["isin"] = isin

    df["date_str"] = df["date"].dt.strftime("%Y-%m-%d")
    df["key"] = df["date_str"] + "_" + df["isin"]

    df = df[~df["key"].isin(existing_keys)]

    if df.empty:
        print("✔ Sin nuevos datos")
        return

    df["vl"] = df["vl"].astype(float).round(6)

    rows = df[["date_str", "isin", "vl"]].values.tolist()

    ws_hist.append_rows(rows, value_input_option="RAW")

    print(f"📤 Insertadas {len(rows)} filas")

# =========================
# MAIN
# =========================

def actualizar_valores():

    print("📥 Cargando fondos...")
    fondos = load_fondos()

    print(f"📊 Fondos encontrados: {len(fondos)}")

    print("📥 Cargando histórico existente...")
    existing_keys = load_existing_keys()

    print(f"🔑 Registros existentes: {len(existing_keys)}")

    for _, row in fondos.iterrows():

        isin = row["isin"]
        fondo = row["fondo"]

        print(f"\n⬇️ Procesando {fondo} ({isin})")

        df = get_historico_ft(isin)

        if df is None:
            continue

        print("📤 Subiendo nuevos datos...")
        append_to_sheet(df, isin, existing_keys)

    print("\n✅ PROCESO COMPLETADO")


if __name__ == "__main__":
    actualizar_valores()