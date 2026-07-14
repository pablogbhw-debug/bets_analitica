import streamlit as st

from controllers.transacciones import diagnosticar_ciclo, registrar_movimiento_bd, retiro_permitido
from views.componentes import dinero, guardar_mensaje_y_limpiar, selector_casa


def mostrar(casas):
    st.header("Registrar un retiro")
    casa = selector_casa(casas, "casa_retiro")
    diagnostico = diagnosticar_ciclo(casa)
    c1, c2, c3 = st.columns(3)
    c1.metric("Disponible registrado", dinero(casa["saldo_retirable"]))
    c2.metric("Retiro mínimo", dinero(casa["minimo_retiro"]))
    c3.metric("Rollover pendiente", dinero(casa["rollover_pendiente"]))
    if retiro_permitido(casa):
        st.success("El retiro cumple las reglas registradas de la casa.")
    else:
        st.warning(diagnostico["recomendacion"])
    with st.form("form_retiro", clear_on_submit=True):
        monto_retiro = st.number_input(
            "Monto retirado", min_value=1.0, step=5.0, format="%.2f"
        )
        guardar_retiro = st.form_submit_button("Guardar retiro")
    if guardar_retiro:
        try:
            registrar_movimiento_bd(casa["id"], "RETIRO", monto_retiro, 1, "RETIRO")
            guardar_mensaje_y_limpiar("Retiro registrado correctamente.", ("casa_retiro",))
        except ValueError as exc:
            st.error(str(exc))
