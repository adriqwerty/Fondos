import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import streamlit as st

# =========================
# CONFIG
# =========================


st.set_page_config(page_title="Dashboard Fondos2", layout="wide")


st.title("📊 Dashboard de Fondos")

SPREADSHEET_ID = "1QA6bpWTw_uILBwO3-z7GXfA3QOGor_EoX4m-ljdsTe4"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# =========================
# CONEXIÓN GOOGLE SHEETS
# =========================
@st.cache_resource
def connect_gsheets():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    return gspread.authorize(creds)

client = connect_gsheets()


# =========================
# LOAD APORTACIONES
# =========================
@st.cache_data(ttl=300)
def load_aportaciones():
    sh = client.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("Aportaciones_A")
    return pd.DataFrame(ws.get_all_records())

@st.cache_data(ttl=300)
def load_fondos():
    sh = client.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("Fondos")
    return pd.DataFrame(ws.get_all_records())

fondos = load_fondos()
isin_to_fund = dict(zip(fondos["isin"], fondos["fondo"]))
fondos = fondos.sort_values("orden")
orden_fondos = fondos["fondo"].tolist()
orden_dict = dict(zip(fondos["fondo"], fondos["orden"]))

# =========================
# LOAD HISTÓRICO VL
# =========================
@st.cache_data(ttl=300)
def load_prices():
    sh = client.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("HistoricoVL")

    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])

    df["vl"] = df["vl"].astype(str).str.replace(",", ".").astype(float)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    df = df.dropna(subset=["date", "vl", "isin"])
    df = df.sort_values(["isin", "date"])

    latest = df.groupby("isin").tail(1)

    return dict(zip(latest["isin"], latest["vl"])), df

def color_rentabilidad(val):
        try:
            val = float(val)
            if val > 0:
                return "color: #27ae60; font-weight: bold"   # verde
            elif val < 0:
                return "color: #c0392b; font-weight: bold"   # rojo
        except:
            pass
        return "color: black"
def bold_columns(df):
    return pd.DataFrame(
        [["font-weight: bold" for _ in df.columns] for _ in range(len(df))],
        columns=df.columns
    )
# =========================
# CARGA DATOS
# =========================
df = load_aportaciones()
price_map, hist_df = load_prices()

hist_df["fund"] = hist_df["isin"].map(isin_to_fund)
hist_df = hist_df.dropna(subset=["fund"])
# =========================
# NORMALIZACIÓN
# =========================
df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
df["price"] = pd.to_numeric(df["price"], errors="coerce")
df["date"] = pd.to_datetime(df["date"], format="%d/%m/%Y", errors="coerce")

df["current_price"] = df["isin"].astype(str).str.strip().map(price_map)


# =========================
# CÁLCULOS APORTACIONES
# =========================
df["valor_actual"] = (df["amount"] / df["price"]) * df["current_price"]
df["beneficio"] = df["valor_actual"] - df["amount"]
df["rentabilidad"] = (df["beneficio"] / df["amount"]) * 100


# =========================
# DETALLE
# =========================


# =========================
# RESUMEN POR FONDO
# =========================
resumen = (
    df.groupby("fund")
      .agg(
          invertido=("amount", "sum"),
          valor_actual=("valor_actual", "sum"),
          beneficio=("beneficio", "sum")
      )
      .reset_index()
)

resumen["rentabilidad"] = resumen["beneficio"] / resumen["invertido"] * 100


# última fecha por fondo
last_dates = (
    hist_df.loc[
        hist_df.groupby("fund")["date"].idxmax()
    ][["fund", "date"]]
    .rename(columns={"date": "last_date"})
)


# =========================
# MÉTRICAS HISTÓRICAS
# =========================
def calc_changes(group):
    group = group.sort_values("date")

    latest = group.iloc[-1]
    last_vl = latest["vl"]
    last_date = latest["date"]

    prev_day = group.iloc[-2]["vl"] if len(group) > 1 else None

    week_date = last_date - pd.Timedelta(days=7)
    week_data = group[group["date"] <= week_date]
    week_vl = week_data.iloc[-1]["vl"] if not week_data.empty else None

    return pd.Series({
        "last_vl": last_vl,
        "prev_day_vl": prev_day,
        "week_vl": week_vl
    })


metrics = hist_df.groupby(["fund", "isin"]).apply(calc_changes).reset_index()

metrics["%_1d"] = (metrics["last_vl"] - metrics["prev_day_vl"]) / metrics["prev_day_vl"] * 100
metrics["%_7d"] = (metrics["last_vl"] - metrics["week_vl"]) / metrics["week_vl"] * 100


metrics_fund = metrics.groupby("fund").agg({
    "%_1d": "mean",
    "%_7d": "mean"
}).reset_index()


# =========================
# FINAL
# =========================
final = resumen.merge(metrics_fund, on="fund", how="left")
final = final.merge(last_dates, on="fund", how="left")
final["order"] = final["fund"].map(orden_dict)

final = final.sort_values("order", na_position="last").drop(columns=["order"])

final = final.rename(columns={
    "fund": "Fondo",
    "invertido": "Invertido",
    "valor_actual": "Valor actual",
    "beneficio": "Ganancia",
    "rentabilidad": "Rentabilidad (%)",
    "%_1d": "1 día (%)",
    "%_7d": "7 días (%)",
    "last_date": "Última actualización"
})


# =========================
# RESUMEN
# =========================
st.subheader("📊 Resumen por fondo")
altura_tabla = 35* len(final) +38
styled = (
    final.style
    .format({
        "Invertido": "{:,.2f} €",
        "Valor actual": "{:,.2f} €",
        "Ganancia": "{:,.2f} €",
        "Rentabilidad (%)": "{:.2f} %",
        "1 día (%)": "{:.2f} %",
        "7 días (%)": "{:.2f} %",
        "Última actualización": lambda x: x.strftime("%d/%m/%Y") if pd.notnull(x) else ""
    })
    .map(
        color_rentabilidad,
        subset=["Ganancia", "1 día (%)", "7 días (%)", "Rentabilidad (%)"]
    )
    .set_properties(**{
        "text-align": "center",
        "font-weight": "bold"
    })
)



st.dataframe(
    styled,
    use_container_width=True,
    hide_index=True,
    height=altura_tabla
)



st.subheader("📄 Detalle aportaciones")

df_view = df.sort_values("date", ascending=False)

st.dataframe(
    df_view.style.format({
        "amount": "{:,.2f} €",
        "price": "{:,.2f}",
        "current_price": "{:,.2f}",
        "valor_actual": "{:,.2f} €",
        "beneficio": "{:,.2f} €",
        "rentabilidad": "{:.2f} %"
    }),
    use_container_width=True,
    hide_index=True
)
