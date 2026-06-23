import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import streamlit as st
import plotly.graph_objects as go

# =========================
# CONFIGURACIÓN DE PÁGINA PREMIUM
# =========================
st.set_page_config(page_title="Inversiones", layout="wide", initial_sidebar_state="expanded")

# Estilo CSS personalizado para mejorar fuentes, tarjetas y el diseño general
st.markdown("""
    <style>
    .main .block-container { padding-top: 2rem; }
    div[data-testid="stMetricValue"] { font-size: 24px; font-weight: bold; }
    .header-container { text-align: center; padding: 20px; border-bottom: 2px solid #f0f2f6; margin-bottom: 30px; }
    </style>
""", unsafe_allow_html=True)

# Encabezado unificado
st.markdown("<div class='header-container'><h1 style='color: #1e293b; font-size: 38px; margin-bottom: 5px;'>💼 Evolución de la Inversión</h1><p style='color: #64748b;'>Cuadro de mando financiero y control de carteras</p></div>", unsafe_allow_html=True)

SPREADSHEET_ID = "1QA6bpWTw_uILBwO3-z7GXfA3QOGor_EoX4m-ljdsTe4"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

from actualizar_valores import actualizar_valores

# =========================
# SIDEBAR REORGANIZADA
# =========================
with st.sidebar:
    st.markdown("<h2 style='font-size: 20px; color: #1e293b; margin-bottom: 0px;'>👤 Selección de Cartera</h2>", unsafe_allow_html=True)
    usuario = st.selectbox(
        "Elige el titular de la cuenta",
        ["Adrian", "Oscar", "Arancha"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.markdown("<h2 style='font-size: 18px; color: #1e293b; margin-bottom: 10px;'>⚙️ Mantenimiento</h2>", unsafe_allow_html=True)
    
    if st.button("🔄 Forzar actualización", use_container_width=True):
        with st.spinner("Actualizando Precios..."):
            actualizar_valores()
        st.success("Datos actualizados correctamente")
        st.cache_data.clear()
        st.rerun()

SHEETS_MAP = {
    "Adrian": {"aportaciones": "Aportaciones_A"},
    "Oscar": {"aportaciones": "Aportaciones_B"},
    "Arancha": {"aportaciones": "Aportaciones_C"}
}

cfg = SHEETS_MAP[usuario]

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
# LOAD DATA (Tus funciones intactas)
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

fondos = load_fondos()
isin_to_fund = dict(zip(fondos["isin"], fondos["fondo"]))
fondos = fondos.sort_values("orden")
orden_fondos = fondos["fondo"].tolist()
orden_dict = dict(zip(fondos["fondo"], fondos["orden"]))

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
        if val > 0: return "color: #27ae60; font-weight: bold"
        elif val < 0: return "color: #c0392b; font-weight: bold"
    except: pass
    return "color: #1e293b"

# =========================
# CARGA Y PROCESAMIENTO (Lógica Intacta)
# =========================
df = load_aportaciones(cfg["aportaciones"])
price_map, hist_df = load_prices()

hist_df["fund"] = hist_df["isin"].map(isin_to_fund)
hist_df = hist_df.dropna(subset=["fund"])

df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
df["price"] = pd.to_numeric(df["price"], errors="coerce")
df["date"] = pd.to_datetime(df["date"], format="%d/%m/%Y", errors="coerce")
df["date"] = df["date"].dt.date
df["current_price"] = df["isin"].astype(str).str.strip().map(price_map)

df["valor_actual"] = (df["amount"] / df["price"]) * df["current_price"]
df["beneficio"] = df["valor_actual"] - df["amount"]
df["rentabilidad"] = (df["beneficio"] / df["amount"]) * 100
df["units"] = df["amount"] / df["price"]

resumen = df.groupby("fund").agg(invertido=("amount", "sum"), valor_actual=("valor_actual", "sum"), beneficio=("beneficio", "sum")).reset_index()
resumen["rentabilidad"] = resumen["beneficio"] / resumen["invertido"] * 100

last_dates = hist_df.loc[hist_df.groupby("fund")["date"].idxmax()][["fund", "date"]].rename(columns={"date": "last_date"})

def calc_changes(group):
    group = group.sort_values("date")
    latest = group.iloc[-1]
    last_vl = latest["vl"]
    last_date = latest["date"]
    prev_day = group.iloc[-2]["vl"] if len(group) > 1 else None
    week_date = last_date - pd.Timedelta(days=7)
    week_data = group[group["date"] <= week_date]
    week_vl = week_data.iloc[-1]["vl"] if not week_data.empty else None
    month_date = last_date - pd.Timedelta(days=30)
    month_data = group[group["date"] <= month_date]
    month_vl = month_data.iloc[-1]["vl"] if not month_data.empty else None
    return pd.Series({"last_vl": last_vl, "prev_day_vl": prev_day, "week_vl": week_vl, "month_vl": month_vl})

metrics = hist_df.groupby(["fund", "isin"]).apply(calc_changes).reset_index()
metrics["%_1d"] = (metrics["last_vl"] - metrics["prev_day_vl"]) / metrics["prev_day_vl"] * 100
metrics["%_7d"] = (metrics["last_vl"] - metrics["week_vl"]) / metrics["week_vl"] * 100
metrics["%_30d"] = (metrics["last_vl"] - metrics["month_vl"]) / metrics["month_vl"] * 100

metrics_fund = metrics.groupby("fund").agg({"%_1d": "mean", "%_7d": "mean", "%_30d": "mean"}).reset_index()

df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
daily_cash = df.groupby(["date", "fund"], as_index=False)["amount"].sum().rename(columns={"amount": "invested"})
daily_units = df.groupby(["date", "fund"], as_index=False)["units"].sum()

all_dates = pd.date_range(df["date"].min(), pd.Timestamp.today().normalize(), freq="D")
funds = df["fund"].dropna().unique()
grid = pd.MultiIndex.from_product([all_dates, funds], names=["date", "fund"]).to_frame(index=False)

evolution = grid.merge(daily_cash, on=["date", "fund"], how="left")
evolution = evolution.merge(daily_units, on=["date", "fund"], how="left")
hist_df["fund"] = hist_df["isin"].map(isin_to_fund)
hist_df = hist_df[["date", "fund", "vl"]]
evolution = evolution.merge(hist_df, on=["date", "fund"], how="left")
evolution = evolution.sort_values(["fund", "date"])
evolution["vl"] = evolution.groupby("fund")["vl"].ffill()

dense = grid.merge(evolution, on=["date", "fund"], how="left")
dense["invested"] = dense["invested"].fillna(0)
dense["units"] = dense["units"].fillna(0)
dense["cum_invested"] = dense.groupby("fund")["invested"].cumsum()
dense["cum_units"] = dense.groupby("fund")["units"].cumsum()
dense["market_value"] = dense["cum_units"] * dense["vl"]

final = resumen.merge(metrics_fund, on="fund", how="left").merge(last_dates, on="fund", how="left")
final["order"] = final["fund"].map(orden_dict)
final = final.sort_values("order", na_position="last").drop(columns=["order"])

final = final.rename(columns={
    "fund": "Fondo", "invertido": "Invertido", "valor_actual": "Valor actual", "beneficio": "Ganancia",
    "rentabilidad": "Rentabilidad (%)", "%_1d": "1 día (%)", "%_7d": "7 días (%)", "%_30d": "1 mes (%)", "last_date": "Última actualización"
})

portfolio = dense.groupby("date", as_index=False).agg(invested=("cum_invested", "sum"), value=("market_value", "sum")).sort_values("date").reset_index(drop=True)
portfolio = portfolio.dropna(subset=["value"])
portfolio = portfolio[portfolio["value"] > 0]
portfolio["profit"] = portfolio["value"] - portfolio["invested"]
portfolio["1d (%)"] = portfolio["value"].pct_change(1) * 100
portfolio["7d (%)"] = portfolio["value"].pct_change(7) * 100
portfolio["1m (%)"] = portfolio["value"].pct_change(30) * 100

last = portfolio.iloc[-2]

# =========================
# 🏛️ NUEVA UI: TARJETAS DE MÉTRICAS (KPIs)
# =========================
st.subheader("📊 Resumen General")
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.metric(label="💰 Total Invertido", value=f"{last['invested']:,.2f} €")
with kpi2:
    st.metric(label="📈 Valor de Cartera", value=f"{last['value']:,.2f} €")
with kpi3:
    rentabilidad_total = (last["profit"] / last["invested"]) * 100 if last["invested"] else 0
    st.metric(label="🍀 Ganancia Global", value=f"{last['profit']:,.2f} €", delta=f"{rentabilidad_total:.2f} %")
with kpi4:
    # Mostramos el cambio de 1 día como delta del estado de mercado actual
    st.metric(label="⚡ Variación (24h)", value=f"{last['1d (%)']:.2f} %", delta=f"{last['1d (%)']:.2f} %", delta_color="normal")

st.markdown("---")

# =========================
# 📑 ORGANIZACIÓN EN PESTAÑAS (TABS)
# =========================
tab_resumen, tab_graficos, tab_detalles = st.tabs(["📋 Resumen de Fondos", "📈 Gráficos de Evolución", "🔍 Detalle de Operaciones"])

with tab_resumen:
    st.markdown("<h3 style='font-size: 20px; color: #1e293b;'>Análisis Detallado por Fondo</h3>", unsafe_allow_html=True)
    altura_tabla = 35 * len(final) + 38
    styled = (
        final.style
        .format({
            "Invertido": "{:,.2f} €", "Valor actual": "{:,.2f} €", "Ganancia": "{:,.2f} €",
            "Rentabilidad (%)": "{:.2f} %", "1 día (%)": "{:.2f} %", "7 días (%)": "{:.2f} %", "1 mes (%)": "{:.2f} %",
            "Última actualización": lambda x: x.strftime("%d/%m/%Y") if pd.notnull(x) else ""
        })
        .map(color_rentabilidad, subset=["Ganancia", "1 día (%)", "7 días (%)", "1 mes (%)", "Rentabilidad (%)"])
        .set_properties(**{"text-align": "center"})
    )
    st.dataframe(styled, use_container_width=True, hide_index=True, height=altura_tabla)

with tab_graficos:
    # Re-procesado de datos para gráficas (manteniendo tus variables)
    start_date = pd.Timestamp("2026-05-18")
    dense_filtered = dense[dense["date"] >= start_date]
    portfolio_graph = dense_filtered.groupby("date", as_index=False).agg(invested=("cum_invested", "sum"), value=("market_value", "sum")).sort_values("date")
    portfolio_graph["profit"] = (portfolio_graph["value"] - portfolio_graph["invested"])

    # Gráficas en dos columnas para aprovechar el espacio 'wide'
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=portfolio_graph["date"], y=portfolio_graph["invested"], name="Invertido", mode="lines", line=dict(color="#64748b", width=2)))
        fig1.add_trace(go.Scatter(x=portfolio_graph["date"], y=portfolio_graph["value"], name="Valor cartera", mode="lines", line=dict(color="#2563eb", width=2.5)))
        fig1.update_layout(title="Evolución Inversión vs Mercado", template="plotly_white", hovermode="x unified", margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig1, use_container_width=True)

    with col_g2:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=portfolio_graph["date"], y=portfolio_graph["profit"], name="Beneficio", mode="lines", line=dict(color="#10b981", width=2.5)))
        fig2.add_hline(y=0, line_dash="dash", line_color="#cbd5e1")
        fig2.update_layout(title="Evolución del Beneficio Neto (€)", template="plotly_white", hovermode="x unified", margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig2, use_container_width=True)

    # Gráfico de distribución (Tarta) centrado abajo
    st.markdown("---")
    latest = dense.sort_values("date").groupby("fund").tail(1).dropna(subset=["market_value"])
    alloc = latest.groupby("fund", as_index=False).agg(value=("market_value", "sum")).sort_values("value", ascending=False)

    fig_pie = go.Figure(data=[go.Pie(
        labels=alloc["fund"], values=alloc["value"], hole=0.5,
        textinfo="label+percent", textposition="inside",
        hovertemplate="<b>%{label}</b><br>Valor: %{value:,.2f} €<br>Peso: %{percent}<extra></extra>",
        sort=False, marker=dict(line=dict(color="white", width=2))
    )])
    fig_pie.update_layout(title=dict(text="📊 Distribución Actual de la Cartera", x=0.5), showlegend=True, height=500)
    st.plotly_chart(fig_pie, use_container_width=True)

