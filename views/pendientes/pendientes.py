import streamlit as st

from controllers import analitica_pendientes as analitica
from controllers.transacciones import eliminar_apuesta_pendiente, obtener_apuestas, resolver_apuesta
from views.componentes import dinero, guardar_mensaje_y_limpiar


def mostrar(casas):
    st.header("Gestionar apuestas pendientes")
    pendientes = obtener_apuestas("PENDIENTE")
    if not pendientes:
        st.info("No hay apuestas pendientes.")
    else:
        opciones = {
            f"#{a['id']} · {a['nombre_casa']} · {a['evento']} · {dinero(a['monto'])} @ {a['cuota']}": a
            for a in pendientes
        }
        apuesta_pendiente = opciones[st.selectbox("Apuesta pendiente", list(opciones))]
        simulacion = analitica.calcular_retorno_potencial(
            apuesta_pendiente["monto"], apuesta_pendiente["cuota"], apuesta_pendiente["tipo_saldo"]
        )
        st.write(f"**Detalle:** {apuesta_pendiente['seleccion']}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Capital en riesgo", dinero(apuesta_pendiente["monto"]))
        c2.metric("Retorno potencial", dinero(simulacion["retorno_total"]))
        c3.metric("Ganancia potencial", dinero(simulacion["ganancia_neta"]))
        st.info(
            "Esta apuesta es una simulación pendiente: todavía no ha sido descontada. "
            "El monto se descontará del saldo cuando la completes, excepto si se anula."
        )

        with st.form("form_resolver_pendiente", clear_on_submit=True):
            resultado_final = st.radio(
                "Resultado final", ["GANADA", "PERDIDA", "ANULADA", "CASH_OUT"], horizontal=True
            )
            monto_cashout = st.number_input(
                "Monto recibido por cash out (solo si corresponde)", min_value=0.0,
                step=1.0, format="%.2f"
            )
            confirmar_resultado = st.checkbox("Confirmo que este es el resultado mostrado por la casa")
            resolver = st.form_submit_button("Completar apuesta")
        if resolver:
            if not confirmar_resultado:
                st.error("Confirma el resultado antes de completar la apuesta.")
            elif resultado_final == "CASH_OUT" and monto_cashout <= 0:
                st.error("Ingresa el monto real recibido por cash out.")
            else:
                try:
                    liquidacion = resolver_apuesta(
                        apuesta_pendiente["id"], resultado_final, monto_cashout
                    )
                    if resultado_final == "PERDIDA":
                        mensaje_liquidacion = (
                            f"Apuesta completada como PERDIDA. Se descontaron "
                            f"{dinero(liquidacion['descontado_al_finalizar'])}; saldo actual para jugar: "
                            f"{dinero(liquidacion['saldo_para_jugar'])}."
                        )
                    else:
                        mensaje_liquidacion = (
                            f"Apuesta completada como {resultado_final}. Retorno registrado: "
                            f"{dinero(liquidacion['retorno'])}; saldo actual para jugar: "
                            f"{dinero(liquidacion['saldo_para_jugar'])}."
                        )
                    guardar_mensaje_y_limpiar(mensaje_liquidacion)
                except ValueError as exc:
                    st.error(str(exc))

        st.divider()
        st.error(
            "Eliminar borra esta simulación de la bitácora. Como una pendiente todavía no descuenta saldo, "
            "Usa esta opción solo si el registro fue creado por error."
        )
        with st.form("form_eliminar_pendiente"):
            confirmar_eliminacion = st.text_input("Escribe ELIMINAR para confirmar")
            eliminar_pendiente = st.form_submit_button("Eliminar apuesta pendiente")
        if eliminar_pendiente:
            if confirmar_eliminacion.strip().upper() != "ELIMINAR":
                st.error("El texto de confirmación no coincide.")
            else:
                try:
                    eliminar_apuesta_pendiente(apuesta_pendiente["id"])
                    guardar_mensaje_y_limpiar(
                        "Apuesta pendiente eliminada. El saldo no necesitó modificación."
                    )
                except ValueError as exc:
                    st.error(str(exc))
