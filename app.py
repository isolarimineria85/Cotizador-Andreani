import streamlit as st
import pandas as pd
import re

# Configuración inicial de la página
st.set_page_config(page_title="Cotizador Andreani", page_icon="📦", layout="centered")

def convertir_numero(valor):
    """Limpia el formato de moneda/número por si Google Sheets exporta textos como '$ 1.000,50'"""
    if pd.isna(valor) or valor == '':
        return 0.0
    if isinstance(valor, str):
        # Quitamos signo pesos, puntos de miles y cambiamos coma por punto decimal
        valor = valor.replace('$', '').replace('.', '').replace(',', '.').strip()
    try:
        return float(valor)
    except:
        return 0.0

@st.cache_data(ttl=600)  # La app vuelve a leer el sheet cada 10 minutos (600 segundos) para buscar actualizaciones
def cargar_datos_desde_sheets(url):
    # Extraemos el ID y el GID de la URL que pegaste
    match_id = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
    match_gid = re.search(r'gid=([0-9]+)', url)
    
    if not match_id:
        raise ValueError("URL de Google Sheets no válida.")
        
    sheet_id = match_id.group(1)
    gid = match_gid.group(1) if match_gid else "0"
    
    # Armamos la URL de exportación directa a CSV
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    
    # Leemos la planilla directamente desde internet
    df = pd.read_csv(csv_url, header=None)
    
    # Las filas de datos van de la 6 a la 32 (índices 6 a 32 en pandas si no usamos cabecera)
    data_rows = df.iloc[6:33].copy()
    
    tramos_kg = [100, 125, 150, 175, 200, 225, 250, 275, 300, 325, 350, 400, 500]
    datos_limpios = []
    
    for index, row in data_rows.iterrows():
        destino = str(row.iloc[3]).strip().upper()
        if destino == 'NAN' or not destino:
            continue
            
        # Extraer tarifas por tramo (columnas 4 a 16) limpiando el formato de número
        tarifas = {t: convertir_numero(row.iloc[4 + i]) for i, t in enumerate(tramos_kg)}
        
        datos_limpios.append({
            'Destino': destino,
            'Tarifas': tarifas,
            'Tarifa_500': convertir_numero(row.iloc[16]),
            'Kilo_Exc': convertir_numero(row.iloc[17])
        })
        
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

# --- INTERFAZ DE STREAMLIT ---
st.title("📦 Cotizador Automático de Fletes")
st.markdown("Calculá la tarifa seleccionando destino, peso y volumen de la carga.")

# ACA TENES QUE PEGAR EL LINK DE TU GOOGLE SHEET
URL_GOOGLE_SHEET = "https://docs.google.com/spreadsheets/d/1ENaoYS3fQnrauKP2So9fqiLeVRY192-jBb7Qv6xUD-A/edit?usp=drive_link"

try:
    df_tarifas = cargar_datos_desde_sheets(URL_GOOGLE_SHEET)
    destinos = df_tarifas['Destino'].tolist()
except Exception as e:
    st.error("Error al leer el Google Sheet. Verificá que el link sea correcto y que tenga permisos de 'Cualquier persona con el enlace'.")
    st.stop()

# Formularios de ingreso
st.subheader("Datos de la carga")
col1, col2, col3 = st.columns(3)

with col1:
    indice_defecto = destinos.index("PTO. MADRYN") if "PTO. MADRYN" in destinos else 0
    destino_seleccionado = st.selectbox("Destino", options=destinos, index=indice_defecto)
with col2:
    peso_real = st.number_input("Peso Real (Kg)", min_value=0.0, value=1530.0, step=10.0)
with col3:
    m3_carga = st.number_input("Volumen (M3)", min_value=0.0, value=6.08, step=0.1)

# Botón para calcular
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
