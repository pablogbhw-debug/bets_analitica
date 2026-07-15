"""Componentes visuales compartidos por las vistas Streamlit."""

import pandas as pd
import streamlit as st

def dinero(valor):
    return f"S/ {float(valor):,.2f}"

def guardar_mensaje_y_limpiar(mensaje, claves=()):
    """Muestra el resultado tras rerun y reinicia widgets para el siguiente registro."""
    st.session_state["mensaje_exito"] = mensaje
    st.session_state["claves_por_limpiar"] = list(claves)
    st.rerun()

def resaltar_fila_financiera(fila):
    """Colorea filas completas según resultado o tipo de movimiento."""
    estado = str(fila.get("estado", "")).upper()
    movimiento = str(fila.get("tipo_movimiento", "")).upper()
    resultado = fila.get("resultado")
    if estado == "CASH_OUT":
        monto = float(fila.get("monto", 0) or 0)
        retorno = float(fila.get("retorno", 0) or 0)
        if retorno < monto:
            estilo = "background-color: #F8D7DA; color: #842029; font-weight: 600"
        else:
            estilo = "background-color: #D3D3D3; color: #343A40; font-weight: 600"
    elif "PERDIDA" in estado or "PERDIDA" in movimiento:
        estilo = "background-color: #F8D7DA; color: #842029; font-weight: 600"
    elif "GANADA" in estado or "GANADA" in movimiento:
        estilo = "background-color: #D1E7DD; color: #0F5132; font-weight: 600"
    elif movimiento == "RECARGA":
        estilo = "background-color: #D3D3D3; color: #343A40; font-weight: 600"
    elif isinstance(resultado, (int, float)) and resultado < 0:
        estilo = "background-color: #F8D7DA; color: #842029; font-weight: 600"
    elif isinstance(resultado, (int, float)) and resultado > 0:
        estilo = "background-color: #D1E7DD; color: #0F5132; font-weight: 600"
    else:
        estilo = ""
    return [estilo] * len(fila)

def tabla_financiera(tabla):
    """Devuelve un Styler reutilizable para dataframes y data editors."""
    formatos = {
        columna: "{:,.2f}"
        for columna in tabla.columns
        if pd.api.types.is_numeric_dtype(tabla[columna])
        and columna not in {"id", "apuestas", "seleccionar"}
    }
    estilo = tabla.style.apply(resaltar_fila_financiera, axis=1).format(formatos)
    if "ganadas" in tabla.columns:
        estilo = estilo.map(
            lambda valor: ("background-color: #198754; color: white; font-weight: 700"
                           if float(valor) > 0 else "color: #198754; font-weight: 700"),
            subset=["ganadas"],
        )
    if "perdidas" in tabla.columns:
        estilo = estilo.map(
            lambda valor: ("background-color: #DC3545; color: white; font-weight: 700"
                           if float(valor) > 0 else "color: #DC3545; font-weight: 700"),
            subset=["perdidas"],
        )
    for columna_cashout in ("cashout_neutros",):
        if columna_cashout in tabla.columns:
            estilo = estilo.map(
                lambda valor: ("background-color: #6C757D; color: white; font-weight: 700"
                               if float(valor) > 0 else "color: #6C757D"),
                subset=[columna_cashout],
            )
    if "cashout_perdida" in tabla.columns:
        estilo = estilo.map(
            lambda valor: ("background-color: #DC3545; color: white; font-weight: 700"
                           if float(valor) > 0 else "color: #DC3545"),
            subset=["cashout_perdida"],
        )
    return estilo

def selector_casa(casas, clave, etiqueta="Casa de apuestas", detener_si_vacia=True):
    opciones = {f"{c['nombre_casa']} ({c['id']})": c for c in casas}
    seleccion = st.selectbox(
        etiqueta, list(opciones), index=None,
        placeholder="Selecciona una casa explícitamente", key=clave,
    )
    if seleccion is None:
        st.info("Selecciona la casa para continuar. Cada movimiento se registra por separado.")
        if detener_si_vacia:
            st.stop()
        return None
    return opciones[seleccion]
