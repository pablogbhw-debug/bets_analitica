from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from mysql.connector import IntegrityError
from models.mysql_adapter import ConexionMySQL


MINIMO_RETIRO = 50.0
ZONA_LOCAL = ZoneInfo("America/Lima")


def ahora_utc_sql():
    """Fecha UTC canónica usada por MySQL: YYYY-MM-DD HH:MM:SS."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def fecha_utc_a_local(valor):
    """Convierte una fecha UTC de MySQL a hora de Lima para presentación."""
    if not valor:
        return valor
    texto = str(valor).strip().replace("T", " ")
    try:
        fecha = datetime.fromisoformat(texto)
    except ValueError:
        return valor
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    return fecha.astimezone(ZONA_LOCAL).replace(tzinfo=None)


def normalizar_fecha_evento(valor):
    """Valida fechas de calendario y devuelve siempre AAAA-MM-DD."""
    try:
        return datetime.strptime(str(valor), "%Y-%m-%d").date().isoformat()
    except (TypeError, ValueError):
        raise ValueError("La fecha del evento debe tener el formato AAAA-MM-DD.") from None


@contextmanager
def obtener_conexion():
    conn = ConexionMySQL()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _agregar_columna(cursor, tabla, definicion):
    nombre = definicion.split()[0]
    columnas = {fila["COLUMN_NAME"] for fila in cursor.execute(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s", (tabla,)
    )}
    if nombre not in columnas:
        cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN {definicion}")


def inicializar_db():
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                nombre VARCHAR(120) NOT NULL,
                correo VARCHAR(254) NOT NULL UNIQUE,
                password_hash VARCHAR(60) NOT NULL,
                fecha_registro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                activo BOOLEAN NOT NULL DEFAULT TRUE
            ) ENGINE=InnoDB
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS casas_apuestas (
                id VARCHAR(40) PRIMARY KEY,
                nombre_casa VARCHAR(120) NOT NULL,
                saldo_deposito REAL NOT NULL DEFAULT 0,
                saldo_bono REAL NOT NULL DEFAULT 0,
                saldo_retirable REAL NOT NULL DEFAULT 0,
                rollover_pendiente REAL NOT NULL DEFAULT 0,
                minimo_retiro REAL NOT NULL DEFAULT 50,
                rollover_deposito REAL NOT NULL DEFAULT 1,
                rollover_bono REAL NOT NULL DEFAULT 1,
                cuota_minima_rollover REAL NOT NULL DEFAULT 1.01,
                deportes VARCHAR(500) NOT NULL DEFAULT 'Futbol,Baloncesto,Tenis'
            )
        """)
        for definicion in (
            "minimo_retiro REAL NOT NULL DEFAULT 50",
            "rollover_deposito REAL NOT NULL DEFAULT 1",
            "rollover_bono REAL NOT NULL DEFAULT 1",
            "cuota_minima_rollover REAL NOT NULL DEFAULT 1.01",
            "deportes TEXT NOT NULL DEFAULT 'Futbol,Baloncesto,Tenis'",
        ):
            _agregar_columna(cursor, "casas_apuestas", definicion)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historial_transacciones (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                id_casa VARCHAR(40) NOT NULL,
                tipo_movimiento VARCHAR(40) NOT NULL,
                monto REAL NOT NULL,
                cuota REAL DEFAULT 1.0,
                tipo_saldo_usado VARCHAR(20) NOT NULL,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                apuesta_id INTEGER,
                FOREIGN KEY (id_casa) REFERENCES casas_apuestas(id)
            )
        """)
        _agregar_columna(cursor, "historial_transacciones", "apuesta_id INTEGER")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS apuestas (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                id_casa VARCHAR(40) NOT NULL,
                deporte VARCHAR(80) NOT NULL,
                liga VARCHAR(120) NOT NULL,
                evento VARCHAR(255) NOT NULL,
                mercado VARCHAR(120) NOT NULL,
                seleccion VARCHAR(255) NOT NULL,
                fecha_evento DATE NOT NULL,
                monto REAL NOT NULL CHECK (monto > 0),
                cuota REAL NOT NULL CHECK (cuota > 1),
                tipo_saldo VARCHAR(20) NOT NULL,
                estado VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',
                retorno REAL NOT NULL DEFAULT 0,
                monto_conciliado REAL NOT NULL DEFAULT 0,
                rollover_liberado REAL NOT NULL DEFAULT 0,
                fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                fecha_resolucion TIMESTAMP,
                FOREIGN KEY (id_casa) REFERENCES casas_apuestas(id)
            )
        """)
        _agregar_columna(cursor, "apuestas", "monto_conciliado REAL NOT NULL DEFAULT 0")
        _agregar_columna(cursor, "apuestas", "rollover_liberado REAL NOT NULL DEFAULT 0")
        _agregar_columna(
            cursor, "apuestas",
            "fecha_registro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
        )
        _agregar_columna(cursor, "apuestas", "fecha_resolucion TIMESTAMP NULL")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS configuracion_control (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                limite_deposito_diario REAL NOT NULL DEFAULT 100,
                limite_apuesta_diario REAL NOT NULL DEFAULT 100,
                limite_apuesta_individual REAL NOT NULL DEFAULT 20,
                limite_perdida_semanal REAL NOT NULL DEFAULT 150,
                pausa_hasta DATETIME,
                modo_estricto INTEGER NOT NULL DEFAULT 1
            )
        """)
        cursor.execute("INSERT IGNORE INTO configuracion_control (id) VALUES (1)")


def registrar_casa_apuesta(id_casa, nombre, minimo_retiro=50, rollover_deposito=1,
                            rollover_bono=1, cuota_minima_rollover=1.01, deportes="Futbol,Baloncesto,Tenis"):
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
                (id, nombre_casa, minimo_retiro, rollover_deposito, rollover_bono,
                 cuota_minima_rollover, deportes) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (id_casa, nombre, float(minimo_retiro), float(rollover_deposito),
                  float(rollover_bono), float(cuota_minima_rollover), deportes.strip()))
        return True
    except IntegrityError:
        return False


def inicializar_casas_predeterminadas(forzar=False):
    """Crea los tres activos iniciales sin duplicar registros existentes."""
    with obtener_conexion() as conn:
        cantidad = int(conn.execute("SELECT COUNT(*) FROM casas_apuestas").fetchone()[0])
    if cantidad > 0 and not forzar:
        return
    casas = [
        ("BETANO", "Betano Perú"),
        ("INKABET", "Inkabet"),
        ("TE_APUESTO", "Te Apuesto"),
    ]
    for codigo, nombre in casas:
        registrar_casa_apuesta(codigo, nombre)


def eliminar_casa_apuesta(id_casa):
    """Elimina una casa únicamente cuando no posee datos financieros asociados."""
    id_casa = id_casa.upper().strip()
    with obtener_conexion() as conn:
        casa = conn.execute("SELECT * FROM casas_apuestas WHERE id=?", (id_casa,)).fetchone()
        if not casa:
            raise ValueError("La casa seleccionada no existe.")
        apuestas = int(conn.execute("SELECT COUNT(*) FROM apuestas WHERE id_casa=?", (id_casa,)).fetchone()[0])
        movimientos = int(conn.execute(
            "SELECT COUNT(*) FROM historial_transacciones WHERE id_casa=?", (id_casa,)
        ).fetchone()[0])
        saldos = sum(float(casa[campo]) for campo in (
            "saldo_deposito", "saldo_bono", "saldo_retirable", "rollover_pendiente"
        ))
        if apuestas > 0 or movimientos > 0 or abs(saldos) > 0.001:
            raise ValueError(
                "No se puede eliminar: la casa tiene apuestas, movimientos, saldos o rollover registrados."
            )
        conn.execute("DELETE FROM casas_apuestas WHERE id=?", (id_casa,))
        return True


def reiniciar_datos_conservando_casas():
    """Borra la actividad financiera y deja intacto el catálogo y reglas de casas."""
    with obtener_conexion() as conn:
        movimientos = int(conn.execute("SELECT COUNT(*) FROM historial_transacciones").fetchone()[0])
        apuestas = int(conn.execute("SELECT COUNT(*) FROM apuestas").fetchone()[0])
        conn.execute("DELETE FROM historial_transacciones")
        conn.execute("DELETE FROM apuestas")
        conn.execute("""UPDATE casas_apuestas SET saldo_deposito=0, saldo_bono=0,
                     saldo_retirable=0, rollover_pendiente=0""")
        # Reinicia los contadores para que la nueva bitácora comience desde el identificador 1.
        conn.execute("ALTER TABLE apuestas AUTO_INCREMENT=1")
        conn.execute("ALTER TABLE historial_transacciones AUTO_INCREMENT=1")
        return {"apuestas_eliminadas": apuestas, "movimientos_eliminados": movimientos}


def actualizar_casa(id_casa, minimo_retiro, rollover_deposito, rollover_bono,
                    cuota_minima_rollover, deportes):
    valores = [float(minimo_retiro), float(rollover_deposito), float(rollover_bono),
               float(cuota_minima_rollover)]
    if min(valores[:3]) < 0 or valores[3] < 1 or not deportes.strip():
        raise ValueError("Revise las reglas de retiro y rollover.")
    with obtener_conexion() as conn:
        conn.execute("""
            UPDATE casas_apuestas SET minimo_retiro=?, rollover_deposito=?, rollover_bono=?,
            cuota_minima_rollover=?, deportes=? WHERE id=?
        """, (*valores, deportes.strip(), id_casa.upper().strip()))


def obtener_resumen_casas():
    with obtener_conexion() as conn:
        return [dict(f) for f in conn.execute("SELECT * FROM casas_apuestas ORDER BY nombre_casa")]


def obtener_casa(id_casa):
    with obtener_conexion() as conn:
        fila = conn.execute("SELECT * FROM casas_apuestas WHERE id=?", (id_casa.upper().strip(),)).fetchone()
        return dict(fila) if fila else None


def obtener_configuracion():
    with obtener_conexion() as conn:
        return dict(conn.execute("SELECT * FROM configuracion_control WHERE id=1").fetchone())


def actualizar_configuracion(limite_deposito_diario, limite_apuesta_diario,
                             limite_apuesta_individual, limite_perdida_semanal, modo_estricto):
    valores = list(map(float, (limite_deposito_diario, limite_apuesta_diario,
                              limite_apuesta_individual, limite_perdida_semanal)))
    if min(valores) <= 0:
        raise ValueError("Todos los límites deben ser mayores que cero.")
    with obtener_conexion() as conn:
        conn.execute("""UPDATE configuracion_control SET limite_deposito_diario=?,
            limite_apuesta_diario=?, limite_apuesta_individual=?, limite_perdida_semanal=?,
            modo_estricto=? WHERE id=1""", (*valores, int(bool(modo_estricto))))


def activar_pausa(horas=24):
    hasta = (datetime.now(timezone.utc) + timedelta(hours=int(horas))).isoformat(timespec="seconds")
    with obtener_conexion() as conn:
        conn.execute("UPDATE configuracion_control SET pausa_hasta=? WHERE id=1", (hasta,))
    return hasta


def estado_pausa():
    config = obtener_configuracion()
    if not config["pausa_hasta"]:
        return False, None
    hasta = datetime.fromisoformat(config["pausa_hasta"])
    # Compatibilidad con pausas antiguas, que se guardaban como hora local sin zona.
    if hasta.tzinfo is None:
        hasta = hasta.replace(tzinfo=ZONA_LOCAL)
    return hasta > datetime.now(timezone.utc), hasta.astimezone(ZONA_LOCAL)


def _suma_periodo(conn, tipos, desde):
    marcas = ",".join("?" for _ in tipos)
    fila = conn.execute(f"SELECT COALESCE(SUM(monto),0) FROM historial_transacciones "
                        f"WHERE tipo_movimiento IN ({marcas}) AND datetime(fecha)>=datetime(?)",
                        (*tipos, desde)).fetchone()
    return float(fila[0])


def evaluar_limites(tipo, monto):
    monto = float(monto)
    config = obtener_configuracion()
    pausado, hasta = estado_pausa()
    razones = []
    with obtener_conexion() as conn:
        ahora_local = datetime.now(ZONA_LOCAL)
        hoy_local = ahora_local.replace(hour=0, minute=0, second=0, microsecond=0)
        hoy = hoy_local.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        semana = (ahora_local - timedelta(days=7)).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        if tipo == "RECARGA":
            usado = _suma_periodo(conn, ["RECARGA"], hoy)
            if usado + monto > config["limite_deposito_diario"]:
                razones.append(f"Límite diario de depósitos: S/ {config['limite_deposito_diario']:.2f}.")
        if tipo == "APUESTA":
            usado = _suma_periodo(conn, ["APUESTA_PENDIENTE"], hoy)
            if monto > config["limite_apuesta_individual"]:
                razones.append(f"Límite por apuesta: S/ {config['limite_apuesta_individual']:.2f}.")
            if usado + monto > config["limite_apuesta_diario"]:
                razones.append(f"Límite diario apostado: S/ {config['limite_apuesta_diario']:.2f}.")
            perdidas = _suma_periodo(conn, ["APUESTA_PERDIDA", "LIQUIDACION_PERDIDA"], semana)
            if perdidas >= config["limite_perdida_semanal"]:
                razones.append(f"Límite semanal de pérdidas: S/ {config['limite_perdida_semanal']:.2f}.")
    if pausado:
        razones.append(f"Pausa activa hasta {hasta:%d/%m/%Y %H:%M}.")
    # Los límites son referencias analíticas. El sistema registra la decisión del usuario
    # aunque se superen; únicamente los retiros obedecen reglas operativas de la casa.
    return {"permitido": True, "razones": razones, "modo_estricto": False}


def registrar_movimiento_bd(id_casa, tipo, monto, cuota=1, saldo_usado="DEPOSITO"):
    id_casa, tipo, saldo_usado = id_casa.upper().strip(), tipo.upper().strip(), saldo_usado.upper().strip()
    monto, cuota = float(monto), float(cuota)
    if monto <= 0:
        raise ValueError("El monto debe ser mayor que cero.")
    limite = evaluar_limites(tipo, monto)
    with obtener_conexion() as conn:
        casa = conn.execute("SELECT * FROM casas_apuestas WHERE id=?", (id_casa,)).fetchone()
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
        elif tipo in {"APUESTA_GANADA", "APUESTA_PERDIDA"}:  # compatibilidad histórica/manual
            if saldo_usado == "DEPOSITO": dep -= monto
            elif saldo_usado == "BONO": bono -= monto
            elif saldo_usado == "RETIRABLE": ret -= monto
            else: raise ValueError("Billetera no válida.")
            if cuota >= float(casa["cuota_minima_rollover"]): roll = max(0, roll - monto)
            if tipo == "APUESTA_GANADA":
                ret += monto * (cuota - 1) if saldo_usado == "BONO" else monto * cuota
        else:
            raise ValueError(f"Tipo de movimiento no soportado: {tipo}")
        if min(dep, bono, ret, roll) < -0.001:
            raise ValueError("El movimiento dejaría un saldo negativo.")
        conn.execute("INSERT INTO historial_transacciones (id_casa,tipo_movimiento,monto,cuota,tipo_saldo_usado) VALUES (?,?,?,?,?)",
                     (id_casa, tipo, monto, cuota, saldo_usado))
        conn.execute("UPDATE casas_apuestas SET saldo_deposito=?,saldo_bono=?,saldo_retirable=?,rollover_pendiente=? WHERE id=?",
                     (round(dep, 2), round(bono, 2), round(ret, 2), round(roll, 2), id_casa))


def registrar_recarga_bitacora(id_casa, monto_deposito, monto_bono=0):
    """Registra depósito y bono juntos aplicando el rollover particular de la casa."""
    id_casa = id_casa.upper().strip()
    monto_deposito, monto_bono = float(monto_deposito), float(monto_bono)
    if monto_deposito < 0 or monto_bono < 0 or monto_deposito + monto_bono <= 0:
        raise ValueError("Ingrese un monto positivo de depósito o bono.")
    with obtener_conexion() as conn:
        casa = conn.execute("SELECT * FROM casas_apuestas WHERE id=?", (id_casa,)).fetchone()
        if not casa:
            raise ValueError(f"No existe la casa de apuestas {id_casa}.")
        rollover_generado = (
            monto_deposito * float(casa["rollover_deposito"])
            + monto_bono * float(casa["rollover_bono"])
        )
        conn.execute("""UPDATE casas_apuestas
            SET saldo_deposito=saldo_deposito+?, saldo_bono=saldo_bono+?,
                rollover_pendiente=rollover_pendiente+? WHERE id=?""",
            (monto_deposito, monto_bono, rollover_generado, id_casa))
        movimientos = []
        if monto_deposito > 0:
            movimientos.append((id_casa, "RECARGA", monto_deposito, 1.0, "DEPOSITO"))
        if monto_bono > 0:
            movimientos.append((id_casa, "BONO", monto_bono, 1.0, "BONO"))
        conn.executemany("""INSERT INTO historial_transacciones
            (id_casa,tipo_movimiento,monto,cuota,tipo_saldo_usado) VALUES (?,?,?,?,?)""",
            movimientos)
        return {
            "deposito": round(monto_deposito, 2),
            "bono": round(monto_bono, 2),
            "rollover_generado": round(rollover_generado, 2),
        }


def registrar_apuesta(id_casa, deporte, liga, evento, mercado, seleccion, fecha_evento,
                      monto, cuota, tipo_saldo):
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
        casa = conn.execute("SELECT * FROM casas_apuestas WHERE id=?", (id_casa,)).fetchone()
        if not casa or float(casa[columna]) < monto:
            raise ValueError("Saldo insuficiente en la billetera seleccionada.")
        cursor = conn.execute("""INSERT INTO apuestas
            (id_casa,deporte,liga,evento,mercado,seleccion,fecha_evento,monto,cuota,tipo_saldo)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", (id_casa, deporte.strip(), liga.strip(), evento.strip(),
            mercado.strip(), seleccion.strip(), str(fecha_evento), monto, cuota, tipo_saldo))
        apuesta_id = cursor.lastrowid
        conn.execute("UPDATE apuestas SET monto_conciliado=? WHERE id=?", (monto, apuesta_id))
        roll = float(casa["rollover_pendiente"])
        roll_anterior = roll
        if cuota >= float(casa["cuota_minima_rollover"]): roll = max(0, roll - monto)
        conn.execute(f"UPDATE casas_apuestas SET {columna}={columna}-?, rollover_pendiente=? WHERE id=?",
                     (monto, round(roll, 2), id_casa))
        conn.execute("UPDATE apuestas SET rollover_liberado=? WHERE id=?",
                     (round(roll_anterior - roll, 2), apuesta_id))
        conn.execute("""INSERT INTO historial_transacciones
            (id_casa,tipo_movimiento,monto,cuota,tipo_saldo_usado,apuesta_id)
            VALUES (?,?,?,?,?,?)""", (id_casa, "APUESTA_PENDIENTE", monto, cuota, tipo_saldo, apuesta_id))
        return apuesta_id


