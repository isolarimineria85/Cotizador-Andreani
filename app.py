import streamlit as st
import pandas as pd
import re

# 1. Configuración de página
st.set_page_config(page_title="Cotizador Larocca Neumáticos", page_icon="🛞", layout="centered")

# 2. Inyección de CSS para diseño corporativo (Rojo Larocca)
st.markdown("""
    <style>
        .block-container {
            padding-top: 2rem;
        }
        h1, h2, h3 {
            color: #000000 !important;
            font-family: 'Arial', sans-serif;
            font-weight: 700 !important;
        }
        /* Estilo del botón de calcular (Rojo Larocca y texto blanco) */
        .stButton>button {
            background-color: #E3000F !important; 
            color: #FFFFFF !important;
            font-weight: 800 !important;
            border-radius: 5px !important;
            border: 2px solid #E3000F !important;
            width: 100%;
            transition: all 0.3s ease;
        }
        .stButton>button:hover {
            background-color: #000000 !important;
            color: #E3000F !important;
            border: 2px solid #000000 !important;
        }
        /* Estilo de la caja de información del destino */
        div[data-testid="stAlert"] {
            background-color: #FDF2F2 !important;
            border-left: 5px solid #E3000F !important;
            color: #000000 !important;
        }
        /* Estilo de las métricas (los números grandes de resultados) */
        div[data-testid="metric-container"] {
            background-color: #F8F9FA;
            border: 1px solid #E9ECEF;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
        }
        div[data-testid="stMetricValue"] {
            color: #000000 !important;
            font-weight: bold !important;
        }
    </style>
""", unsafe_allow_html=True)

def limpiar_numero(valor):
    if pd.isna(valor) or valor == '' or valor is None:
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    val_str = str(valor).replace('$', '').replace('.', '').replace(',', '.').strip()
    try:
        return float(val_str)
    except:
        return 0.0

@st.cache_data(ttl=300)
def cargar_datos_desde_drive(url):
    match_id = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
    if not match_id:
        raise ValueError("URL de Google Drive / Sheets no válida.")
    
    file_id = match_id.group(1)
    match_gid = re.search(r'[#&?]gid=([0-9]+)', url)
    gid = match_gid.group(1) if match_gid else "170077304"
    
    csv_url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv&gid={gid}"
    
    try:
        df = pd.read_csv(csv_url, header=None)
    except Exception:
        excel_url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
        df = pd.read_excel(excel_url, header=None)

    datos_limpios = []
    tramos_kg = [100, 125, 150, 175, 200, 225, 250, 275, 300, 325, 350, 400, 500]

    for idx in range(len(df)):
        row = df.iloc[idx]
        if len(row) < 20:
            continue
            
        valor_cp = str(row.iloc[3]).strip().replace('.0', '')
        if not valor_cp.isdigit():
            continue
            
        provincia = str(row.iloc[4]).strip()
        localidad = str(row.iloc[5]).strip()

        tarifas = {}
        for i, t in enumerate(tramos_kg):
            col_idx = 6 + i
            tarifas[t] = limpiar_numero(row.iloc[col_idx])

        tarifa_500 = limpiar_numero(row.iloc[18])
        kilo_exc = limpiar_numero(row.iloc[19])

        etiqueta = f"{valor_cp} - {localidad} ({provincia})"

        datos_limpios.append({
            'CP': valor_cp,
            'Localidad': localidad,
            'Provincia': provincia,
            'Etiqueta': etiqueta,
            'Tarifas': tarifas,
            'Tarifa_500': tarifa_500,
            'Kilo_Exc': kilo_exc
        })

    if not datos_limpios:
        raise ValueError("No se encontraron registros.")

    return pd.DataFrame(datos_limpios)

