"""Analítica correspondiente a este caso de uso."""

import numpy as np
from models.database import obtener_apuestas
from controllers.analitica_apuesta import calcular_retorno_potencial

def resumen_apuestas_pendientes():
    pendientes = obtener_apuestas("PENDIENTE")
    montos = np.array([float(a["monto"]) for a in pendientes], dtype=float)
    retornos = np.array([float(a["monto"]) * float(a["cuota"]) for a in pendientes], dtype=float)
    return {
        "cantidad": len(pendientes),
        "capital_en_riesgo": round(float(np.sum(montos)) if montos.size else 0.0, 2),
        "retorno_potencial": round(float(np.sum(retornos)) if retornos.size else 0.0, 2),
        "ganancia_potencial": round(float(np.sum(retornos - montos)) if montos.size else 0.0, 2),
    }
