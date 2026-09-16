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
    
    csv_url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv&gid={gid}"
    
    try:
        df = pd.read_csv(csv_url, header=None)
    except Exception:
        excel_url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
        df = pd.read_excel(excel_url, header=None)

    datos_limpios = []
    tramos_kg = [100, 125, 150, 175, 200, 225, 250, 275, 300, 325, 350, 400, 500]

    for idx in range(len(df)):
        row = df.iloc[idx].values
        
        # Filtrar elementos no nulos para ubicar dinámicamente las celdas
        valores_fila = [v for v in row if pd.notna(v) and str(v).strip() != '']
        if len(valores_fila) < 5:
            continue
            
        # Detectar la celda donde está el CP
        valor_cp = ""
        localidad = "No especificada"
        provincia = "No especificada"
        valores_numericos = []
        
        for i, val in enumerate(valores_fila):
            val_clean = str(val).strip().replace('.0', '')
            if val_clean.isdigit() and len(val_clean) <= 5:
                valor_cp = val_clean
                # Extraer texto cercano como localidad y provincia
                textos = [str(x).strip() for x in valores_fila[:i] if not str(x).strip().replace('.0', '').isdigit()]
                if len(textos) >= 2:
                    provincia = textos[0]
                    localidad = textos[1]
                elif len(textos) == 1:
                    localidad = textos[0]
                valores_numericos = valores_fila[i+1:]
                break

        if not valor_cp:
            continue

        # Mapear tarifas de peso
        tarifas = {}
        for i, t in enumerate(tramos_kg):
            if i < len(valores_numericos):
                tarifas[t] = limpiar_numero(valores_numericos[i])

        tarifa_500 = limpiar_numero(valores_numericos[12]) if len(valores_numericos) > 12 else 0.0
        kilo_exc = limpiar_numero(valores_numericos[13]) if len(valores_numericos) > 13 else 0.0

        datos_limpios.append({
            'CP': valor_cp,
            'Localidad': localidad,
            'Provincia': provincia,
            'Etiqueta': f"{valor_cp} - {localidad} ({provincia})" if localidad != "No especificada" else valor_cp,
            'Tarifas': tarifas,
            'Tarifa_500': tarifa_500,
            'Kilo_Exc': kilo_exc
        })

    if not datos_limpios:
        raise ValueError("No se encontraron registros de Códigos Postales en la solapa del Google Sheet.")

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
st.markdown("Seleccioná el Código Postal para ver la localidad asociada y calcular el flete.")

URL_GOOGLE_SHEET = "https://docs.google.com/spreadsheets/d/10npzsWWPaospCZbE692bia6tVPgxKnVa/edit?gid=170077304#gid=170077304"

try:
    df_tarifas = cargar_datos_desde_drive(URL_GOOGLE_SHEET)
    opciones_cp = df_tarifas['Etiqueta'].unique().tolist()
except Exception as e:
    st.error(f"Error de conexión con el tarifario: {e}")
    st.stop()

st.subheader("Datos de Destino y Carga")

# Desplegable enriquecido con CP + Localidad + Provincia
seleccion = st.selectbox("Buscar por Código Postal / Localidad", options=opciones_cp)

# Extraer el registro seleccionado
cp_data = df_tarifas[df_tarifas['Etiqueta'] == seleccion].iloc[0]

# Mostrar tarjeta informativa del destino
st.info(f"📍 **Destino Seleccionado:** Localidad de **{cp_data['Localidad']}**, Provincia de **{cp_data['Provincia']}** (CP {cp_data['CP']})")

col1, col2 = st.columns(2)
with col1:
    peso_real = st.number_input("Peso Real (Kg)", min_value=0.0, value=1530.0, step=10.0)
with col2:
    m3_carga = st.number_input("Volumen (M3)", min_value=0.0, value=6.08, step=0.1)

if st.button("Calcular Cotización", type="primary"):
    resultado = calcular_tarifa(cp_data, peso_real, m3_carga)
    
    st.success("¡Cotización calculada!")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Peso Facturable", f"{resultado['Peso Facturable']:,.2f} kg")
    c2.metric("Tramo Aplicado", resultado['Tramo'])
    c3.metric("Costo Total", f"${resultado['Costo Total']:,.2f}")
    
    st.divider()
    st.markdown("### 📋 Desglose del Cálculo")
    st.write(f"- **Código Postal:** {cp_data['CP']}")
    st.write(f"- **Localidad:** {cp_data['Localidad']}")
    st.write(f"- **Provincia:** {cp_data['Provincia']}")
    st.write(f"- **Peso Volumétrico:** {resultado['Peso Volumétrico']:,.2f} kg (Cálculo: M3 × 175 kg)")
    st.write(f"- **Tarifa Base Aplicada:** ${resultado['Costo Base']:,.2f}")
    if resultado['Costo Excedente'] > 0:
        kg_exc = resultado['Peso Facturable'] - 500
        st.write(f"- **Kilos Excedentes (>500 kg):** {kg_exc:,.2f} kg")
        st.write(f"- **Costo Excedente:** ${resultado['Costo Excedente']:,.2f}")
