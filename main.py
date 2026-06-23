import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import streamlit as st
import plotly.graph_objects as go

# ==========================================================
# 🌌 INTERFAZ COMPLETA EN MODO OSCURO (FORZADO POR CSS)
# ==========================================================
st.set_page_config(page_title="Inversiones", layout="wide", initial_sidebar_state="expanded")

# Inyección de CSS premium corregida para eliminar cabeceras blancas en tablas
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght=400;500;600;700&display=swap');
    
    /* Configuración de fuente y fondo global */
    html, body, [class*="css"], .main .block-container {
        font-family: 'Inter', sans-serif;
        color: #f8fafc !important;
    }
    
    /* Fondo oscuro obligatorio para toda la app y la barra lateral */
    .stApp, div[data-testid="stSidebar"] {
        background-color: #0f172a !important;
    }
    
    .main .block-container { padding-top: 1.5rem; }
    
    /* Asegurar textos legibles en la sidebar */
    div[data-testid="stSidebar"] p, div[data-testid="stSidebar"] h2, div[data-testid="stSidebar"] label {
        color: #f8fafc !important;
    }
    
    /* 🎨 CORRECCIÓN ABSOLUTA DE ENCABEZADOS DE TABLAS (EVITA FILAS BLANCAS) */
    div[data-testid="stDataFrame"] table thead tr th,
    div[data-testid="stDataFrame"] [data-testid="stDataFrame-HeaderCell"],
    .stDataFrame th, 
    thead th {
        background-color: #1e293b !important;
        color: #f8fafc !important; /* Texto en blanco premium */
        font-weight: 600 !important;
        text-transform: uppercase !important;
        font-size: 12px !important;
        letter-spacing: 0.5px !important;
        border-bottom: 2px solid #334155 !important;
    }
    
    /* Contenedor general de tablas con bordes suavizados */
    div[data-testid="stDataFrame"] {
        border: 1px solid #334155 !important;
        border-radius: 12px !important;
        overflow: hidden;
        background-color: #0f172a !important;
    }
    
    /* Unificación de color para títulos de pestañas (Tabs) */
    button[data-baseweb="tab"] p {
        color: #94a3b8 !important;
    }
    button[aria-selected="true"] p {
        color: #3b82f6 !important;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

SPREADSHEET_ID = "1QA6bpWTw_uILBwO3-z7GXfA3QOGor_EoX4m-ljdsTe4"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

from actualizar_valores import actualizar_valores

# ==========================================
# SIDEBAR REORGANIZADA
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='font-size: 18px; font-weight: 600; color: #f8fafc; margin-bottom: 12px;'>👤 Selección de Cartera</h2>", unsafe_allow_html=True)
    usuario = st.selectbox(
        "Elige cartera",
        ["Adrian", "Oscar", "Arancha"],
        label_visibility="collapsed"
    )
    
    st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("<h2 style='font-size: 16px; font-weight: 600; color: #f8fafc; margin-bottom: 12px;'>⚙️ Mantenimiento</h2>", unsafe_allow_html=True)
    
    if st.button("🔄 Forzar actualización", use_container_width=True):
        with st.spinner("Actualizando Precios..."):
            actualizar_valores()
        st.sidebar.success("Datos actualizados correctamente")
        st.cache_data.clear()
        st.rerun()

SHEETS_MAP = {
    "Adrian": {"aportaciones": "Aportaciones_A"},
    "Oscar": {"aportaciones": "Aportaciones_B"},
    "Arancha": {"aportaciones": "Aportaciones_C"}
}

cfg = SHEETS_MAP[usuario]

# ==========================================
# CONEXIÓN GOOGLE SHEETS
# ==========================================
@st.cache_resource
def connect_gsheets():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    return gspread.authorize(creds)

client = connect_gsheets()

# ==========================================
# CARGA DE DATOS
# ==========================================
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

# ==========================================================
# Estilos de Celda Dinámicos para Evitar Fondos Blancos
# ==========================================================
def color_rentabilidad(val):
    try:
        val = float(val)
        if val > 0:
            return "background-color: #1e293b; color: #10b981; font-weight: bold; text-align: center;"
        elif val < 0:
            return "background-color: #1e293b; color: #f43f5e; font-weight: bold; text-align: center;"
    except:
        pass
    return "background-color: #1e293b; color: #f8fafc; text-align: center;"

def style_base_cells(val):
    return "background-color: #1e293b; color: #f8fafc; text-align: center;"

# ==========================================
# PROCESAMIENTO Y LÓGICA
# ==========================================
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

last_dates = (
    hist_df.loc[
        hist_df.groupby("fund")["date"].idxmax()
    ][["fund", "date"]]
    .rename(columns={"date": "last_date"})
)

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

    return pd.Series({
        "last_vl": last_vl,
        "prev_day_vl": prev_day,
        "week_vl": week_vl,
        "month_vl": month_vl
    })

metrics = hist_df.groupby(["fund", "isin"]).apply(calc_changes).reset_index()

metrics["%_1d"] = (metrics["last_vl"] - metrics["prev_day_vl"]) / metrics["prev_day_vl"] * 100
metrics["%_7d"] = (metrics["last_vl"] - metrics["week_vl"]) / metrics["week_vl"] * 100
metrics["%_30d"] = (metrics["last_vl"] - metrics["month_vl"]) / metrics["month_vl"] * 100

metrics_fund = metrics.groupby("fund").agg({
    "%_1d": "mean",
    "%_7d": "mean",
    "%_30d": "mean"
}).reset_index()

df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()

daily_cash = (
    df.groupby(["date", "fund"], as_index=False)["amount"]
    .sum()
    .rename(columns={"amount": "invested"})
)
daily_units = (
    df.groupby(["date", "fund"], as_index=False)["units"]
    .sum()
)

all_dates = pd.date_range(
    df["date"].min(),
    pd.Timestamp.today().normalize(),
    freq="D"
)

funds = df["fund"].dropna().unique()

grid = pd.MultiIndex.from_product(
    [all_dates, funds],
    names=["date", "fund"]
).to_frame(index=False)

evolution = grid.merge(
    daily_cash,
    on=["date", "fund"],
    how="left"
)

evolution = evolution.merge(
    daily_units,
    on=["date", "fund"],
    how="left"
)

hist_df["fund"] = hist_df["isin"].map(isin_to_fund)
hist_df = hist_df[["date", "fund", "vl"]]

evolution = evolution.merge(
    hist_df,
    on=["date", "fund"],
    how="left"
)

evolution = evolution.sort_values(["fund", "date"])

evolution["vl"] = (
    evolution.groupby("fund")["vl"].ffill()
)

dense = grid.merge(evolution, on=["date", "fund"], how="left")

dense["invested"] = dense["invested"].fillna(0)
dense["units"] = dense["units"].fillna(0)

dense["cum_invested"] = dense.groupby("fund")["invested"].cumsum()
dense["cum_units"] = dense.groupby("fund")["units"].cumsum()
dense["market_value"]=dense["cum_units"]*dense["vl"]

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
    "%_30d": "1 mes (%)",
    "last_date": "Última actualización"
})

