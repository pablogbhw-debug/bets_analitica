import streamlit as st

from controllers.transacciones import (
    actualizar_casa,
    eliminar_casa_apuesta,
    registrar_casa_apuesta,
    reiniciar_datos_conservando_casas,
)
from views.componentes import guardar_mensaje_y_limpiar, selector_casa


def mostrar(casas):
    st.header("Configurar casas de apuestas")
    tab1, tab2, tab3, tab4 = st.tabs([
        "Editar casa", "Agregar casa", "Eliminar casa", "Reiniciar datos"
    ])
    with tab1:
        casa = selector_casa(
            casas, "casa_editar", "Casa que deseas editar", detener_si_vacia=False
        )
        if casa is not None:
            with st.form("form_editar_casa", clear_on_submit=True):
                st.text_input("Código", value=casa["id"], disabled=True)
                st.text_input("Nombre", value=casa["nombre_casa"], disabled=True)
                minimo = st.number_input(
                    "Retiro mínimo", min_value=0.0, value=float(casa["minimo_retiro"]),
                    step=5.0, format="%.2f"
                )
                rollover_deposito = st.number_input(
                    "Rollover del depósito", min_value=0.0,
                    value=float(casa["rollover_deposito"]), step=0.5
                )
                rollover_bono = st.number_input(
                    "Rollover del bono", min_value=0.0,
                    value=float(casa["rollover_bono"]), step=0.5
                )
                cuota_minima = st.number_input(
                    "Cuota mínima para liberar rollover", min_value=1.0,
                    value=float(casa["cuota_minima_rollover"]), step=0.05
                )
                deportes = st.text_input(
                    "Deportes separados por coma", value=casa["deportes"]
                )
                guardar_casa = st.form_submit_button("Guardar configuración")
            if guardar_casa:
                try:
                    actualizar_casa(
                        casa["id"], minimo, rollover_deposito, rollover_bono,
                        cuota_minima, deportes,
                    )
                    guardar_mensaje_y_limpiar(
                        "Configuración actualizada correctamente.", ("casa_editar",)
                    )
                except ValueError as exc:
                    st.error(str(exc))
    with tab2:
        with st.form("form_agregar_casa", clear_on_submit=True):
            codigo_nuevo = st.text_input("Código corto", placeholder="NUEVA_CASA")
            nombre_nuevo = st.text_input("Nombre visible")
            minimo_nuevo = st.number_input(
                "Retiro mínimo inicial", min_value=0.0, value=50.0, step=5.0, format="%.2f"
            )
            rollover_dep_nuevo = st.number_input("Rollover depósito inicial", min_value=0.0, value=1.0, step=0.5)
            rollover_bono_nuevo = st.number_input("Rollover bono inicial", min_value=0.0, value=1.0, step=0.5)
            cuota_nueva = st.number_input("Cuota mínima inicial", min_value=1.0, value=1.01, step=0.05)
            deportes_nuevos = st.text_input(
                "Deportes", value="Fútbol,Baloncesto,Tenis"
            )
            agregar_casa = st.form_submit_button("Agregar casa")
        if agregar_casa:
            try:
                creada = registrar_casa_apuesta(
                    codigo_nuevo, nombre_nuevo, minimo_nuevo, rollover_dep_nuevo,
                    rollover_bono_nuevo, cuota_nueva, deportes_nuevos,
                )
                if creada:
                    guardar_mensaje_y_limpiar(
                        "Casa agregada correctamente; ya está disponible en los selectores."
                    )
                else:
                    st.warning("Ya existe una casa con ese código.")
            except ValueError as exc:
                st.error(str(exc))
    with tab3:
        casa_eliminar = selector_casa(
            casas, "casa_eliminar", "Casa que deseas eliminar", detener_si_vacia=False
        )
        st.warning(
            "Solo se puede eliminar una casa sin apuestas, recargas, retiros, saldos ni rollover."
        )
        if casa_eliminar is not None:
            with st.form("form_eliminar_casa"):
                confirmacion = st.text_input(
                    f"Escribe {casa_eliminar['id']} para confirmar"
                )
                eliminar = st.form_submit_button("Eliminar casa")
            if eliminar:
                if confirmacion.strip().upper() != casa_eliminar["id"]:
                    st.error("El código de confirmación no coincide.")
                else:
                    try:
                        eliminar_casa_apuesta(casa_eliminar["id"])
                        st.success("Casa eliminada correctamente. Actualiza la página para refrescar los selectores.")
                    except ValueError as exc:
                        st.error(str(exc))
    with tab4:
        st.error(
            "ATENCIÓN: estás a punto de borrar todos tus datos para volver a comenzar. "
            "Se eliminarán apuestas, recargas, bonos, retiros e historial. "
            "Las casas y sus condiciones se conservarán. Esta acción no se puede deshacer."
        )
        with st.form("form_reiniciar_datos"):
            acepta_borrado = st.checkbox(
                "Entiendo que perderé definitivamente todos los registros financieros"
            )
            texto_borrado = st.text_input("Escribe BORRAR TODO para confirmar")
            reiniciar = st.form_submit_button("Borrar datos y volver a comenzar")
        if reiniciar:
            if not acepta_borrado:
                st.error("Debes aceptar la advertencia antes de continuar.")
            elif texto_borrado.strip().upper() != "BORRAR TODO":
                st.error("El texto de confirmación no coincide. Escribe BORRAR TODO.")
            else:
                resumen_borrado = reiniciar_datos_conservando_casas()
                st.success(
                    "Datos eliminados correctamente. Puedes volver a comenzar. "
                    f"Se borraron {resumen_borrado['apuestas_eliminadas']} apuestas y "
                    f"{resumen_borrado['movimientos_eliminados']} movimientos; las casas se conservaron."
                )
