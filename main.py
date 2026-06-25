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
# FUNCIÓN COMPONENTE: PROCESADOR DE CSV DE ÓRDENES REAL
# ==========================================================
def procesar_y_subir_csv(uploaded_file, client, spreadsheet_id, sheet_name):
    try:
        # Leer usando punto y coma como separador (estándar del archivo proporcionado)
        nuevo_df = pd.read_csv(uploaded_file, sep=';')
        
        # Validar columnas requeridas basadas en el archivo real
        columnas_banco = ["Fecha de la orden", "ISIN", "Importe estimado", "Nº de participaciones"]
        for col in columnas_banco:
            if col not in nuevo_df.columns:
                st.sidebar.error(f"❌ Estructura incorrecta. Falta la columna: '{col}'")
                return False
        
        # Limpieza de importes y participaciones (reemplazar comas decimales por puntos y quitar divisas)
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
        
        # Calcular precio implícito (Price = Amount / Units)
        nuevo_df["price"] = nuevo_df["Importe estimado"] / nuevo_df["Nº de participaciones"]
        
        # Estructurar filas para Google Sheets en orden estándar: [Fecha, ISIN, Importe, Precio]
        filas_finales = []
        for _, fila in nuevo_df.iterrows():
            registro = [
                str(fila["Fecha de la orden"]), 
                str(fila["ISIN"]),             
                float(fila["Importe estimado"]),
                round(float(fila["price"]), 4)  
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