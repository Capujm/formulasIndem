# -*- coding: utf-8 -*-
"""
Streamlit app: Calculadora de Indemnización (Vuotto, Méndez, Acciarri, Marshall y Local)
Integración RIPTE con índice (IB 07/1994 = 100) y mejoras de inputs solicitadas.
- Inputs de salario en una sola fila.
- Usar fecha del evento como inicio para actualización RIPTE (sin nuevo input).
- Opción de usar Índice No Decreciente (SRT/ART) para evitar coeficientes < 1.
"""


import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
import io

import pandas as pd

@st.cache_data
def cargar_ripte(path="data/ripte.csv"):
    try:
        df = pd.read_csv(path)
    except Exception:
        st.error("No se encontró el archivo RIPTE en data/ripte.csv. Suba el CSV con columnas: fecha (YYYY-MM), indice.")
        uploaded = st.file_uploader("Subir CSV RIPTE", type=["csv"])
        if uploaded:
            df = pd.read_csv(uploaded)
        else:
            return pd.DataFrame()
    df.columns = [c.lower().strip() for c in df.columns]
    if "fecha" not in df.columns or "indice" not in df.columns:
        st.error("El CSV debe tener columnas 'fecha' y 'indice'.")
        return pd.DataFrame()
    df['fecha'] = pd.to_datetime(df['fecha']).dt.to_period('M')
    df['indice'] = pd.to_numeric(df['indice'], errors='coerce')
    df = df.dropna().sort_values('fecha').drop_duplicates(subset=['fecha'], keep='last').reset_index(drop=True)
    return df

def seleccionar_periodos(df, fecha_inicial, fecha_final):
    if df.empty:
        return None, None
    pi = pd.Period(f"{fecha_inicial.year}-{fecha_inicial.month:02d}")
    pf = pd.Period(f"{fecha_final.year}-{fecha_final.month:02d}")
    if pf < pi:
        pi, pf = pf, pi
    if pi not in set(df['fecha']):
        ant = df[df['fecha'] <= pi]['fecha']
        pi = ant.max() if not ant.empty else df['fecha'].min()
    if pf not in set(df['fecha']):
        ant = df[df['fecha'] <= pf]['fecha']
        pf = ant.max() if not ant.empty else df['fecha'].max()
    pf = min(pf, df['fecha'].max())
    return pi, pf

def coeficiente_ripte(df, pi, pf, usar_nd=True):
    if df.empty or pi is None or pf is None:
        return 1.0
    serie = df.copy()
    if usar_nd:
        serie['indice_nd'] = serie['indice'].cummax()
        vi = float(serie.loc[serie['fecha'] == pi, 'indice_nd'].iloc[0])
        vf = float(serie.loc[serie['fecha'] == pf, 'indice_nd'].iloc[0])
    else:
        vi = float(serie.loc[serie['fecha'] == pi, 'indice'].iloc[0])
        vf = float(serie.loc[serie['fecha'] == pf, 'indice'].iloc[0])
    return vf / vi if vi > 0 else 1.0


# Constante: Salario mínimo vital y móvil (SMVM) Argentina
SMVM = 322000  # mensual

# Función para coeficiente actuarial
def coeficiente_actuarial(i, n):
    if n <= 0:
        return 0
    return (1 - (1 / ((1 + i) ** n))) / i

# Fórmulas clásicas
def formula_vuotto(salario_anual, i, n, incapacidad):
    return salario_anual * coeficiente_actuarial(i, n) * incapacidad

def formula_mendez(salario_anual, i, n, incapacidad, edad):
    return salario_anual * (60 / edad) * coeficiente_actuarial(i, n) * incapacidad

def formula_acciarri(salario_anual, i, n, incapacidad, edad):
    coef_extra = 1.1
    return salario_anual * (60 / edad) * coeficiente_actuarial(i, n) * incapacidad * coef_extra

def formula_marshall(salario_anual, i, n, incapacidad):
    return salario_anual * coeficiente_actuarial(i, n) * incapacidad

# Fórmula Local
def formula_local(valor_punto, puntos_fisicos, puntos_psico, dano_moral_pct, tasa_interes, anos_transcurridos):
    base = (valor_punto * puntos_fisicos) + (valor_punto * puntos_psico * 0.5) + (valor_punto * puntos_fisicos * dano_moral_pct)
    factor_tasa = (1 + tasa_interes) ** anos_transcurridos
    return base * factor_tasa

# Configuración Streamlit
st.set_page_config(page_title="Calculadora Indemnización", layout="wide")
st.title("Calculadora de Indemnización (Vuotto, Méndez, Acciarri, Marshall y Local)")

