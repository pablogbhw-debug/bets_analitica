"""Analítica correspondiente a este caso de uso."""

import numpy as np
from models.database import (
    obtener_apuestas,
    obtener_historial_completo,
    obtener_resumen_casas,
    retiro_permitido,
)
from controllers.analitica_comun import _alerta, _apuestas_liquidadas, _racha_perdidas

UMBRAL_TASA_ALTA = 0.65
UMBRAL_ROI_SEGURO = -0.10
UMBRAL_CONCENTRACION = 0.70

def analizar_rendimiento_psicologico():
    """Analiza resultados financieros y patrones de comportamiento para generar alertas."""
    historial = obtener_historial_completo()
    casas = obtener_resumen_casas()
    df = _apuestas_liquidadas()
    if df.empty:
        return None, "Registra y liquida apuestas para activar el análisis de inversiones."

    # NumPy se usa realmente para sumas, medias, mínimos, máximos y máscaras vectorizadas.
    montos = df["monto"].to_numpy(dtype=float)
    flujos = df["Flujo_Efectivo"].to_numpy(dtype=float)
    ganadas_mask = df["resultado"].eq("GANADA").to_numpy(dtype=bool)
    perdidas_mask = df["resultado"].eq("PERDIDA").to_numpy(dtype=bool)
    balance_acumulado = np.cumsum(flujos)
    maximos_historicos = np.maximum.accumulate(np.maximum(balance_acumulado, 0))
    drawdowns = maximos_historicos - balance_acumulado
    df["Balance_Acumulado"] = balance_acumulado
    df["Drawdown"] = drawdowns
    df["Retorno_Porcentual"] = np.where(montos > 0, flujos / montos * 100, 0)

    total_apostado = float(np.sum(montos))
    resultado_apuestas = float(np.sum(flujos))
    ticket_promedio = float(np.mean(montos))
    peor_resultado = float(np.min(flujos))
    mejor_resultado = float(np.max(flujos))
    drawdown = float(np.max(drawdowns))
    ganadas, perdidas = int(np.sum(ganadas_mask)), int(np.sum(perdidas_mask))
    decisiones_binarias = ganadas + perdidas
    tasa_acierto = ganadas / decisiones_binarias if decisiones_binarias else 0.0
    roi = resultado_apuestas / total_apostado if total_apostado else 0.0
    racha = _racha_perdidas(df["resultado"])

    montos_previos = np.roll(montos, 1)
    perdida_previa = np.roll(perdidas_mask, 1)
    perdida_previa[0] = False
    persecucion_mask = np.logical_and(perdida_previa, montos > montos_previos * 1.25)
    df["Aumento_Tras_Perdida"] = persecucion_mask
    persecuciones = int(np.sum(persecucion_mask))

    total_depositado = float(np.sum([float(x["monto"]) for x in historial
                                     if x["tipo_movimiento"] == "RECARGA"]))
    total_retirado = float(np.sum([float(x["monto"]) for x in historial
                                  if x["tipo_movimiento"] == "RETIRO"]))
    saldo_depositos = float(np.sum([float(c["saldo_deposito"]) for c in casas]))
    saldo_bonos = float(np.sum([float(c["saldo_bono"]) for c in casas]))
    saldo_retirable_total = float(np.sum([float(c["saldo_retirable"]) for c in casas]))
    saldos_actuales = saldo_depositos + saldo_bonos + saldo_retirable_total
    capital_propio_actual = saldo_depositos + saldo_retirable_total
    # Los bonos no son dinero depositado por el usuario y no deben maquillar su balance real.
    patrimonio_neto = capital_propio_actual + total_retirado - total_depositado
    flujo_caja = total_retirado - total_depositado
    capital_restringido = float(np.sum([
        min(float(c["rollover_pendiente"]),
            float(c["saldo_deposito"]) + float(c["saldo_bono"]) + float(c["saldo_retirable"]))
        for c in casas
    ]))
    capital_libre = float(np.sum([float(c["saldo_retirable"]) for c in casas if retiro_permitido(c)]))

    alertas = []
    ilusion = bool(tasa_acierto >= UMBRAL_TASA_ALTA and resultado_apuestas < 0)
    if ilusion:
        alertas.append(_alerta("ILUSION_GANANCIA", "ALTO",
            "Alerta de ilusión: ganas una proporción alta de apuestas, pero el balance neto real es negativo."))
    if roi < UMBRAL_ROI_SEGURO or drawdown >= max(100.0, total_apostado * 0.25):
        alertas.append(_alerta("DRAWDOWN", "ALTO",
            "El ROI y la caída acumulada muestran deterioro del portafolio. No aumentes la siguiente jugada para recuperar."))
    casas_rollover = [c["nombre_casa"] for c in casas if float(c["rollover_pendiente"]) > 0]
    if capital_restringido > 0:
        alertas.append(_alerta("ROLLOVER", "MEDIO",
            f"Capital condicionado por rollover en: {', '.join(casas_rollover)}. No lo consideres dinero libre."))
    if persecuciones:
        alertas.append(_alerta("PERSECUCION", "ALTO",
            f"Se detectaron {persecuciones} aumentos de monto después de perder."))
    if racha >= 3:
        alertas.append(_alerta("RACHA", "ALTO", f"Racha actual de {racha} pérdidas consecutivas."))
    if saldo_bonos > 0 and flujo_caja < 0 and total_retirado < total_depositado:
        alertas.append(_alerta("BONO_CAMUFLA_PERDIDA", "MEDIO",
            "El bono eleva el saldo visible, pero los retiros todavía no recuperan los depósitos."))

    capital_por_casa = np.array([
        float(c["saldo_deposito"]) + float(c["saldo_bono"]) + float(c["saldo_retirable"]) for c in casas
    ])
    concentracion = float(np.max(capital_por_casa) / np.sum(capital_por_casa)) if np.sum(capital_por_casa) else 0.0
    if concentracion >= UMBRAL_CONCENTRACION and len(casas) > 1:
        casa_concentrada = casas[int(np.argmax(capital_por_casa))]["nombre_casa"]
        alertas.append(_alerta("CONCENTRACION", "MEDIO",
            f"{concentracion:.1%} del saldo está concentrado en {casa_concentrada}."))

    puntos = sum(3 if a["nivel"] == "ALTO" else 1 for a in alertas)
    if patrimonio_neto < 0:
        puntos += 2
    nivel = "CRÍTICO" if puntos >= 7 else "ALTO" if puntos >= 4 else "MEDIO" if puntos >= 2 else "BAJO"
    dictamenes = {
        "CRÍTICO": "Las pérdidas y los patrones detectados justifican reducir la exposición y evitar perseguir pérdidas.",
        "ALTO": "No aumentes montos para recuperar. Conserva el límite calculado o reduce la exposición.",
        "MEDIO": "Existen señales de riesgo; interpreta bonos y saldos condicionados con cautela.",
        "BAJO": "No hay señales fuertes en la muestra actual; esto no predice resultados futuros.",
    }

    por_casa = df.groupby("nombre_casa", as_index=False).agg(
        resultado=("Flujo_Efectivo", "sum"), total_apostado=("monto", "sum"),
        monto_conciliado=("monto_conciliado", "sum"),
        apuestas=("monto", "count"),
        ganadas=("resultado", lambda valores: int((valores == "GANADA").sum())),
        perdidas=("resultado", lambda valores: int((valores == "PERDIDA").sum())),
        cashout_neutros=("cashout_neutro", "sum"),
        cashout_perdida=("cashout_perdida", "sum"),
        promedio=("monto", "mean"))
    por_casa["sin_conciliar"] = por_casa["total_apostado"] - por_casa["monto_conciliado"]
    por_casa["roi"] = np.where(por_casa["total_apostado"] > 0,
                               por_casa["resultado"] / por_casa["total_apostado"] * 100, 0)

    return df, {
        "resultado_apuestas": round(resultado_apuestas, 2), "balance_neto_real": round(patrimonio_neto, 2),
        "patrimonio_neto": round(patrimonio_neto, 2), "saldos_actuales": round(saldos_actuales, 2),
        "capital_propio_actual": round(capital_propio_actual, 2), "saldo_bonos": round(saldo_bonos, 2),
        "total_depositado": round(total_depositado, 2), "total_retirado": round(total_retirado, 2),
        "flujo_caja": round(flujo_caja, 2), "total_apostado": round(total_apostado, 2),
        "ticket_promedio": round(ticket_promedio, 2), "peor_resultado": round(peor_resultado, 2),
        "mejor_resultado": round(mejor_resultado, 2), "peor_caida": round(drawdown, 2),
        "tasa_acierto": round(tasa_acierto * 100, 2), "roi": round(roi * 100, 2),
        "racha_perdidas": racha, "persecuciones": persecuciones, "nivel_riesgo": nivel,
        "apuestas_ganadas": ganadas, "apuestas_perdidas": perdidas,
        "capital_restringido": round(capital_restringido, 2), "capital_libre": round(capital_libre, 2),
        "concentracion": round(concentracion * 100, 2), "sesgo_ilusion": ilusion,
        "dictamen_ia": dictamenes[nivel], "alertas": [a["mensaje"] for a in alertas],
        "mensajes_riesgo": alertas, "por_casa": por_casa.round(2),
    }

