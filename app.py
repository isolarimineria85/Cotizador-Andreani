import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="Cotizador Andreani", page_icon="📦", layout="centered")

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
def cargar_datos_desde_sheets(url):
    match_id = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
    if not match_id:
        raise ValueError("La URL proporcionada no parece ser un enlace válido de Google Sheets.")
    
    sheet_id = match_id.group(1)
    match_gid = re.search(r'[#&?]gid=([0-9]+)', url)
    gid = match_gid.group(1) if match_gid else "0"
    
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    
    try:
        df = pd.read_csv(csv_url, header=None)
    except Exception as err:
        raise ConnectionError(f"No se pudo descargar la planilla. Verificá permisos. Detalle: {err}")

    # Buscar la fila de encabezados que contiene los tramos (ej: MINIMO DE HASTA 100 KG)
    header_row_idx = None
    for idx, row in df.iterrows():
        row_str = " ".join(row.dropna().astype(str).values).upper()
        if "100" in row_str and "500" in row_str:
            header_row_idx = idx
            break

    if header_row_idx is None:
        header_row_idx = 5  # Fila por defecto si no detecta el texto

    # Filtrar solo las filas con información de destinos
    datos_limpios = []
    tramos_kg = [100, 125, 150, 175, 200, 225, 250, 275, 300, 325, 350, 400, 500]

    for idx in range(header_row_idx + 1, len(df)):
        row = df.iloc[idx].values
        
        # Filtrar valores no nulos en la fila
        valores_fila = [v for v in row if pd.notna(v) and str(v).strip() != '']
        
        # Si la fila no tiene suficientes datos numéricos/tarifas, se ignora
        if len(valores_fila) < 14:
            continue
            
        destino = str(valores_fila[0]).strip().upper()
        # Si la primera columna limpia es 'AMBA', tomamos la segunda como destino
        if destino == 'AMBA' and len(valores_fila) > 1:
            destino = str(valores_fila[1]).strip().upper()
            valores_numericos = valores_fila[2:]
        else:
            valores_numericos = valores_fila[1:]
            
        if destino in ['NAN', 'NONE', 'ORIGEN', 'REGION / ZONA DESTINO'] or len(valores_numericos) < 14:
            continue

        # Mapear los tramos de peso con sus valores
        tarifas = {}
        for i, t in enumerate(tramos_kg):
            if i < len(valores_numericos):
                tarifas[t] = limpiar_numero(valores_numericos[i])

        tarifa_500 = limpiar_numero(valores_numericos[12]) if len(valores_numericos) > 12 else 0.0
        kilo_exc = limpiar_numero(valores_numericos[13]) if len(valores_numericos) > 13 else 0.0

        datos_limpios.append({
            'Destino': destino,
            'Tarifas': tarifas,
            'Tarifa_500': tarifa_500,
            'Kilo_Exc': kilo_exc
        })

    if not datos_limpios:
        raise ValueError("No se pudieron extraer los destinos de la planilla. Revisá la solapa seleccionada.")

    return pd.DataFrame(datos_limpios)

def calcular_tarifa(destino_data, peso_real, m3):
    peso_vol = m3 * 175
    peso_facturable = max(peso_real, peso_vol)
    
    if peso_facturable <= 500:
        tramos = sorted(destino_data['Tarifas'].keys())
        for t in tramos:
            if peso_facturable <= t:
                costo_total = destino_data['Tarifas'][t]
                return {
                    "Peso Volumétrico": peso_vol,
                    "Peso Facturable": peso_facturable,
                    "Tramo": f"Hasta {t} kg",
                    "Costo Base": costo_total,
                    "Costo Excedente": 0.0,
                    "Costo Total": costo_total
                }
    else:
        tarifa_500 = destino_data['Tarifa_500']
        kilo_exc = destino_data['Kilo_Exc']
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

# --- INTERFAZ ---
st.title("📦 Cotizador Automático de Fletes")
st.markdown("Calculá la tarifa seleccionando destino, peso y volumen de la carga.")

# PEGAR ACÁ EL ENLACE DE GOOGLE SHEETS
URL_GOOGLE_SHEET = "https://docs.google.com/spreadsheets/d/1ENaoYS3fQnrauKP2So9fqiLeVRY192-jBb7Qv6xUD-A/edit?usp=drive_link"

try:
    df_tarifas = cargar_datos_desde_sheets(URL_GOOGLE_SHEET)
    destinos = df_tarifas['Destino'].tolist()
except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

st.subheader("Datos de la carga")
col1, col2, col3 = st.columns(3)

with col1:
    indice_defecto = destinos.index("PTO. MADRYN") if "PTO. MADRYN" in destinos else 0
    destino_seleccionado = st.selectbox("Destino", options=destinos, index=indice_defecto)
with col2:
    peso_real = st.number_input("Peso Real (Kg)", min_value=0.0, value=1530.0, step=10.0)
with col3:
    m3_carga = st.number_input("Volumen (M3)", min_value=0.0, value=6.08, step=0.1)

if st.button("Calcular Costo", type="primary"):
    destino_data = df_tarifas[df_tarifas['Destino'] == destino_seleccionado].iloc[0]
    resultado = calcular_tarifa(destino_data, peso_real, m3_carga)
    
    st.success("¡Cotización generada con éxito!")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Peso Facturable", f"{resultado['Peso Facturable']:,.2f} kg")
    c2.metric("Tramo / Categoría", resultado['Tramo'])
    c3.metric("Costo Total", f"${resultado['Costo Total']:,.2f}")
    
    st.divider()
    st.markdown("### 📋 Desglose del cálculo")
    st.write(f"- **Peso Volumétrico calculado:** {resultado['Peso Volumétrico']:,.2f} kg (1m3 = 175kg)")
    st.write(f"- **Tarifa Base aplicada:** ${resultado['Costo Base']:,.2f}")
    if resultado['Costo Excedente'] > 0:
        kg_exc = resultado['Peso Facturable'] - 500
        st.write(f"- **Kilos Excedentes:** {kg_exc:,.2f} kg")
        st.write(f"- **Costo por Excedente:** ${resultado['Costo Excedente']:,.2f}")
