import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import streamlit as st
import plotly.graph_objects as go

# ==========================================================
# 🌌 INTERFAZ COMPLETA EN MODO OSCURO TRABAJADA (CSS PREMIUM)
# ==========================================================
st.set_page_config(page_title="Inversiones", layout="wide", initial_sidebar_state="expanded")

# Inyección de CSS global (Sidebar, Inputs, Selectores, Contenedores y File Uploader)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght=400;500;600;700&display=swap');
    
    html, body, [class*="css"], .main .block-container {
        font-family: 'Inter', sans-serif;
        color: #f8fafc !important;
    }
    
    /* Fondo principal de la app y Sidebar unificado */
    .stApp, div[data-testid="stSidebar"] {
        background-color: #0f172a !important;
    }
    
    /* Tunear la barra lateral (Bordes y elementos) */
    div[data-testid="stSidebar"] {
        border-right: 1px solid #1e293b;
    }
    div[data-testid="stSidebar"] p, div[data-testid="stSidebar"] h2, div[data-testid="stSidebar"] label {
        color: #f8fafc !important;
    }
    
    .main .block-container { padding-top: 1.5rem; }
    
    /* 🎨 ARREGLO DE LOS SELECTBOX (DESPLEGABLES) Y SIDEBAR NATIVOS */
    div[data-baseweb="select"] {
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
    }
    div[data-baseweb="select"] * {
        color: #f8fafc !important; 
        background-color: transparent !important;
    }
    /* Lista desplegada (Opciones flotantes del selectbox) */
    ul[data-baseweb="menu"] {
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
    }
    ul[data-baseweb="menu"] li {
        color: #f8fafc !important;
        background-color: #1e293b !important;
    }
    ul[data-baseweb="menu"] li:hover {
        background-color: #334155 !important; 
    }
    
    /* Botones nativos en la barra lateral */
    div[data-testid="stSidebar"] button {
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        color: #f8fafc !important;
    }
    div[data-testid="stSidebar"] button:hover {
        border-color: #3b82f6 !important;
        color: #3b82f6 !important;
    }
    
    /* 🎨 TUNEAR CAJA DE SUBIDA DE ARCHIVOS (FILE UPLOADER) */
    div[data-testid="stFileUploader"] {
        background-color: #1e293b !important;
        border: 1px dashed #334155 !important;
        border-radius: 8px !important;
        padding: 10px !important;
    }
    div[data-testid="stFileUploader"] section {
        background-color: transparent !important;
    }
    div[data-testid="stFileUploader"] label {
        display: none !important; 
    }
    
    /* 📌 Pestañas (Tabs) estilo Hub Financiero - Tamaño Grande */
    button[data-baseweb="tab"] p {
        color: #94a3b8 !important;
        font-size: 20px !important; 
        font-weight: 500 !important;
        padding: 4px 8px !important;
    }
    button[aria-selected="true"] p {
        color: #3b82f6 !important; 
        font-size: 20px !important; 
        font-weight: 700 !important; 
    }
    div[data-things="tab-border"] {
        background-color: #334155 !important;
    }
    </style>