portfolio = (
    dense.groupby("date", as_index=False)
    .agg(
        invested=("cum_invested", "sum"),
        value=("market_value", "sum")
    )
    .sort_values("date")
    .reset_index(drop=True)
)

portfolio = portfolio.dropna(subset=["value"])
portfolio = portfolio[portfolio["value"] > 0]

portfolio["profit"] = portfolio["value"] - portfolio["invested"]

portfolio["1d (%)"] =portfolio["value"].pct_change(1) * 100
portfolio["7d (%)"] = portfolio["value"].pct_change(7) * 100
portfolio["1m (%)"] = portfolio["value"].pct_change(30) * 100

last = portfolio.iloc[-2]

# ==========================================
# 🏛️ INTERFAZ OSCURA: TARJETAS EJECUTIVAS
# ==========================================
st.markdown("<h3 style='font-size: 22px; font-weight: 700; color: #f8fafc; margin-top: 0px; margin-bottom: 20px;'>💼 Evolución de la Inversión</h3>", unsafe_allow_html=True)
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.markdown(f"""
        <div style="background-color: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; box-shadow: 0 1px 2px rgba(0,0,0,0.2);">
            <p style="margin: 0; font-size: 12px; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">💰 Total Invertido</p>
            <p style="margin: 6px 0 0 0; font-size: 24px; font-weight: 700; color: #f8fafc;">{last['invested']:,.2f} €</p>
        </div>
    """, unsafe_allow_html=True)

