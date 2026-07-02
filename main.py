import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import streamlit as st
import plotly.graph_objects as go
import datetime
import numpy as np

# ==========================================================
# 🌌 INTERFAZ COMPLETA EN MODO OSCURO (CSS PREMIUM)
# ==========================================================
st.set_page_config(page_title="Inversiones", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght=400;500;600;700&display=swap');
    
    html, body, [class*="css"], .main .block-container {
        font-family: 'Inter', sans-serif;
        color: #f8fafc !important;
    }
    
    .stApp, div[data-testid="stSidebar"] {
        background-color: #0f172a !important;
    }
    
    div[data-testid="stSidebar"] {
        border-right: 1px solid #1e293b;
    }
    div[data-testid="stSidebar"] p, div[data-testid="stSidebar"] h2, div[data-testid="stSidebar"] label {
        color: #f8fafc !important;
    }
    
    .main .block-container { padding-top: 1.5rem; }
    
    div[data-baseweb="select"] {
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
    }
    div[data-baseweb="select"] * {
        color: #f8fafc !important; 
        background-color: transparent !important;
    }
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
    
    div[data-testid="stSidebar"] button {
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        color: #f8fafc !important;
    }
    div[data-testid="stSidebar"] button:hover {
        border-color: #3b82f6 !important;
        color: #3b82f6 !important;
    }
    
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
    table.financial-table td {
        padding: 12px 16px;
        border-bottom: 0px solid #334155;
        font-weight: 500;
        vertical-align: middle;
    }
    table.financial-table tbody tr:last-child td {
        border-bottom: none;
    }
    table.financial-table tbody tr:nth-of-type(even) {
        background-color: #1a2333;
    }
    table.financial-table tbody tr:hover {
        background-color: #243146;
        transition: background-color 0.15s ease;
    }
    .pos-val { color: #10b981 !important; font-weight: 700; }
    .neg-val { color: #f43f5e !important; font-weight: 700; }
    .sparkline-container { display: flex; justify-content: center; align-items: center; }
    </style>
""", unsafe_allow_html=True)

def generate_sparkline_svg(values):
    if not isinstance(values, list) or len(values) < 2:
        return ""
    try:
        values = [float(v) for v in values]
    except:
        return ""
    
    min_v, max_v = min(values), max(values)
    rng = max_v - min_v if max_v != min_v else 1
    
    referencia = values[0]
    pct_referencia = 100 - (((referencia - min_v) / rng) * 100)
    pct_referencia = max(5, min(95, pct_referencia))
    
    width, height = 120, 30
    padding = 2
    
    points = []
    for i, v in enumerate(values):
        x = padding + (i / (len(values) - 1)) * (width - 2 * padding)
        y = (height - padding) - ((v - min_v) / rng) * (height - 2 * padding)
        points.append(f"{x},{y}")
    
    polyline_str = " ".join(points)
    color_final = "#10b981" if values[-1] >= values[0] else "#f43f5e"
    gradient_id = f"grad_{abs(hash(polyline_str))}"
    
    svg = f"""
    <div class="sparkline-container">
        <svg width="{width}" height="{height}">
            <defs>
                <linearGradient id="{gradient_id}" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stop-color="#10b981" />
                    <stop offset="{pct_referencia}%" stop-color="#10b981" />
                    <stop offset="{pct_referencia}%" stop-color="#f43f5e" />
                    <stop offset="100%" stop-color="#f43f5e" />
                </linearGradient>
            </defs>
            <line x1="{padding}" y1="{(height-padding)-((referencia-min_v)/rng)*(height-2*padding)}" x2="{width-padding}" y2="{(height-padding)-((referencia-min_v)/rng)*(height-2*padding)}" stroke="rgba(148, 163, 184, 0.15)" stroke-width="1" stroke-dasharray="2,2" />
            <polyline fill="none" stroke="url(#{gradient_id})" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" points="{polyline_str}"/>
            <circle cx="{points[-1].split(',')[0]}" cy="{points[-1].split(',')[1]}" r="2.5" fill="{color_final}"/>
        </svg>
    </div>
    """
    return svg

def render_financial_table(df_styled, cols_color_render=None):
    df_clean = df_styled.dropna(how='all').reset_index(drop=True)
    html_table = f'<div class="financial-table-container"><table class="financial-table"><thead><tr>'
    for col in df_clean.columns:
        html_table += f'<th>{col}</th>'
    html_table += '</tr></thead><tbody>'
    
    for _, row in df_clean.iterrows():
        if row.astype(str).str.strip().eq("").all():
            continue
        html_table += '<tr>'
        for col in df_clean.columns:
            val = row[col]
            if isinstance(val, list):
                sparkline_content = generate_sparkline_svg(val)
                html_table += f'<td>{sparkline_content}</td>'
                continue
                
            val_str = str(val).strip()
            if val_str == "nan" or val_str == "None" or val_str == "-":
                val_str = "-"
            cell_class = ""
            if cols_color_render and col in cols_color_render and val_str != "-":
                if "-" in val_str:
                    cell_class = ' class="neg-val"'
                elif val_str != "0.00 %" and val_str != "0.00 €" and any(char.isdigit() for char in val_str):
                    cell_class = ' class="pos-val"'
            html_table += f'<td{cell_class}>{val_str}</td>'
        html_table += '</tr>'
    html_table += '</tbody></table></div>'
    st.write(html_table, unsafe_allow_html=True)


SPREADSHEET_ID = "1QA6bpWTw_uILBwO3-z7GXfA3QOGor_EoX4m-ljdsTe4"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

from actualizar_valores import actualizar_valores

@st.cache_resource
def connect_gsheets():
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
    return gspread.authorize(creds)

client = connect_gsheets()

SHEETS_MAP = {
    "Adrian": {"aportaciones": "Aportaciones_A"},
    "Oscar": {"aportaciones": "Aportaciones_B"},
    "Arancha": {"aportaciones": "Aportaciones_C"}
}

@st.cache_data(ttl=300)
def load_fondos_dict():
    try:
        sh = client.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet("Fondos")
        df_f = pd.DataFrame(ws.get_all_records())
        return dict(zip(df_f["isin"].astype(str).str.strip(), df_f["fondo"].astype(str).str.strip()))
    except:
        return {}

isin_to_fund_global = load_fondos_dict()

# ========================================================
# SIDEBAR CON PROCESAMIENTO SEGURO DEL CSV
# ========================================================
with st.sidebar:
    st.markdown("<h2 style='font-size: 16px; font-weight: 600; color: #f8fafc; margin-bottom: 10px; margin-top: 10px;'>👤 Cartera Activa</h2>", unsafe_allow_html=True)
    usuario = st.selectbox("Elige cartera", ["Adrian", "Oscar", "Arancha"], label_visibility="collapsed")
    
    st.markdown("<hr style='border-color: #1e293b;'>", unsafe_allow_html=True)
    st.markdown("<h2 style='font-size: 15px; font-weight: 600; color: #f8fafc; margin-bottom: 5px;'>📥 Importar Órdenes CSV</h2>", unsafe_allow_html=True)
    
    archivo_csv = st.file_uploader("Subir CSV", type=["csv"], label_visibility="collapsed", key="uploader_csv")
    
    if archivo_csv is not None:
        try:
            nuevo_df = pd.read_csv(archivo_csv, sep=';', dtype=str)
            columnas_banco = ["Fecha de la orden", "ISIN", "Importe estimado", "Nº de participaciones"]
            
            if not all(col in nuevo_df.columns for col in columnas_banco):
                st.error("❌ El formato del CSV no coincide con las columnas esperadas del banco.")
            else:
                nuevo_df["Importe estimado"] = (
                    nuevo_df["Importe estimado"]
                    .str.replace(" EUR", "", case=False)
                    .str.replace(" ", "")
                    .str.strip()
                    .str.replace(",", ".")
                    .astype(float)
                )
                
                nuevo_df["Nº de participaciones"] = (
                    nuevo_df["Nº de participaciones"]
                    .str.replace(" ", "")
                    .str.strip()
                    .str.replace(",", ".")
                    .astype(float)
                )
                
                nuevo_df["price"] = nuevo_df["Importe estimado"] / nuevo_df["Nº de participaciones"]
                
                sh_check = client.open_by_key(SPREADSHEET_ID)
                ws_check = sh_check.worksheet(SHEETS_MAP[usuario]["aportaciones"])
                datos_actuales = pd.DataFrame(ws_check.get_all_records())
                
                registros_existentes = set()
                if not datos_actuales.empty and "isin" in datos_actuales.columns:
                    for _, r in datos_actuales.iterrows():
                        fecha_raw = str(r.get("date", "")).strip()
                        try:
                            fecha_norm = pd.to_datetime(fecha_raw, dayfirst=True).strftime('%Y-%m-%d')
                        except:
                            fecha_norm = fecha_raw
                        isin_norm = str(r.get("isin", "")).strip()
                        try:
                            amount_raw = str(r.get("amount", "0")).replace(",", ".")
                            importe_norm = round(float(amount_raw), 2)
                        except:
                            importe_norm = 0.0
                        registros_existentes.add((fecha_norm, isin_norm, importe_norm))
                
                filas_para_subir = []
                resumen_vista = []
                
                for _, fila in nuevo_df.iterrows():
                    f_orden = str(fila["Fecha de la orden"]).strip()
                    try:
                        f_orden_norm = pd.to_datetime(f_orden, dayfirst=True).strftime('%Y-%m-%d')
                    except:
                        f_orden_norm = f_orden
                    isin_clean = str(fila["ISIN"]).strip()
                    importe_val = round(float(fila["Importe estimado"]), 2)
                    precio_val = round(float(fila["price"]), 4)
                    nombre_fondo = isin_to_fund_global.get(isin_clean, "Desconocido")
                    
                    llave_fila = (f_orden_norm, isin_clean, importe_val)
                    es_duplicado = llave_fila in registros_existentes
                    duplicado = "⚠️ Ya existe" if es_duplicado else "✅ Nueva"
                    
                    if not es_duplicado:
                        filas_para_subir.append([
                            f_orden, 
                            float(importe_val), 
                            float(precio_val), 
                            nombre_fondo, 
                            isin_clean
                        ])
                    resumen_vista.append({"Fondo": nombre_fondo, "Importe": f"{importe_val:.2f} €", "Estado": duplicado})
                
                df_resumen = pd.DataFrame(resumen_vista)
                st.markdown("<p style='font-size: 13px; font-weight: 600; color: #cbd5e1; margin-top: 10px;'>📋 Resumen de carga detectado:</p>", unsafe_allow_html=True)
                st.dataframe(df_resumen, use_container_width=True, hide_index=True)
                
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("👍 Validar y Subir", use_container_width=True, type="primary"):
                        if len(filas_para_subir) == 0:
                            st.sidebar.warning("⚠️ No hay filas nuevas que subir. Todas ya existen.")
                        else:
                            with st.spinner(f"Subiendo {len(filas_para_subir)} registros nuevos..."):
                                ws_check.append_rows(filas_para_subir, value_input_option="USER_ENTERED")
                                st.sidebar.success(f"¡{len(filas_para_subir)} filas subidas con éxito!")
                                st.cache_data.clear()
                                st.rerun()
                with c2:
                    if st.button("❌ Cancelar", use_container_width=True):
                        st.cache_data.clear()
                        st.rerun()
                        
        except Exception as e:
            st.sidebar.error(f"Error al analizar el archivo temporal: {str(e)}")

    st.markdown("<hr style='border-color: #1e293b;'>", unsafe_allow_html=True)
    if st.button("🔄 Actualizar Cotizaciones", use_container_width=True):
        with st.spinner("Conectando con mercados..."):
            actualizar_valores()
        st.sidebar.success("Datos actualizados")
        st.cache_data.clear()
        st.rerun()

cfg = SHEETS_MAP[usuario]

# ==========================================
# LECTURA DE DATOS SEGUROS
# ==========================================
@st.cache_data(ttl=300)
def load_aportaciones(sheet_name):
    sh = client.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet(sheet_name)
    data = ws.get_all_values()
    df_data = pd.DataFrame(data[1:], columns=data[0])
    if not df_data.empty:
        if "amount" in df_data.columns:
            df_data["amount"] = pd.to_numeric(df_data["amount"].astype(str).str.replace(",", "."), errors="coerce")
        if "price" in df_data.columns:
            df_data["price"] = df_data["price"].astype(str).str.replace(",", ".").str.strip()
            df_data["price"] = pd.to_numeric(df_data["price"], errors="coerce")
    return df_data

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
    
    df["vl"] = df["vl"].astype(str).str.replace(",", ".").str.strip()
    df["vl"] = pd.to_numeric(df["vl"], errors="coerce")
    
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "vl", "isin"])
    df = df.sort_values(["isin", "date"])
    latest = df.groupby("isin").tail(1)
    return dict(zip(latest["isin"], latest["vl"])), df

# ==========================================
# PROCESAMIENTO Y LÓGICA GENERAL
# ==========================================
df = load_aportaciones(cfg["aportaciones"])
price_map, hist_df = load_prices()

hist_df["fund"] = hist_df["isin"].map(isin_to_fund)
hist_df = hist_df.dropna(subset=["fund"])

df["amount"] = pd.to_numeric(df["amount"].astype(str).str.replace(",", "."), errors="coerce")
df["price"] = pd.to_numeric(df["price"].astype(str).str.replace(",", "."), errors="coerce")
df["date"] = pd.to_datetime(df["date"], format="%d/%m/%Y", errors="coerce")

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

resumen["isin_temp"] = resumen["fund"].map({v: k for k, v in isin_to_fund.items()})
resumen["Precio VL"] = resumen["isin_temp"].map(price_map)
resumen = resumen.drop(columns=["isin_temp"])

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

hist_df_lookup = hist_df[["date", "fund", "vl"]].drop_duplicates(subset=["date", "fund"])

grid["date"] = pd.to_datetime(grid["date"])
evolution["date"] = pd.to_datetime(evolution["date"])
hist_df_lookup["date"] = pd.to_datetime(hist_df_lookup["date"])

evolution = evolution.merge(hist_df_lookup, on=["date", "fund"], how="left")
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

sparklines_dict = {}
for f in funds:
    f_hist = hist_df_lookup[hist_df_lookup["fund"] == f].sort_values("date").reset_index(drop=True)
    if not f_hist.empty:
        last_date = f_hist["date"].iloc[-1]
        month_date = last_date - pd.Timedelta(days=30)
        month_data = f_hist[f_hist["date"] <= month_date]
        if not month_data.empty:
            start_date = month_data.iloc[-1]["date"]
        else:
            start_date = f_hist.iloc[0]["date"]
        sparklines_dict[f] = f_hist[f_hist["date"] >= start_date]["vl"].tolist()
    else:
        sparklines_dict[f] = []

final["Tendencia (1m)"] = final["fund"].map(sparklines_dict)

final = final.rename(columns={
    "fund": "Fondo", "invertido": "Invertido", "valor_actual": "Valor actual", "beneficio": "Ganancia",
    "rentabilidad": "Rentabilidad (%)", "%_1d": "1 día (%)", "%_7d": "7 días (%)", "%_30d": "1 mes (%)",
    "last_date": "Última actualización"
})

dense["date"] = pd.to_datetime(dense["date"])
portfolio = dense.groupby("date", as_index=False).agg(invested=("cum_invested", "sum"), value=("market_value", "sum")).sort_values("date").reset_index(drop=True)
portfolio = portfolio.dropna(subset=["value"])
portfolio = portfolio[portfolio["value"] > 0]
portfolio["profit"] = portfolio["value"] - portfolio["invested"]

portfolio["1d (€)"] = portfolio["profit"].diff(1)
portfolio["1d (%)"] = (portfolio["1d (€)"] / portfolio["value"].shift(1)) * 100

last = portfolio.iloc[-1] if not portfolio.empty else {"value": 0, "invested": 0, "profit": 0, "1d (%)": 0, "1d (€)": 0, "date": pd.Timestamp.today()}

datos_circular = final.copy()
datos_circular["Valor actual"] = pd.to_numeric(
    datos_circular["Valor actual"].astype(str).str.replace(" €", "").str.replace(",", ""), 
    errors="coerce"
)

# ==========================================================
# CÁLCULO DE VARIACIÓN MENSUAL (MTD)
# ==========================================================
var_mensual_porcentaje = 0.0
var_mensual_euros = 0.0
valores_mes = []

if not portfolio.empty:
    portfolio["date_dt"] = pd.to_datetime(portfolio["date"])
    ultima_fecha_datos = portfolio["date_dt"].max()
    año_actual = ultima_fecha_datos.year
    mes_actual = ultima_fecha_datos.month
    
    portfolio_mes = portfolio[
        (portfolio["date_dt"].dt.year == año_actual) & 
        (portfolio["date_dt"].dt.month == mes_actual)
    ].sort_values("date_dt")
    
    if not portfolio_mes.empty:
        valores_mes = portfolio_mes["value"].tolist()
        valor_final_mes = portfolio_mes["value"].iloc[-1]
        valor_inicial_mes = portfolio_mes["value"].iloc[0]
        
        if len(portfolio_mes) == 1:
            mes_anterior = portfolio[portfolio["date_dt"] < portfolio_mes["date_dt"].iloc[0]]
            if not mes_anterior.empty:
                valor_inicial_mes = mes_anterior["value"].iloc[-1]
        
        var_mensual_euros = valor_final_mes - valor_inicial_mes
        var_mensual_porcentaje = (var_mensual_euros / valor_inicial_mes) * 100 if valor_inicial_mes else 0

# ==========================================
# VISTA GENERAL Y PANELES
# ==========================================
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.markdown(f"""
        <div style="background-color: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; height: 104px; display: flex; flex-direction: column; justify-content: center;">
            <p style="margin: 0; font-size: 11px; color: #94a3b8; font-weight: 600; text-transform: uppercase;">💰 Estado del Capital</p>
            <p style="margin: 4px 0 0 0; font-size: 22px; font-weight: 700; color: #60a5fa;">
                {last["value"]:,.2f} €
            </p>
            <p style="margin: 2px 0 0 0; font-size: 12px; color: #94a3b8; font-weight: 500;">
                Invertido: <span style="color: #f8fafc; font-weight: 600;">{last["invested"]:,.2f} €</span>
            </p>
        </div>
    """, unsafe_allow_html=True)

with kpi2:
    rentabilidad_total = (last["profit"] / last["invested"]) * 100 if last["invested"] else 0
    color_ganancia = "#10b981" if last["profit"] >= 0 else "#f43f5e"
    st.markdown(f'<div style="background-color: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155;"><p style="margin: 0; font-size: 11px; color: #94a3b8; font-weight: 600; text-transform: uppercase;">🍀 Ganancia acumulada</p><p style="margin: 6px 0 0 0; font-size: 24px; font-weight: 700; color: {color_ganancia};">{last["profit"]:,.2f} € <span style="font-size: 13px; color: #94a3b8;">({rentabilidad_total:.2f}%)</span></p></div>', unsafe_allow_html=True)

with kpi3:
    var_porcentaje = last["1d (%)"]
    var_euros = last["1d (€)"]
    color_var = "#10b981" if var_porcentaje >= 0 else "#f43f5e"
    signo = "+" if var_porcentaje >= 0 else ""
    st.markdown(f'<div style="background-color: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155;"><p style="margin: 0; font-size: 11px; color: #94a3b8; font-weight: 600; text-transform: uppercase;">⚡ Variación Diaria</p><p style="margin: 6px 0 0 0; font-size: 24px; font-weight: 700; color: {color_var};">{signo}{var_euros:,.2f} € <span style="font-size: 13px; color: #94a3b8;">({signo}{var_porcentaje:.2f}%)</span></p></div>', unsafe_allow_html=True)

with kpi4:
    color_var_mes = "#10b981" if var_mensual_porcentaje >= 0 else "#f43f5e"
    signo_mes = "+" if var_mensual_porcentaje >= 0 else ""
    
    sparkline_mes_html = ""
    if len(valores_mes) >= 2:
        referencia = valores_mes[0]
        min_v, max_v = min(valores_mes), max(valores_mes)
        rng = max_v - min_v if max_v != min_v else 1
        
        pct_referencia = 100 - (((referencia - min_v) / rng) * 100)
        pct_referencia = max(5, min(95, pct_referencia))
        
        width, height = 150, 35
        padding = 2
        points = []
        for i, v in enumerate(valores_mes):
            x = padding + (i / (len(valores_mes) - 1)) * (width - 2 * padding)
            y = (height - padding) - ((v - min_v) / rng) * (height - 2 * padding)
            points.append(f"{x},{y}")
        polyline_str = " ".join(points)
        ultimo_x, ultimo_y = points[-1].split(",")
        
        sparkline_mes_html = f"""
        <div class="sparkline-container" style="width: 100%;">
            <svg width="100%" height="{height}" viewBox="0 0 {width} {height}" preserveAspectRatio="none" style="display: block;">
                <defs>
                    <linearGradient id="bicolorGradientKPI" x1="0%" y1="0%" x2="0%" y2="100%">
                        <stop offset="0%" stop-color="#10b981" />
                        <stop offset="{pct_referencia}%" stop-color="#10b981" />
                        <stop offset="{pct_referencia}%" stop-color="#f43f5e" />
                        <stop offset="100%" stop-color="#f43f5e" />
                    </linearGradient>
                </defs>
                <line x1="{padding}" y1="{(height-padding)-((referencia-min_v)/rng)*(height-2*padding)}" x2="{width-padding}" y2="{(height-padding)-((referencia-min_v)/rng)*(height-2*padding)}" stroke="rgba(148, 163, 184, 0.15)" stroke-width="1" stroke-dasharray="2,2" />
                <polyline fill="none" stroke="url(#bicolorGradientKPI)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" points="{polyline_str}"/>
                <circle cx="{ultimo_x}" cy="{ultimo_y}" r="3" fill="{color_var_mes}"/>
            </svg>
        </div>
        """.replace("\n", "").strip()
    
    elif len(valores_mes) == 1:
        sparkline_mes_html = f"""
        <div class="sparkline-container" style="width: 100%; display: flex; align-items: center; justify-content: center;">
            <svg width="100%" height="35">
                <circle cx="75" cy="17.5" r="4" fill="#94a3b8" />
            </svg>
        </div>
        """

    kpi4_html = (
        f'<div style="background-color: #1e293b; padding: 15px 20px; border-radius: 12px; border: 1px solid #334155; height: 104px; display: flex; flex-direction: column; justify-content: center;">'
        f'<p style="margin: 0; font-size: 11px; color: #94a3b8; font-weight: 600; text-transform: uppercase;">⚡ Variación Mes</p>'
        f'<div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">'
        f'<div>'
        f'<p style="margin: 0; font-size: 20px; font-weight: 700; color: {color_var_mes};">{signo_mes}{var_mensual_euros:,.2f} €</p>'
        f'<p style="margin: 0; font-size: 12px; color: #94a3b8; font-weight: 500;">({signo_mes}{var_mensual_porcentaje:.2f}%)</p>'
        f'</div>'
        f'<div style="width: 150px; margin-left: 10px; flex-shrink: 0;">{sparkline_mes_html}</div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(kpi4_html, unsafe_allow_html=True)


st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)

tab_resumen, tab_graficos, tab_evolucion, tab_distribucion, tab_detalles = st.tabs([
    "📋 Resumen de Fondos", "📈 Gráficos de Evolución", "📊 Historial de Evolución", "⚖️ Distribución", "🔍 Detalle de Aportaciones"
])

# TAB 1: RESUMEN DE FONDOS
with tab_resumen:
    final_html = final.copy()
    final_html["Invertido"] = final_html["Invertido"].map("{:,.2f} €".format)
    final_html["Valor actual"] = final_html["Valor actual"].map("{:,.2f} €".format)
    final_html["Ganancia"] = final_html["Ganancia"].map("{:,.2f} €".format)
    final_html["Rentabilidad (%)"] = final_html["Rentabilidad (%)"].map("{:.2f} %".format)
    final_html["1 día (%)"] = final_html["1 día (%)"].map("{:.2f} %".format)
    final_html["7 días (%)"] = final_html["7 días (%)"].map("{:.2f} %".format)
    final_html["1 mes (%)"] = final_html["1 mes (%)"].map("{:.2f} %".format)
    final_html["Precio VL"] = final_html["Precio VL"].map("{:,.2f} €".format)
    
    final_html["Última actualización"] = final_html["Última actualización"].apply(lambda x: x.strftime("%d/%m/%Y") if pd.notnull(x) else "")
    
    columnas_ordenadas = [
        "Fondo", "Invertido", "Valor actual", "Ganancia", "Rentabilidad (%)", 
        "1 día (%)", "7 días (%)", "1 mes (%)", "Tendencia (1m)", "Precio VL", "Última actualización"
    ]
    final_html = final_html[columnas_ordenadas]
    
    render_financial_table(final_html, cols_color_render=["Ganancia", "1 día (%)", "7 días (%)", "1 mes (%)", "Rentabilidad (%)"])

# TAB 2: GRÁFICOS
with tab_graficos:
    start_date = pd.Timestamp("2026-05-18")
    dense_filtered = dense[dense["date"] >= start_date]
    
    if not dense_filtered.empty:
        portfolio_graph = dense_filtered.groupby("date", as_index=False).agg(invested=("cum_invested", "sum"), value=("market_value", "sum")).sort_values("date")
        portfolio_graph["profit"] = (portfolio_graph["value"] - portfolio_graph["invested"])

        val_min = min(portfolio_graph["value"].min(), portfolio_graph["invested"].min()) if not portfolio_graph.empty else 0
        suelo_grafico = val_min * 0.98 

        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(x=portfolio_graph["date"], y=portfolio_graph["invested"], name="Invertido", mode="lines", line=dict(color="rgba(148, 163, 184, 0.5)", width=1.5, dash="dot")))
            fig1.add_trace(go.Scatter(x=portfolio_graph["date"], y=portfolio_graph["value"], name="Valor Cartera", mode="lines", line=dict(color="#3b82f6", width=3), fill='tonexty', fillcolor='rgba(59, 130, 246, 0.05)'))
            fig1.update_layout(title=dict(text="<b>Evolución del Valor Total</b>", font=dict(size=14, color="#cbd5e1")), template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=15, r=15, t=50, b=15), height=450, hovermode="x unified", xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="rgba(51, 65, 85, 0.4)", range=[suelo_grafico, portfolio_graph["value"].max() * 1.02]))
            st.plotly_chart(fig1, use_container_width=True, config={'displayModeBar': False})

        with col_g2:
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=portfolio_graph["date"], y=portfolio_graph["profit"], name="Beneficio Neto", mode="lines", line=dict(color="#10b981", width=3), fill='tozeroy', fillcolor='rgba(16, 185, 129, 0.05)'))
            fig2.update_layout(title=dict(text="<b>Evolución de la Ganancia Neta</b>", font=dict(size=14, color="#cbd5e1")), template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=10, r=10, t=50, b=10), height=450, hovermode="x unified", xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="rgba(51, 65, 85, 0.5)", autorange=True, rangemode='normal'))
            st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False})
    else:
        st.info("No hay datos históricos disponibles a partir del 18/05/2026.")

# ==========================================================
# 📊 TAB 3: HISTORIAL DE EVOLUCIÓN (ESTILO MATRIZ MYINVESTOR)
# ==========================================================
# ==========================================================
# 📊 TAB 3: HISTORIAL DE EVOLUCIÓN (MATRIZ COMPACTA % Y €)
# ==========================================================
with tab_evolucion:
    if not portfolio.empty:
        # 1. Preparar columnas de control temporal
        portfolio["year"] = portfolio["date_dt"].dt.year
        portfolio["month"] = portfolio["date_dt"].dt.month
        
        # 2. Obtener los cierres de cada mes
        cierres_mensuales = portfolio.sort_values("date_dt").groupby(["year", "month"]).last().reset_index()
        
        cierres_mensuales["prev_value"] = cierres_mensuales["value"].shift(1)
        cierres_mensuales["diff_profit"] = cierres_mensuales["profit"].diff(1)
        
        # 3. Calcular ambas métricas simultáneamente
        cierres_mensuales["rent_pct"] = (cierres_mensuales["diff_profit"] / cierres_mensuales["prev_value"]) * 100
        cierres_mensuales["rent_eur"] = cierres_mensuales["diff_profit"]
        
        if not cierres_mensuales.empty:
            primer_idx = cierres_mensuales.index[0]
            cierres_mensuales.loc[primer_idx, "rent_pct"] = (cierres_mensuales.loc[primer_idx, "profit"] / cierres_mensuales.loc[primer_idx, "invested"]) * 100 if cierres_mensuales.loc[primer_idx, "invested"] else 0
            cierres_mensuales.loc[primer_idx, "rent_eur"] = cierres_mensuales.loc[primer_idx, "profit"]

        meses_es = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"}
        cierres_mensuales["Mes"] = cierres_mensuales["month"].map(meses_es)
        
        # 4. Calcular Totales Anuales
        totales_pct = {}
        totales_eur = {}
        for y in cierres_mensuales["year"].unique():
            datos_y = portfolio[portfolio["year"] == y].sort_values("date_dt")
            if not datos_y.empty:
                val_final = datos_y["value"].iloc[-1]
                prof_final = datos_y["profit"].iloc[-1]
                
                datos_ant = portfolio[portfolio["year"] < y].sort_values("date_dt")
                if not datos_ant.empty:
                    val_inicial = datos_ant["value"].iloc[-1]
                    prof_inicial = datos_ant["profit"].iloc[-1]
                else:
                    val_inicial = datos_y["invested"].iloc[0]
                    prof_inicial = 0
                
                ganancia_neta_año = prof_final - prof_inicial
                totales_pct[y] = (ganancia_neta_año / val_inicial) * 100 if val_inicial else 0
                totales_eur[y] = ganancia_neta_año

        # 5. Pivotar datos
        pivot_pct = cierres_mensuales.pivot(index="month", columns="year", values="rent_pct").reindex(range(1, 13))
        pivot_eur = cierres_mensuales.pivot(index="month", columns="year", values="rent_eur").reindex(range(1, 13))
        
        years_columns = sorted(list(cierres_mensuales["year"].unique()), reverse=True)
        
        # 6. HTML con CSS personalizado inline para controlar el ancho (max-width y margin: auto)
        html_matriz = """
        <div class="financial-table-container" style="max-width: 600px; margin: 0 auto 25px auto; border-radius: 16px;">
            <table class="financial-table" style="width: 100%;">
                <thead>
                    <tr>
                        <th style="text-align: left; padding-left: 24px; width: 35%;"></th>
        """
        for y in years_columns:
            html_matriz += f'<th style="width: calc(65% / {len(years_columns)});">{y}</th>'
        html_matriz += '</tr></thead><tbody>'
        
        # --- FILA DE TOTALES ---
        html_matriz += '<tr style="background-color: #0f172a; border-bottom: 2px solid #334155; font-size: 15px;">'
        html_matriz += '<td style="font-weight: 700; text-align: left; padding-left: 24px; color: #ffffff;">Total</td>'
        for y in years_columns:
            p_val = totales_pct.get(y, None)
            e_val = totales_eur.get(y, None)
            
            if p_val is not None and e_val is not None:
                clase = ' class="pos-val"' if p_val > 0 else (' class="neg-val"' if p_val < 0 else '')
                signo = '+' if p_val > 0 else ''
                html_matriz += f'<td style="padding: 12px 16px;">' \
                               f'<div{clase} style="font-size: 15px;">{signo}{p_val:.2f} %</div>' \
                               f'<div style="font-size: 11px; color: #94a3b8; margin-top: 2px; font-weight: 400;">{signo}{e_val:,.2f} €</div>' \
                               f'</td>'
            else:
                html_matriz += '<td>-</td>'
        html_matriz += '</tr>'
        
        # --- FILAS DE LOS MESES ---
        for m_num in range(1, 13):
            nombre_mes = meses_es[m_num]
            html_matriz += '<tr>'
            html_matriz += f'<td style="text-align: left; padding-left: 24px; color: #cbd5e1; font-weight: 600;">{nombre_mes}</td>'
            
            for y in years_columns:
                p_val = pivot_pct.loc[m_num, y] if y in pivot_pct.columns else None
                e_val = pivot_eur.loc[m_num, y] if y in pivot_eur.columns else None
                
                if pd.notnull(p_val) and pd.notnull(e_val):
                    clase = ' class="pos-val"' if p_val > 0 else (' class="neg-val"' if p_val < 0 else '')
                    signo = '+' if p_val > 0 else ''
                    html_matriz += f'<td style="padding: 10px 16px;">' \
                                   f'<div{clase}>{signo}{p_val:.2f} %</div>' \
                                   f'<div style="font-size: 11px; color: #94a3b8; margin-top: 2px; font-weight: 400;">{signo}{e_val:,.2f} €</div>' \
                                   f'</td>'
                else:
                    html_matriz += '<td style="color: #475569;">-</td>'
            html_matriz += '</tr>'
            
        html_matriz += '</tbody></table></div>'
        
        st.write(html_matriz, unsafe_allow_html=True)
    else:
        st.info("No hay datos suficientes para generar la matriz de rendimiento.")

# TAB 4: DISTRIBUCIÓN
with tab_distribucion:
    import plotly.express as px
    colores_premium = ["#2563eb", "#059669", "#4f46e5", "#7c3aed", "#e11d48", "#0891b2", "#d97706"]
    
    fig_pie = px.pie(
        datos_circular, 
        values="Valor actual", 
        names="Fondo",
        hole=0.40, 
        color_discrete_sequence=colores_premium
    )
    
    fig_pie.update_layout(
        template="plotly_dark",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        margin=dict(t=10, b=10, l=10, r=10),
        height=600 
    )
    
    fig_pie.update_traces(
        textinfo='percent+label', 
        textposition='inside',
        insidetextorientation='radial',
        textfont=dict(size=14, color="#ffffff", family="Inter, sans-serif", weight="bold"),
        marker=dict(
            line=dict(color='#0b111e', width=4), 
            colors=colores_premium
        ),
        pull=[0.03] * len(datos_circular), 
        hovertemplate="<b>%{label}</b><br>Valor: %{value:,.2f} €<br>Porcentaje: %{percent}<extra></extra>"
    )
    
    _, col_grande, _ = st.columns([0.3, 3.4, 0.3])
    with col_grande:
        st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})

# ==========================================================
# TAB 5: DETALLE DE APORTACIONES
# ==========================================================
with tab_detalles:

    col_select, _ = st.columns([1.5, 2])

    with col_select:
        fondo_seleccionado = st.selectbox(
            "Filtrar por fondo específico:",
            ["Todos"] + sorted(df["fund"].dropna().unique().tolist())
        )

    df_detalles_filtrado = (
        df.copy()
        if fondo_seleccionado == "Todos"
        else df[df["fund"] == fondo_seleccionado].copy()
    )

    # ==========================================================
    # GRÁFICO
    # ==========================================================
    if fondo_seleccionado != "Todos" and not df_detalles_filtrado.empty:

        graf = df_detalles_filtrado.sort_values("date").copy()

        ultimo_vl = graf["current_price"].iloc[0]

        # ------------------------------------
        # Histórico del VL
        # ------------------------------------
        hist = (
            hist_df[hist_df["fund"] == fondo_seleccionado][["date", "vl"]]
            .sort_values("date")
            .copy()
        )

        if hist.empty:

            hist = (
                graf[["date", "price"]]
                .rename(columns={"price": "vl"})
            )

        else:

            primera_fecha_vl = hist["date"].min()

            compras = (
                graf[graf["date"] <= primera_fecha_vl][["date", "price"]]
                .rename(columns={"price": "vl"})
            )

            hist = pd.concat(
                [compras, hist],
                ignore_index=True
            )

            hist = (
                hist.sort_values("date")
                    .groupby("date", as_index=False)
                    .last()
            )

            hist["vl"] = hist["vl"].ffill()

        # ------------------------------------
        # Color de las compras
        # ------------------------------------
        graf["Color"] = np.where(
            graf["price"] <= ultimo_vl,
            "#10b981",
            "#ef4444"
        )

        # ------------------------------------
        # Tamaño según importe invertido
        # ------------------------------------
        tam_min = 10
        tam_max = 35

        if graf["amount"].max() == graf["amount"].min():

            graf["size"] = 18

        else:

            graf["size"] = (
                tam_min
                + (
                    (graf["amount"] - graf["amount"].min())
                    /
                    (graf["amount"].max() - graf["amount"].min())
                )
                * (tam_max - tam_min)
            )

        # ------------------------------------
        # Gráfico
        # ------------------------------------
        fig = go.Figure()

        # Evolución del VL

        fig.add_trace(
            go.Scatter(
                x=hist["date"],
                y=hist["vl"],
                mode="lines",
                name="VL",
                line=dict(
                    color="#3b82f6",
                    width=3
                )
            )
        )

        # Línea VL actual

        fig.add_hline(
            y=ultimo_vl,
            line_dash="dash",
            line_color="#60a5fa",
            annotation_text=f"VL actual: {ultimo_vl:.2f} €",
            annotation_position="top right"
        )

        # Compras

        fig.add_trace(
            go.Scatter(
                x=graf["date"],
                y=graf["price"],
                mode="markers",
                name="Aportaciones",
                marker=dict(
                    color=graf["Color"],
                    size=graf["size"],
                    sizemode="diameter",
                    opacity=0.90,
                    line=dict(
                        color="white",
                        width=1.5
                    )
                ),
                customdata=np.stack(
                    (
                        graf["amount"],
                        graf["units"],
                        graf["beneficio"],
                        graf["rentabilidad"]
                    ),
                    axis=-1
                ),
                hovertemplate=
                    "<b>%{x|%d/%m/%Y}</b><br>"
                    "Precio compra: %{y:.4f} €<br>"
                    "Importe: %{customdata[0]:.2f} €<br>"
                    "Participaciones: %{customdata[1]:.4f}<br>"
                    "Ganancia: %{customdata[2]:.2f} €<br>"
                    "Rentabilidad: %{customdata[3]:.2f}%<extra></extra>"
            )
        )

        fig.update_layout(

            title=f"{fondo_seleccionado}",

            template="plotly_dark",

            paper_bgcolor="rgba(0,0,0,0)",

            plot_bgcolor="rgba(0,0,0,0)",

            height=600,

            hovermode="closest",

            xaxis_title="Fecha",

            yaxis_title="Valor liquidativo (€)",

            legend=dict(
                orientation="h",
                y=1.02,
                x=0
            )

        )

        fig.update_xaxes(showgrid=False)

        fig.update_yaxes(
            gridcolor="rgba(51,65,85,0.35)"
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            config={"displayModeBar": False}
        )

    # ==========================================================
    # TABLA
    # ==========================================================

    if not df_detalles_filtrado.empty:

        df_detalles_filtrado = df_detalles_filtrado.sort_values(
            "date",
            ascending=False
        )

        df_detalles_html = pd.DataFrame()

        df_detalles_html["Fecha"] = df_detalles_filtrado["date"].dt.strftime("%d/%m/%Y")
        df_detalles_html["Fondo"] = df_detalles_filtrado["fund"]
        df_detalles_html["Invertido"] = df_detalles_filtrado["amount"].map("{:,.2f} €".format)
        df_detalles_html["Precio Compra"] = df_detalles_filtrado["price"].map("{:,.4f} €".format)
        df_detalles_html["Participaciones"] = df_detalles_filtrado["units"].map("{:,.4f}".format)
        df_detalles_html["Valor Actual"] = df_detalles_filtrado["valor_actual"].map("{:,.2f} €".format)
        df_detalles_html["Ganancia"] = df_detalles_filtrado["beneficio"].map("{:,.2f} €".format)
        df_detalles_html["Rentabilidad"] = df_detalles_filtrado["rentabilidad"].map("{:.2f} %".format)

        render_financial_table(
            df_detalles_html,
            cols_color_render=["Ganancia", "Rentabilidad"]
        )

    else:
        st.info("No se encontraron aportaciones para el criterio seleccionado.")