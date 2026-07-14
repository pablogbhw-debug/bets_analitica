"""Capa de presentación: bitácora simple de apuestas y retiros."""

import streamlit as st

from controllers.transacciones import (
    inicializar_casas_predeterminadas,
    inicializar_db,
    obtener_resumen_casas,
    recalcular_rollover_casa,
)
from views.autenticacion import mostrar_autenticacion
from views.apuesta.apuesta import mostrar as mostrar_apuesta
from views.casas.casas import mostrar as mostrar_casas
from views.historial.historial import mostrar as mostrar_historial
from views.pendientes.pendientes import mostrar as mostrar_pendientes
from views.recarga.recarga import mostrar as mostrar_recarga
from views.resumen.resumen import mostrar as mostrar_resumen
from views.retiro.retiro import mostrar as mostrar_retiro

st.set_page_config(page_title="Bitácora de apuestas", layout="wide")

MODULOS = {
    'Resumen y análisis': mostrar_resumen,
    'Registrar recarga': mostrar_recarga,
    'Registrar apuesta': mostrar_apuesta,
    'Apuestas pendientes': mostrar_pendientes,
    'Registrar retiro': mostrar_retiro,
    'Configurar casas': mostrar_casas,
    'Historial': mostrar_historial,
}


@st.cache_resource
def inicializar_sistema():
    """Ejecuta migraciones y preparación financiera una sola vez por proceso."""
    inicializar_db()
    inicializar_casas_predeterminadas()
    for casa in obtener_resumen_casas():
        recalcular_rollover_casa(casa["id"])
    return True


def mostrar_aplicacion(usuario):
    """Renderiza la zona privada únicamente cuando existe una sesión válida."""
    casas = obtener_resumen_casas()

    for clave in st.session_state.pop("claves_por_limpiar", []):
        st.session_state.pop(clave, None)
    if mensaje := st.session_state.pop("mensaje_exito", None):
        st.success(mensaje)

    st.title("Bitácora analizadora de apuestas")
    st.caption(
        "Registra apuestas y retiros. El sistema analiza ganancias, pérdidas y patrones de riesgo; "
        "no predice resultados deportivos."
    )
    modulo = st.sidebar.radio("Módulos", list(MODULOS))
    st.sidebar.info(
        "Registra recargas, apuestas terminadas y retiros; el análisis aparece en el Dashboard."
    )
    st.sidebar.caption(f"Sesión: {usuario['correo']}")
    if st.sidebar.button("Cerrar sesión", width="stretch"):
        st.session_state.pop("usuario", None)
        st.rerun()
        return
    MODULOS[modulo](casas)


inicializar_sistema()
usuario_actual = st.session_state.get("usuario")
if usuario_actual is None:
    mostrar_autenticacion()
else:
    mostrar_aplicacion(usuario_actual)