with kpi2:
    st.markdown(f"""
        <div style="background-color: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; box-shadow: 0 1px 2px rgba(0,0,0,0.2);">
            <p style="margin: 0; font-size: 12px; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">📈 Valor Actual</p>
            <p style="margin: 6px 0 0 0; font-size: 24px; font-weight: 700; color: #60a5fa;">{last['value']:,.2f} €</p>
        </div>
    """, unsafe_allow_html=True)

with kpi3:
    rentabilidad_total = (last["profit"] / last["invested"]) * 100 if last["invested"] else 0
    color_ganancia = "#10b981" if last["profit"] >= 0 else "#f43f5e"
    st.markdown(f"""
        <div style="background-color: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; box-shadow: 0 1px 2px rgba(0,0,0,0.2);">
            <p style="margin: 0; font-size: 12px; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">🍀 Ganancia acumulada</p>
            <p style="margin: 6px 0 0 0; font-size: 24px; font-weight: 700; color: {color_ganancia};">{last['profit']:,.2f} € <span style="font-size: 14px; font-weight: 500; color: #94a3b8;">({rentabilidad_total:.2f}%)</span></p>
        </div>
    """, unsafe_allow_html=True)

with kpi4:
    color_var = "#10b981" if last["1d (%)"] >= 0 else "#f43f5e"
    signo = "+" if last["1d (%)"] >= 0 else ""
    st.markdown(f"""
        <div style="background-color: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; box-shadow: 0 1px 2px rgba(0,0,0,0.2);">
            <p style="margin: 0; font-size: 12px; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">⚡ Variación Diaria</p>
            <p style="margin: 6px 0 0 0; font-size: 24px; font-weight: 700; color: {color_var};">{signo}{last['1d (%)']:.2f} %</p>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)

# ==========================================================
# 📑 ESTRUCTURA EN PESTAÑAS (4 TABS SEPARADOS NATIVOS)
# ==========================================================
tab_resumen, tab_graficos, tab_evolucion, tab_detalles = st.tabs([
    "📋 Resumen de Fondos", 
    "📈 Gráficos de Evolución", 
    "📊 Historial de Evolución",
    "🔍 Detalle de Aportaciones"
])

# ----------------------------------------------------------
# TAB 1: RESUMEN DE FONDOS
# ----------------------------------------------------------
with tab_resumen:
    st.markdown("<h3 style='font-size: 18px; font-weight: 600; color: #f8fafc; margin-top: 10px; margin-bottom: 16px;'>📊 Distribución analítica por fondo</h3>", unsafe_allow_html=True)
    altura_tabla = 35 * len(final) + 38
    styled = (
        final.style
        .format({
            "Invertido": "{:,.2f} €",
            "Valor actual": "{:,.2f} €",
            "Ganancia": "{:,.2f} €",
            "Rentabilidad (%)": "{:.2f} %",
            "1 día (%)": "{:.2f} %",
            "7 días (%)": "{:.2f} %",
            "1 mes (%)": "{:.2f} %",
            "Última actualización": lambda x: x.strftime("%d/%m/%Y") if pd.notnull(x) else ""
        })
        .map(style_base_cells)
        .map(
            color_rentabilidad,
            subset=["Ganancia", "1 día (%)", "7 días (%)", "1 mes (%)","Rentabilidad (%)"]
        )
    )

    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        height=altura_tabla
    )

# ----------------------------------------------------------
# TAB 2: GRÁFICOS DE EVOLUCIÓN
# ----------------------------------------------------------
with tab_graficos:
    start_date = pd.Timestamp("2026-05-18")
    dense_filtered = dense[dense["date"] >= start_date]
    portfolio_graph = (
        dense_filtered.groupby("date", as_index=False)
        .agg(
            invested=("cum_invested", "sum"),
            value=("market_value", "sum")
        )
        .sort_values("date")
    )
    portfolio_graph["profit"] = (portfolio_graph["value"] - portfolio_graph["invested"])

    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(
            x=portfolio_graph["date"], y=portfolio_graph["invested"],
            name="Invertido", mode="lines", line=dict(color="#64748b", width=2)
        ))
        fig1.add_trace(go.Scatter(
            x=portfolio_graph["date"], y=portfolio_graph["value"],
            name="Valor cartera", mode="lines", line=dict(color="#3b82f6", width=3)
        ))
        fig1.update_layout(
            title=dict(
                text="Evolución inversión vs mercado", 
                font=dict(color="#f8fafc", size=18, family="Inter") # Unificación tamaño/color
            ),
            xaxis_title="Fecha", yaxis_title="€",
            template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            hovermode="x unified", margin=dict(l=10, r=10, t=50, b=10)
        )
        st.plotly_chart(fig1, use_container_width=True)

    with col_g2:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=portfolio_graph["date"], y=portfolio_graph["profit"],
            name="Beneficio", mode="lines", line=dict(color="#10b981", width=2.5)
        ))
        fig2.add_hline(y=0, line_dash="dash", line_color="#475569")
        fig2.update_layout(
            title=dict(
                text="Evolución del beneficio", 
                font=dict(color="#f8fafc", size=18, family="Inter") # Unificación tamaño/color
            ),
            xaxis_title="Fecha", yaxis_title="€",
            template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            hovermode="x unified", margin=dict(l=10, r=10, t=50, b=10)
        )
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    
    # Distribución de cartera
    latest = dense.sort_values("date").groupby("fund").tail(1)
    latest = latest.dropna(subset=["market_value"])
    alloc = (
        latest.groupby("fund", as_index=False)
        .agg(value=("market_value", "sum"))
        .sort_values("value", ascending=False)
    )

    fig_pie = go.Figure(
        data=[
            go.Pie(
                labels=alloc["fund"],
                values=alloc["value"],
                hole=0.55,
                textinfo="label+percent",
                textposition="inside",
                textfont=dict(size=14, color="white"),
                hovertemplate="<b>%{label}</b><br>Valor: %{value:,.0f} €<br>Peso: %{percent}<extra></extra>",
                sort=False,
                marker=dict(line=dict(color="#0f172a", width=2))
            )
        ]
    )
    import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import streamlit as st
import plotly.graph_objects as go

# ==========================================================
# 🌌 INTERFAZ COMPLETA EN MODO OSCURO (FORZADO POR CSS)
# ==========================================================
st.set_page_config(page_title="Inversiones", layout="wide", initial_sidebar_state="expanded")

# Inyección de CSS premium corregida para eliminar cabeceras blancas en tablas
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght=400;500;600;700&display=swap');
    
    /* Configuración de fuente y fondo global */
    html, body, [class*="css"], .main .block-container {
        font-family: 'Inter', sans-serif;
        color: #f8fafc !important;
    }
    
    /* Fondo oscuro obligatorio para toda la app y la barra lateral */
    .stApp, div[data-testid="stSidebar"] {
        background-color: #0f172a !important;
    }
    
    .main .block-container { padding-top: 1.5rem; }
    
    /* Asegurar textos legibles en la sidebar */
    div[data-testid="stSidebar"] p, div[data-testid="stSidebar"] h2, div[data-testid="stSidebar"] label {
        color: #f8fafc !important;
    }
    
    /* 🎨 CORRECCIÓN ABSOLUTA DE ENCABEZADOS DE TABLAS (EVITA FILAS BLANCAS) */
    div[data-testid="stDataFrame"] table thead tr th,
    div[data-testid="stDataFrame"] [data-testid="stDataFrame-HeaderCell"],
    .stDataFrame th, 
    thead th {
        background-color: #1e293b !important;
        color: #f8fafc !important; /* Texto en blanco premium */
        font-weight: 600 !important;
        text-transform: uppercase !important;
        font-size: 12px !important;
        letter-spacing: 0.5px !important;
        border-bottom: 2px solid #334155 !important;
    }
    
    /* Contenedor general de tablas con bordes suavizados */
    div[data-testid="stDataFrame"] {
        border: 1px solid #334155 !important;
        border-radius: 12px !important;
        overflow: hidden;
        background-color: #0f172a !important;
    }
    
    /* Unificación de color para títulos de pestañas (Tabs) */
    button[data-baseweb="tab"] p {
        color: #94a3b8 !important;
    }
    button[aria-selected="true"] p {
        color: #3b82f6 !important;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

SPREADSHEET_ID = "1QA6bpWTw_uILBwO3-z7GXfA3QOGor_EoX4m-ljdsTe4"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

from actualizar_valores import actualizar_valores

# ==========================================
# SIDEBAR REORGANIZADA
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='font-size: 18px; font-weight: 600; color: #f8fafc; margin-bottom: 12px;'>👤 Selección de Cartera</h2>", unsafe_allow_html=True)
    usuario = st.selectbox(
        "Elige cartera",
        ["Adrian", "Oscar", "Arancha"],
        label_visibility="collapsed"
    )
    
    st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("<h2 style='font-size: 16px; font-weight: 600; color: #f8fafc; margin-bottom: 12px;'>⚙️ Mantenimiento</h2>", unsafe_allow_html=True)
    
    if st.button("🔄 Forzar actualización", use_container_width=True):
        with st.spinner("Actualizando Precios..."):
            actualizar_valores()
        st.sidebar.success("Datos actualizados correctamente")
        st.cache_data.clear()
        st.rerun()

SHEETS_MAP = {
    "Adrian": {"aportaciones": "Aportaciones_A"},
    "Oscar": {"aportaciones": "Aportaciones_B"},
    "Arancha": {"aportaciones": "Aportaciones_C"}
}

cfg = SHEETS_MAP[usuario]

# ==========================================
# CONEXIÓN GOOGLE SHEETS
# ==========================================
@st.cache_resource
def connect_gsheets():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    return gspread.authorize(creds)

client = connect_gsheets()

# ==========================================
# CARGA DE DATOS
# ==========================================
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

# ==========================================================
# Estilos de Celda Dinámicos para Evitar Fondos Blancos
# ==========================================================
def color_rentabilidad(val):
    try:
        val = float(val)
        if val > 0:
            return "background-color: #1e293b; color: #10b981; font-weight: bold; text-align: center;"
        elif val < 0:
            return "background-color: #1e293b; color: #f43f5e; font-weight: bold; text-align: center;"
    except:
        pass
    return "background-color: #1e293b; color: #f8fafc; text-align: center;"

def style_base_cells(val):
    return "background-color: #1e293b; color: #f8fafc; text-align: center;"

# ==========================================
# PROCESAMIENTO Y LÓGICA
# ==========================================
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

last_dates = (
    hist_df.loc[
        hist_df.groupby("fund")["date"].idxmax()
    ][["fund", "date"]]
    .rename(columns={"date": "last_date"})
)

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

    return pd.Series({
        "last_vl": last_vl,
        "prev_day_vl": prev_day,
        "week_vl": week_vl,
        "month_vl": month_vl
    })

metrics = hist_df.groupby(["fund", "isin"]).apply(calc_changes).reset_index()

metrics["%_1d"] = (metrics["last_vl"] - metrics["prev_day_vl"]) / metrics["prev_day_vl"] * 100
metrics["%_7d"] = (metrics["last_vl"] - metrics["week_vl"]) / metrics["week_vl"] * 100
metrics["%_30d"] = (metrics["last_vl"] - metrics["month_vl"]) / metrics["month_vl"] * 100

metrics_fund = metrics.groupby("fund").agg({
    "%_1d": "mean",
    "%_7d": "mean",
    "%_30d": "mean"
}).reset_index()

df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()

daily_cash = (
    df.groupby(["date", "fund"], as_index=False)["amount"]
    .sum()
    .rename(columns={"amount": "invested"})
)
daily_units = (
    df.groupby(["date", "fund"], as_index=False)["units"]
    .sum()
)

all_dates = pd.date_range(
    df["date"].min(),
    pd.Timestamp.today().normalize(),
    freq="D"
)

funds = df["fund"].dropna().unique()

grid = pd.MultiIndex.from_product(
    [all_dates, funds],
    names=["date", "fund"]
).to_frame(index=False)

evolution = grid.merge(
    daily_cash,
    on=["date", "fund"],
    how="left"
)

evolution = evolution.merge(
    daily_units,
    on=["date", "fund"],
    how="left"
)

hist_df["fund"] = hist_df["isin"].map(isin_to_fund)
hist_df = hist_df[["date", "fund", "vl"]]

evolution = evolution.merge(
    hist_df,
    on=["date", "fund"],
    how="left"
)

evolution = evolution.sort_values(["fund", "date"])

evolution["vl"] = (
    evolution.groupby("fund")["vl"].ffill()
)

dense = grid.merge(evolution, on=["date", "fund"], how="left")

dense["invested"] = dense["invested"].fillna(0)
dense["units"] = dense["units"].fillna(0)

dense["cum_invested"] = dense.groupby("fund")["invested"].cumsum()
dense["cum_units"] = dense.groupby("fund")["units"].cumsum()
dense["market_value"]=dense["cum_units"]*dense["vl"]

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
    "%_30d": "1 mes (%)",
    "last_date": "Última actualización"
})

portfolio = (
    dense.groupby("date", as_index=False)
    .agg(
        invested=("cum_invested", "sum"),
        value=("market_value", "sum")
    )
    .sort_values("date")
    .reset_index(drop=True)
)

portfolio = portfolio.dropna(subset=["value"])
portfolio = portfolio[portfolio["value"] > 0]

portfolio["profit"] = portfolio["value"] - portfolio["invested"]

portfolio["1d (%)"] =portfolio["value"].pct_change(1) * 100
portfolio["7d (%)"] = portfolio["value"].pct_change(7) * 100
portfolio["1m (%)"] = portfolio["value"].pct_change(30) * 100

last = portfolio.iloc[-2]

# ==========================================
# 🏛️ INTERFAZ OSCURA: TARJETAS EJECUTIVAS
# ==========================================
st.markdown("<h3 style='font-size: 22px; font-weight: 700; color: #f8fafc; margin-top: 0px; margin-bottom: 20px;'>💼 Evolución de la Inversión</h3>", unsafe_allow_html=True)
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.markdown(f"""
        <div style="background-color: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; box-shadow: 0 1px 2px rgba(0,0,0,0.2);">
            <p style="margin: 0; font-size: 12px; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">💰 Total Invertido</p>
            <p style="margin: 6px 0 0 0; font-size: 24px; font-weight: 700; color: #f8fafc;">{last['invested']:,.2f} €</p>
        </div>
    """, unsafe_allow_html=True)

with kpi2:
    st.markdown(f"""
        <div style="background-color: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; box-shadow: 0 1px 2px rgba(0,0,0,0.2);">
            <p style="margin: 0; font-size: 12px; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">📈 Valor Actual</p>
            <p style="margin: 6px 0 0 0; font-size: 24px; font-weight: 700; color: #60a5fa;">{last['value']:,.2f} €</p>
        </div>
    """, unsafe_allow_html=True)

with kpi3:
    rentabilidad_total = (last["profit"] / last["invested"]) * 100 if last["invested"] else 0
    color_ganancia = "#10b981" if last["profit"] >= 0 else "#f43f5e"
    st.markdown(f"""
        <div style="background-color: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; box-shadow: 0 1px 2px rgba(0,0,0,0.2);">
            <p style="margin: 0; font-size: 12px; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">🍀 Ganancia acumulada</p>
            <p style="margin: 6px 0 0 0; font-size: 24px; font-weight: 700; color: {color_ganancia};">{last['profit']:,.2f} € <span style="font-size: 14px; font-weight: 500; color: #94a3b8;">({rentabilidad_total:.2f}%)</span></p>
        </div>
    """, unsafe_allow_html=True)

with kpi4:
    color_var = "#10b981" if last["1d (%)"] >= 0 else "#f43f5e"
    signo = "+" if last["1d (%)"] >= 0 else ""
    st.markdown(f"""
        <div style="background-color: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; box-shadow: 0 1px 2px rgba(0,0,0,0.2);">
            <p style="margin: 0; font-size: 12px; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">⚡ Variación Diaria</p>
            <p style="margin: 6px 0 0 0; font-size: 24px; font-weight: 700; color: {color_var};">{signo}{last['1d (%)']:.2f} %</p>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)

