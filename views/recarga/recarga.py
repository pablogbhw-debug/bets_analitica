import streamlit as st

from controllers import analitica_recarga as analitica
from controllers.transacciones import registrar_recarga_bitacora
from views.componentes import dinero, guardar_mensaje_y_limpiar, selector_casa


def mostrar(casas):
    st.header("Registrar una recarga")
    casa = selector_casa(casas, "casa_recarga")
    resumen_casa = analitica.resumen_financiero_casa(casa["id"])
    st.subheader("Bitácora acumulada de la casa")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total recargado", dinero(resumen_casa["total_recargado"]))
    c2.metric("Bonos recibidos", dinero(resumen_casa["total_bonos"]))
    c3.metric("Monto no retirable", dinero(resumen_casa["monto_no_retirable"]))
    c4.metric("Pérdida acumulada", dinero(resumen_casa["perdida_acumulada"]))
    if resumen_casa["resultado_neto"] < 0:
        st.error(
            f"Esta casa registra una pérdida neta de {dinero(resumen_casa['perdida_acumulada'])}. "
            "Una nueva recarga aumenta el capital expuesto y no garantiza recuperar lo perdido."
        )
    elif resumen_casa["resultado_neto"] > 0:
        st.success(
            f"Resultado neto registrado: {dinero(resumen_casa['resultado_neto'])}. "
            f"Total retirado: {dinero(resumen_casa['total_retirado'])}."
        )
    st.subheader("Condiciones configuradas de la casa")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rollover depósito", f"x{float(casa['rollover_deposito']):.2f}")
    c2.metric("Rollover bono", f"x{float(casa['rollover_bono']):.2f}")
    c3.metric("Cuota mínima", f"{float(casa['cuota_minima_rollover']):.2f}")
    c4.metric("Retiro mínimo", dinero(casa["minimo_retiro"]))
    sugerencia = analitica.recomendar_recarga_bitacora()
    proteccion = analitica.evaluar_proteccion_perdidas(casa["id"])
    if sugerencia["sugerida"] <= 0:
        st.error(sugerencia["mensaje"])
    else:
        st.warning(
            f"Recarga sugerida: {dinero(sugerencia['sugerida'])}; máximo recomendado: "
            f"{dinero(sugerencia['maxima'])}. {sugerencia['mensaje']}"
        )
    with st.form("form_recarga", clear_on_submit=True):
        st.markdown(f"**La recarga se registrará únicamente en: {casa['nombre_casa']} ({casa['id']})**")
        monto_deposito = st.number_input("Monto depositado", min_value=0.0, step=5.0, format="%.2f")
        monto_bono = st.number_input("Bono recibido", min_value=0.0, step=5.0, format="%.2f")
        rollover_estimado = (
            monto_deposito * float(casa["rollover_deposito"])
            + monto_bono * float(casa["rollover_bono"])
        )
        st.info(f"Esta operación agregará {dinero(rollover_estimado)} de rollover pendiente.")
        acepta_riesgo = st.checkbox(
            "Entiendo que esta recarga no recupera pérdidas anteriores y que puedo perder el monto completo",
        )
        if proteccion["bloqueada"]:
            st.error(proteccion["mensaje"])
        elif proteccion["requiere_confirmacion"]:
            st.warning(
                f"Pérdida registrada en esta casa: {dinero(proteccion['perdida_casa'])}. "
                "No es una cantidad pendiente por recuperar."
            )
        guardar_recarga = st.form_submit_button("Guardar recarga")
    if guardar_recarga:
        if not acepta_riesgo:
            st.error("Debes confirmar que comprendes el riesgo antes de registrar la recarga.")
        else:
            try:
                registro = registrar_recarga_bitacora(casa["id"], monto_deposito, monto_bono)
                guardar_mensaje_y_limpiar(
                    f"Recarga registrada en {casa['nombre_casa']} ({casa['id']}). "
                    f"Depósito: {dinero(registro['deposito'])}; "
                    f"bono: {dinero(registro['bono'])}; rollover: {dinero(registro['rollover_generado'])}.",
                    ("casa_recarga",),
                )
            except ValueError as exc:
                st.error(str(exc))
