import streamlit as st
import pandas as pd
import re
import io
import urllib.request

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
def cargar_datos_desde_drive(url):
    match_id = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
    if not match_id:
        raise ValueError("La URL proporcionada no parece ser un enlace válido de Google Drive/Sheets.")
    
    file_id = match_id.group(1)
    
    # Intento 1: Descarga directa en formato Excel (.xlsx)
    excel_url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
    
    try:
        df = pd.read_excel(excel_url, header=None)
    except Exception:
        # Intento 2: Descarga en formato CSV (por si el archivo se convirtió a Google Sheets nativo)
        csv_url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv"
        df = pd.read_csv(csv_url, header=None)

    datos_limpios = []
    tramos_kg = [100, 125, 150, 175, 200, 225, 250, 275, 300, 325, 350, 400, 500]

    for idx in range(len(df)):
        row = df.iloc[idx].values
        valores_fila = [v for v in row if pd.notna(v) and str(v).strip() != '']
        
        if len(valores_fila) < 13:
            continue
            
        # Tomar la clave de búsqueda (Código Postal / Destino)
        clave_cp = str(valores_fila[0]).strip().replace('.0', '')
        
        # Omitir filas de encabezado o vacías
        if clave_cp.upper() in ['NAN', 'NONE', 'ORIGEN', 'REGION / ZONA DESTINO', 'CP', 'CODIGO POSTAL'] or len(valores_fila) < 13:
            # Si el CP estaba en la segunda columna:
            if len(valores_fila) > 1 and str(valores_fila[1]).strip().replace('.0', '').isdigit():
                clave_cp = str(valores_fila[1]).strip().replace('.0', '')
                valores_numericos = valores_fila[2:]
            else:
                continue
        else:
            valores_numericos = valores_fila[1:]

        # Procesar valores de las tarifas
        tarifas = {}
        for i, t in enumerate(tramos_kg):
            if i < len(valores_numericos):
                tarifas[t] = limpiar_numero(valores_numericos[i])

        tarifa_500 = limpiar_numero(valores_numericos[12]) if len(valores_numericos) > 12 else 0.0
        kilo_exc = limpiar_numero(valores_numericos[13]) if len(valores_numericos) > 13 else 0.0

        datos_limpios.append({
            'CP': clave_cp,
            'Tarifas': tarifas,
            'Tarifa_500': tarifa_500,
            'Kilo_Exc': kilo_exc
        })

    if not datos_limpios:
        raise ValueError("No se pudieron extraer datos del tarifario. Verificá que el archivo en Drive esté compartido públicamente.")

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
st.markdown("Calculá el flete ingresando el Código Postal de destino, peso y volumen de la carga.")

# URL del nuevo archivo en Google Drive
URL_GOOGLE_SHEET = "https://docs.google.com/spreadsheets/d/10npzsWWPaospCZbE692bia6tVPgxKnVa/edit?usp=sharing"

try:
    df_tarifas = cargar_datos_desde_drive(URL_GOOGLE_SHEET)
    lista_cps = sorted(df_tarifas['CP'].unique().tolist())
except Exception as e:
    st.error(f"Error al leer el tarifario desde Google Drive: {e}")
    st.stop()

st.subheader("Datos de la Carga y Destino")
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
    
    st.success("¡Cotización calculada exitosamente!")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Peso Facturable", f"{resultado['Peso Facturable']:,.2f} kg")
    c2.metric("Categoría / Tramo", resultado['Tramo'])
    c3.metric("Costo Total", f"${resultado['Costo Total']:,.2f}")
    
    st.divider()
    st.markdown("### 📋 Desglose del Cálculo")
    st.write(f"- **Código Postal Seleccionado:** {cp_ingresado}")
    st.write(f"- **Peso Volumétrico:** {resultado['Peso Volumétrico']:,.2f} kg (M3 × 175 kg)")
    st.write(f"- **Tarifa Base Aplicada:** ${resultado['Costo Base']:,.2f}")
    if resultado['Costo Excedente'] > 0:
        kg_exc = resultado['Peso Facturable'] - 500
        st.write(f"- **Kilos Excedentes (>500 kg):** {kg_exc:,.2f} kg")
        st.write(f"- **Costo por Excedente:** ${resultado['Costo Excedente']:,.2f}")