with tab_detalles:
    col_filtro, _ = st.columns([1, 2])
    with col_filtro:
        fondo = st.selectbox("Filtrar por Fondo Específico", ["Todos"] + sorted(df["fund"].dropna().unique().tolist()))

    df_filtrado = df.copy() if fondo == "Todos" else df[df["fund"] == fondo]
    df_view = df_filtrado.sort_values("date", ascending=False)
    
    df_view = df_view.rename(columns={
        "date": "Fecha", "amount": "Invertido", "price": "Precio", "fund":"Fondo",
        "isin":"ISIN", "current_price": "Precio Actual", "valor_actual": "Valor Actual",
        "beneficio": "Ganancia", "rentabilidad": "Rentabilidad (%)",
    })
    df_view = df_view[["Fecha", "Fondo", "ISIN", "Invertido", "Valor Actual", "Precio", "Precio Actual", "Ganancia", "Rentabilidad (%)"]]

    styled_detalles = (
        df_view.style
        .format({
            "Fecha": lambda x: x.strftime("%d/%m/%Y") if pd.notnull(x) else "",
            "Invertido": "{:,.2f} €", "Precio": "{:,.2f} €", "Precio Actual": "{:,.2f} €",
            "Valor Actual": "{:,.2f} €", "Ganancia": "{:,.2f} €", "Rentabilidad (%)": "{:.2f} %"
        })
        .map(color_rentabilidad, subset=["Ganancia","Rentabilidad (%)"])
        .set_properties(**{"text-align": "center"})
    )
    st.dataframe(styled_detalles, use_container_width=True, hide_index=True)