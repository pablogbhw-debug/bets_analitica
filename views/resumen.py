import pandas as pd
import streamlit as st

from controllers.transacciones import (
    diagnosticar_ciclo,
    obtener_apuestas,
    recalcular_rollover_casa,
    retiro_permitido,
)
from controllers import analitica_resumen as analitica
from controllers.analitica_apuesta import recomendar_monto_bitacora
from controllers.analitica_pendientes import resumen_apuestas_pendientes
from controllers.analitica_recarga import evaluar_proteccion_perdidas, recomendar_recarga_bitacora
from views.componentes import dinero, tabla_financiera


def mostrar(casas):
    """Muestra la vista de resumen y gestiona sus interacciones."""
    st.header("Resumen financiero y de riesgo")
    st.caption("Primero revisa tu balance, el nivel de riesgo y la posibilidad real de retirar.")
    df, resultado = analitica.analizar_rendimiento_psicologico()
    auditoria = analitica.auditar_conciliacion_historial()
    recarga = recomendar_recarga_bitacora()
    proteccion_global = evaluar_proteccion_perdidas()
    if isinstance(resultado, dict):
        icono_riesgo = {"BAJO": "🟢", "MEDIO": "🟡", "ALTO": "🟠", "CRÍTICO": "🔴"}.get(
            resultado["nivel_riesgo"], "⚪"
        )
        with st.container(border=True):
            st.markdown("### Resumen ejecutivo")
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Balance registrado", dinero(resultado["balance_neto_real"]))
            r2.metric("Capital propio actual", dinero(resultado["capital_propio_actual"]))
            r3.metric("Capital libre para retirar", dinero(resultado["capital_libre"]))
            r4.metric("Riesgo", f"{icono_riesgo} {resultado['nivel_riesgo']}")
    if proteccion_global["bloqueada"]:
        st.error(
            "🛑 RECOMENDACIÓN DE PAUSA: el historial presenta pérdidas o patrones de riesgo considerables. "
            "No interpretes el saldo, los bonos ni las analíticas como una posibilidad de recuperación."
        )
    with st.container(border=True):
        st.markdown("### Recomendación principal")
        c1, c2, c3 = st.columns(3)
        c1.metric("Recarga sugerida", dinero(recarga["sugerida"]))
        c2.metric("Máximo de recarga", dinero(recarga["maxima"]))
        c3.metric("Riesgo para recargar", recarga["nivel"])
        if recarga["sugerida"] <= 0:
            st.error(recarga["mensaje"])
        else:
            st.warning(recarga["mensaje"])
    st.subheader("Indicadores generales")
    if df is None:
        st.info(resultado)
    else:
        tab_rentabilidad, tab_comportamiento, tab_capital = st.tabs([
            "Rentabilidad", "Comportamiento", "Capital"
        ])
        with tab_rentabilidad:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Balance registrado", dinero(resultado["balance_neto_real"]))
                c2.metric("Resultado de apuestas", dinero(resultado["resultado_apuestas"]))
                c3.metric("Total apostado", dinero(resultado["total_apostado"]))
                c4.metric("ROI", f"{resultado['roi']:.2f}%")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Ganadas", resultado["apuestas_ganadas"])
                c2.metric("Perdidas", resultado["apuestas_perdidas"])
                c3.metric("Acierto", f"{resultado['tasa_acierto']:.2f}%")
                c4.metric("Promedio por jugada", dinero(resultado["ticket_promedio"]))
        with tab_comportamiento:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Nivel de riesgo", resultado["nivel_riesgo"])
                c2.metric("Máxima caída", dinero(resultado["peor_caida"]))
                c3.metric("Racha de pérdidas", resultado["racha_perdidas"])
                c4.metric("Aumentos tras perder", resultado["persecuciones"])
                st.caption("Estos indicadores describen patrones del historial; no predicen resultados futuros.")
        with tab_capital:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total recargado", dinero(resultado["total_depositado"]))
                c2.metric("Capital propio actual", dinero(resultado["capital_propio_actual"]))
                c3.metric("Bonos actuales", dinero(resultado["saldo_bonos"]))
                c4.metric("Total retirado", dinero(resultado["total_retirado"]))
                st.caption(
                    "Los bonos se muestran separados para que no aumenten artificialmente el dinero propio."
                )

        if resultado["nivel_riesgo"] in {"ALTO", "CRÍTICO"}:
            st.error(resultado["dictamen_ia"])
        elif resultado["nivel_riesgo"] == "MEDIO":
            st.warning(resultado["dictamen_ia"])
        else:
            st.info(resultado["dictamen_ia"])

        for alerta in resultado["mensajes_riesgo"]:
            mensaje = f"{alerta['codigo']}: {alerta['mensaje']}"
            if alerta["nivel"] == "ALTO":
                st.error(mensaje)
            else:
                st.warning(mensaje)

        st.subheader("Evolución de ganancias y pérdidas")
        st.line_chart(df, x="fecha", y="Balance_Acumulado")
        st.subheader("Resultado por casa")
        st.caption("El rendimiento anterior es descriptivo y no garantiza resultados futuros.")
        st.dataframe(tabla_financiera(resultado["por_casa"]), width="stretch", hide_index=True)
        if not auditoria["confiable_saldos"]:
            st.warning(auditoria["mensaje"])
            with st.expander("Ver apuestas sin conciliación completa"):
                st.dataframe(tabla_financiera(pd.DataFrame(auditoria["apuestas"])),
                             width="stretch", hide_index=True)
    st.subheader("Referencia para la próxima jugada")
    recomendaciones = []
    for casa in casas:
        recomendacion = recomendar_monto_bitacora(casa["id"])
        recomendaciones.append({
            "Casa": casa["nombre_casa"],
            "Máximo sugerido": dinero(recomendacion["monto"]),
            "Riesgo": recomendacion["nivel_riesgo"],
            "Recomendación": recomendacion["mensaje"],
        })
    st.dataframe(pd.DataFrame(recomendaciones), width="stretch", hide_index=True)
    resumen_pendientes = resumen_apuestas_pendientes()
    st.subheader("⏳ Exposición pendiente")
    c1, c2, c3 = st.columns(3)
    c1.metric("Apuestas pendientes", resumen_pendientes["cantidad"])
    c2.metric("Capital actualmente en riesgo", dinero(resumen_pendientes["capital_en_riesgo"]))
    c3.metric("Ganancia potencial", dinero(resumen_pendientes["ganancia_potencial"]))
    pendientes_dashboard = obtener_apuestas("PENDIENTE")
    if pendientes_dashboard:
        st.warning(
            "Estos importes todavía no son ganancias ni pérdidas realizadas. "
            "Evalúa la exposición total antes de registrar otra apuesta."
        )
        tabla_pendientes = pd.DataFrame(pendientes_dashboard).rename(
            columns={"seleccion": "detalle_apuesta"}
        )
        columnas = ["id", "nombre_casa", "evento", "detalle_apuesta", "monto", "cuota", "fecha_evento"]
        st.dataframe(tabla_financiera(tabla_pendientes[columnas]), width="stretch", hide_index=True)
    st.subheader("Disponibilidad de retiro por casa")
    st.caption("Disponibilidad calculada con los saldos registrados en cada billetera.")
    if not auditoria["confiable_saldos"]:
        st.warning(
            "La disponibilidad siguiente es contablemente estimada: existen apuestas sin "
            "conciliación completa. Compárala con el saldo que muestra cada casa."
        )
    columnas_casas = st.columns(min(3, max(1, len(casas))))
    for indice, casa in enumerate(casas):
        desglose_rollover = recalcular_rollover_casa(casa["id"])
        casa["rollover_pendiente"] = desglose_rollover["pendiente"]
        diagnostico = diagnosticar_ciclo(casa)
        disponible = retiro_permitido(casa)
        faltante = max(0.0, float(casa["minimo_retiro"]) - float(casa["saldo_retirable"]))
        with columnas_casas[indice % len(columnas_casas)]:
            with st.container(border=True):
                st.markdown(f"### {casa['nombre_casa']}")
                if disponible:
                    st.success("✅ LISTO PARA RETIRAR")
                else:
                    st.error("⛔ RETIRO NO DISPONIBLE")
                st.metric("Saldo retirable", dinero(casa["saldo_retirable"]))
                progreso_retiro = (min(1.0, float(casa["saldo_retirable"]) /
                                      float(casa["minimo_retiro"]))
                                   if float(casa["minimo_retiro"]) > 0 else 1.0)
                st.progress(
                    progreso_retiro,
                    text=f"{progreso_retiro:.0%} del mínimo de retiro",
                )
                col_minimo, col_faltante = st.columns(2)
                col_minimo.metric("Mínimo", dinero(casa["minimo_retiro"]))
                col_faltante.metric("Falta", dinero(faltante))
                col_dep, col_bono = st.columns(2)
                col_dep.metric("Depósito", dinero(casa["saldo_deposito"]))
                col_bono.metric("Bono", dinero(casa["saldo_bono"]))
                st.metric("Rollover pendiente", dinero(casa["rollover_pendiente"]))
                st.caption(
                    f"Rollover generado: {dinero(desglose_rollover['generado'])}; "
                    f"liberado por apuestas existentes: {dinero(desglose_rollover['liberado'])}."
                )
                if disponible:
                    st.info("Prioridad sugerida: retirar y proteger el saldo antes de volver a exponerlo.")
                else:
                    st.warning(diagnostico["recomendacion"])
    apuestas_recientes = obtener_apuestas()[:10]
    if apuestas_recientes:
        st.subheader("Últimas apuestas registradas")
        tabla_recientes = pd.DataFrame(apuestas_recientes).rename(
            columns={"seleccion": "detalle_apuesta"}
        )
        columnas = ["fecha_evento", "nombre_casa", "evento", "detalle_apuesta",
                    "monto", "cuota", "estado", "retorno"]
        st.dataframe(tabla_financiera(tabla_recientes[columnas]), width="stretch", hide_index=True)
