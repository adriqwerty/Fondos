import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import streamlit as st
import plotly.graph_objects as go

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
        border-bottom: 1px solid #334155;
        font-weight: 500;
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
    </style>
""", unsafe_allow_html=True)

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
            # 🛠️ Forzamos inicialmente lectura como texto para evitar interpretaciones locales
            nuevo_df = pd.read_csv(archivo_csv, sep=';', dtype=str)
            columnas_banco = ["Fecha de la orden", "ISIN", "Importe estimado", "Nº de participaciones"]
            
            if not all(col in nuevo_df.columns for col in columnas_banco):
                st.error("❌ El formato del CSV no coincide con las columnas esperadas del banco.")
            else:
                # 🛠️ LIMPIEZA ABSOLUTA DE COMAS EN EL IMPORTE
                nuevo_df["Importe estimado"] = (
                    nuevo_df["Importe estimado"]
                    .str.replace(" EUR", "", case=False)
                    .str.replace(" ", "")
                    .str.strip()
                    .str.replace(",", ".")
                    .astype(float)
                )
                
                # 🛠️ LIMPIEZA ABSOLUTA DE COMAS EN EL NÚMERO DE PARTICIPACIONES
                nuevo_df["Nº de participaciones"] = (
                    nuevo_df["Nº de participaciones"]
                    .str.replace(" ", "")
                    .str.strip()
                    .str.replace(",", ".")
                    .astype(float)
                )
                
                # Al ser ambos ya floats puros con punto, el precio calculado nace limpio
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
                                ws_check.append_rows(filas_para_subir, value_input_option="RAW")
                                st.sidebar.success(f"¡{len(filas_para_subir)} filas subidas con éxito!")
                                st.cache_data.clear()
                                st.rerun