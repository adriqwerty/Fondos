import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

# =========================
# CONFIG UI
# =========================

st.set_page_config(page_title="Inversiones", layout="wide")

st.markdown("""
<style>
.stApp {
    background-color: #0e1117;
    color: white;
}
h1, h2, h3 {
    color: white;
}
[data-testid="stMetric"] {
    background-color: #1e222d;
    border-radius: 12px;
    padding: 15px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<h1 style='text-align: center;'>💼 Evolución de la Inversión</h1>
""", unsafe_allow_html=True)

SPREADSHEET_ID = "1QA6bpWTw_uILBwO3-z7GXfA3QOGor_EoX4m-ljdsTe4"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

from actualizar_valores import actualizar_valores

# =========================
# SIDEBAR
# =========================

st.sidebar.header("⚙️ Mantenimiento")

if st.sidebar.button("🔄 Forzar actualización"):
    with st.spinner("Actualizando precios..."):
        actualizar_valores()
    st.sidebar.success("Datos actualizados correctamente")

st.sidebar.title("👤 Selección de cartera")

usuario = st.sidebar.selectbox("Elige cartera", ["Adrian", "Oscar", "Arancha"])

SHEETS_MAP = {
    "Adrian": {"aportaciones": "Aportaciones_A"},
    "Oscar": {"aportaciones": "Aportaciones_B"},
    "Arancha": {"aportaciones": "Aportaciones_C"}
}

cfg = SHEETS_MAP[usuario]

# =========================
# CONEXIÓN
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
# LOAD DATA
# =========================

@st.cache_data(ttl=300)
def load_aportaciones(sheet_name):
    sh = client.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet(sheet_name)
    return pd.DataFrame(ws.get_all_records())

@st.cache_data(ttl=300)
def load_fondos():
    sh = client.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("Fondos")
    return pd.DataFrame(ws.get_all_records())

@st.cache_data(ttl=300)
def load_prices():
    sh = client.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("HistoricoVL")

    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])

    df["vl"] = df["vl"].astype(str).str.replace(",", ".").astype(float)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    df = df.dropna(subset=["date", "vl", "isin"]).sort_values(["isin", "date"])

    latest = df.groupby("isin").tail(1)

    return dict(zip(latest["isin"], latest["vl"])), df


# =========================
# DATA
# =========================

df = load_aportaciones(cfg["aportaciones"])
fondos = load_fondos()

isin_to_fund = dict(zip(fondos["isin"], fondos["fondo"]))
fondos = fondos.sort_values("orden")
orden_dict = dict(zip(fondos["fondo"], fondos["orden"]))

price_map, hist_df = load_prices()
hist_df["fund"] = hist_df["isin"].map(isin_to_fund)
hist_df = hist_df.dropna(subset=["fund"])

# =========================
# NORMALIZACIÓN
# =========================

df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
df["price"] = pd.to_numeric(df["price"], errors="coerce")
df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()

df["current_price"] = df["isin"].astype(str).str.strip().map(price_map)

df["units"] = df["amount"] / df["price"]
df["valor_actual"] = df["units"] * df["current_price"]
df["beneficio"] = df["valor_actual"] - df["amount"]

# =========================
# RESUMEN
# =========================

resumen = df.groupby("fund").agg(
    invertido=("amount", "sum"),
    valor_actual=("valor_actual", "sum"),
    beneficio=("beneficio", "sum")
).reset_index()

resumen["rentabilidad"] = resumen["beneficio"] / resumen["invertido"] * 100

# =========================
# PORTFOLIO EVOLUTION
# =========================

daily = df.groupby(["date", "fund"], as_index=False).agg(
    invested=("amount", "sum"),
    units=("units", "sum")
)

all_dates = pd.date_range(df["date"].min(), pd.Timestamp.today().normalize(), freq="D")

grid = pd.MultiIndex.from_product(
    [all_dates, df["fund"].dropna().unique()],
    names=["date", "fund"]
).to_frame(index=False)

dense = grid.merge(daily, on=["date", "fund"], how="left")
dense["invested"] = dense["invested"].fillna(0)
dense["units"] = dense["units"].fillna(0)

hist_df = hist_df[["date", "fund", "vl"]]
dense = dense.merge(hist_df, on=["date", "fund"], how="left")
dense["vl"] = dense.groupby("fund")["vl"].ffill()

dense["cum_invested"] = dense.groupby("fund")["invested"].cumsum()
dense["cum_units"] = dense.groupby("fund")["units"].cumsum()
dense["market_value"] = dense["cum_units"] * dense["vl"]

portfolio = dense.groupby("date", as_index=False).agg(
    invested=("cum_invested", "sum"),
    value=("market_value", "sum")
)

portfolio["profit"] = portfolio["value"] - portfolio["invested"]

# =========================
# KPIs TOP
# =========================

last = portfolio.dropna().iloc[-1]

c1, c2, c3, c4 = st.columns(4)

c1.metric("💰 Invertido", f"{last['invested']:,.0f} €")
c2.metric("📈 Valor", f"{last['value']:,.0f} €")
c3.metric("🏆 Beneficio", f"{last['profit']:,.0f} €")
c4.metric("📊 Rentabilidad", f"{(last['profit']/last['invested']*100):.2f} %")

# =========================
# GRÁFICO EVOLUCIÓN
# =========================

fig1 = go.Figure()

fig1.add_trace(go.Scatter(
    x=portfolio["date"],
    y=portfolio["invested"],
    name="Invertido",
    mode="lines"
))

fig1.add_trace(go.Scatter(
    x=portfolio["date"],
    y=portfolio["value"],
    name="Valor cartera",
    mode="lines",
    fill="tonexty"
))

fig1.update_layout(
    template="plotly_dark",
    title="Evolución de la cartera",
    hovermode="x unified"
)

st.plotly_chart(fig1, use_container_width=True)

# =========================
# BENEFICIO
# =========================

fig2 = go.Figure()

fig2.add_trace(go.Scatter(
    x=portfolio["date"],
    y=portfolio["profit"],
    name="Beneficio",
    line=dict(color="green")
))

fig2.add_hline(y=0, line_dash="dash")

fig2.update_layout(
    template="plotly_dark",
    title="Evolución del beneficio"
)

st.plotly_chart(fig2, use_container_width=True)

# =========================
# DISTRIBUCIÓN (TREEMAP)
# =========================

latest = dense.groupby("fund").tail(1)

alloc = latest.groupby("fund", as_index=False).agg(
    value=("market_value", "sum")
)

fig3 = px.treemap(
    alloc,
    path=["fund"],
    values="value",
    title="Distribución cartera"
)

fig3.update_layout(template="plotly_dark")

st.plotly_chart(fig3, use_container_width=True)

# =========================
# TABLA RESUMEN
# =========================

st.subheader("📊 Resumen por fondo")

styled = resumen.sort_values("beneficio", ascending=False)

st.dataframe(styled, use_container_width=True)