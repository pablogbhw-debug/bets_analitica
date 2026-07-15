"""Registro, edición, liquidación y eliminación de apuestas."""

from models.repositorios.conexion import (
    ahora_utc_sql,
    normalizar_fecha_evento,
    obtener_conexion,
    obtener_usuario_actual,
)
from models.repositorios.configuracion import evaluar_limites
from models.repositorios.historial import recalcular_rollover_casa


def registrar_apuesta(id_casa, deporte, liga, evento, mercado, seleccion, fecha_evento,
                      monto, cuota, tipo_saldo):
    usuario_id = obtener_usuario_actual()
    monto, cuota = float(monto), float(cuota)
    if cuota <= 1 or monto <= 0:
        raise ValueError("Monto y cuota deben ser válidos; la cuota debe superar 1.00.")
    control = evaluar_limites("APUESTA", monto)
    fecha_evento = normalizar_fecha_evento(fecha_evento)
    textos = [deporte, liga, evento, mercado, seleccion, fecha_evento]
    if any(not str(x).strip() for x in textos):
        raise ValueError("Complete los datos deportivos de la apuesta.")
    id_casa, tipo_saldo = id_casa.upper().strip(), tipo_saldo.upper().strip()
    if tipo_saldo == "SALDO":
        tipo_saldo = "DEPOSITO"
    columna = {"DEPOSITO": "saldo_deposito", "BONO": "saldo_bono", "RETIRABLE": "saldo_retirable"}.get(tipo_saldo)
    if not columna:
        raise ValueError("Billetera no válida.")
    with obtener_conexion() as conn:
        casa = conn.execute("SELECT * FROM casas_apuestas WHERE usuario_id=? AND id=?",
                            (usuario_id, id_casa)).fetchone()
        if not casa or float(casa[columna]) < monto:
            raise ValueError("Saldo insuficiente en la billetera seleccionada.")
        cursor = conn.execute("""INSERT INTO apuestas
            (usuario_id,id_casa,deporte,liga,evento,mercado,seleccion,fecha_evento,monto,cuota,tipo_saldo)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (usuario_id, id_casa, deporte.strip(), liga.strip(), evento.strip(),
            mercado.strip(), seleccion.strip(), str(fecha_evento), monto, cuota, tipo_saldo))
        apuesta_id = cursor.lastrowid
        conn.execute("UPDATE apuestas SET monto_conciliado=? WHERE usuario_id=? AND id=?",
                     (monto, usuario_id, apuesta_id))
        roll = float(casa["rollover_pendiente"])
        roll_anterior = roll
        if cuota >= float(casa["cuota_minima_rollover"]): roll = max(0, roll - monto)
        conn.execute(f"UPDATE casas_apuestas SET {columna}={columna}-?, rollover_pendiente=? "
                     "WHERE usuario_id=? AND id=?",
                     (monto, round(roll, 2), usuario_id, id_casa))
        conn.execute("UPDATE apuestas SET rollover_liberado=? WHERE usuario_id=? AND id=?",
                     (round(roll_anterior - roll, 2), usuario_id, apuesta_id))
        conn.execute("""INSERT INTO historial_transacciones
            (usuario_id,id_casa,tipo_movimiento,monto,cuota,tipo_saldo_usado,apuesta_id)
            VALUES (?,?,?,?,?,?,?)""", (usuario_id, id_casa, "APUESTA_PENDIENTE", monto, cuota, tipo_saldo, apuesta_id))
        return apuesta_id


def registrar_apuesta_bitacora(id_casa, deporte, liga, evento, mercado, seleccion,
                               fecha_evento, monto, cuota, tipo_saldo, resultado):
    """Registra una apuesta ya resuelta sin exigir depósitos previos.

    Es el flujo principal del modo bitácora: el usuario transcribe la operación realizada
    en la casa y el sistema la utiliza para analizar rentabilidad y riesgo.
    """
    usuario_id = obtener_usuario_actual()
    monto, cuota = float(monto), float(cuota)
    fecha_evento = normalizar_fecha_evento(fecha_evento)
    id_casa, tipo_saldo, resultado = (id_casa.upper().strip(), tipo_saldo.upper().strip(),
                                      resultado.upper().strip())
    if tipo_saldo == "SALDO":
        tipo_saldo = "DEPOSITO"
    if monto <= 0 or cuota <= 1:
        raise ValueError("El monto debe ser positivo y la cuota mayor que 1.00.")
    if tipo_saldo not in {"DEPOSITO", "BONO", "RETIRABLE"}:
        raise ValueError("Origen del dinero no válido.")
    if resultado not in {"PENDIENTE", "GANADA", "PERDIDA", "ANULADA"}:
        raise ValueError("Resultado no válido.")
    textos = [deporte, liga, evento, mercado, seleccion]
    if any(not str(valor).strip() for valor in textos):
        raise ValueError("Complete la información de la apuesta.")

    retorno = 0.0
    if resultado == "GANADA":
        retorno = monto * cuota
        if tipo_saldo == "BONO":
            retorno = monto * (cuota - 1)
    elif resultado == "ANULADA":
        retorno = monto

    with obtener_conexion() as conn:
        casa = conn.execute("SELECT * FROM casas_apuestas WHERE usuario_id=? AND id=?",
                            (usuario_id, id_casa)).fetchone()
        if not casa:
            raise ValueError(f"No existe la casa de apuestas {id_casa}.")
        tipos_saldo = ("BONO",) if tipo_saldo == "BONO" else ("DEPOSITO", "RETIRABLE")
        marcas = ",".join("?" for _ in tipos_saldo)
        reservado = float(conn.execute(
            f"SELECT COALESCE(SUM(monto),0) FROM apuestas WHERE usuario_id=? AND id_casa=? "
            f"AND estado='PENDIENTE' AND tipo_saldo IN ({marcas})",
            (usuario_id, id_casa, *tipos_saldo),
        ).fetchone()[0])
        saldo_origen = (float(casa["saldo_bono"]) if tipo_saldo == "BONO" else
                        float(casa["saldo_deposito"]) + float(casa["saldo_retirable"]))
        disponible = max(0.0, saldo_origen - reservado)
        if monto > disponible + 0.001:
            raise ValueError(
                f"Saldo insuficiente en {id_casa}: hay S/ {disponible:.2f} disponibles "
                f"en {'BONO' if tipo_saldo == 'BONO' else 'SALDO'} después de reservar "
                "las apuestas pendientes. Registra primero la recarga o bono omitido."
            )
        fecha_resolucion = None if resultado == "PENDIENTE" else ahora_utc_sql()
        cursor = conn.execute("""INSERT INTO apuestas
            (usuario_id,id_casa,deporte,liga,evento,mercado,seleccion,fecha_evento,monto,cuota,
             tipo_saldo,estado,retorno,fecha_resolucion)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (usuario_id, id_casa, str(deporte).strip(), str(liga).strip(), str(evento).strip(),
             str(mercado).strip(), str(seleccion).strip(), str(fecha_evento), monto,
             cuota, tipo_saldo, resultado, round(retorno, 2), fecha_resolucion))
        apuesta_id = cursor.lastrowid
        columnas_origen = (["saldo_bono"] if tipo_saldo == "BONO"
                           else ["saldo_deposito", "saldo_retirable"])
        monto_conciliado = 0.0
        descuentos = {columna: 0.0 for columna in columnas_origen}
        if resultado != "PENDIENTE":
            restante = monto
            for columna in columnas_origen:
                descuento = min(restante, float(casa[columna]))
                descuentos[columna] = descuento
                monto_conciliado += descuento
                restante -= descuento
                if descuento > 0:
                    conn.execute(f"UPDATE casas_apuestas SET {columna}={columna}-? "
                                 "WHERE usuario_id=? AND id=?",
                                 (descuento, usuario_id, id_casa))
        conn.execute("UPDATE apuestas SET monto_conciliado=? WHERE usuario_id=? AND id=?",
                     (round(monto_conciliado, 2), usuario_id, apuesta_id))
        if resultado == "GANADA" and retorno > 0:
            conn.execute("UPDATE casas_apuestas SET saldo_retirable=saldo_retirable+? "
                         "WHERE usuario_id=? AND id=?",
                         (round(retorno, 2), usuario_id, id_casa))
        elif resultado == "ANULADA" and monto_conciliado > 0:
            for columna, descuento in descuentos.items():
                if descuento > 0:
                    conn.execute(f"UPDATE casas_apuestas SET {columna}={columna}+? "
                                 "WHERE usuario_id=? AND id=?",
                                 (descuento, usuario_id, id_casa))
        rollover = float(casa["rollover_pendiente"])
        rollover_anterior = rollover
        if resultado != "PENDIENTE" and cuota >= float(casa["cuota_minima_rollover"]):
            rollover = max(0.0, rollover - monto)
            conn.execute("UPDATE casas_apuestas SET rollover_pendiente=? "
                         "WHERE usuario_id=? AND id=?",
                         (round(rollover, 2), usuario_id, id_casa))
        conn.execute("UPDATE apuestas SET rollover_liberado=? WHERE usuario_id=? AND id=?",
                     (round(rollover_anterior - rollover, 2), usuario_id, apuesta_id))
        tipo_movimiento = "APUESTA_PENDIENTE" if resultado == "PENDIENTE" else f"LIQUIDACION_{resultado}"
        conn.execute("""INSERT INTO historial_transacciones
            (usuario_id,id_casa,tipo_movimiento,monto,cuota,tipo_saldo_usado,apuesta_id)
            VALUES (?,?,?,?,?,?,?)""", (usuario_id, id_casa, tipo_movimiento, monto,
                                      cuota, tipo_saldo, apuesta_id))
        return apuesta_id


