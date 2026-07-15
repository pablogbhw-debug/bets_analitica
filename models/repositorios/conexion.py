"""Conexión, contexto de usuario e inicialización del esquema MySQL."""

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from models.mysql_adapter import ConexionMySQL

MINIMO_RETIRO = 50.0
ZONA_LOCAL = ZoneInfo("America/Lima")
_usuario_actual = ContextVar("usuario_actual", default=None)


def establecer_usuario_actual(usuario_id):
    """Asocia el usuario autenticado a la ejecución actual de Streamlit."""
    if usuario_id is None:
        _usuario_actual.set(None)
        return
    usuario_id = int(usuario_id)
    if usuario_id <= 0:
        raise ValueError("El identificador de usuario no es válido.")
    _usuario_actual.set(usuario_id)


def obtener_usuario_actual(requerido=True):
    usuario_id = _usuario_actual.get()
    if requerido and usuario_id is None:
        raise PermissionError("Debes iniciar sesión para acceder a estos datos.")
    return usuario_id


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


obtener_conexion_global = obtener_conexion


def inicializar_db():
    """Crea el esquema relacional compartido con aislamiento por usuario_id."""
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
                CONSTRAINT fk_sesion_usuario FOREIGN KEY (usuario_id)
                    REFERENCES usuarios(id) ON DELETE CASCADE,
                INDEX idx_sesion_usuario (usuario_id)
            ) ENGINE=InnoDB
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS casas_apuestas (
                usuario_id BIGINT NOT NULL,
                id VARCHAR(40) NOT NULL,
                nombre_casa VARCHAR(120) NOT NULL,
                saldo_deposito DECIMAL(12,2) NOT NULL DEFAULT 0,
                saldo_bono DECIMAL(12,2) NOT NULL DEFAULT 0,
                saldo_retirable DECIMAL(12,2) NOT NULL DEFAULT 0,
                rollover_pendiente DECIMAL(12,2) NOT NULL DEFAULT 0,
                minimo_retiro DECIMAL(12,2) NOT NULL DEFAULT 50,
                rollover_deposito DECIMAL(8,2) NOT NULL DEFAULT 1,
                rollover_bono DECIMAL(8,2) NOT NULL DEFAULT 1,
                cuota_minima_rollover DECIMAL(8,2) NOT NULL DEFAULT 1.01,
                deportes VARCHAR(500) NOT NULL DEFAULT 'Futbol,Baloncesto,Tenis',
                PRIMARY KEY (usuario_id, id),
                CONSTRAINT fk_casa_usuario FOREIGN KEY (usuario_id)
                    REFERENCES usuarios(id) ON DELETE CASCADE
            ) ENGINE=InnoDB
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS apuestas (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                usuario_id BIGINT NOT NULL,
                id_casa VARCHAR(40) NOT NULL,
                deporte VARCHAR(80) NOT NULL,
                liga VARCHAR(120) NOT NULL,
                evento VARCHAR(255) NOT NULL,
                mercado VARCHAR(120) NOT NULL,
                seleccion VARCHAR(255) NOT NULL,
                fecha_evento DATE NOT NULL,
                monto DECIMAL(12,2) NOT NULL CHECK (monto > 0),
                cuota DECIMAL(8,2) NOT NULL CHECK (cuota > 1),
                tipo_saldo VARCHAR(20) NOT NULL,
                estado VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',
                retorno DECIMAL(12,2) NOT NULL DEFAULT 0,
                monto_conciliado DECIMAL(12,2) NOT NULL DEFAULT 0,
                rollover_liberado DECIMAL(12,2) NOT NULL DEFAULT 0,
                fecha_registro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                fecha_resolucion TIMESTAMP NULL,
                UNIQUE KEY uq_apuesta_usuario_id (usuario_id, id),
                CONSTRAINT fk_apuesta_usuario FOREIGN KEY (usuario_id)
                    REFERENCES usuarios(id) ON DELETE CASCADE,
                CONSTRAINT fk_apuesta_casa FOREIGN KEY (usuario_id, id_casa)
                    REFERENCES casas_apuestas(usuario_id, id)
            ) ENGINE=InnoDB
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historial_transacciones (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                usuario_id BIGINT NOT NULL,
                id_casa VARCHAR(40) NOT NULL,
                apuesta_id BIGINT NULL,
                tipo_movimiento VARCHAR(40) NOT NULL,
                monto DECIMAL(12,2) NOT NULL,
                cuota DECIMAL(8,2) NOT NULL DEFAULT 1,
                tipo_saldo_usado VARCHAR(20) NOT NULL,
                fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_historial_usuario FOREIGN KEY (usuario_id)
                    REFERENCES usuarios(id) ON DELETE CASCADE,
                CONSTRAINT fk_historial_casa FOREIGN KEY (usuario_id, id_casa)
                    REFERENCES casas_apuestas(usuario_id, id),
                CONSTRAINT fk_historial_apuesta FOREIGN KEY (usuario_id, apuesta_id)
                    REFERENCES apuestas(usuario_id, id) ON DELETE CASCADE,
                INDEX idx_historial_usuario_fecha (usuario_id, fecha)
            ) ENGINE=InnoDB
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS configuracion_control (
                usuario_id BIGINT PRIMARY KEY,
                limite_deposito_diario DECIMAL(12,2) NOT NULL DEFAULT 100,
                limite_apuesta_diario DECIMAL(12,2) NOT NULL DEFAULT 100,
                limite_apuesta_individual DECIMAL(12,2) NOT NULL DEFAULT 20,
                limite_perdida_semanal DECIMAL(12,2) NOT NULL DEFAULT 150,
                pausa_hasta DATETIME NULL,
                modo_estricto BOOLEAN NOT NULL DEFAULT TRUE,
                CONSTRAINT fk_configuracion_usuario FOREIGN KEY (usuario_id)
                    REFERENCES usuarios(id) ON DELETE CASCADE
            ) ENGINE=InnoDB
        """)
