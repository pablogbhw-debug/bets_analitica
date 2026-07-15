"""Movimientos de billetera, retiros y recargas aislados por usuario."""

from models.repositorios.conexion import obtener_conexion, obtener_usuario_actual
from models.repositorios.configuracion import evaluar_limites
from models.repositorios.historial import retiro_permitido


def registrar_movimiento_bd(id_casa, tipo, monto, cuota=1, saldo_usado="DEPOSITO"):
    usuario_id = obtener_usuario_actual()
    id_casa, tipo = id_casa.upper().strip(), tipo.upper().strip()
    saldo_usado = saldo_usado.upper().strip()
    monto, cuota = float(monto), float(cuota)
    if monto <= 0:
        raise ValueError("El monto debe ser mayor que cero.")
    evaluar_limites(tipo, monto)
    with obtener_conexion() as conn:
        casa = conn.execute(
            "SELECT * FROM casas_apuestas WHERE usuario_id=? AND id=?",
            (usuario_id, id_casa),
        ).fetchone()
        if not casa:
            raise ValueError(f"No existe la casa de apuesta {id_casa}.")
        dep, bono, ret, roll = map(float, (casa["saldo_deposito"], casa["saldo_bono"],
                                          casa["saldo_retirable"], casa["rollover_pendiente"]))
        if tipo == "RECARGA":
            dep += monto
            roll += monto * float(casa["rollover_deposito"])
        elif tipo == "BONO":
            bono += monto
            roll += monto * float(casa["rollover_bono"])
        elif tipo == "RETIRO":
            if not retiro_permitido(dict(casa)) or monto > ret:
                raise ValueError("El retiro no cumple las reglas configuradas de la casa.")
            ret -= monto
        elif tipo == "CIERRE_NO_RETIRABLE":
            ret -= monto
        elif tipo in {"APUESTA_GANADA", "APUESTA_PERDIDA"}:
            if saldo_usado == "DEPOSITO":
                dep -= monto
            elif saldo_usado == "BONO":
                bono -= monto
            elif saldo_usado == "RETIRABLE":
                ret -= monto
            else:
                raise ValueError("Billetera no válida.")
            if cuota >= float(casa["cuota_minima_rollover"]):
                roll = max(0, roll - monto)
            if tipo == "APUESTA_GANADA":
                ret += monto * (cuota - 1) if saldo_usado == "BONO" else monto * cuota
        else:
            raise ValueError(f"Tipo de movimiento no soportado: {tipo}")
        if min(dep, bono, ret, roll) < -0.001:
            raise ValueError("El movimiento dejaría un saldo negativo.")
        conn.execute("""INSERT INTO historial_transacciones
            (usuario_id,id_casa,tipo_movimiento,monto,cuota,tipo_saldo_usado)
            VALUES (?,?,?,?,?,?)""",
            (usuario_id, id_casa, tipo, monto, cuota, saldo_usado))
        conn.execute("""UPDATE casas_apuestas SET saldo_deposito=?,saldo_bono=?,
            saldo_retirable=?,rollover_pendiente=? WHERE usuario_id=? AND id=?""",
            (round(dep, 2), round(bono, 2), round(ret, 2), round(roll, 2),
             usuario_id, id_casa))


def registrar_recarga_bitacora(id_casa, monto_deposito, monto_bono=0):
    usuario_id = obtener_usuario_actual()
    id_casa = id_casa.upper().strip()
    monto_deposito, monto_bono = float(monto_deposito), float(monto_bono)
    if monto_deposito < 0 or monto_bono < 0 or monto_deposito + monto_bono <= 0:
        raise ValueError("Ingrese un monto positivo de depósito o bono.")
    with obtener_conexion() as conn:
        casa = conn.execute(
            "SELECT * FROM casas_apuestas WHERE usuario_id=? AND id=?",
            (usuario_id, id_casa),
        ).fetchone()
        if not casa:
            raise ValueError(f"No existe la casa de apuestas {id_casa}.")
        rollover_generado = (
            monto_deposito * float(casa["rollover_deposito"])
            + monto_bono * float(casa["rollover_bono"])
        )
        conn.execute("""UPDATE casas_apuestas SET saldo_deposito=saldo_deposito+?,
            saldo_bono=saldo_bono+?,rollover_pendiente=rollover_pendiente+?
            WHERE usuario_id=? AND id=?""",
            (monto_deposito, monto_bono, rollover_generado, usuario_id, id_casa))
        movimientos = []
        if monto_deposito > 0:
            movimientos.append((usuario_id, id_casa, "RECARGA", monto_deposito, 1.0, "DEPOSITO"))
        if monto_bono > 0:
            movimientos.append((usuario_id, id_casa, "BONO", monto_bono, 1.0, "BONO"))
        conn.executemany("""INSERT INTO historial_transacciones
            (usuario_id,id_casa,tipo_movimiento,monto,cuota,tipo_saldo_usado)
            VALUES (?,?,?,?,?,?)""", movimientos)
        return {"deposito": round(monto_deposito, 2), "bono": round(monto_bono, 2),
                "rollover_generado": round(rollover_generado, 2)}