# ==========================================================
# 📑 ESTRUCTURA EN PESTAÑAS (4 TABS SEPARADOS NATIVOS)
# ==========================================================
tab_resumen, tab_graficos, tab_evolucion, tab_detalles = st.tabs([
    "📋 Resumen de Fondos", 
    "📈 Gráficos de Evolución", 
    "📊 Historial de Evolución",
    "🔍 Detalle de Aportaciones"
])

# ----------------------------------------------------------
# TAB 1: RESUMEN DE FONDOS
# ----------------------------------------------------------
with tab_resumen:
    st.markdown("<h3 style='font-size: 18px; font-weight: 600; color: #f8fafc; margin-top: 10px; margin-bottom: 16px;'>📊 Distribución analítica por fondo</h3>", unsafe_allow_html=True)
    altura_tabla = 35 * len(final) + 38
    styled = (
        final.style
        .format({
            "Invertido": "{:,.2f} €",
            "Valor actual": "{:,.2f} €",
            "Ganancia": "{:,.2f} €",
            "Rentabilidad (%)": "{:.2f} %",
            "1 día (%)": "{:.2f} %",
            "7 días (%)": "{:.2f} %",
            "1 mes (%)": "{:.2f} %",
            "Última actualización": lambda x: x.strftime("%d/%m/%Y") if pd.notnull(x) else ""
        })
        .map(style_base_cells)
        .map(
            color_rentabilidad,
            subset=["Ganancia", "1 día (%)", "7 días (%)", "1 mes (%)","Rentabilidad (%)"]
        )
    )

    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        height=altura_tabla
    )