def registrar_apuesta_bitacora(id_casa, deporte, liga, evento, mercado, seleccion,
                               fecha_evento, monto, cuota, tipo_saldo, resultado):
    """Registra una apuesta ya resuelta sin exigir depósitos previos.

    Es el flujo principal del modo bitácora: el usuario transcribe la operación realizada
    en la casa y el sistema la utiliza para analizar rentabilidad y riesgo.
    """
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
        casa = conn.execute("SELECT * FROM casas_apuestas WHERE id=?", (id_casa,)).fetchone()
        if not casa:
            raise ValueError(f"No existe la casa de apuestas {id_casa}.")
        tipos_saldo = ("BONO",) if tipo_saldo == "BONO" else ("DEPOSITO", "RETIRABLE")
        marcas = ",".join("?" for _ in tipos_saldo)
        reservado = float(conn.execute(
            f"SELECT COALESCE(SUM(monto),0) FROM apuestas WHERE id_casa=? "
            f"AND estado='PENDIENTE' AND tipo_saldo IN ({marcas})",
            (id_casa, *tipos_saldo),
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
            (id_casa,deporte,liga,evento,mercado,seleccion,fecha_evento,monto,cuota,
             tipo_saldo,estado,retorno,fecha_resolucion)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (id_casa, str(deporte).strip(), str(liga).strip(), str(evento).strip(),
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
                    conn.execute(f"UPDATE casas_apuestas SET {columna}={columna}-? WHERE id=?",
                                 (descuento, id_casa))
        conn.execute("UPDATE apuestas SET monto_conciliado=? WHERE id=?",
                     (round(monto_conciliado, 2), apuesta_id))
        if resultado == "GANADA" and retorno > 0:
            conn.execute("UPDATE casas_apuestas SET saldo_retirable=saldo_retirable+? WHERE id=?",
                         (round(retorno, 2), id_casa))
        elif resultado == "ANULADA" and monto_conciliado > 0:
            for columna, descuento in descuentos.items():
                if descuento > 0:
                    conn.execute(f"UPDATE casas_apuestas SET {columna}={columna}+? WHERE id=?",
                                 (descuento, id_casa))
        rollover = float(casa["rollover_pendiente"])
        rollover_anterior = rollover
        if resultado != "PENDIENTE" and cuota >= float(casa["cuota_minima_rollover"]):
            rollover = max(0.0, rollover - monto)
            conn.execute("UPDATE casas_apuestas SET rollover_pendiente=? WHERE id=?",
                         (round(rollover, 2), id_casa))
        conn.execute("UPDATE apuestas SET rollover_liberado=? WHERE id=?",
                     (round(rollover_anterior - rollover, 2), apuesta_id))
        tipo_movimiento = "APUESTA_PENDIENTE" if resultado == "PENDIENTE" else f"LIQUIDACION_{resultado}"
        conn.execute("""INSERT INTO historial_transacciones
            (id_casa,tipo_movimiento,monto,cuota,tipo_saldo_usado,apuesta_id)
            VALUES (?,?,?,?,?,?)""", (id_casa, tipo_movimiento, monto,
                                      cuota, tipo_saldo, apuesta_id))
        return apuesta_id


def obtener_apuestas(estado=None):
    consulta = "SELECT a.*,c.nombre_casa FROM apuestas a JOIN casas_apuestas c ON c.id=a.id_casa"
    params = ()
    if estado:
        consulta += " WHERE a.estado=?"; params = (estado.upper(),)
    consulta += " ORDER BY a.fecha_registro DESC,a.id DESC"
    with obtener_conexion() as conn:
        return [dict(f) for f in conn.execute(consulta, params)]


def editar_apuesta_bitacora(apuesta_id, deporte, liga, evento, mercado, seleccion,
                            fecha_evento, cuota, tipo_saldo):
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
        apuesta = conn.execute("SELECT id,id_casa,tipo_saldo,monto_conciliado FROM apuestas WHERE id=?",
                               (int(apuesta_id),)).fetchone()
        if not apuesta:
            raise ValueError("La apuesta no existe.")
        if (tipo_saldo != apuesta["tipo_saldo"] and
                float(apuesta["monto_conciliado"]) > 0.001):
            raise ValueError(
                "No se puede cambiar el origen de una apuesta ya conciliada porque alteraría "
                "los saldos. Elimina y vuelve a registrar la apuesta con el origen correcto."
            )
        conn.execute("""UPDATE apuestas SET deporte=?,liga=?,evento=?,mercado=?,seleccion=?,
                     fecha_evento=?,cuota=?,tipo_saldo=? WHERE id=?""",
                     (*textos, fecha_evento, cuota, tipo_saldo, int(apuesta_id)))
        conn.execute("""UPDATE historial_transacciones SET cuota=?,tipo_saldo_usado=?
                     WHERE apuesta_id=?""", (cuota, tipo_saldo, int(apuesta_id)))
    recalcular_rollover_casa(apuesta["id_casa"])


def eliminar_apuesta_bitacora(apuesta_id):
    """Elimina una apuesta y revierte de forma transaccional su efecto financiero."""
    columnas = {"DEPOSITO": "saldo_deposito", "BONO": "saldo_bono",
                "RETIRABLE": "saldo_retirable"}
    with obtener_conexion() as conn:
        apuesta = conn.execute("SELECT * FROM apuestas WHERE id=?", (int(apuesta_id),)).fetchone()
        if not apuesta:
            raise ValueError("La apuesta no existe.")
        casa = conn.execute("SELECT * FROM casas_apuestas WHERE id=?", (apuesta["id_casa"],)).fetchone()
        estado = apuesta["estado"]
        retorno = float(apuesta["retorno"])
        conciliado = float(apuesta["monto_conciliado"])

        # Una ganancia o cash out acreditó retorno al saldo retirable: se retira antes de restaurar la apuesta.
        if estado in {"GANADA", "CASH_OUT"} and retorno > 0:
            if float(casa["saldo_retirable"]) + 0.001 < retorno:
                raise ValueError("No se puede eliminar: el retorno ya no está disponible en el saldo retirable.")
            conn.execute("UPDATE casas_apuestas SET saldo_retirable=saldo_retirable-? WHERE id=?",
                         (retorno, apuesta["id_casa"]))

        # ANULADA ya devolvió lo conciliado; los demás resultados recuperan el capital descontado.
        if estado != "ANULADA" and conciliado > 0:
            columna = columnas[apuesta["tipo_saldo"]]
            conn.execute(f"UPDATE casas_apuestas SET {columna}={columna}+? WHERE id=?",
                         (conciliado, apuesta["id_casa"]))
        rollover = float(apuesta["rollover_liberado"])
        if rollover > 0:
            conn.execute("UPDATE casas_apuestas SET rollover_pendiente=rollover_pendiente+? WHERE id=?",
                         (rollover, apuesta["id_casa"]))
        conn.execute("DELETE FROM historial_transacciones WHERE apuesta_id=?", (int(apuesta_id),))
        conn.execute("DELETE FROM apuestas WHERE id=?", (int(apuesta_id),))
        id_casa = apuesta["id_casa"]
    recalcular_rollover_casa(id_casa)
    return True


def resolver_apuesta(apuesta_id, resultado, monto_cashout=0):
    resultado = resultado.upper().strip()
    if resultado not in {"GANADA", "PERDIDA", "ANULADA", "CASH_OUT"}:
        raise ValueError("Resultado no válido.")
    with obtener_conexion() as conn:
        apuesta = conn.execute("SELECT * FROM apuestas WHERE id=?", (int(apuesta_id),)).fetchone()
        if not apuesta or apuesta["estado"] != "PENDIENTE":
            raise ValueError("La apuesta no existe o ya fue liquidada.")
        monto_conciliado = float(apuesta["monto_conciliado"])
        rollover_liberado = float(apuesta["rollover_liberado"])
        if monto_conciliado <= 0 and resultado != "ANULADA":
            casa_antes = conn.execute(
                "SELECT * FROM casas_apuestas WHERE id=?", (apuesta["id_casa"],)
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
                    conn.execute(f"UPDATE casas_apuestas SET {columna}={columna}-? WHERE id=?",
                                 (descuento, apuesta["id_casa"]))
                    restante -= descuento
                    monto_conciliado += descuento
                if restante <= 0:
                    break
            if float(apuesta["cuota"]) >= float(casa_antes["cuota_minima_rollover"]):
                rollover_anterior = float(casa_antes["rollover_pendiente"])
                rollover_nuevo = max(0.0, rollover_anterior - float(apuesta["monto"]))
                rollover_liberado = rollover_anterior - rollover_nuevo
                conn.execute("UPDATE casas_apuestas SET rollover_pendiente=? WHERE id=?",
                             (round(rollover_nuevo, 2), apuesta["id_casa"]))
            conn.execute("UPDATE apuestas SET monto_conciliado=?,rollover_liberado=? WHERE id=?",
                         (round(monto_conciliado, 2), round(rollover_liberado, 2), apuesta_id))

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
            conn.execute(f"UPDATE casas_apuestas SET {destino}={destino}+? WHERE id=?",
                         (monto_acreditar, apuesta["id_casa"]))
        conn.execute("UPDATE apuestas SET estado=?,retorno=?,fecha_resolucion=CURRENT_TIMESTAMP WHERE id=?",
                     (resultado, round(retorno, 2), apuesta_id))
        conn.execute("""INSERT INTO historial_transacciones
            (id_casa,tipo_movimiento,monto,cuota,tipo_saldo_usado,apuesta_id)
            VALUES (?,?,?,?,?,?)""", (apuesta["id_casa"], f"LIQUIDACION_{resultado}", apuesta["monto"],
                                      apuesta["cuota"], apuesta["tipo_saldo"], apuesta_id))
        casa_actualizada = conn.execute(
            "SELECT saldo_deposito,saldo_bono,saldo_retirable FROM casas_apuestas WHERE id=?",
            (apuesta["id_casa"],),
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
    with obtener_conexion() as conn:
        apuesta = conn.execute("SELECT * FROM apuestas WHERE id=?", (int(apuesta_id),)).fetchone()
        if not apuesta or apuesta["estado"] != "PENDIENTE":
            raise ValueError("Solo se pueden eliminar apuestas pendientes.")
        columna = {"DEPOSITO": "saldo_deposito", "BONO": "saldo_bono",
                   "RETIRABLE": "saldo_retirable"}[apuesta["tipo_saldo"]]
        conciliado = float(apuesta["monto_conciliado"])
        if conciliado > 0:
            conn.execute(f"UPDATE casas_apuestas SET {columna}={columna}+? WHERE id=?",
                         (conciliado, apuesta["id_casa"]))
        rollover_liberado = float(apuesta["rollover_liberado"])
        if rollover_liberado > 0:
            conn.execute("""UPDATE casas_apuestas
                SET rollover_pendiente=rollover_pendiente+? WHERE id=?""",
                (rollover_liberado, apuesta["id_casa"]))
        conn.execute("DELETE FROM historial_transacciones WHERE apuesta_id=?", (apuesta_id,))
        conn.execute("DELETE FROM apuestas WHERE id=?", (apuesta_id,))
        return True


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
