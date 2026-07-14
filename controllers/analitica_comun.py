"""Auxiliares internos compartidos por los módulos analíticos."""

import pandas as pd
from models.database import fecha_utc_a_local, obtener_apuestas, obtener_historial_completo

def _racha_perdidas(resultados):
    racha = 0
    for resultado in reversed(list(resultados)):
        if resultado != "PERDIDA":
            break
        racha += 1
    return racha

def _apuestas_liquidadas():
    """Combina apuestas nuevas y registros anteriores en una lista de diccionarios."""
    filas = []
    for apuesta in obtener_apuestas():
        if apuesta["estado"] not in {"GANADA", "PERDIDA", "CASH_OUT"}:
            continue
        if apuesta["estado"] == "GANADA":
            flujo = float(apuesta["monto"]) * (float(apuesta["cuota"]) - 1)
        elif apuesta["estado"] == "CASH_OUT":
            # Para el análisis conservador, cash out solo puede ser neutral o pérdida.
            flujo = min(0.0, float(apuesta["retorno"]) - float(apuesta["monto"]))
        else:
            flujo = -float(apuesta["monto"])
        filas.append({
            "fecha": apuesta["fecha_resolucion"] or apuesta["fecha_registro"],
            "nombre_casa": apuesta["nombre_casa"],
            "resultado": ("PERDIDA" if apuesta["estado"] == "CASH_OUT" and flujo < 0
                          else apuesta["estado"]),
            "es_cashout": apuesta["estado"] == "CASH_OUT",
            "cashout_neutro": apuesta["estado"] == "CASH_OUT" and flujo == 0,
            "cashout_perdida": apuesta["estado"] == "CASH_OUT" and flujo < 0,
            "monto": float(apuesta["monto"]),
            "monto_conciliado": float(apuesta["monto_conciliado"]),
            "cuota": float(apuesta["cuota"]),
            "tipo_saldo": apuesta["tipo_saldo"],
            "deporte": apuesta["deporte"],
            "mercado": apuesta["mercado"],
            "evento": apuesta["evento"],
            "Flujo_Efectivo": flujo,
            "origen": "NUEVA",
        })
    for movimiento in obtener_historial_completo():
        tipos_historicos = ("APUESTA_GANADA", "APUESTA_PERDIDA")  # tupla inmutable
        if movimiento.get("apuesta_id") is not None or movimiento["tipo_movimiento"] not in tipos_historicos:
            continue
        ganada = movimiento["tipo_movimiento"] == "APUESTA_GANADA"
        flujo = (float(movimiento["monto"]) * (float(movimiento["cuota"]) - 1)
                 if ganada else -float(movimiento["monto"]))
        filas.append({
            "fecha": movimiento["fecha"], "nombre_casa": movimiento["nombre_casa"],
            "resultado": "GANADA" if ganada else "PERDIDA", "monto": float(movimiento["monto"]),
            "monto_conciliado": float(movimiento["monto"]),
            "cuota": float(movimiento["cuota"]), "tipo_saldo": movimiento["tipo_saldo_usado"],
            "deporte": "Histórico", "mercado": "Sin clasificar", "evento": "Registro anterior",
            "Flujo_Efectivo": flujo, "origen": "HISTÓRICA",
            "es_cashout": False, "cashout_neutro": False, "cashout_perdida": False,
        })
    if not filas:
        return pd.DataFrame()
    df = pd.DataFrame(filas)
    # MySQL entrega fechas SQL; también se toleran registros ISO históricos.
    # format="mixed" evita que Pandas descarte silenciosamente uno de los dos formatos.
    df["fecha"] = df["fecha"].map(fecha_utc_a_local)
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df = df.dropna(subset=["fecha", "monto", "cuota"]).sort_values("fecha").reset_index(drop=True)
    return df

def _alerta(codigo, nivel, mensaje):
    return {"codigo": codigo, "nivel": nivel, "mensaje": mensaje}
