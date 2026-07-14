"""Consultas de historial, rollover y diagnóstico financiero."""

from models.repositorios.conexion import MINIMO_RETIRO, obtener_conexion


def obtener_historial_completo():
    with obtener_conexion() as conn:
        return [dict(f) for f in conn.execute("""SELECT h.*,c.nombre_casa FROM historial_transacciones h
            JOIN casas_apuestas c ON h.id_casa=c.id ORDER BY h.fecha,h.id""")]


def retiro_permitido(casa):
    minimo = float(casa.get("minimo_retiro", MINIMO_RETIRO))
    return float(casa["saldo_retirable"]) >= minimo and float(casa["rollover_pendiente"]) <= 0


def saldo_jugable(casa):
    return sum(float(casa[k]) for k in ("saldo_deposito", "saldo_bono", "saldo_retirable"))


def recalcular_rollover_casa(id_casa):
    """Deriva el rollover únicamente de recargas, bonos y apuestas existentes."""
    id_casa = id_casa.upper().strip()
    with obtener_conexion() as conn:
        casa = conn.execute("SELECT * FROM casas_apuestas WHERE id=?", (id_casa,)).fetchone()
        if not casa:
            raise ValueError("La casa no existe.")
        movimientos = conn.execute("""SELECT tipo_movimiento,monto
            FROM historial_transacciones WHERE id_casa=?
            AND tipo_movimiento IN ('RECARGA','BONO')""", (id_casa,)).fetchall()
        generado = sum(
            float(m["monto"]) * (float(casa["rollover_deposito"])
            if m["tipo_movimiento"] == "RECARGA" else float(casa["rollover_bono"]))
            for m in movimientos
        )
        apostado_valido = float(conn.execute("""SELECT COALESCE(SUM(monto),0)
            FROM apuestas WHERE id_casa=? AND estado!='PENDIENTE' AND cuota>=?""",
            (id_casa, float(casa["cuota_minima_rollover"]))).fetchone()[0])
        liberado = min(generado, apostado_valido)
        pendiente = max(0.0, generado - liberado)
        conn.execute("UPDATE casas_apuestas SET rollover_pendiente=? WHERE id=?",
                     (round(pendiente, 2), id_casa))
        return {"generado": round(generado, 2), "liberado": round(liberado, 2),
                "pendiente": round(pendiente, 2), "apostado_valido": round(apostado_valido, 2)}


def diagnosticar_ciclo(casa):
    jugable, retirable = saldo_jugable(casa), float(casa["saldo_retirable"])
    minimo, rollover = float(casa.get("minimo_retiro", MINIMO_RETIRO)), float(casa["rollover_pendiente"])
    faltante = max(0, minimo - retirable)
    razones = []
    if rollover > 0:
        razones.append(f"rollover pendiente de S/ {rollover:.2f}")
    if retirable < minimo:
        razones.append(f"faltan S/ {faltante:.2f} de saldo retirable para el mínimo")
    if retiro_permitido(casa):
        estado = "LISTO_PARA_RETIRAR"
        mensaje = "Cumple el mínimo y no tiene rollover pendiente. Prioriza retirar antes de volver a apostar."
    elif rollover > 0:
        estado = "ROLLOVER_PENDIENTE"
        mensaje = "Retiro no disponible: " + " y ".join(razones) + ". No recargues para intentar habilitarlo."
    elif retirable > 0:
        estado = "MINIMO_NO_ALCANZADO"
        mensaje = (f"Retiro no disponible: faltan S/ {faltante:.2f} de saldo retirable. "
                   "Los depósitos y bonos no cuentan como saldo retirable.")
    elif jugable > 0:
        estado = "SIN_SALDO_RETIRABLE"
        mensaje = "Hay saldo para jugar, pero S/ 0.00 retirables. No lo presentes como retiro disponible."
    else:
        estado = "CICLO_CERRADO"
        mensaje = "No hay saldo activo ni saldo retirable."
    return {"estado": estado, "recomendacion": mensaje, "razones_bloqueo": razones,
            "faltante_retiro": faltante, "saldo_jugable": jugable,
            "saldo_retirable": retirable, "rollover_pendiente": rollover}


def recalcular_saldos_desde_historial():
    raise ValueError("La reconstrucción automática está desactivada: las apuestas pendientes requieren conciliación individual.")
