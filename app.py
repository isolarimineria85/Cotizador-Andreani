import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="Cotizador Andreani por CP", page_icon="📦", layout="centered")

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
    
    # URL directa para descargar la solapa específica en formato CSV
    csv_url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv&gid={gid}"
    
    try:
        df = pd.read_csv(csv_url, header=None)
    except Exception:
        # Alternativa de respaldo en formato XLSX
        excel_url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
        df = pd.read_excel(excel_url, header=None)

    datos_limpios = []
    tramos_kg = [100, 125, 150, 175, 200, 225, 250, 275, 300, 325, 350, 400, 500]

    # Recorrer las filas buscando los CPs
    for idx in range(len(df)):
        row = df.iloc[idx]
        
        # Tomar la Columna D (Índice 3 en Pandas)
        valor_cp = str(row.iloc[3]).strip().replace('.0', '') if len(row) > 3 else ''
        
        # Si la columna D no tiene el CP, intentar con las primeras columnas
        if valor_cp.upper() in ['NAN', 'NONE', '', 'CP', 'CODIGO POSTAL', 'ORIGEN']:
            posible_cp = str(row.iloc[0]).strip().replace('.0', '') if len(row) > 0 else ''
            if posible_cp.isdigit():
                valor_cp = posible_cp

        if not valor_cp.isdigit():
            continue

        # Mapear tarifas de peso
        tarifas = {}
        # Asumiendo que las tarifas empiezan en la columna E (Índice 4)
        for i, t in enumerate(tramos_kg):
            if (4 + i) < len(row):
                tarifas[t] = limpiar_numero(row.iloc[4 + i])

        tarifa_500 = limpiar_numero(row.iloc[16]) if len(row) > 16 else 0.0
        kilo_exc = limpiar_numero(row.iloc[17]) if len(row) > 17 else 0.0

        datos_limpios.append({
            'CP': valor_cp,
            'Tarifas': tarifas,
            'Tarifa_500': tarifa_500,
            'Kilo_Exc': kilo_exc
        })

    if not datos_limpios:
        raise ValueError("No se encontraron Códigos Postales válidos en esta solapa de Google Sheets.")

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

# --- INTERFAZ STREAMLIT ---
st.title("📦 Cotizador Andreani por Código Postal")
st.markdown("Calculá el flete ingresando el Código Postal de destino.")

# URL exacta de tu pestaña
URL_GOOGLE_SHEET = "https://docs.google.com/spreadsheets/d/10npzsWWPaospCZbE692bia6tVPgxKnVa/edit?gid=170077304#gid=170077304"

try:
    df_tarifas = cargar_datos_desde_drive(URL_GOOGLE_SHEET)
    lista_cps = sorted(df_tarifas['CP'].unique().tolist())
except Exception as e:
    st.error(f"Error de conexión con el tarifario: {e}")
    st.stop()

st.subheader("Datos de la Carga")
col1, col2, col3 = st.columns(3)

with col1:
    cp_ingresado = st.selectbox("Código Postal (CP)", options=lista_cps)
with col2:
    peso_real = st.number_input("Peso Real (Kg)", min_value=0.0, value=1530.0, step=10.0)
with col3:
    m3_carga = st.number_input("Volumen (M3)", min_value=0.0, value=6.08, step=0.1)

if st.button("Calcular Cotización", type="primary"):
    cp_data = df_tarifas[df_tarifas['CP'] == cp_ingresado].iloc[0]
    resultado = calcular_tarifa(cp_data, peso_real, m3_carga)
    
    st.success("¡Cotización calculada!")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Peso Facturable", f"{resultado['Peso Facturable']:,.2f} kg")
    c2.metric("Tramo Aplicado", resultado['Tramo'])
    c3.metric("Costo Total", f"${resultado['Costo Total']:,.2f}")
    
    st.divider()
    st.markdown("### 📋 Desglose")
    st.write(f"- **CP Seleccionado:** {cp_ingresado}")
    st.write(f"- **Peso Volumétrico:** {resultado['Peso Volumétrico']:,.2f} kg")
    st.write(f"- **Tarifa Base:** ${resultado['Costo Base']:,.2f}")
    if resultado['Costo Excedente'] > 0:
        st.write(f"- **Kilos Excedentes (>500 kg):** {resultado['Peso Facturable'] - 500:,.2f} kg")
        st.write(f"- **Costo Excedente:** ${resultado['Costo Excedente']:,.2f}")
