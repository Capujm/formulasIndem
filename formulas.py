# -*- coding: utf-8 -*-
"""
Created on Mon Nov 24 14:26:48 2025


"""


import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
import io

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

col4, col5, col6 = st.columns(3)
salario_mensual = col4.number_input("Salario mensual (opcional)", min_value=0.0, value=0.0)
puntos_psico = col5.number_input("Incapacidad psicológica (puntos)", min_value=0.0, max_value=100.0, step=0.5, value=0.0)
dano_moral_pct = col6.number_input("Daño moral (%)", min_value=0.0, max_value=100.0, step=0.5, value=0.0) / 100

col7, col8 = st.columns(2)
valor_punto = col7.number_input("Valor del punto", min_value=0.0, value=500000.0)
tasa_interes = col8.number_input("Tasa interés anual (%)", min_value=0.0, max_value=100.0, step=0.1, value=6.0) / 100

if salario_mensual <= 0:
    salario_mensual = SMVM
salario_anual = salario_mensual * 13

# Selector de fórmulas
formulas_sel = st.multiselect("Selecciona fórmulas", ["Vuotto", "Méndez", "Acciarri", "Marshall", "Local"], default=["Vuotto", "Méndez"])
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

# Scatter plots individuales
st.subheader("Tendencia por edad (fórmulas clásicas)")
cols = st.columns(4)
for idx, formula in enumerate(["Vuotto", "Méndez", "Acciarri", "Marshall"]):
    df = pd.DataFrame({"Edad": edades, "Indemnización": resultados_por_formula[formula]})
    fig = px.scatter(df, x="Edad", y="Indemnización", size_max=6)
    fig.add_scatter(x=edades, y=resultados_por_formula[formula], mode="lines", line=dict(width=1), name="Tendencia")
    fig.add_scatter(x=[edad_evento], y=[resultados_por_formula[formula][edad_evento - min_age]], mode="markers", marker=dict(color="red", size=10), name="Edad ingresada")
    fig.update_layout(title=formula, margin=dict(l=10, r=10, t=30, b=10), height=250)
    cols[idx].plotly_chart(fig, use_container_width=True)

# Gráfico comparativo con línea vertical
fig_comparativo = go.Figure()
colors = {"Vuotto": "blue", "Méndez": "green", "Acciarri": "orange", "Marshall": "purple"}
for formula in ["Vuotto", "Méndez", "Acciarri", "Marshall"]:
    fig_comparativo.add_trace(go.Scatter(x=edades, y=resultados_por_formula[formula], mode="lines", name=formula, line=dict(width=2, color=colors[formula])))

fig_comparativo.add_shape(type="line", x0=edad_evento, y0=0, x1=edad_evento, y1=max(max(vals) for vals in resultados_por_formula.values()), line=dict(color="red", width=2, dash="dash"))
fig_comparativo.update_layout(title="Comparación de fórmulas vs Edad", xaxis_title="Edad", yaxis_title="Indemnización", height=500)
st.plotly_chart(fig_comparativo, use_container_width=True)