""", unsafe_allow_html=True)

# 🎨 HOJA DE ESTILOS PARA LAS TABLAS HTML (SIN ESPACIOS VACÍOS)
st.markdown("""
    <style>
    .financial-table-container {
        width: 100%;
        overflow-x: auto;
        border: 1px solid #334155;
        border-radius: 12px;
        background-color: #1e293b;
        margin-bottom: 25px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    table.financial-table {
        width: 100%;
        border-collapse: collapse;
        color: #f8fafc;
        font-size: 14px;
        text-align: center;
    }
    
    /* CABECERA PREMIUM OSCURA */
    table.financial-table thead tr {
        background-color: #0f172a !important;
        border-bottom: 2px solid #334155;
    }
    
    table.financial-table th {
        padding: 14px 16px;
        font-weight: 700;
        text-transform: uppercase;
        font-size: 12px;
        letter-spacing: 0.5px;
        color: #cbd5e1 !important;
    }
    
    /* Celdas del cuerpo */
    table.financial-table td {
        padding: 12px 16px;
        border-bottom: 1px solid #334155;
        font-weight: 500;
    }
    
    /* Eliminar borde de la última fila para evitar espacios extraños */
    table.financial-table tbody tr:last-child td {
        border-bottom: none;
    }
    
    /* Alternancia de filas */
    table.financial-table tbody tr:nth-of-type(even) {
        background-color: #1a2333;
    }
    
    /* Efecto Hover */
    table.financial-table tbody tr:hover {
        background-color: #243146;
        transition: background-color 0.15s ease;
    }
    
    /* Formatos de rendimiento */
    .pos-val { color: #10b981 !important; font-weight: 700; }
    .neg-val { color: #f43f5e !important; font-weight: 700; }
    </style>
""", unsafe_allow_html=True)

# ==========================================================
# FUNCIÓN COMPONENTE: RENDERIZADOR OPTIMIZADO (EVITA FILAS VACÍAS)
# ==========================================================
def render_financial_table(df_styled, cols_color_render=None):
    df_clean = df_styled.dropna(how='all').reset_index(drop=True)
    
    html_table = f'<div class="financial-table-container">'
    html_table += f'<table class="financial-table">'
    
    html_table += '<thead><tr>'
    for col in df_clean.columns:
        html_table += f'<th>{col}</th>'
    html_table += '</tr></thead>'
    
    html_table += '<tbody>'
    for _, row in df_clean.iterrows():
        if row.astype(str).str.strip().eq("").all():
            continue
            
        html_table += '<tr>'
        for col in df_clean.columns:
            val_str = str(row[col]).strip()
            
            if val_str == "nan" or val_str == "None":
                val_str = ""
                
            cell_class = ""
            
            if cols_color_render and col in cols_color_render and val_str:
                if "-" in val_str:
                    cell_class = ' class="neg-val"'
                elif val_str != "0.00 %" and val_str != "0.00 €" and any(char.isdigit() for char in val_str):
                    cell_class = ' class="pos-val"'
            
            html_table += f'<td{cell_class}>{val_str}</td>'
        html_table += '</tr>'
    html_table += '</tbody></table></div>'
    
    st.write(html_table, unsafe_allow_html=True)


# ==========================================================
# FUNCIÓN COMPONENTE: PROCESADOR DE CSV CORREGIDO
# ==========================================================
def procesar_y_subir_csv(uploaded_file, client, spreadsheet_id, sheet_name):
    try:
        # Leer usando punto y coma como separador
        nuevo_df = pd.read_csv(uploaded_file, sep=';')
        
        # Validar columnas requeridas basadas en el archivo real
        columnas_banco = ["Fecha de la orden", "ISIN", "Importe estimado", "Nº de participaciones"]
        for col in columnas_banco:
            if col not in nuevo_df.columns:
                st.sidebar.error(f"❌ Estructura incorrecta. Falta la columna: '{col}'")
                return False
        
        # Limpieza de importes y participaciones
        nuevo_df["Importe estimado"] = (
            nuevo_df["Importe estimado"]
            .astype(str)
            .str.replace(" EUR", "", case=False)
            .str.replace(".", "")
            .str.replace(",", ".")
            .astype(float)
        )
        
        nuevo_df["Nº de participaciones"] = (
            nuevo_df["Nº de participaciones"]
            .astype(str)
            .str.replace(".", "")
            .str.replace(",", ".")
            .astype(float)
        )
        
        # Calcular precio implícito (Precio = Importe / Participaciones)
        nuevo_df["price"] = nuevo_df["Importe estimado"] / nuevo_df["Nº de participaciones"]
        
        # AJUSTE DE ORDEN EXACTO PARA GOOGLE SHEETS: [amount, price, date, isin]
        # De acuerdo a la asignación de tu script: 
        # df["amount"] (Col A), df["price"] (Col B), df["date"] (Col C), df["isin"] (Col D)
        filas_finales = []
        for _, fila in nuevo_df.iterrows():
            registro = [
                float(fila["Importe estimado"]), # Col A: amount
                round(float(fila["price"]), 4),  # Col B: price
                str(fila["Fecha de la orden"]),  # Col C: date
                str(fila["ISIN"])                # Col D: isin
            ]
            filas_finales.append(registro)
            
        if len(filas_finales) > 0:
            sh = client.open_by_key(spreadsheet_id)
            ws = sh.worksheet(sheet_name)
            ws.append_rows(filas_finales, value_input_option="USER_ENTERED")
            return True
        else:
            st.sidebar.warning("⚠️ No se encontraron registros válidos.")
            return False
            
    except Exception as e:
        st.sidebar.error(f"❌ Error procesando el archivo: {str(e)}")
        return False


SPREADSHEET_ID = "1QA6bpWTw_uILBwO3-z7GXfA3QOGor_EoX4m-ljdsTe4"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

from actualizar_valores import actualizar_valores

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

SHEETS_MAP = {
    "Adrian": {"aportaciones": "Aportaciones_A"},
    "Oscar": {"aportaciones": "Aportaciones_B"},
    "Arancha": {"aportaciones": "Aportaciones_C"}
}

# ==========================================
# SIDEBAR ESTILIZADA CON CARGADOR DE CSV
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='font-size: 16px; font-weight: 600; color: #f8fafc; margin-bottom: 10px; margin-top: 10px;'>👤 Cartera Activa</h2>", unsafe_allow_html=True)
    usuario = st.selectbox(
        "Elige cartera",
        ["Adrian", "Oscar", "Arancha"],
        label_visibility="collapsed"
    )
    
    st.markdown("<div style='margin: 15px 0;'></div>", unsafe_allow_html=True)
    st.markdown("<hr style='border-color: #1e293b;'>", unsafe_allow_html=True)
    
    # 📥 FUNCIONALIDAD: SUBIR CSV
    st.markdown("<h2 style='font-size: 15px; font-weight: 600; color: #f8fafc; margin-bottom: 5px;'>📥 Importar Órdenes CSV</h2>", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 12px; color: #94a3b8; margin-bottom: 12px;'>Sube el archivo de órdenes exportado de tu plataforma.</p>", unsafe_allow_html=True)
    
    archivo_csv = st.file_uploader("Subir CSV", type=["csv"], label_visibility="collapsed")
    
    if archivo_csv is not None:
        if st.button("🚀 Cargar Aportaciones", use_container_width=True):
            with st.spinner("Procesando y subiendo a Google Sheets..."):
                hoja_destino = SHEETS_MAP[usuario]["aportaciones"]
                exito = procesar_y_subir_csv(archivo_csv, client, SPREADSHEET_ID, hoja_destino)
                
                if exito:
                    st.sidebar.success("✅ ¡Órdenes añadidas con éxito!")
                    st.cache_data.clear()
                    st.rerun()

    st.markdown("<div style='margin: 15px 0;'></div>", unsafe_allow_html=True)
    st.markdown("<hr style='border-color: #1e293b;'>", unsafe_allow_html=True)
    st.markdown("<h2 style='font-size: 15px; font-weight: 600; color: #94a3b8; margin-bottom: 10px;'>⚙️ Sistema</h2>", unsafe_allow_html=True)
    
    if st.button("🔄 Actualizar Cotizaciones", use_container_width=True):
        with st.spinner("Conectando con mercados..."):
            actualizar_valores()
        st.sidebar.success("Datos actualizados")
        st.cache_data.clear()
        st.rerun()

cfg = SHEETS_MAP[usuario]

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
      .agg(invertido=("amount", "sum"), valor_actual=("valor_actual", "sum"), beneficio=("beneficio", "sum"))
      .reset_index()
)
resumen["rentabilidad"] = resumen["beneficio"] / resumen["invertido"] * 100

last_dates = (
    hist_df.loc[hist_df.groupby("fund")["date"].idxmax()][["fund", "date"]]
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
    "rentabilidad": "Rentabilidad (%)", "%_1d": "1 día (%)", "%_7d": "7 días (%)", "%_30d": "1 mes (%)",
    "last_date": "Última actualización"
})

portfolio = dense.groupby("date", as_index=False).agg(invested=("cum_invested", "sum"), value=("market_value", "sum")).sort_values("date").reset_index(drop=True)
portfolio = portfolio.dropna(subset=["value"])
portfolio = portfolio[portfolio["value"] > 0]
portfolio["profit"] = portfolio["value"] - portfolio["invested"]
portfolio["1d (%)"] = portfolio["value"].pct_change(1) * 100

last = portfolio.iloc[-2]

# ==========================================
# TARJETAS DE MÉTRICAS
# ==========================================
st.markdown("<h3 style='font-size: 20px; font-weight: 700; color: #f8fafc; margin-top: 5px; margin-bottom: 20px;'>💼 Evolución de la Inversión</h3>", unsafe_allow_html=True)
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.markdown(f'<div style="background-color: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155;"><p style="margin: 0; font-size: 11px; color: #94a3b8; font-weight: 600; text-transform: uppercase;">💰 Total Invertido</p><p style="margin: 6px 0 0 0; font-size: 24px; font-weight: 700; color: #f8fafc;">{last["invested"]:,.2f} €</p></div>', unsafe_allow_html=True)
with kpi2:
    st.markdown(f'<div style="background-color: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155;"><p style="margin: 0; font-size: 11px; color: #94a3b8; font-weight: 600; text-transform: uppercase;">📈 Valor Actual</p><p style="margin: 6px 0 0 0; font-size: 24px; font-weight: 700; color: #60a5fa;">{last["value"]:,.2f} €</p></div>', unsafe_allow_html=True)
with kpi3:
    rentabilidad_total = (last["profit"] / last["invested"]) * 100 if last["invested"] else 0
    color_ganancia = "#10b981" if last["profit"] >= 0 else "#f43f5e"
    st.markdown(f'<div style="background-color: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155;"><p style="margin: 0; font-size: 11px; color: #94a3b8; font-weight: 600; text-transform: uppercase;">🍀 Ganancia acumulada</p><p style="margin: 6px 0 0 0; font-size: 24px; font-weight: 700; color: {color_ganancia};">{last["profit"]:,.2f} € <span style="font-size: 13px; color: #94a3b8;">({rentabilidad_total:.2f}%)</span></p></div>', unsafe_allow_html=True)
with kpi4:
    color_var = "#10b981" if last["1d (%)"] >= 0 else "#f43f5e"
    signo = "+" if last["1d (%)"] >= 0 else ""
    st.markdown(f'<div style="background-color: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155;"><p style="margin: 0; font-size: 11px; color: #94a3b8; font-weight: 600; text-transform: uppercase;">⚡ Variación Diaria</p><p style="margin: 6px 0 0 0; font-size: 24px; font-weight: 700; color: {color_var};">{signo}{last["1d (%)"]:.2f} %</p></div>', unsafe_allow_html=True)

st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)

# PESTAÑAS (TABS NATIVOS AGRANDADOS)
tab_resumen, tab_graficos, tab_evolucion, tab_detalles = st.tabs([
    "📋 Resumen de Fondos", "📈 Gráficos de Evolución", "📊 Historial de Evolución", "🔍 Detalle de Aportaciones"
])

# TAB 1: RESUMEN DE FONDOS
with tab_resumen:
    st.markdown("<h3 style='font-size: 16px; font-weight: 600; color: #f8fafc; margin-top: 10px; margin-bottom: 16px;'>📊 Distribución analítica por fondo</h3>", unsafe_allow_html=True)
    
    final_html = final.copy()
    final_html["Invertido"] = final_html["Invertido"].map("{:,.2f} €".format)
    final_html["Valor actual"] = final_html["Valor actual"].map("{:,.2f} €".format)
    final_html["Ganancia"] = final_html["Ganancia"].map("{:,.2f} €".format)
    final_html["Rentabilidad (%)"] = final_html["Rentabilidad (%)"].map("{:.2f} %".format)
    final_html["1 día (%)"] = final_html["1 día (%)"].map("{:.2f} %".format)
    final_html["7 días (%)"] = final_html["7 días (%)"].map("{:.2f} %".format)
    final_html["1 mes (%)"] = final_html["1 mes (%)"].map("{:.2f} %".format)
    final_html["Última actualización"] = final_html["Última actualización"].apply(lambda x: x.strftime("%d/%m/%Y") if pd.notnull(x) else "")

    render_financial_table(final_html, cols_color_render=["Ganancia", "1 día (%)", "7 días (%)", "1 mes (%)", "Rentabilidad (%)"])

# TAB 2: GRÁFICOS
with tab_graficos:
    start_date = pd.Timestamp("2026-05-18")
    dense_filtered = dense[dense["date"] >= start_date]
    portfolio_graph = dense_filtered.groupby("date", as_index=False).agg(invested=("cum_invested", "sum"), value=("market_value", "sum")).sort_values("date")
    portfolio_graph["profit"] = (portfolio_graph["value"] - portfolio_graph["invested"])

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=portfolio_graph["date"], y=portfolio_graph["invested"], name="Invertido", mode="lines", line=dict(color="#64748b", width=2)))
        fig1.add_trace(go.Scatter(x=portfolio_graph["date"], y=portfolio_graph["value"], name="Valor cartera", mode="lines", line=dict(color="#3b82f6", width=3)))
        fig1.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig1, use_container_width=True)
    with col_g2:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=portfolio_graph["date"], y=portfolio_graph["profit"], name="Beneficio", mode="lines", line=dict(color="#10b981", width=2.5)))
        fig2.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig2, use_container_width=True)

# TAB 3: HISTORIAL DE EVOLUCIÓN
with tab_evolucion:
    st.markdown("<h3 style='font-size: 16px; font-weight: 600; color: #f8fafc; margin-top: 10px; margin-bottom: 16px;'>📊 Historial Cronológico de Rendimientos</h3>", unsafe_allow_html=True)
    df_view_evo = portfolio_graph.sort_values("date", ascending=False).rename(columns={"date": "Fecha", "invested": "Invertido", "value": "Precio", "profit":"Ganancia"})
    df_evo_html = df_view_evo.copy()
    df_evo_html["Fecha"] = df_evo_html["Fecha"].apply(lambda x: x.strftime("%d/%m/%Y") if pd.notnull(x) else "")
    df_evo_html["Invertido"] = df_evo_html["Invertido"].map("{:,.2f} €".format)
    df_evo_html["Precio"] = df_evo_html["Precio"].map("{:,.2f} €".format)
    df_evo_html["Ganancia"] = df_evo_html["Ganancia"].map("{:,.2f} €".format)
    render_financial_table(df_evo_html, cols_color_render=["Ganancia"])

# TAB 4: DETALLE DE APORTACIONES
with tab_detalles:
    st.markdown("<h3 style='font-size: 16px; font-weight: 600; color: #f8fafc; margin-top: 10px; margin-bottom: 16px;'>🔍 Historial completo de movimientos</h3>", unsafe_allow_html=True)
    
    col_select, _ = st.columns([1.5, 2])
    with col_select:
        fondo = st.selectbox("Filtrar por fondo específico:", ["Todos"] + sorted(df["fund"].dropna().unique().tolist()))

    df_filtrado = df[df["fund"] == fondo] if fondo != "Todos" else df.copy()
    df_view = df_filtrado.sort_values("date", ascending=False).rename(columns={
        "date": "Fecha", "amount": "Invertido", "price": "Precio", "fund":"Fondo", "isin":"ISIN",
        "current_price": "Precio Actual", "valor_actual": "Valor Actual", "beneficio": "Ganancia", "rentabilidad": "Rentabilidad (%)"
    })
    df_view = df_view[["Fecha", "Fondo", "ISIN", "Invertido", "Valor Actual", "Precio", "Precio Actual", "Ganancia", "Rentabilidad (%)"]]

    df_detalles_html = df_view.copy()
    df_detalles_html["Fecha"] = df_detalles_html["Fecha"].apply(lambda x: x.strftime("%d/%m/%Y") if pd.notnull(x) else "")
    df_detalles_html["Invertido"] = df_detalles_html["Invertido"].map("{:,.2f} €".format)
    df_detalles_html["Precio"] = df_detalles_html["Precio"].map("{:,.2f} €".format)
    df_detalles_html["Precio Actual"] = df_detalles_html["Precio Actual"].map("{:,.2f} €".format)
    df_detalles_html["Valor Actual"] = df_detalles_html["Valor Actual"].map("{:,.2f} €".format)
    df_detalles_html["Ganancia"] = df_detalles_html["Ganancia"].map("{:,.2f} €".format)
    df_detalles_html["Rentabilidad (%)"] = df_detalles_html["Rentabilidad (%)"].map("{:.2f} %".format)

    render_financial_table(df_detalles_html, cols_color_render=["Ganancia", "Rentabilidad (%)"])