def obtener_apuestas(estado=None):
    usuario_id = obtener_usuario_actual()
    consulta = ("SELECT a.*,c.nombre_casa FROM apuestas a JOIN casas_apuestas c "
                "ON c.usuario_id=a.usuario_id AND c.id=a.id_casa WHERE a.usuario_id=?")
    params = (usuario_id,)
    if estado:
        consulta += " AND a.estado=?"; params = (usuario_id, estado.upper())
    consulta += " ORDER BY a.fecha_registro DESC,a.id DESC"
    with obtener_conexion() as conn:
        return [dict(f) for f in conn.execute(consulta, params)]


def editar_apuesta_bitacora(apuesta_id, deporte, liga, evento, mercado, seleccion,
                            fecha_evento, cuota, tipo_saldo):
    usuario_id = obtener_usuario_actual()
    """Corrige los datos de una apuesta sin recalcular su resultado histórico."""
    textos = [str(x).strip() for x in (deporte, liga, evento, mercado, seleccion)]
    if not all(textos):
        raise ValueError("Deporte, liga, evento, mercado y detalle son obligatorios.")
    fecha_evento = normalizar_fecha_evento(fecha_evento)
    cuota = float(cuota)
    tipo_saldo = str(tipo_saldo).upper().strip()
    if tipo_saldo == "SALDO":
        tipo_saldo = "DEPOSITO"
    if cuota <= 1 or tipo_saldo not in {"DEPOSITO", "BONO", "RETIRABLE"}:
        raise ValueError("La cuota debe ser mayor que 1 y el tipo de saldo debe ser válido.")
    with obtener_conexion() as conn:
        apuesta = conn.execute("""SELECT id,id_casa,tipo_saldo,monto_conciliado
            FROM apuestas WHERE usuario_id=? AND id=?""",
            (usuario_id, int(apuesta_id))).fetchone()
        if not apuesta:
            raise ValueError("La apuesta no existe.")
        if (tipo_saldo != apuesta["tipo_saldo"] and
                float(apuesta["monto_conciliado"]) > 0.001):
            raise ValueError(
                "No se puede cambiar el origen de una apuesta ya conciliada porque alteraría "
                "los saldos. Elimina y vuelve a registrar la apuesta con el origen correcto."
            )
        conn.execute("""UPDATE apuestas SET deporte=?,liga=?,evento=?,mercado=?,seleccion=?,
                     fecha_evento=?,cuota=?,tipo_saldo=? WHERE usuario_id=? AND id=?""",
                     (*textos, fecha_evento, cuota, tipo_saldo, usuario_id, int(apuesta_id)))
        conn.execute("""UPDATE historial_transacciones SET cuota=?,tipo_saldo_usado=?
                     WHERE usuario_id=? AND apuesta_id=?""",
                     (cuota, tipo_saldo, usuario_id, int(apuesta_id)))
    recalcular_rollover_casa(apuesta["id_casa"])


