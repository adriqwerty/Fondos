```python
import requests
import pandas as pd
import re
import gspread
import os
import json
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials
from concurrent.futures import ThreadPoolExecutor

# =========================
# CONFIG
# =========================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1QA6bpWTw_uILBwO3-z7GXfA3QOGor_EoX4m-ljdsTe4"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    )
}

# ISINs que NO están disponibles en Financial Times
# y utilizan una fuente alternativa.
FINANZPARTNER_ISINS = {
    "LU1295551144"
}

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
        raise RuntimeError(
            "No credentials found "
            "(Streamlit secrets or GOOGLE_CREDS env var)"
        )


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

    if x is None:
        return None

    x = str(x).strip()

    # Elimina espacios
    x = x.replace(" ", "")

    # Caso habitual FT:
    # 26.6700
    #
    # Si viene algo como:
    # 1,234.56
    # se elimina la coma.
    x = x.replace(",", "")

    try:
        return float(x)

    except Exception:
        return None


def clean_date(x):

    match = re.search(
        r'([A-Za-z]{3,9}\s\d{1,2},\s\d{4})',
        str(x)
    )

    return match.group(1) if match else x


# =========================
# FINANCIAL TIMES SCRAPER
# =========================
def procesar_ft(isin, existing_keys):

    url = (
        "https://markets.ft.com/data/funds/"
        f"tearsheet/historical?s={isin}:EUR"
    )

    try:

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=10
        )

        if r.status_code != 200:
            print(
                f"❌ FT {isin}: HTTP {r.status_code}"
            )
            return None

    except Exception as e:

        print(
            f"❌ FT {isin}: error de conexión: {e}"
        )

        return None

    soup = BeautifulSoup(
        r.text,
        "lxml"
    )

    table = soup.find("table")

    if not table:

        print(
            f"⚠️ FT {isin}: no se encontró tabla"
        )

        return None

    rows = table.find_all("tr")

    data = []

    for r_node in rows[1:]:

        cols = r_node.find_all("td")

        if len(cols) < 5:
            continue

        data.append({
            "date": cols[0].get_text(
                strip=True
            ),

            "vl": cols[4].get_text(
                strip=True
            )
        })

    if not data:

        print(
            f"⚠️ FT {isin}: tabla sin datos"
        )

        return None

    df = pd.DataFrame(data)

    # -------------------------
    # FECHA
    # -------------------------
    df["date"] = df["date"].apply(
        clean_date
    )

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    # -------------------------
    # VL
    # -------------------------
    df["vl"] = df["vl"].apply(
        clean_vl
    )

    df = df.dropna(
        subset=["date", "vl"]
    )

    if df.empty:
        return None

    # -------------------------
    # METADATOS
    # -------------------------
    df["isin"] = isin

    df["date_str"] = (
        df["date"]
        .dt
        .strftime("%Y-%m-%d")
    )

    df["key"] = (
        df["date_str"]
        + "_"
        + df["isin"]
    )

    # -------------------------
    # ELIMINAR DUPLICADOS
    # -------------------------
    df = df[
        ~df["key"].isin(
            existing_keys
        )
    ]

    if df.empty:

        print(
            f"✔ FT {isin}: sin datos nuevos"
        )

        return None

    df["vl"] = (
        df["vl"]
        .astype(float)
        .round(6)
    )

    print(
        f"📈 FT {isin}: "
        f"{len(df)} nuevos registros"
    )

    return df[
        ["date_str", "isin", "vl"]
    ].values.tolist()


# =========================
# FINANZPARTNER SCRAPER
# =========================
def procesar_finanzpartner(
    isin,
    existing_keys
):

    # Actualmente solo utilizamos
    # esta función para LU1295551144.
    if isin == "LU1295551144":

        url = (
            "https://www.finanzpartner.de/fi/"
            "lu1295551144/"
            "capital-group-new-perspective-fund-lux-b-eur/"
        )

    else:

        print(
            f"❌ Finanzpartner: "
            f"URL no configurada para {isin}"
        )

        return None

    try:

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=10
        )

        if r.status_code != 200:

            print(
                f"❌ Finanzpartner {isin}: "
                f"HTTP {r.status_code}"
            )

            return None

    except Exception as e:

        print(
            f"❌ Finanzpartner {isin}: "
            f"error de conexión: {e}"
        )

        return None

    soup = BeautifulSoup(
        r.text,
        "lxml"
    )

    tables = soup.find_all("table")

    data = []

    # =========================
    # BUSCAR TABLA HISTÓRICA
    # =========================
    for table in tables:

        rows = table.find_all("tr")

        for row in rows:

            cols = row.find_all(
                ["td", "th"]
            )

            if len(cols) < 2:
                continue

            date_text = cols[0].get_text(
                " ",
                strip=True
            )

            vl_text = cols[1].get_text(
                " ",
                strip=True
            )

            # -------------------------
            # FECHA
            # -------------------------
            date_match = re.search(
                r'(\d{1,2}\.\d{1,2}\.\d{4})',
                date_text
            )

            if not date_match:
                continue

            # -------------------------
            # VL
            # -------------------------
            vl_match = re.search(
                r'(\d+[.,]\d+)\s*EUR',
                vl_text,
                re.IGNORECASE
            )

            if not vl_match:
                continue

            fecha = date_match.group(1)

            vl_text_clean = vl_match.group(1)

            try:

                fecha_dt = pd.to_datetime(
                    fecha,
                    format="%d.%m.%Y"
                )

                # Finanzpartner utiliza
                # punto decimal en el valor.
                vl = float(
                    vl_text_clean.replace(
                        ",",
                        "."
                    )
                )

            except Exception:

                continue

            date_str = (
                fecha_dt.strftime(
                    "%Y-%m-%d"
                )
            )

            key = (
                date_str
                + "_"
                + isin
            )

            if key in existing_keys:
                continue

            data.append([
                date_str,
                isin,
                round(vl, 6)
            ])

    if not data:

        print(
            f"✔ Finanzpartner {isin}: "
            f"sin datos nuevos"
        )

        return None

    # Eliminar posibles duplicados
    # dentro de la propia respuesta.
    data = list(
        {
            (
                row[0],
                row[1],
                row[2]
            ): row
            for row in data
        }.values()
    )

    print(
        f"📈 Finanzpartner {isin}: "
        f"{len(data)} nuevos registros"
    )

    return data


# =========================
# PROCESAR UN ISIN
# =========================
def procesar_un_isin(
    row,
    existing_keys
):

    isin = str(
        row["isin"]
    ).strip()

    fondo = row["fondo"]

    # =========================
    # SELECCIONAR FUENTE
    # =========================
    if isin in FINANZPARTNER_ISINS:

        print(
            f"🔄 {isin} | {fondo} "
            f"→ Finanzpartner"
        )

        return procesar_finanzpartner(
            isin,
            existing_keys
        )

    # =========================
    # RESTO → FINANCIAL TIMES
    # =========================
    print(
        f"🌐 {isin} | {fondo} "
        f"→ Financial Times"
    )

    return procesar_ft(
        isin,
        existing_keys
    )


# =========================
# GOOGLE SHEETS HELPERS
# =========================
def load_fondos():

    init_sheets()

    return pd.DataFrame(
        ws_fondos.get_all_records()
    )


def load_existing_keys():

    init_sheets()

    try:

        data = ws_hist.get_all_records()

        df = pd.DataFrame(data)

        if df.empty:
            return set()

        df["key"] = (
            df["date"]
            .astype(str)
            + "_"
            + df["isin"]
            .astype(str)
        )

        return set(
            df["key"]
        )

    except Exception as e:

        print(
            f"⚠️ Error cargando histórico: {e}"
        )

        return set()


# =========================
# MAIN
# =========================
def actualizar_valores():

    print(
        "📥 Cargando datos iniciales "
        "de Google Sheets..."
    )

    fondos = load_fondos()

    existing_keys = (
        load_existing_keys()
    )

    print(
        f"📊 Fondos: {len(fondos)} "
        f"| 🔑 Registros en histórico: "
        f"{len(existing_keys)}"
    )

    print(
        "🚀 Lanzando extracción "
        "en paralelo..."
    )

    filas_a_insertar = []

    # =========================
    # MULTIHILO
    # =========================
    with ThreadPoolExecutor(
        max_workers=10
    ) as executor:

        resultados = executor.map(
            lambda r:
                procesar_un_isin(
                    r,
                    existing_keys
                ),

            [
                row
                for _, row
                in fondos.iterrows()
            ]
        )

        for res in resultados:

            if res is not None:

                filas_a_insertar.extend(
                    res
                )

    # =========================
    # SUBIDA MASIVA
    # =========================
    if filas_a_insertar:

        print(
            f"📤 Subiendo "
            f"{len(filas_a_insertar)} "
            f"nuevas filas a Google Sheets "
            f"en un solo bloque..."
        )

        init_sheets()

        ws_hist.append_rows(
            filas_a_insertar,
            value_input_option="RAW"
        )

        print(
            "✔ Datos subidos con éxito."
        )

    else:

        print(
            "✔ Sin nuevos datos que añadir hoy."
        )

    print(
        "\n✅ PROCESO COMPLETADO"
    )


# =========================
# EJECUCIÓN
# =========================
if __name__ == "__main__":

    actualizar_valores()
```