# ----------------------------------------------------------
# TAB 2: GRÁFICOS DE EVOLUCIÓN
# ----------------------------------------------------------
with tab_graficos:
    start_date = pd.Timestamp("2026-05-18")
    dense_filtered = dense[dense["date"] >= start_date]
    portfolio_graph = (
        dense_filtered.groupby("date", as_index=False)
        .agg(
            invested=("cum_invested", "sum"),
            value=("market_value", "sum")
        )
        .sort_values("date")
    )
    portfolio_graph["profit"] = (portfolio_graph["value"] - portfolio_graph["invested"])

    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(
            x=portfolio_graph["date"], y=portfolio_graph["invested"],
            name="Invertido", mode="lines", line=dict(color="#64748b", width=2)
        ))
        fig1.add_trace(go.Scatter(
            x=portfolio_graph["date"], y=portfolio_graph["value"],
            name="Valor cartera", mode="lines", line=dict(color="#3b82f6", width=3)
        ))
        fig1.update_layout(
            title=dict(
                text="Evolución inversión vs mercado", 
                font=dict(color="#f8fafc", size=18, family="Inter") # Unificación tamaño/color
            ),
            xaxis_title="Fecha", yaxis_title="€",
            template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            hovermode="x unified", margin=dict(l=10, r=10, t=50, b=10)
        )
        st.plotly_chart(fig1, use_container_width=True)

    with col_g2:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=portfolio_graph["date"], y=portfolio_graph["profit"],
            name="Beneficio", mode="lines", line=dict(color="#10b981", width=2.5)
        ))
        fig2.add_hline(y=0, line_dash="dash", line_color="#475569")
        fig2.update_layout(
            title=dict(
                text="Evolución del beneficio", 
                font=dict(color="#f8fafc", size=18, family="Inter") # Unificación tamaño/color
            ),
            xaxis_title="Fecha", yaxis_title="€",
            template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            hovermode="x unified", margin=dict(l=10, r=10, t=50, b=10)
        )
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    
    # Distribución de cartera
    latest = dense.sort_values("date").groupby("fund").tail(1)
    latest = latest.dropna(subset=["market_value"])
    alloc = (
        latest.groupby("fund", as_index=False)
        .agg(value=("market_value", "sum"))
        .sort_values("value", ascending=False)
    )

    fig_pie = go.Figure(
        data=[
            go.Pie(
                labels=alloc["fund"],
                values=alloc["value"],
                hole=0.55,
                textinfo="label+percent",
                textposition="inside",
                textfont=dict(size=14, color="white"),
                hovertemplate="<b>%{label}</b><br>Valor: %{value:,.0f} €<br>Peso: %{percent}<extra></extra>",
                sort=False,
                marker=dict(line=dict(color="#0f172a", width=2))
            )
        ]
    )
    fig_pie.update_layout(
        title=dict(
            text="📊 Distribución de la cartera", 
            x=0.0, # <--- Cambiado de 0.5 a 0.0 para alinearlo perfectamente a la izquierda con los otros gráficos
            font=dict(color="#f8fafc", size=18, family="Inter")
        ),
        template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False, height=650, margin=dict(l=10, r=20, t=60, b=20) # Reducido margen izquierdo a 10
    )