def auditar_conciliacion_historial():
    """Detecta apuestas cuyo monto no fue respaldado por las billeteras registradas."""
    liquidadas = [a for a in obtener_apuestas()
                  if a["estado"] in {"GANADA", "PERDIDA", "ANULADA", "CASH_OUT"}]
    inconsistentes = []
    for apuesta in liquidadas:
        diferencia = max(0.0, float(apuesta["monto"]) - float(apuesta["monto_conciliado"]))
        if diferencia > 0.001:
            inconsistentes.append({
                "id": apuesta["id"], "casa": apuesta["nombre_casa"],
                "evento": apuesta["evento"], "monto": float(apuesta["monto"]),
                "conciliado": float(apuesta["monto_conciliado"]),
                "sin_conciliar": diferencia, "estado": apuesta["estado"],
            })
    total = float(np.sum([a["sin_conciliar"] for a in inconsistentes])) if inconsistentes else 0.0
    return {
        "confiable_saldos": not inconsistentes,
        "cantidad": len(inconsistentes),
        "monto_sin_conciliar": round(total, 2),
        "apuestas": inconsistentes,
        "mensaje": (f"Hay {len(inconsistentes)} apuestas por S/ {total:.2f} que no fueron "
                    "descontadas completamente de las billeteras registradas. El rendimiento "
                    "histórico las incluye, pero los saldos y la disponibilidad de retiro solo "
                    "reflejan el capital conciliado.") if inconsistentes else
                   "Todas las apuestas liquidadas están conciliadas con las billeteras registradas.",
    }
