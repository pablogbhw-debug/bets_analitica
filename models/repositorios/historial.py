"""Consultas de historial, rollover y diagnóstico financiero por usuario."""

from models.repositorios.conexion import MINIMO_RETIRO, obtener_conexion, obtener_usuario_actual


def obtener_historial_completo():
    """Consulta la bitácora completa de movimientos del usuario."""
    usuario_id = obtener_usuario_actual()
    with obtener_conexion() as conn:
        return [dict(f) for f in conn.execute("""
            SELECT h.*,c.nombre_casa FROM historial_transacciones h
            JOIN casas_apuestas c
              ON c.usuario_id=h.usuario_id AND c.id=h.id_casa
            WHERE h.usuario_id=? ORDER BY h.fecha,h.id
        """, (usuario_id,))]


def retiro_permitido(casa):
    """Indica si una casa cumple saldo mínimo y rollover para retirar."""
    minimo = float(casa.get("minimo_retiro", MINIMO_RETIRO))
    return float(casa["saldo_retirable"]) >= minimo and float(casa["rollover_pendiente"]) <= 0


def saldo_jugable(casa):
    """Calcula el saldo total disponible para realizar apuestas en una casa."""
    return sum(float(casa[k]) for k in ("saldo_deposito", "saldo_bono", "saldo_retirable"))


def recalcular_rollover_casa(id_casa):
    """Reconstruye y actualiza el rollover pendiente de una casa."""
    usuario_id = obtener_usuario_actual()
    id_casa = id_casa.upper().strip()
    with obtener_conexion() as conn:
        casa = conn.execute(
            "SELECT * FROM casas_apuestas WHERE usuario_id=? AND id=?",
            (usuario_id, id_casa),
        ).fetchone()
        if not casa:
            raise ValueError("La casa no existe.")
        movimientos = conn.execute("""
            SELECT tipo_movimiento,monto FROM historial_transacciones
            WHERE usuario_id=? AND id_casa=?
              AND tipo_movimiento IN ('RECARGA','BONO')
        """, (usuario_id, id_casa)).fetchall()
        generado = sum(
            float(m["monto"]) * (float(casa["rollover_deposito"])
            if m["tipo_movimiento"] == "RECARGA" else float(casa["rollover_bono"]))
            for m in movimientos
        )
        apostado_valido = float(conn.execute("""
            SELECT COALESCE(SUM(monto),0) FROM apuestas
            WHERE usuario_id=? AND id_casa=? AND estado!='PENDIENTE' AND cuota>=?
        """, (usuario_id, id_casa, float(casa["cuota_minima_rollover"]))).fetchone()[0])
        liberado = min(generado, apostado_valido)
        pendiente = max(0.0, generado - liberado)
        conn.execute("""UPDATE casas_apuestas SET rollover_pendiente=?
                     WHERE usuario_id=? AND id=?""",
                     (round(pendiente, 2), usuario_id, id_casa))
        return {"generado": round(generado, 2), "liberado": round(liberado, 2),
                "pendiente": round(pendiente, 2), "apostado_valido": round(apostado_valido, 2)}


def diagnosticar_ciclo(casa):
    """Explica las condiciones que permiten o bloquean un retiro."""
    jugable, retirable = saldo_jugable(casa), float(casa["saldo_retirable"])
    minimo = float(casa.get("minimo_retiro", MINIMO_RETIRO))
    rollover = float(casa["rollover_pendiente"])
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
        mensaje = "Hay saldo para jugar, pero S/ 0.00 retirables."
    else:
        estado = "CICLO_CERRADO"
        mensaje = "No hay saldo activo ni saldo retirable."
    return {"estado": estado, "recomendacion": mensaje, "razones_bloqueo": razones,
            "faltante_retiro": faltante, "saldo_jugable": jugable,
            "saldo_retirable": retirable, "rollover_pendiente": rollover}


def recalcular_saldos_desde_historial():
    """Reconstruye los saldos de las casas usando el historial registrado."""
    raise ValueError("La reconstrucción automática está desactivada.")
