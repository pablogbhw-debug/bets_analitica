from datetime import date

import streamlit as st

from controllers import analitica_apuesta as analitica
from controllers.transacciones import registrar_apuesta_desde_formulario
from views.componentes import dinero, guardar_mensaje_y_limpiar, selector_casa


def mostrar(casas):
    st.header("Registrar una apuesta")
    casa = selector_casa(casas, "casa_apuesta")
    recomendacion = analitica.recomendar_monto_bitacora(casa["id"])
    saldo_para_jugar = sum(float(casa[campo]) for campo in
                           ("saldo_deposito", "saldo_bono", "saldo_retirable"))
    st.subheader("Saldo y recomendación antes de apostar")
    c1, c2, c3 = st.columns(3)
    c1.metric("Saldo para jugar", dinero(saldo_para_jugar))
    c2.metric("Máximo recomendado", dinero(recomendacion["monto"]))
    c3.metric("Riesgo actual", recomendacion["nivel_riesgo"])
    if saldo_para_jugar <= 0:
        st.error(recomendacion["mensaje"])
    else:
        st.info(f"Máximo sugerido: {dinero(recomendacion['monto'])}. {recomendacion['mensaje']}")
    st.subheader("Cotejar retorno antes de guardar")
    col1, col2 = st.columns(2)
    monto = col1.number_input(
        "Monto apostado", min_value=1.0, step=1.0, format="%.2f", key="monto_simulador"
    )
    cuota = col2.number_input(
        "Cuota decimal", min_value=1.01, value=1.50, step=0.05, key="cuota_simulador"
    )
    origen = st.radio(
        "Origen", ["SALDO", "BONO"], horizontal=True, key="origen_simulador"
    )
    simulacion = analitica.calcular_retorno_potencial(monto, cuota, origen)
    cotejo_saldo = analitica.verificar_saldo_para_apuesta(casa["id"], origen, monto)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Retorno total teórico", dinero(simulacion["retorno_total"]))
    c2.metric("Ganancia neta", dinero(simulacion["ganancia_neta"]))
    c3.metric("Retirable estimado", dinero(simulacion["retirable_estimado"]))
    c4.metric("Pérdida si falla", dinero(simulacion["perdida_maxima"]))
    st.caption(
        "Fórmula: retorno total = monto × cuota; ganancia neta = monto × (cuota − 1). "
        "Compara estos valores con los que muestra la casa antes de guardar."
    )
    if origen == "BONO":
        st.warning(
            "Con bono, la bitácora considera retirable solo la ganancia neta; "
            "el importe promocional apostado no se convierte en efectivo."
        )
    if cotejo_saldo["suficiente"]:
        st.success(cotejo_saldo["mensaje"])
    else:
        st.error(cotejo_saldo["mensaje"])
        st.caption(
            f"Movimientos registrados en {casa['nombre_casa']}: recargas "
            f"{dinero(cotejo_saldo['total_recargado'])}, bonos "
            f"{dinero(cotejo_saldo['total_bonos'])} y retiros "
            f"{dinero(cotejo_saldo['total_retirado'])}."
        )
    deportes = [texto.strip() for texto in casa["deportes"].split(",") if texto.strip()]
    with st.form("form_apuesta", clear_on_submit=True):
        deporte = st.selectbox("Deporte", deportes or ["Otro"])
        liga = st.text_input("Liga o torneo")
        evento = st.text_input("Evento", placeholder="Equipo A vs Equipo B")
        detalle_apuesta = st.text_area(
            "Detalle de la apuesta",
            placeholder="Ejemplo: combinada de goles, córners y tarjetas; cuota total 3.50",
        )
        fecha_evento = st.date_input("Fecha", max_value=date.today())
        resultado_apuesta = st.radio(
            "Estado inicial", ["PENDIENTE", "GANADA", "PERDIDA", "ANULADA"], horizontal=True
        )
        guardar = st.form_submit_button(
            "Guardar en la bitácora", disabled=not cotejo_saldo["suficiente"]
        )
    if guardar:
        try:
            apuesta_id = registrar_apuesta_desde_formulario(
                casa["id"], monto, origen, cuota, deporte, liga, evento,
                "BITACORA", detalle_apuesta, fecha_evento, resultado_apuesta,
            )
            avisos = []
            if monto > recomendacion["monto"]:
                avisos.append("Superó el máximo recomendado.")
            if not cotejo_saldo["suficiente"]:
                avisos.append("Quedó sin conciliación completa; revisa recargas, bonos y retiros.")
            if resultado_apuesta == "PENDIENTE":
                mensaje_guardado = (f"Apuesta #{apuesta_id} registrada como pendiente. "
                                    "Ya aparece como capital en riesgo.")
            else:
                mensaje_guardado = f"Apuesta #{apuesta_id} registrada correctamente."
            if avisos:
                mensaje_guardado += " " + " ".join(avisos)
            guardar_mensaje_y_limpiar(
                mensaje_guardado,
                ("casa_apuesta", "monto_simulador", "cuota_simulador", "origen_simulador"),
            )
        except ValueError as exc:
            st.error(str(exc))
