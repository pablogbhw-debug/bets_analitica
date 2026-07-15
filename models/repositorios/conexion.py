"""Conexión, fechas e inicialización del esquema MySQL."""

import os
from contextvars import ContextVar
from contextlib import contextmanager
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from models.mysql_adapter import ConexionMySQL

MINIMO_RETIRO = 50.0
ZONA_LOCAL = ZoneInfo("America/Lima")
_usuario_actual = ContextVar("usuario_actual", default=None)


def establecer_usuario_actual(usuario_id):
    """Selecciona el almacén privado usado durante la ejecución actual."""
    if usuario_id is None:
        _usuario_actual.set(None)
        return
    usuario_id = int(usuario_id)
    if usuario_id <= 0:
        raise ValueError("El identificador de usuario no es válido.")
    _usuario_actual.set(usuario_id)


def obtener_usuario_actual():
    return _usuario_actual.get()


def _base_datos_global():
    return os.getenv("MYSQL_DATABASE", "apuestas_analitica")


def _base_datos_actual():
    usuario_id = obtener_usuario_actual()
    base = _base_datos_global()
    return f"{base}_usuario_{usuario_id}" if usuario_id is not None else base


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
    conn = ConexionMySQL(_base_datos_actual())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def obtener_conexion_global():
    """Conecta al almacén global, reservado para las cuentas de acceso."""
    conn = ConexionMySQL(_base_datos_global())
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
            CREATE TABLE IF NOT EXISTS sesiones_usuario (
                token_hash CHAR(64) PRIMARY KEY,
                usuario_id BIGINT NOT NULL,
                creada TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expira DATETIME NOT NULL,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
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