# Inputs
col1, col2, col3 = st.columns(3)
edad_evento = col1.number_input("Edad al hecho", min_value=0, max_value=120, value=30)
fecha_hecho = col2.date_input("Fecha del hecho", value=datetime.today(), min_value=date(1990, 1, 1), max_value=date.today())
puntos_fisicos = col3.number_input("Incapacidad física (puntos)", min_value=0.0, max_value=100.0, step=0.5, value=10.0)


col7, col8 = st.columns(2)
valor_punto = col7.number_input("Valor del punto", min_value=0.0, value=500000.0)
tasa_interes = col8.number_input("Tasa interés anual (%)", min_value=0.0, max_value=100.0, step=0.5, value=6.0) / 100

# Bloque de salario reorganizado con RIPTE
st.subheader("Salario")
colS1, colS2, colS3, colS4 = st.columns(4)
salario_mensual = colS1.number_input("Salario mensual", min_value=0.0, step=50000.0, value=0.0, help="Si se deja en 0, se usa SMVM vigente.")
puntos_psico = colS2.number_input("Incapacidad psicológica (puntos)", min_value=0.0, max_value=100.0, step=0.5, value=0.0)
dano_moral_pct = colS3.number_input("Daño moral (%)", min_value=0.0, max_value=100.0, step=1.0, value=0.0) / 100
tipo_salario = colS4.radio("Tipo", ["Valor actual", "Valor histórico"], index=0)
fecha_calculo = st.date_input("Fecha de cálculo", value=date.today(), max_value=date.today())
usar_nd = st.checkbox("Índice No Decreciente (SRT/ART)", value=True)

ripte_df = pd.DataFrame()
coef_aplicado = 1.0
periodo_inicial_usado = None
periodo_final_usado = None
if tipo_salario == "Valor histórico":
    ripte_df = cargar_ripte()
    if salario_mensual > 0 and not ripte_df.empty:
        pi, pf = seleccionar_periodos(ripte_df, fecha_hecho, fecha_calculo)
        coef_aplicado = coeficiente_ripte(ripte_df, pi, pf, usar_nd=usar_nd)
        salario_mensual = salario_mensual * coef_aplicado
        periodo_inicial_usado, periodo_final_usado = pi, pf

if salario_mensual <= 0:
    salario_mensual = SMVM
salario_anual = salario_mensual * 13

if tipo_salario == "Valor histórico" and periodo_inicial_usado is not None:
    st.info(f"RIPTE aplicado: coef {coef_aplicado:.4f}. Periodo inicial: {periodo_inicial_usado}, final: {periodo_final_usado}. Salario actualizado: $ {salario_mensual:,.0f}")

if salario_mensual <= 0:
    salario_mensual = SMVM
salario_anual = salario_mensual * 13

# Selector de fórmulas
formulas_sel = st.multiselect("Selecciona fórmulas", ["Vuotto", "Méndez", "Acciarri", "Marshall", "Local"], default=["Vuotto", "Méndez", "Acciarri", "Marshall", "Local"])
interes_default = {"Vuotto": 0.06, "Méndez": 0.04, "Acciarri": 0.04, "Marshall": 0.06}

# Criterio de cálculo
criterio = st.radio("Criterio de cálculo de años restantes (n)", ["Usar edad al hecho", "Recalcular con edad actual"], index=0)

# Edad base y años transcurridos
edad_base = edad_evento
edad_actual = edad_evento
hoy = date.today()
anos_transcurridos = (hoy.year - fecha_hecho.year) - ((hoy.month, hoy.day) < (fecha_hecho.month, fecha_hecho.day))
if criterio == "Recalcular con edad actual":
    edad_base = max(edad_evento + anos_transcurridos, 0)
    edad_actual = edad_base

# Calcular resultados
resultados = {}
info_detalle = {}
incapacidad = puntos_fisicos / 100  # Para fórmulas clásicas sigue siendo %
for f in formulas_sel:
    if f == "Vuotto":
        n = max(65 - edad_base, 0)
        i = interes_default[f]
        resultados[f] = formula_vuotto(salario_anual, i, n, incapacidad)
        info_detalle[f] = f"Edad base: {edad_base} | Años restantes: {n}"
    elif f == "Méndez":
        n = max(75 - edad_base, 0)
        i = interes_default[f]
        resultados[f] = formula_mendez(salario_anual, i, n, incapacidad, edad_base)
        info_detalle[f] = f"Edad base: {edad_base} | Años restantes: {n}"
    elif f == "Acciarri":
        n = max(75 - edad_base, 0)
        i = interes_default[f]
        resultados[f] = formula_acciarri(salario_anual, i, n, incapacidad, edad_base)
        info_detalle[f] = f"Edad base: {edad_base} | Años restantes: {n}"
    elif f == "Marshall":
        n = max(80 - edad_base, 0)
        i = interes_default[f]
        resultados[f] = formula_marshall(salario_anual, i, n, incapacidad)
        info_detalle[f] = f"Edad base: {edad_base} | Años restantes: {n}"
    elif f == "Local":
        resultados[f] = formula_local(valor_punto, puntos_fisicos, puntos_psico, dano_moral_pct, tasa_interes, anos_transcurridos)
        info_detalle[f] = f"Años transcurridos: {anos_transcurridos} | Tasa aplicada: {(1+tasa_interes)**anos_transcurridos:.2f}"

