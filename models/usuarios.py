"""Persistencia MySQL de usuarios."""

from mysql.connector import IntegrityError

from models.database import obtener_conexion


def buscar_usuario_por_correo(correo):
    with obtener_conexion() as conexion:
        fila = conexion.execute(
            "SELECT id,nombre,correo,password_hash,activo FROM usuarios WHERE correo=?",
            (correo,),
        ).fetchone()
        return dict(fila) if fila else None


def crear_usuario(nombre, correo, password_hash):
    """Inserta un usuario; UNIQUE(correo) garantiza la no duplicidad concurrente."""
    try:
        with obtener_conexion() as conexion:
            cursor = conexion.execute(
                "INSERT INTO usuarios (nombre,correo,password_hash) VALUES (?,?,?)",
                (nombre, correo, password_hash),
            )
            return int(cursor.lastrowid)
    except IntegrityError:
        return None
