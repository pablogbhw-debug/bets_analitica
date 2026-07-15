"""Persistencia multiusuario del catálogo y saldos de casas de apuestas."""

from mysql.connector import IntegrityError

from models.repositorios.conexion import obtener_conexion, obtener_usuario_actual


def registrar_casa_apuesta(id_casa, nombre, minimo_retiro=50, rollover_deposito=1,
                            rollover_bono=1, cuota_minima_rollover=1.01,
                            deportes="Futbol,Baloncesto,Tenis"):
    usuario_id = obtener_usuario_actual()
    id_casa, nombre = id_casa.upper().strip(), nombre.strip()
    if not id_casa or not nombre:
        raise ValueError("El código y el nombre de la casa son obligatorios.")
    valores = [float(minimo_retiro), float(rollover_deposito), float(rollover_bono),
               float(cuota_minima_rollover)]
    if min(valores[:3]) < 0 or valores[3] < 1 or not deportes.strip():
        raise ValueError("Revise el retiro, rollover, cuota mínima y deportes de la casa.")
    try:
        with obtener_conexion() as conn:
            conn.execute("""
                INSERT INTO casas_apuestas
                (usuario_id,id,nombre_casa,minimo_retiro,rollover_deposito,
                 rollover_bono,cuota_minima_rollover,deportes)
                VALUES (?,?,?,?,?,?,?,?)
            """, (usuario_id, id_casa, nombre, *valores, deportes.strip()))
        return True
    except IntegrityError:
        return False


def inicializar_casas_predeterminadas(forzar=False):
    """Crea las casas iniciales únicamente para el usuario autenticado."""
    usuario_id = obtener_usuario_actual()
    with obtener_conexion() as conn:
        cantidad = int(conn.execute(
            "SELECT COUNT(*) FROM casas_apuestas WHERE usuario_id=?", (usuario_id,)
        ).fetchone()[0])
    if cantidad > 0 and not forzar:
        return
    for codigo, nombre in (
        ("BETANO", "Betano Perú"),
        ("INKABET", "Inkabet"),
        ("TE_APUESTO", "Te Apuesto"),
    ):
        registrar_casa_apuesta(codigo, nombre)


def eliminar_casa_apuesta(id_casa):
    usuario_id = obtener_usuario_actual()
    id_casa = id_casa.upper().strip()
    with obtener_conexion() as conn:
        casa = conn.execute(
            "SELECT * FROM casas_apuestas WHERE usuario_id=? AND id=?",
            (usuario_id, id_casa),
        ).fetchone()
        if not casa:
            raise ValueError("La casa seleccionada no existe.")
        apuestas = int(conn.execute(
            "SELECT COUNT(*) FROM apuestas WHERE usuario_id=? AND id_casa=?",
            (usuario_id, id_casa),
        ).fetchone()[0])
        movimientos = int(conn.execute(
            "SELECT COUNT(*) FROM historial_transacciones WHERE usuario_id=? AND id_casa=?",
            (usuario_id, id_casa),
        ).fetchone()[0])
        saldos = sum(float(casa[campo]) for campo in (
            "saldo_deposito", "saldo_bono", "saldo_retirable", "rollover_pendiente"
        ))
        if apuestas > 0 or movimientos > 0 or abs(saldos) > 0.001:
            raise ValueError(
                "No se puede eliminar: la casa tiene apuestas, movimientos, saldos o rollover registrados."
            )
        conn.execute(
            "DELETE FROM casas_apuestas WHERE usuario_id=? AND id=?",
            (usuario_id, id_casa),
        )
        return True


def reiniciar_datos_conservando_casas():
    """Borra exclusivamente la actividad financiera del usuario autenticado."""
    usuario_id = obtener_usuario_actual()
    with obtener_conexion() as conn:
        movimientos = int(conn.execute(
            "SELECT COUNT(*) FROM historial_transacciones WHERE usuario_id=?", (usuario_id,)
        ).fetchone()[0])
        apuestas = int(conn.execute(
            "SELECT COUNT(*) FROM apuestas WHERE usuario_id=?", (usuario_id,)
        ).fetchone()[0])
        conn.execute("DELETE FROM historial_transacciones WHERE usuario_id=?", (usuario_id,))
        conn.execute("DELETE FROM apuestas WHERE usuario_id=?", (usuario_id,))
        conn.execute("""UPDATE casas_apuestas SET saldo_deposito=0,saldo_bono=0,
                     saldo_retirable=0,rollover_pendiente=0 WHERE usuario_id=?""",
                     (usuario_id,))
        return {"apuestas_eliminadas": apuestas, "movimientos_eliminados": movimientos}


def actualizar_casa(id_casa, minimo_retiro, rollover_deposito, rollover_bono,
                    cuota_minima_rollover, deportes):
    usuario_id = obtener_usuario_actual()
    valores = [float(minimo_retiro), float(rollover_deposito), float(rollover_bono),
               float(cuota_minima_rollover)]
    if min(valores[:3]) < 0 or valores[3] < 1 or not deportes.strip():
        raise ValueError("Revise las reglas de retiro y rollover.")
    with obtener_conexion() as conn:
        conn.execute("""UPDATE casas_apuestas SET minimo_retiro=?,rollover_deposito=?,
                     rollover_bono=?,cuota_minima_rollover=?,deportes=?
                     WHERE usuario_id=? AND id=?""",
                     (*valores, deportes.strip(), usuario_id, id_casa.upper().strip()))


def obtener_resumen_casas():
    usuario_id = obtener_usuario_actual()
    with obtener_conexion() as conn:
        return [dict(f) for f in conn.execute(
            "SELECT * FROM casas_apuestas WHERE usuario_id=? ORDER BY nombre_casa",
            (usuario_id,),
        )]


def obtener_casa(id_casa):
    usuario_id = obtener_usuario_actual()
    with obtener_conexion() as conn:
        fila = conn.execute(
            "SELECT * FROM casas_apuestas WHERE usuario_id=? AND id=?",
            (usuario_id, id_casa.upper().strip()),
        ).fetchone()
        return dict(fila) if fila else None
