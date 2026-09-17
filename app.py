import streamlit as st
import pandas as pd
import re

# 1. Configuración de página
st.set_page_config(page_title="Cotizador Andreani", page_icon="📦", layout="centered")

# 2. CSS para diseño e interfaz centrada
st.markdown("""
    <style>
        .block-container {
            padding-top: 2rem;
        }
        .titulo-cotizador {
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            color: #111111;
            font-size: 2.3rem;
            font-weight: 800;
            text-align: center;
            letter-spacing: -0.5px;
            margin-bottom: 5px;
            padding-bottom: 10px;
            border-bottom: 3px solid #E3000F;
        }
        .subtitulo-cotizador {
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            color: #666666;
            font-size: 1rem;
            text-align: center;
            margin-bottom: 25px;
        }
        .stButton>button {
            background-color: #E3000F !important; 
            color: #FFFFFF !important;
            font-weight: 700 !important;
            font-size: 1.1rem !important;
            border-radius: 6px !important;
            border: 2px solid #E3000F !important;
            width: 100%;
            padding: 12px 0px !important;
            transition: all 0.3s ease;
        }
        .stButton>button:hover {
            background-color: #000000 !important;
            color: #FFFFFF !important;
            border: 2px solid #000000 !important;
        }
        div[data-testid="stAlert"] {
            background-color: #FDF2F2 !important;
            border-left: 5px solid #E3000F !important;
            color: #000000 !important;
        }
        .resultado-box {
            background-color: #F8F9FA;
            border: 2px solid #E3000F;
            border-radius: 12px;
            padding: 25px;
            text-align: center;
            margin-top: 20px;
            margin-bottom: 25px;
            box-shadow: 0px 4px 12px rgba(0,0,0,0.08);
        }
        .resultado-label {
            font-size: 1.1rem;
            color: #555555;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 5px;
        }
        .resultado-monto {
            font-size: 2.8rem;
            color: #E3000F;
            font-weight: 900;
            margin-bottom: 15px;
            line-height: 1;
        }
        .resultado-sub-info {
            display: flex;
            justify-content: space-around;
            border-top: 1px solid #E9ECEF;
            padding-top: 15px;
            margin-top: 10px;
        }
        .sub-info-item {
            font-size: 0.95rem;
            color: #333333;
        }
        .sub-info-val {
            font-weight: bold;
            color: #000000;
        }
    </style>
""", unsafe_allow_html=True)

# 3. Conversor numérico inteligente
def limpiar_numero(valor):
    if pd.isna(valor) or valor == '' or valor is None:
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    
    val_str = str(valor).replace('$', '').strip()
    
    # Caso A: Si tiene ambos separadores ("473.591,51" o "473,591.51")
    if '.' in val_str and ',' in val_str:
        if val_str.rfind('.') < val_str.rfind(','):
            val_str = val_str.replace('.', '').replace(',', '.')
        else:
            val_str = val_str.replace(',', '')
    # Caso B: Solo contiene coma decimal ("473591,51")
    elif ',' in val_str:
        val_str = val_str.replace(',', '.')
    # Caso C: Solo contiene punto ("473.591")
    elif '.' in val_str:
        partes = val_str.split('.')
        # Si tiene 3 dígitos tras el punto (ej: 473.591), es separador de miles
        if len(partes) == 2 and len(partes[1]) == 3 and float(partes[0]) > 0:
            val_str = val_str.replace('.', '')
        elif len(partes) > 2:
            val_str = val_str.replace('.', '')
            
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
        raise ValueError("No se encontraron registros de Códigos Postales.")

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

# --- ENCABEZADO ---
st.markdown('<div class="titulo-cotizador">Cotizador Andreani</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitulo-cotizador">Cálculo automático de tarifas de flete según destino y peso volumétrico</div>', unsafe_allow_html=True)

URL_GOOGLE_SHEET = "https://docs.google.com/spreadsheets/d/10npzsWWPaospCZbE692bia6tVPgxKnVa/edit?gid=170077304#gid=170077304"

try:
    df_tarifas = cargar_datos_desde_drive(URL_GOOGLE_SHEET)
    opciones_cp = df_tarifas['Etiqueta'].unique().tolist()
except Exception as e:
    st.error(f"Error de conexión con el tarifario: {e}")
    st.stop()

st.subheader("Datos del Envío")

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
    
    st.markdown(f"""
        <div class="resultado-box">
            <div class="resultado-label">Costo Total del Flete</div>
            <div class="resultado-monto">${resultado['Costo Total']:,.2f}</div>
            <div class="resultado-sub-info">
                <div class="sub-info-item">Peso Facturable: <span class="sub-info-val">{resultado['Peso Facturable']:,.2f} kg</span></div>
                <div class="sub-info-item">Escala Aplicada: <span class="sub-info-val">{resultado['Tramo']}</span></div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### 📋 Desglose del Cálculo")
    st.write(f"- **Código Postal:** {cp_data['CP']}")
    st.write(f"- **Localidad:** {cp_data['Localidad']}, {cp_data['Provincia']}")
    st.write(f"- **Peso Volumétrico:** {resultado['Peso Volumétrico']:,.2f} kg (Cálculo: M3 × 175 kg)")
    st.write(f"- **Tarifa Base Aplicada:** ${resultado['Costo Base']:,.2f}")
    if resultado['Costo Excedente'] > 0:
        kg_exc = resultado['Peso Facturable'] - 500
        st.write(f"- **Kilos Excedentes (>500 kg):** {kg_exc:,.2f} kg")
        st.write(f"- **Costo Excedente:** ${resultado['Costo Excedente']:,.2f}")