def eliminar_apuesta_bitacora(apuesta_id):
    """Elimina una apuesta y revierte de forma transaccional su efecto financiero."""
    usuario_id = obtener_usuario_actual()
    columnas = {"DEPOSITO": "saldo_deposito", "BONO": "saldo_bono",
                "RETIRABLE": "saldo_retirable"}
    with obtener_conexion() as conn:
        apuesta = conn.execute("SELECT * FROM apuestas WHERE usuario_id=? AND id=?",
                               (usuario_id, int(apuesta_id))).fetchone()
        if not apuesta:
            raise ValueError("La apuesta no existe.")
        casa = conn.execute("SELECT * FROM casas_apuestas WHERE usuario_id=? AND id=?",
                            (usuario_id, apuesta["id_casa"])).fetchone()
        estado = apuesta["estado"]
        retorno = float(apuesta["retorno"])
        conciliado = float(apuesta["monto_conciliado"])

        # Una ganancia o cash out acreditó retorno al saldo retirable: se retira antes de restaurar la apuesta.
        if estado in {"GANADA", "CASH_OUT"} and retorno > 0:
            if float(casa["saldo_retirable"]) + 0.001 < retorno:
                raise ValueError("No se puede eliminar: el retorno ya no está disponible en el saldo retirable.")
            conn.execute("UPDATE casas_apuestas SET saldo_retirable=saldo_retirable-? "
                         "WHERE usuario_id=? AND id=?",
                         (retorno, usuario_id, apuesta["id_casa"]))

        # ANULADA ya devolvió lo conciliado; los demás resultados recuperan el capital descontado.
        if estado != "ANULADA" and conciliado > 0:
            columna = columnas[apuesta["tipo_saldo"]]
            conn.execute(f"UPDATE casas_apuestas SET {columna}={columna}+? "
                         "WHERE usuario_id=? AND id=?",
                         (conciliado, usuario_id, apuesta["id_casa"]))
        rollover = float(apuesta["rollover_liberado"])
        if rollover > 0:
            conn.execute("UPDATE casas_apuestas SET rollover_pendiente=rollover_pendiente+? "
                         "WHERE usuario_id=? AND id=?",
                         (rollover, usuario_id, apuesta["id_casa"]))
        conn.execute("DELETE FROM historial_transacciones WHERE usuario_id=? AND apuesta_id=?",
                     (usuario_id, int(apuesta_id)))
        conn.execute("DELETE FROM apuestas WHERE usuario_id=? AND id=?",
                     (usuario_id, int(apuesta_id)))
        id_casa = apuesta["id_casa"]
    recalcular_rollover_casa(id_casa)
    return True