# ----------------------------------------------------------
# TAB 3: HISTORIAL DE EVOLUCIÓN (PESTAÑA INDEPENDIENTE)
# ----------------------------------------------------------
with tab_evolucion:
    st.markdown("<h3 style='font-size: 18px; font-weight: 600; color: #f8fafc; margin-top: 10px; margin-bottom: 16px;'>📊 Historial Cronológico de Rendimientos</h3>", unsafe_allow_html=True)
    
    df_view_evo = portfolio_graph.sort_values("date", ascending=False).rename(columns={
        "date": "Fecha", "invested": "Invertido", "value": "Precio", "profit":"Ganancia",
    })
    
    styled_evo = (
        df_view_evo.style
        .format({
            "Fecha": lambda x: x.strftime("%d/%m/%Y") if pd.notnull(x) else "",
            "Invertido": "{:,.2f} €", "Precio": "{:,.2f} €", "Ganancia": "{:,.2f} €"
        })
        .map(style_base_cells)
        .map(color_rentabilidad, subset=["Ganancia"])
    )
    st.dataframe(styled_evo, use_container_width=True, hide_index=True)

# ----------------------------------------------------------
# TAB 4: DETALLE DE APORTACIONES
# ----------------------------------------------------------
with tab_detalles:
    st.markdown("<h3 style='font-size: 18px; font-weight: 600; color: #f8fafc; margin-top: 10px; margin-bottom: 16px;'>🔍 Historial completo de movimientos</h3>", unsafe_allow_html=True)
    
    col_select, _ = st.columns([1, 2])
    with col_select:
        fondo = st.selectbox(
            "Selecciona un fondo",
            ["Todos"] + sorted(df["fund"].dropna().unique().tolist())
        )

    if fondo != "Todos":
        df_filtrado = df[df["fund"] == fondo]
    else:
        df_filtrado = df.copy()

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
        .map(style_base_cells)
        .map(color_rentabilidad, subset=["Ganancia","Rentabilidad (%)"])
    )

    st.dataframe(styled_detalles, use_container_width=True, hide_index=True)
    st.plotly_chart(fig_pie, use_container_width=True)

