"""Analítica correspondiente a este caso de uso."""

import numpy as np
from models.database import obtener_apuestas, obtener_configuracion, obtener_resumen_casas
from controllers.analitica_comun import _apuestas_liquidadas
from controllers.analitica_resumen import analizar_rendimiento_psicologico
from controllers.analitica_recarga import resumen_financiero_casa

def calcular_retorno_potencial(monto, cuota, tipo_saldo="DEPOSITO"):
    """Calcula el pago mostrado por la casa y la utilidad neta antes de registrar."""
    monto, cuota = float(monto), float(cuota)
    tipo_saldo = tipo_saldo.upper().strip()
    if monto <= 0 or cuota <= 1:
        raise ValueError("El monto debe ser positivo y la cuota mayor que 1.00.")
    retorno_total = monto * cuota
    ganancia_neta = monto * (cuota - 1)
    retirable_estimado = ganancia_neta if tipo_saldo == "BONO" else retorno_total
    return {
        "retorno_total": round(retorno_total, 2),
        "ganancia_neta": round(ganancia_neta, 2),
        "retirable_estimado": round(retirable_estimado, 2),
        "perdida_maxima": round(monto, 2),
    }

def recomendar_monto_maximo(casa):
    """Referencia conservadora según saldo expuesto y riesgo, nunca una predicción."""
    saldo_expuesto = float(casa["saldo_deposito"]) + float(casa["saldo_bono"])
    if saldo_expuesto <= 0:
        return {"monto": 0.0, "porcentaje": 0.0, "nivel_riesgo": "SIN SALDO",
                "mensaje": "No hay depósito o bono disponible; no se recomienda reexponer saldo retirable."}
    _, resultado = analizar_rendimiento_psicologico()
    nivel = resultado.get("nivel_riesgo", "BAJO") if isinstance(resultado, dict) else "BAJO"
    porcentajes = {"BAJO": 0.05, "MEDIO": 0.03, "ALTO": 0.02, "CRÍTICO": 0.01}
    porcentaje = porcentajes[nivel]
    referencia_personal = float(obtener_configuracion()["limite_apuesta_individual"])
    monto = min(saldo_expuesto, referencia_personal, max(1.0, saldo_expuesto * porcentaje))
    mensaje = (f"Referencia máxima: {porcentaje:.0%} del depósito y bono por riesgo {nivel}. "
               "No estima la probabilidad de ganar.")
    if nivel in {"ALTO", "CRÍTICO"}:
        mensaje += " La recomendación principal es no aumentar el monto para recuperar pérdidas."
    return {"monto": round(monto, 2), "porcentaje": porcentaje * 100,
            "nivel_riesgo": nivel, "mensaje": mensaje}

def recomendar_monto_bitacora(id_casa=None):
    """Sugiere no escalar el stake usando el promedio histórico como referencia."""
    df = _apuestas_liquidadas()
    referencia_personal = float(obtener_configuracion()["limite_apuesta_individual"])
    casa_seleccionada = None
    if id_casa:
        casa_seleccionada = next((c for c in obtener_resumen_casas() if c["id"] == id_casa), None)
    if id_casa and not df.empty:
        nombre = casa_seleccionada["nombre_casa"] if casa_seleccionada else None
        df = df[df["nombre_casa"] == nombre]
    _, metricas = analizar_rendimiento_psicologico()
    nivel = metricas.get("nivel_riesgo", "BAJO") if isinstance(metricas, dict) else "BAJO"
    if nivel in {"ALTO", "CRÍTICO"}:
        return {"monto": 0.0, "nivel_riesgo": nivel,
                "mensaje": ("No se recomienda una nueva apuesta: el riesgo actual exige una pausa. "
                            "Las pérdidas anteriores no son una cantidad pendiente por recuperar.")}
    saldo_disponible = 0.0
    if casa_seleccionada:
        saldo_disponible = sum(float(casa_seleccionada[campo]) for campo in
                               ("saldo_deposito", "saldo_bono", "saldo_retirable"))
        if saldo_disponible <= 0:
            return {"monto": 0.0, "nivel_riesgo": nivel,
                    "mensaje": "No hay saldo registrado para jugar en esta casa. Registra una recarga antes de exponer capital."}
    if df.empty:
        monto_inicial = min(referencia_personal, saldo_disponible) if casa_seleccionada else referencia_personal
        return {"monto": round(monto_inicial, 2), "nivel_riesgo": nivel,
                "mensaje": "Sin historial suficiente: usa tu referencia personal y no la incrementes por una corazonada."}
    promedio = float(np.mean(df["monto"].to_numpy(dtype=float)))
    factores = {"BAJO": 1.0, "MEDIO": 0.75, "ALTO": 0.50, "CRÍTICO": 0.25}
    limites = [referencia_personal, max(1.0, promedio * factores[nivel])]
    if casa_seleccionada:
        limites.append(saldo_disponible)
    monto = min(limites)
    return {"monto": round(monto, 2), "nivel_riesgo": nivel,
            "mensaje": (f"Máximo sugerido según el promedio histórico y riesgo {nivel}. "
                        "No aumentes el monto para recuperar una pérdida anterior.")}

def verificar_saldo_para_apuesta(id_casa, origen, monto):
    """Coteja una apuesta con recargas, bonos, retiros y saldos de su casa."""
    casa = next((c for c in obtener_resumen_casas() if c["id"] == id_casa), None)
    if not casa:
        raise ValueError("La casa seleccionada no existe.")
    origen = str(origen).upper().strip()
    monto = float(monto)
    if origen not in {"SALDO", "BONO"} or monto <= 0:
        raise ValueError("El origen y el monto de la apuesta no son válidos.")
    resumen = resumen_financiero_casa(id_casa)
    pendientes = [a for a in obtener_apuestas("PENDIENTE") if a["id_casa"] == id_casa]
    reservado = float(np.sum([
        float(a["monto"]) for a in pendientes
        if (a["tipo_saldo"] == "BONO") == (origen == "BONO")
    ]))
    saldo_billetera = (float(casa["saldo_bono"]) if origen == "BONO" else
                       float(casa["saldo_deposito"]) + float(casa["saldo_retirable"]))
    disponible = max(0.0, saldo_billetera - reservado)
    faltante = max(0.0, monto - disponible)
    suficiente = faltante <= 0.001
    mensaje = (f"Saldo {origen.lower()} suficiente: S/ {disponible:.2f} disponibles para "
               f"una apuesta de S/ {monto:.2f}.") if suficiente else (
        f"Saldo {origen.lower()} insuficiente: hay S/ {disponible:.2f} y la apuesta es de "
        f"S/ {monto:.2f}. Faltan S/ {faltante:.2f}. Verifica si olvidaste registrar una "
        "recarga, un bono o un retiro antes de guardar."
    )
    return {
        "suficiente": suficiente,
        "disponible": round(disponible, 2),
        "reservado_pendientes": round(reservado, 2),
        "faltante": round(faltante, 2),
        "total_recargado": resumen["total_recargado"],
        "total_bonos": resumen["total_bonos"],
        "total_retirado": resumen["total_retirado"],
        "mensaje": mensaje,
    }