def resolver_apuesta(apuesta_id, resultado, monto_cashout=0):
    usuario_id = obtener_usuario_actual()
    resultado = resultado.upper().strip()
    if resultado not in {"GANADA", "PERDIDA", "ANULADA", "CASH_OUT"}:
        raise ValueError("Resultado no válido.")
    with obtener_conexion() as conn:
        apuesta = conn.execute("SELECT * FROM apuestas WHERE usuario_id=? AND id=?",
                               (usuario_id, int(apuesta_id))).fetchone()
        if not apuesta or apuesta["estado"] != "PENDIENTE":
            raise ValueError("La apuesta no existe o ya fue liquidada.")
        monto_conciliado = float(apuesta["monto_conciliado"])
        rollover_liberado = float(apuesta["rollover_liberado"])
        if monto_conciliado <= 0 and resultado != "ANULADA":
            casa_antes = conn.execute(
                "SELECT * FROM casas_apuestas WHERE usuario_id=? AND id=?",
                (usuario_id, apuesta["id_casa"])
            ).fetchone()
            columnas = {"DEPOSITO": "saldo_deposito", "BONO": "saldo_bono",
                        "RETIRABLE": "saldo_retirable"}
            orden = (["BONO"] if apuesta["tipo_saldo"] == "BONO"
                     else ["DEPOSITO", "RETIRABLE"])
            restante = float(apuesta["monto"])
            for tipo in orden:
                columna = columnas[tipo]
                descuento = min(restante, float(casa_antes[columna]))
                if descuento > 0:
                    conn.execute(f"UPDATE casas_apuestas SET {columna}={columna}-? "
                                 "WHERE usuario_id=? AND id=?",
                                 (descuento, usuario_id, apuesta["id_casa"]))
                    restante -= descuento
                    monto_conciliado += descuento
                if restante <= 0:
                    break
            if float(apuesta["cuota"]) >= float(casa_antes["cuota_minima_rollover"]):
                rollover_anterior = float(casa_antes["rollover_pendiente"])
                rollover_nuevo = max(0.0, rollover_anterior - float(apuesta["monto"]))
                rollover_liberado = rollover_anterior - rollover_nuevo
                conn.execute("UPDATE casas_apuestas SET rollover_pendiente=? "
                             "WHERE usuario_id=? AND id=?",
                             (round(rollover_nuevo, 2), usuario_id, apuesta["id_casa"]))
            conn.execute("""UPDATE apuestas SET monto_conciliado=?,rollover_liberado=?
                         WHERE usuario_id=? AND id=?""",
                         (round(monto_conciliado, 2), round(rollover_liberado, 2),
                          usuario_id, apuesta_id))

        retorno = 0.0
        if resultado == "GANADA":
            retorno = apuesta["monto"] * apuesta["cuota"]
            if apuesta["tipo_saldo"] == "BONO":
                retorno = apuesta["monto"] * (apuesta["cuota"] - 1)
        elif resultado == "CASH_OUT":
            retorno = float(monto_cashout)
            if retorno < 0:
                raise ValueError("El monto de cash out no puede ser negativo.")
        if resultado == "ANULADA": retorno = apuesta["monto"]
        if retorno:
            destino = "saldo_retirable" if resultado in {"GANADA", "CASH_OUT"} else {
                "DEPOSITO": "saldo_deposito", "BONO": "saldo_bono", "RETIRABLE": "saldo_retirable"
            }[apuesta["tipo_saldo"]]
            monto_acreditar = retorno
            if resultado == "ANULADA":
                monto_acreditar = float(apuesta["monto_conciliado"])
            conn.execute(f"UPDATE casas_apuestas SET {destino}={destino}+? "
                         "WHERE usuario_id=? AND id=?",
                         (monto_acreditar, usuario_id, apuesta["id_casa"]))
        conn.execute("""UPDATE apuestas SET estado=?,retorno=?,fecha_resolucion=CURRENT_TIMESTAMP
                     WHERE usuario_id=? AND id=?""",
                     (resultado, round(retorno, 2), usuario_id, apuesta_id))
        conn.execute("""INSERT INTO historial_transacciones
            (usuario_id,id_casa,tipo_movimiento,monto,cuota,tipo_saldo_usado,apuesta_id)
            VALUES (?,?,?,?,?,?,?)""", (usuario_id, apuesta["id_casa"], f"LIQUIDACION_{resultado}", apuesta["monto"],
                                      apuesta["cuota"], apuesta["tipo_saldo"], apuesta_id))
        casa_actualizada = conn.execute(
            """SELECT saldo_deposito,saldo_bono,saldo_retirable FROM casas_apuestas
            WHERE usuario_id=? AND id=?""",
            (usuario_id, apuesta["id_casa"]),
        ).fetchone()
        return {
            "resultado": resultado,
            "monto_apostado": float(apuesta["monto"]),
            "descontado_al_finalizar": round(monto_conciliado, 2),
            "retorno": round(float(retorno), 2),
            "saldo_para_jugar": round(sum(float(casa_actualizada[campo]) for campo in
                ("saldo_deposito", "saldo_bono", "saldo_retirable")), 2),
        }