def calcular_tarifa(cp_data, peso_real, m3):
    peso_vol = m3 * 175
    peso_facturable = max(peso_real, peso_vol)
    
    if peso_facturable <= 500:
        tramos = sorted(cp_data['Tarifas'].keys())
        for t in tramos:
            if peso_facturable <= t:
                costo_total = cp_data['Tarifas'][t]
                return {
                    "Peso Volumétrico": peso_vol,
                    "Peso Facturable": peso_facturable,
                    "Tramo": f"Hasta {t} kg",
                    "Costo Base": costo_total,
                    "Costo Excedente": 0.0,
                    "Costo Total": costo_total
                }
    else:
        tarifa_500 = cp_data['Tarifa_500']
        kilo_exc = cp_data['Kilo_Exc']
        kg_excedentes = peso_facturable - 500
        costo_excedente = kg_excedentes * kilo_exc
        
        return {
            "Peso Volumétrico": peso_vol,
            "Peso Facturable": peso_facturable,
            "Tramo": "+ de 500 kg",
            "Costo Base": tarifa_500,
            "Costo Excedente": costo_excedente,
            "Costo Total": tarifa_500 + costo_excedente
        }

# --- ENCABEZADO CON LOGO ---
# Centramos el logo usando las columnas de Streamlit
col_logo1, col_logo2, col_logo3 = st.columns([1, 2, 1])
with col_logo2:
    try:
        st.image("Logo Larocca.jpg", use_container_width=True)
    except Exception:
        # Si la imagen todavía no se subió a GitHub, muestra este título de respaldo
        st.title("Cotizador Larocca Neumáticos")

st.markdown("---")

URL_GOOGLE_SHEET = "https://docs.google.com/spreadsheets/d/10npzsWWPaospCZbE692bia6tVPgxKnVa/edit?gid=170077304#gid=170077304"

try:
    df_tarifas = cargar_datos_desde_drive(URL_GOOGLE_SHEET)
    opciones_cp = df_tarifas['Etiqueta'].unique().tolist()
except Exception as e:
    st.error(f"Error de conexión con el tarifario: {e}")
    st.stop()

st.subheader("Datos de Envío")

seleccion = st.selectbox("📌 Buscar por Código Postal o Localidad", options=opciones_cp)

cp_data = df_tarifas[df_tarifas['Etiqueta'] == seleccion].iloc[0]

st.info(f"**Destino Confirmado:** {cp_data['Localidad']}, {cp_data['Provincia']} (CP {cp_data['CP']})")

col1, col2 = st.columns(2)
with col1:
    peso_real = st.number_input("Peso Real (Kg)", min_value=0.0, value=1530.0, step=10.0)
with col2:
    m3_carga = st.number_input("Volumen (M3)", min_value=0.0, value=6.08, step=0.1)

st.markdown("<br>", unsafe_allow_html=True)

if st.button("CALCULAR COTIZACIÓN", type="primary"):
    resultado = calcular_tarifa(cp_data, peso_real, m3_carga)
    
    st.success("✔️ Cotización calculada exitosamente")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Peso Facturable", f"{resultado['Peso Facturable']:,.2f} kg")
    c2.metric("Tramo de Escala", resultado['Tramo'])
    c3.metric("Costo Total", f"${resultado['Costo Total']:,.2f}")
    
    st.divider()
    st.markdown("### 📋 Detalle de Facturación")
    st.write(f"- **Destino:** {cp_data['Localidad']}, {cp_data['Provincia']} (CP {cp_data['CP']})")
    st.write(f"- **Peso Volumétrico:** {resultado['Peso Volumétrico']:,.2f} kg (M3 × 175 kg)")
    st.write(f"- **Tarifa Base Aplicada:** ${resultado['Costo Base']:,.2f}")
    if resultado['Costo Excedente'] > 0:
        kg_exc = resultado['Peso Facturable'] - 500
        st.write(f"- **Kilos Excedentes (>500 kg):** {kg_exc:,.2f} kg")
        st.write(f"- **Costo por Excedente:** ${resultado['Costo Excedente']:,.2f}")