# ----------------------------------------------------------
# TAB 3: HISTORIAL DE EVOLUCIÓN (PESTAÑA INDEPENDIENTE)
# ----------------------------------------------------------
with tab_evolucion:
    st.markdown("<h3 style='font-size: 18px; font-weight: 600; color: #f8fafc; margin-top: 10px; margin-bottom: 16px;'>📊 Historial Cronológico de Rendimientos</h3>", unsafe_allow_html=True)
    
    df_view_evo = portfolio_graph.sort_values("date", ascending=False).rename(columns={
        "date": "Fecha", "invested": "Invertido", "value": "Precio", "profit":"Ganancia",
    })
    
    styled_evo = (
        df_view_evo.style
        .format({
            "Fecha": lambda x: x.strftime("%d/%m/%Y") if pd.notnull(x) else "",
            "Invertido": "{:,.2f} €", "Precio": "{:,.2f} €", "Ganancia": "{:,.2f} €"
        })
        .map(style_base_cells)
        .map(color_rentabilidad, subset=["Ganancia"])
    )
    st.dataframe(styled_evo, use_container_width=True, hide_index=True)

# ----------------------------------------------------------
# TAB 4: DETALLE DE APORTACIONES
# ----------------------------------------------------------
with tab_detalles:
    st.markdown("<h3 style='font-size: 18px; font-weight: 600; color: #f8fafc; margin-top: 10px; margin-bottom: 16px;'>🔍 Historial completo de movimientos</h3>", unsafe_allow_html=True)
    
    col_select, _ = st.columns([1, 2])
    with col_select:
        fondo = st.selectbox(
            "Selecciona un fondo",
            ["Todos"] + sorted(df["fund"].dropna().unique().tolist())
        )

    if fondo != "Todos":
        df_filtrado = df[df["fund"] == fondo]
    else:
        df_filtrado = df.copy()

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
        .map(style_base_cells)
        .map(color_rentabilidad, subset=["Ganancia","Rentabilidad (%)"])
    )

    st.dataframe(styled_detalles, use_container_width=True, hide_index=True)