# Mostrar resultados
st.subheader("Resultados")
if resultados:
    cols = st.columns(len(resultados))
    for idx, (formula, valor) in enumerate(resultados.items()):
        cols[idx].metric(label=formula, value=f"$ {valor:,.0f}")
else:
    st.warning("No hay fórmulas seleccionadas o los años restantes son cero.")

# Detalle adicional
st.write(f"Edad al hecho: {edad_evento} | Edad actual: {edad_actual}")
for f in formulas_sel:
    st.write(f"{f}: {info_detalle.get(f, '')}")

# Gráfico comparativo de barras
if formulas_sel:
    df_resultados = pd.DataFrame(list(resultados.items()), columns=["Fórmula", "Indemnización ($)"])
    if not df_resultados.empty:
        fig_bar = px.bar(df_resultados, x="Fórmula", y="Indemnización ($)", title="Comparación de Fórmulas", text="Indemnización ($)")
        fig_bar.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
        st.plotly_chart(fig_bar, use_container_width=True)

# ========================= NUEVA SECCIÓN =========================
# Slider para rango de edad
min_age, max_age = st.slider("Rango de edad para gráficos comparativos", 1, 100, (1, 100))

# Generar datos para edades en rango
edades = list(range(min_age, max_age + 1))
resultados_por_formula = {}
for formula in ["Vuotto", "Méndez", "Acciarri", "Marshall"]:
    indemnizaciones = []
    for edad in edades:
        if formula == "Vuotto":
            n = max(65 - edad, 0)
            i = interes_default[formula]
            indemnizaciones.append(formula_vuotto(salario_anual, i, n, incapacidad))
        elif formula == "Méndez":
            n = max(75 - edad, 0)
            i = interes_default[formula]
            indemnizaciones.append(formula_mendez(salario_anual, i, n, incapacidad, edad))
        elif formula == "Acciarri":
            n = max(75 - edad, 0)
            i = interes_default[formula]
            indemnizaciones.append(formula_acciarri(salario_anual, i, n, incapacidad, edad))
        elif formula == "Marshall":
            n = max(80 - edad, 0)
            i = interes_default[formula]
            indemnizaciones.append(formula_marshall(salario_anual, i, n, incapacidad))
    resultados_por_formula[formula] = indemnizaciones

# Scatter plots individuales sin leyenda
st.subheader("Tendencia por edad (fórmulas clásicas)")
st.caption("Línea: tendencia | Punto rojo: edad ingresada")
cols = st.columns(4)
for idx, formula in enumerate(["Vuotto", "Méndez", "Acciarri", "Marshall"]):
    df = pd.DataFrame({"Edad": edades, "Indemnización": resultados_por_formula[formula]})
    fig = px.scatter(df, x="Edad", y="Indemnización", size_max=6)
    fig.add_scatter(x=edades, y=resultados_por_formula[formula], mode="lines", line=dict(width=1), showlegend=False)
    fig.add_scatter(x=[edad_evento], y=[resultados_por_formula[formula][edad_evento - min_age]], mode="markers",
                    marker=dict(color="red", size=10), showlegend=False)
    fig.update_layout(title=formula, margin=dict(l=10, r=10, t=30, b=10), height=250, showlegend=False)
    cols[idx].plotly_chart(fig, use_container_width=True)

# Gráfico comparativo con línea vertical
fig_comparativo = go.Figure()
colors = {"Vuotto": "blue", "Méndez": "green", "Acciarri": "orange", "Marshall": "purple"}
for formula in ["Vuotto", "Méndez", "Acciarri", "Marshall"]:
    fig_comparativo.add_trace(go.Scatter(x=edades, y=resultados_por_formula[formula], mode="lines", name=formula, line=dict(width=2, color=colors[formula])))
fig_comparativo.add_shape(type="line", x0=edad_evento, y0=0, x1=edad_evento, y1=max(max(vals) for vals in resultados_por_formula.values()), line=dict(color="red", width=2, dash="dash"))
fig_comparativo.update_layout(title="Comparación de fórmulas vs Edad", xaxis_title="Edad", yaxis_title="Indemnización", height=500)
st.plotly_chart(fig_comparativo, use_container_width=True)

