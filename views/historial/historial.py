import pandas as pd
import streamlit as st

from controllers.transacciones import (
    editar_apuesta_bitacora,
    eliminar_apuesta_bitacora,
    fecha_utc_a_local,
    obtener_apuestas,
    obtener_historial_completo,
)
from views.componentes import tabla_financiera


def mostrar(casas):
    st.header("Historial de la bitácora")
    apuestas = obtener_apuestas()
    movimientos = obtener_historial_completo()
    retiros = [m for m in movimientos if m["tipo_movimiento"] == "RETIRO"]
    recargas = [m for m in movimientos if m["tipo_movimiento"] in {"RECARGA", "BONO"}]
    for movimiento in movimientos:
        movimiento["fecha"] = fecha_utc_a_local(movimiento.get("fecha"))
    tab1, tab2, tab3 = st.tabs(["Apuestas", "Recargas y bonos", "Retiros"])
    with tab1:
        if apuestas:
            tabla_apuestas = pd.DataFrame(apuestas).rename(
                columns={"seleccion": "detalle_apuesta"}
            )
            tabla_apuestas["tipo_saldo"] = tabla_apuestas["tipo_saldo"].replace(
                {"DEPOSITO": "SALDO", "RETIRABLE": "SALDO"}
            )
            tabla_apuestas.insert(0, "seleccionar", False)
            columnas_visibles = [
                "seleccionar", "id", "fecha_evento", "nombre_casa", "deporte", "evento",
                "detalle_apuesta", "monto", "cuota", "tipo_saldo", "estado", "retorno",
            ]
            st.caption("Marca una sola fila y luego elige Editar o Eliminar.")
            tabla_editada = st.data_editor(
                tabla_financiera(tabla_apuestas[columnas_visibles]),
                column_config={
                    "seleccionar": st.column_config.CheckboxColumn("Seleccionar", default=False),
                    "id": st.column_config.NumberColumn("ID", format="#%d"),
                    "fecha_evento": "Fecha",
                    "nombre_casa": "Casa",
                    "detalle_apuesta": "Detalle",
                    "tipo_saldo": "Saldo",
                    "monto": st.column_config.NumberColumn("Monto", format="S/ %.2f"),
                    "cuota": st.column_config.NumberColumn("Cuota", format="%.2f"),
                    "retorno": st.column_config.NumberColumn("Retorno", format="S/ %.2f"),
                },
                disabled=[c for c in columnas_visibles if c != "seleccionar"],
                hide_index=True,
                width="stretch",
                key="editor_historial_apuestas",
            )
            seleccionadas = tabla_editada[tabla_editada["seleccionar"]]
            seleccion_valida = len(seleccionadas) == 1
            if not seleccion_valida:
                if len(seleccionadas) > 1:
                    st.warning("Selecciona solamente una apuesta.")
                else:
                    st.info("Selecciona una apuesta para habilitar las acciones.")
                st.session_state["accion_historial"] = None

            apuesta_id = int(seleccionadas.iloc[0]["id"]) if seleccion_valida else apuestas[0]["id"]
            apuesta_editar = next(a for a in apuestas if a["id"] == apuesta_id)
            boton_editar, boton_eliminar, _ = st.columns([1, 1, 4])
            if boton_editar.button("Editar seleccionada", width="stretch", disabled=not seleccion_valida):
                st.session_state["accion_historial"] = "editar"
                st.session_state["apuesta_accion_id"] = apuesta_id
            if boton_eliminar.button("Eliminar seleccionada", type="primary", width="stretch",
                                     disabled=not seleccion_valida):
                st.session_state["accion_historial"] = "eliminar"
                st.session_state["apuesta_accion_id"] = apuesta_id

            accion = (st.session_state.get("accion_historial")
                      if st.session_state.get("apuesta_accion_id") == apuesta_id else None)
            if accion == "editar":
                st.info(f"Editando la apuesta #{apuesta_editar['id']}.")
            elif accion == "eliminar":
                st.warning(f"Preparando la eliminación de la apuesta #{apuesta_editar['id']}.")
            with st.form("form_editar_apuesta_historial"):
                col1, col2 = st.columns(2)
                deporte = col1.text_input("Deporte", value=apuesta_editar["deporte"])
                liga = col2.text_input("Liga", value=apuesta_editar["liga"])
                evento = st.text_input("Evento", value=apuesta_editar["evento"])
                mercado = col1.text_input("Mercado", value=apuesta_editar["mercado"])
                detalle = col2.text_input("Detalle", value=apuesta_editar["seleccion"])
                fecha_evento = col1.date_input(
                    "Fecha del evento", value=pd.to_datetime(apuesta_editar["fecha_evento"]).date()
                )
                cuota = col2.number_input(
                    "Cuota", min_value=1.01, value=float(apuesta_editar["cuota"]), step=0.01
                )
                tipos = ["SALDO", "BONO"]
                tipo_actual = "BONO" if apuesta_editar["tipo_saldo"] == "BONO" else "SALDO"
                tipo_saldo = st.selectbox(
                    "Tipo de saldo", tipos, index=tipos.index(tipo_actual)
                )
                guardar_edicion = st.form_submit_button(
                    "Guardar cambios", disabled=not seleccion_valida or accion != "editar"
                )
            if guardar_edicion:
                try:
                    editar_apuesta_bitacora(
                        apuesta_editar["id"], deporte, liga, evento, mercado, detalle,
                        fecha_evento, cuota, tipo_saldo,
                    )
                    st.session_state["mensaje_exito"] = f"Apuesta #{apuesta_editar['id']} actualizada."
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

            with st.form("form_eliminar_apuesta_historial"):
                confirmar = st.checkbox(
                    "Confirmo que deseo eliminar esta apuesta y revertir su efecto financiero"
                )
                eliminar_registro = st.form_submit_button(
                    "Eliminar apuesta", type="primary",
                    disabled=not seleccion_valida or accion != "eliminar",
                )
            if eliminar_registro:
                if not confirmar:
                    st.error("Debes confirmar la eliminación.")
                else:
                    try:
                        eliminar_apuesta_bitacora(apuesta_editar["id"])
                        st.session_state["mensaje_exito"] = f"Apuesta #{apuesta_editar['id']} eliminada."
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
        else:
            st.info("Todavía no hay apuestas registradas.")
    with tab2:
        if recargas:
            tabla_recargas = pd.DataFrame(recargas)[
                ["fecha", "nombre_casa", "tipo_movimiento", "monto"]
            ]
            st.dataframe(tabla_financiera(tabla_recargas),
                         width="stretch", hide_index=True)
        else:
            st.info("Todavía no hay recargas registradas.")
    with tab3:
        if retiros:
            tabla_retiros = pd.DataFrame(retiros)[["fecha", "nombre_casa", "monto"]]
            st.dataframe(tabla_financiera(tabla_retiros),
                         width="stretch", hide_index=True)
        else:
            st.info("Todavía no hay retiros registrados.")