def eliminar_apuesta_pendiente(apuesta_id):
    """Elimina una pendiente y restituye el importe conciliado a su billetera original."""
    usuario_id = obtener_usuario_actual()
    with obtener_conexion() as conn:
        apuesta = conn.execute("SELECT * FROM apuestas WHERE usuario_id=? AND id=?",
                               (usuario_id, int(apuesta_id))).fetchone()
        if not apuesta or apuesta["estado"] != "PENDIENTE":
            raise ValueError("Solo se pueden eliminar apuestas pendientes.")
        columna = {"DEPOSITO": "saldo_deposito", "BONO": "saldo_bono",
                   "RETIRABLE": "saldo_retirable"}[apuesta["tipo_saldo"]]
        conciliado = float(apuesta["monto_conciliado"])
        if conciliado > 0:
            conn.execute(f"UPDATE casas_apuestas SET {columna}={columna}+? "
                         "WHERE usuario_id=? AND id=?",
                         (conciliado, usuario_id, apuesta["id_casa"]))
        rollover_liberado = float(apuesta["rollover_liberado"])
        if rollover_liberado > 0:
            conn.execute("""UPDATE casas_apuestas
                SET rollover_pendiente=rollover_pendiente+?
                WHERE usuario_id=? AND id=?""",
                (rollover_liberado, usuario_id, apuesta["id_casa"]))
        conn.execute("DELETE FROM historial_transacciones WHERE usuario_id=? AND apuesta_id=?",
                     (usuario_id, apuesta_id))
        conn.execute("DELETE FROM apuestas WHERE usuario_id=? AND id=?",
                     (usuario_id, apuesta_id))
        return True
