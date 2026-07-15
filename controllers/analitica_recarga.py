"""Analítica correspondiente a este caso de uso."""

import numpy as np
from models.database import (
    obtener_apuestas,
    obtener_configuracion,
    obtener_historial_completo,
    obtener_resumen_casas,
)
from controllers.analitica_resumen import analizar_rendimiento_psicologico


def calcular_rollover_recarga(casa, monto_deposito, monto_bono):
    """Calcula el rollover estimado sin duplicar la regla financiera en la vista."""
    return round(
        float(monto_deposito) * float(casa["rollover_deposito"])
        + float(monto_bono) * float(casa["rollover_bono"]),
        2,
    )

def recomendar_recarga_bitacora():
    """Sugiere exposición adicional solo desde resultados positivos, sin bloquear decisiones."""
    _, metricas = analizar_rendimiento_psicologico()
    if not isinstance(metricas, dict):
        return {"sugerida": 0.0, "maxima": 0.0, "nivel": "SIN DATOS",
                "mensaje": "Aún no existe historial suficiente para sugerir una recarga."}
    beneficio = float(metricas["balance_neto_real"])
    nivel = metricas["nivel_riesgo"]
    if beneficio <= 0 or nivel in {"ALTO", "CRÍTICO"}:
        return {"sugerida": 0.0, "maxima": 0.0, "nivel": nivel,
                "mensaje": "No se recomienda recargar: el historial está en pérdida o presenta riesgo elevado."}
    limite = float(obtener_configuracion()["limite_deposito_diario"])
    sugerida = min(limite, beneficio * 0.20)
    maxima = min(limite, beneficio * 0.30)
    mensaje = ("Referencia calculada únicamente sobre la ganancia neta histórica. "
               "Retirar y proteger ganancias tiene prioridad sobre volver a exponerlas.")
    return {"sugerida": round(sugerida, 2), "maxima": round(maxima, 2),
            "nivel": nivel, "mensaje": mensaje}

def evaluar_proteccion_perdidas(id_casa=None):
    """Decide cuándo una recarga debe detenerse para evitar persecución de pérdidas."""
    _, metricas = analizar_rendimiento_psicologico()
    config = obtener_configuracion()
    limite = float(config["limite_perdida_semanal"])
    resumen = resumen_financiero_casa(id_casa) if id_casa else None
    perdida = float(resumen["perdida_acumulada"]) if resumen else 0.0
    nivel = metricas.get("nivel_riesgo", "SIN DATOS") if isinstance(metricas, dict) else "SIN DATOS"
    racha = int(metricas.get("racha_perdidas", 0)) if isinstance(metricas, dict) else 0
    caida = float(metricas.get("peor_caida", 0)) if isinstance(metricas, dict) else 0.0
    razones = []
    if perdida >= limite:
        razones.append(f"la pérdida de esta casa alcanzó el límite personal de {limite:.2f}")
    if racha >= 3:
        razones.append(f"existe una racha de {racha} pérdidas consecutivas")
    if nivel in {"ALTO", "CRÍTICO"}:
        razones.append(f"el nivel de riesgo global es {nivel}")
    bloqueada = bool(razones)
    return {
        "bloqueada": bloqueada,
        "requiere_confirmacion": perdida > 0 and not bloqueada,
        "perdida_casa": round(perdida, 2),
        "limite_perdida": round(limite, 2),
        "racha_perdidas": racha,
        "peor_caida": round(caida, 2),
        "nivel": nivel,
        "razones": razones,
        "mensaje": ("Se recomienda no recargar: " + "; ".join(razones) + ". "
                    "El dinero perdido no es una deuda ni existe garantía de recuperarlo.")
                   if bloqueada else
                   "Una nueva recarga aumenta el capital expuesto y no recupera pérdidas anteriores.",
    }

def resumen_financiero_casa(id_casa):
    """Resume la bitácora de recargas y pérdidas de una casa específica."""
    casa = next((c for c in obtener_resumen_casas() if c["id"] == id_casa), None)
    if not casa:
        raise ValueError("La casa seleccionada no existe.")
    movimientos = [m for m in obtener_historial_completo() if m["id_casa"] == id_casa]
    total_recargado = float(np.sum([
        float(m["monto"]) for m in movimientos if m["tipo_movimiento"] == "RECARGA"
    ]))
    total_bonos = float(np.sum([
        float(m["monto"]) for m in movimientos if m["tipo_movimiento"] == "BONO"
    ]))
    total_retirado = float(np.sum([
        float(m["monto"]) for m in movimientos if m["tipo_movimiento"] == "RETIRO"
    ]))
    apuestas = [a for a in obtener_apuestas() if a["id_casa"] == id_casa
                and a["estado"] in {"GANADA", "PERDIDA"}]
    resultados = np.array([
        float(a["monto"]) * (float(a["cuota"]) - 1)
        if a["estado"] == "GANADA" else -float(a["monto"])
        for a in apuestas
    ], dtype=float)
    resultado_neto = float(np.sum(resultados)) if resultados.size else 0.0
    no_retirable = float(casa["saldo_deposito"]) + float(casa["saldo_bono"])
    return {
        "total_recargado": round(total_recargado, 2),
        "total_bonos": round(total_bonos, 2),
        "total_retirado": round(total_retirado, 2),
        "monto_no_retirable": round(no_retirable, 2),
        "resultado_neto": round(resultado_neto, 2),
        "perdida_acumulada": round(max(0.0, -resultado_neto), 2),
    }
